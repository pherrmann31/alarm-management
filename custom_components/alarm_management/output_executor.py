"""Restricted, absolute HA commands with durable delivery records and bounded retries."""

import asyncio
from dataclasses import replace
import logging
import re

from homeassistant.exceptions import HomeAssistantError

from .output_engine import plan_outputs
from .notification import delivery_id, request

_LOGGER = logging.getLogger(__name__)
SWITCH_DOMAINS = {"switch", "light", "siren", "input_boolean"}
TEXT_DOMAINS = {"text", "input_text"}
TIMEOUT = 10
RETRY_DELAY = 5
MAX_ATTEMPTS = 3


def service_command(kind, entity_id, value):
    """No arbitrary services, groups, areas, toggle actions or user-supplied code."""
    if not isinstance(entity_id, str) or not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id):
        raise ValueError("Ungültige Zielentität")
    domain = entity_id.split(".", 1)[0]
    if kind == "switch" and domain in SWITCH_DOMAINS and value in ("on", "off"):
        return domain, "turn_on" if value == "on" else "turn_off", {}
    if kind in ("short_text", "long_text") and domain in TEXT_DOMAINS and isinstance(value, str):
        return domain, "set_value", {"value": value}
    raise ValueError("Nicht unterstützter Ausgangsbefehl")


class LiveOutputExecutor:
    def __init__(self, manager):
        self.manager = manager
        self.hass = manager.hass
        self.running = False
        self._tasks = {}
        self._dirty = set()
        self._timers = {}
        self._attempts = {}
        self._semaphore = asyncio.Semaphore(4)
        self._notification_retries = set()

    def start(self):
        self.running = True
        self.schedule()

    def schedule(self, output_id=None):
        if not self.running or not self.manager.running:
            return
        ids = [output_id] if output_id else [output.id for output in self.manager.outputs]
        for item in ids:
            self._dirty.add(item)
            task = self._tasks.get(item)
            if task is None or task.done():
                task = self.hass.async_create_task(self._worker(item))
                self._tasks[item] = task
                # HA starts tasks eagerly. A worker can finish before assignment
                # above, so its own finally block cannot reliably remove itself.
                task.add_done_callback(lambda done, key=item: self._task_done(key, done))

    def _task_done(self, output_id, task):
        if self._tasks.get(output_id) is task:
            self._tasks.pop(output_id, None)

    def retry(self):
        self._attempts.clear()
        self._notification_retries.update(output.id for output in self.manager.outputs if output.notification)
        self.schedule()

    def stop(self):
        self.running = False
        self._dirty.clear()
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()

    async def drain(self):
        while self._tasks:
            # Never busy-loop awaiting already completed eager tasks: in that
            # case gather may finish synchronously and starve the entire HA loop.
            for output_id, task in tuple(self._tasks.items()):
                if task.done():
                    self._task_done(output_id, task)
            if self._tasks:
                await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)

    def _retry_later(self, output_id, delay=RETRY_DELAY):
        if not self.running or output_id in self._timers:
            return
        def wake():
            self._timers.pop(output_id, None)
            self.schedule(output_id)
        self._timers[output_id] = self.hass.loop.call_later(delay, wake)

    async def _worker(self, output_id):
        try:
            while self.running and self.manager.running and output_id in self._dirty:
                self._dirty.discard(output_id)
                try:
                    await self._execute_latest(output_id)
                except (OSError, HomeAssistantError):
                    # A delivery intent must be durable before any external command.
                    self.manager.delivery_failures.add(output_id)
                    self.manager.notify_outputs()
                    _LOGGER.exception("Ausgabestatus konnte nicht gespeichert werden")
                    self._retry_later(output_id)
                except Exception:
                    self.manager.delivery_failures.add(output_id)
                    self.manager.notify_outputs()
                    _LOGGER.exception("Unerwarteter Fehler bei Ausgang %s", output_id)
        finally:
            self._tasks.pop(output_id, None)

    def _desired(self, output_id):
        output = next((item for item in self.manager.outputs if item.id == output_id), None)
        plan = self.manager.session.output_plan.get(output_id)
        if output is None or plan is None:
            return None
        delivery = self.manager.session.executions.get(output_id, {})
        target_id = output.entity_registry_id or plan["entity_id"]
        owned = bool(delivery.get("owned") and delivery.get("target_id") == target_id)
        releasing = not output.enabled or plan["phase"] == "idle"
        if not output.enabled:
            if not owned:
                return None
            targets = self.manager.output_targets.snapshot if self.manager.output_targets else None
            plan = plan_outputs([replace(output, enabled=True)], {}, [], self.manager.session, targets)[output_id]
        if plan["status"] != "planned":
            return None
        if output.entity_id and releasing and not owned:
            # Do not overwrite an unrelated idle device on installation or after a target change.
            return None
        return output, plan, target_id, owned, releasing

    def _observed(self, entity_id):
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state and state.state not in ("unknown", "unavailable") else None

    async def _execute_latest(self, output_id):
        output = next((item for item in self.manager.outputs if item.id == output_id), None)
        if output and output.notification:
            await self._execute_notifications(output)
            return
        desired = self._desired(output_id)
        if desired is None:
            output = next((item for item in self.manager.outputs if item.id == output_id), None)
            plan = self.manager.session.output_plan.get(output_id)
            previous = self.manager.session.executions.get(output_id, {})
            if output and plan and plan["status"] in ("disabled", "planned") and not previous.get("owned"):
                await self.manager.record_delivery(output, plan, output.entity_registry_id or plan["entity_id"], "idle", None, False)
            return
        output, plan, target_id, owned, releasing = desired
        entity_id, value = plan["entity_id"], plan["value"]
        if entity_id is None:
            await self.manager.record_delivery(output, plan, target_id, "internal", None, False)
            return
        key = (target_id, entity_id, value, releasing)
        observed = self._observed(entity_id)
        if observed == value:
            await self.manager.record_delivery(output, plan, target_id, "confirmed", None, owned and not releasing)
            return
        previous = self.manager.session.executions.get(output_id, {})
        state = self._attempts.get(output_id, {"key": key, "count": 0, "last": -100.0})
        if state["key"] != key:
            state = {"key": key, "count": 0, "last": -100.0}
        self._attempts[output_id] = state
        # No repeated blind writes when the target has no feedback but HA accepted the command.
        if state["count"] and observed is None and previous.get("status") == "sent":
            return
        if state["count"] >= MAX_ATTEMPTS:
            status = "mismatch" if previous.get("status") in ("sent", "confirmed", "mismatch") else "failed"
            error = "Zielzustand weicht nach drei Versuchen ab" if status == "mismatch" else previous.get("error") or "Drei Ausgabeversuche fehlgeschlagen"
            await self.manager.record_delivery(output, plan, target_id, status, error, owned)
            return
        remaining = RETRY_DELAY - (self.hass.loop.time() - state["last"])
        if state["count"] and remaining > 0:
            self._retry_later(output_id, remaining)
            return
        async with self._semaphore:
            # A queued command may have been superseded by reset, acknowledgement or another alarm.
            latest = self._desired(output_id)
            if not self.running or not self.manager.running or latest is None:
                return
            new_output, new_plan, new_target, new_owned, new_releasing = latest
            if (new_target, new_plan["entity_id"], new_plan["value"], new_releasing) != key:
                self.schedule(output_id)
                return
            domain, service, data = service_command(output.kind, entity_id, value)
            await self.manager.record_delivery(output, plan, target_id, "pending", None, True)
            latest = self._desired(output_id)
            if (not self.running or not self.manager.running or latest is None or
                    (latest[2], latest[1]["entity_id"], latest[1]["value"], latest[4]) != key):
                self.schedule(output_id)
                return
            state["count"] += 1
            state["last"] = self.hass.loop.time()
            try:
                if not self.hass.services.has_service(domain, service):
                    raise HomeAssistantError(f"Aktion {domain}.{service} ist nicht verfügbar")
                async with asyncio.timeout(TIMEOUT):
                    await self.hass.services.async_call(domain, service, data, target={"entity_id": entity_id}, blocking=True)
            except (HomeAssistantError, TimeoutError, ValueError) as err:
                await self.manager.record_delivery(output, plan, target_id, "failed", str(err)[:1000] or "Zeitüberschreitung", True)
                self._retry_later(output_id)
                return
            confirmed = self._observed(entity_id) == value
            await self.manager.record_delivery(output, plan, target_id, "confirmed" if confirmed else "sent", None, not releasing if confirmed else True)
            if not confirmed and self._observed(entity_id) is not None:
                self._retry_later(output_id)

    async def _execute_notifications(self, output):
        plan = self.manager.session.output_plan.get(output.id)
        if not output.enabled or not plan or plan['status'] != 'planned':
            return
        previous = self.manager.session.executions.get(output.id)
        initial_idle = plan['phase']=='idle' and (not previous or
                (previous.get('status')=='idle' and previous.get('target_id') in (None,'notification_phase:idle')))
        if not plan['value'] or initial_idle:
            await self.manager.record_delivery(output,plan,'notification_phase:'+plan['phase'],'idle',None,False)
            return
        retry = output.id in self._notification_retries
        failures = []
        for route in output.notification['routes']:
            if not self.running or not self.manager.running:
                return
            current = self.manager.session.output_plan.get(output.id)
            if current != plan:
                self.schedule(output.id)
                return
            child = replace(output,id=delivery_id(output.id,route),name=output.name+' · '+route)
            try:
                fingerprint, domain, service, data, target = request(output,plan,self.manager.session,route)
            except ValueError as err:
                failures.append(str(err))
                continue
            last = self.manager.session.executions.get(child.id,{})
            if last.get('target_id') == fingerprint:
                if last.get('status') == 'sent':
                    continue
                if not retry:
                    failures.append(last.get('error') or 'Vorheriger Versand unklar; bei Bedarf manuell erneut versuchen')
                    continue
            async with self._semaphore:
                current = self.manager.session.output_plan.get(output.id)
                if not self.running or not self.manager.running or current != plan:
                    self.schedule(output.id)
                    return
                # A durable intent per recipient prevents duplicate delivery after reload.
                await self.manager.record_delivery(output,plan,None,'pending',None,False)
                await self.manager.record_delivery(child,plan,fingerprint,'pending',None,False)
                if not self.running or not self.manager.running or self.manager.session.output_plan.get(output.id) != plan:
                    self.schedule(output.id)
                    return
                try:
                    if not self.hass.services.has_service(domain,service):
                        raise HomeAssistantError(f'Aktion {domain}.{service} ist nicht verfügbar')
                    kwargs = {'blocking':True}
                    if target:
                        kwargs['target']=target
                    async with asyncio.timeout(TIMEOUT):
                        await self.hass.services.async_call(domain,service,data,**kwargs)
                except (HomeAssistantError,TimeoutError,ValueError) as err:
                    error = str(err)[:800] or 'Versandzeit überschritten; Ergebnis unklar'
                    await self.manager.record_delivery(child,plan,fingerprint,'failed',error,False)
                    failures.append(route+': '+error)
                else:
                    await self.manager.record_delivery(child,plan,fingerprint,'sent',None,False)
        await self.manager.record_delivery(output,plan,None,'failed' if failures else 'sent', '; '.join(failures)[:1000] or None,False)
        self._notification_retries.discard(output.id)
