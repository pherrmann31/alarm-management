"""Serialized alarm changes and durable output delivery records."""

import asyncio
import logging
from copy import deepcopy

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import HISTORY_LIMIT, SIGNAL_INPUTS_UPDATED, SIGNAL_UPDATED
from .session import apply_action, reconcile
from .storage import async_load_session, create_store
from .rule_engine import evaluate_rules
from .output_engine import apply_output_plan
from .notification import delivery_id

_LOGGER = logging.getLogger(__name__)


class AlarmManager:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.store = create_store(hass, entry_id)
        self.lock = asyncio.Lock()
        self.running = False
        self.inputs = None
        self.input_error = False
        self._tasks = set()
        self._retry = None
        self._input_sequence = 0
        self._processed_sequence = -1
        self._last_snapshot = []
        self._pending_session = None
        self.rules = ()
        self.outputs = ()
        self.output_bindings = {}
        self.output_targets = None
        self.executor = None
        self.delivery_failures = set()
        self._remove_shutdown = None

    @callback
    def start_shutdown_listener(self):
        self._remove_shutdown = self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._shutdown)

    @callback
    def _shutdown(self, event):
        self.running = False
        self.stop_inputs()

    @property
    def delivery_error(self):
        return bool(self.delivery_failures)

    @callback
    def notify_outputs(self):
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def record_delivery(self, output, plan, target_id, status, error, owned):
        async with self.lock:
            record = {"output_id": output.id, "name": output.name, "entity_id": plan["entity_id"],
                      "target_id": target_id, "value": plan["value"], "status": status,
                      "error": error, "time": dt_util.utcnow().isoformat(), "owned": owned}
            previous = self.session.executions.get(output.id)
            if previous and all(previous[key] == value for key, value in record.items() if key != "time"):
                self.delivery_failures.discard(output.id)
                return
            candidate = deepcopy(self.session)
            candidate.executions[output.id] = record
            candidate.delivery_history.append(deepcopy(record))
            candidate.delivery_history[:] = candidate.delivery_history[-HISTORY_LIMIT:]
            await self.store.async_save(candidate.to_dict())
            self.session = candidate
            self.delivery_failures.discard(output.id)
            self.notify_outputs()

    def evaluate(self, snapshot=None):
        if snapshot is None:
            snapshot = self.inputs.snapshot if self.inputs is not None else self._last_snapshot
        return evaluate_rules(self.rules, snapshot)

    async def async_load(self) -> None:
        self.session = await async_load_session(self.store)

    @property
    def state(self):
        """Backwards-compatible access to the manual test state."""
        return self.session.manual

    async def _commit(self, candidate):
        # Delivery results may arrive while an earlier input snapshot awaits a disk retry.
        candidate.executions = deepcopy(self.session.executions)
        valid_children = {delivery_id(output.id,route) for output in self.outputs if output.notification for route in output.notification['routes']}
        candidate.executions = {key: value for key,value in candidate.executions.items()
                                if '_notify_' not in key or key in valid_children}
        candidate.delivery_history = deepcopy(self.session.delivery_history)
        targets = self.output_targets.snapshot if self.output_targets is not None else None
        candidate = apply_output_plan(candidate, self.outputs, self.output_bindings, self.rules, dt_util.utcnow().isoformat(), targets)
        if candidate != self.session:
            try:
                await self.store.async_save(candidate.to_dict())
            except (OSError, HomeAssistantError) as err:
                raise HomeAssistantError("Alarm state could not be saved") from err
            self.session = candidate
            _LOGGER.info("Alarm Management: state=%s; no device action", candidate.state)
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)
        if self.executor is not None:
            self.executor.schedule()

    @callback
    def inputs_changed(self):
        self._input_sequence += 1
        async_dispatcher_send(self.hass, SIGNAL_INPUTS_UPDATED)
        if self.running:
            snapshot = deepcopy(self.inputs.snapshot)
            task = self.hass.async_create_task(self._run_inputs(snapshot, self._input_sequence))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _run_inputs(self, snapshot, sequence):
        try:
            await self.async_process_inputs(snapshot, sequence)
        except HomeAssistantError:
            self.input_error = True
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)
            _LOGGER.exception("Alarm Management: input alarm could not be saved; retry in 5 seconds")
            if self.running and self._retry is None:
                self._retry = self.hass.loop.call_later(5, self._retry_inputs)

    @callback
    def _retry_inputs(self):
        self._retry = None
        if self.running:
            self.inputs_changed()

    async def async_process_inputs(self, snapshot, sequence=None):
        async with self.lock:
            if not self.running:
                return
            if sequence is None:
                self._input_sequence += 1
                sequence = self._input_sequence
            if sequence <= self._processed_sequence:
                return
            base = self._pending_session if self._pending_session is not None else self.session
            candidate = reconcile(base, self.evaluate(snapshot), dt_util.utcnow().isoformat())
            try:
                await self._commit(candidate)
            except HomeAssistantError:
                self._pending_session = candidate
                raise
            self._pending_session = None
            self._last_snapshot = deepcopy(snapshot)
            self._processed_sequence = sequence
            if self.input_error:
                self.input_error = False
                async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    @callback
    def stop_inputs(self):
        if self._remove_shutdown is not None:
            self._remove_shutdown()
            self._remove_shutdown = None
        if self.executor is not None:
            self.executor.stop()
        if self.inputs is not None:
            self.inputs.stop()
        if self.output_targets is not None:
            self.output_targets.stop()
        if self._retry is not None:
            self._retry.cancel()
            self._retry = None

    async def async_drain(self):
        while True:
            if self._tasks:
                await asyncio.gather(*list(self._tasks), return_exceptions=True)
            if self.executor is not None:
                await self.executor.drain()
            if not self._tasks:
                break

    async def async_action(self, action: str) -> None:
        async with self.lock:
            if not self.running:
                raise ServiceValidationError("Alarm Management is not loaded")
            snapshot = self.inputs.snapshot if self.inputs is not None else self._last_snapshot
            rule_snapshot = self.evaluate(snapshot)
            now = dt_util.utcnow().isoformat()
            base = reconcile(self._pending_session if self._pending_session is not None else self.session, rule_snapshot, now)
            candidate, accepted = apply_action(base, action, rule_snapshot, now)
            try:
                await self._commit(candidate)
            except HomeAssistantError:
                # Retain observed inputs, but do not silently retry a failed manual action.
                self._pending_session = base
                raise
            self._pending_session = None
            self._processed_sequence = self._input_sequence
            self._last_snapshot = deepcopy(snapshot)
            if not accepted:
                raise ServiceValidationError("Reset blockiert: Eine Regel ist erfüllt oder ihr Zustand ist nicht bestimmbar. Eingänge und Regelstatus prüfen; bei Bedarf die Regel bewusst deaktivieren.")
            if self.input_error:
                self.input_error = False
                async_dispatcher_send(self.hass, SIGNAL_UPDATED)
