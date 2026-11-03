"""Actual command adapter tested against an isolated fake HA registry only."""

import asyncio
from copy import deepcopy
import importlib
import types
import unittest
from unittest.mock import AsyncMock, patch

import test_inputs as inputs
import test_outputs as outputs
import test_platforms as platforms
import test_rules as rules
import test_session as sessions
import test_simulation as old

# Reuse the same HomeAssistantError class as the manager's explicit HA double.
with patch.dict("sys.modules", {"homeassistant.exceptions": types.SimpleNamespace(HomeAssistantError=old.FakeHomeAssistantError)}):
    live = importlib.import_module(f"{old.PACKAGE}.output_executor")


class CommandTests(unittest.TestCase):
    def test_only_absolute_known_services_and_one_concrete_entity(self):
        for domain in ("switch", "light", "siren", "input_boolean"):
            self.assertEqual(live.service_command("switch", f"{domain}.target", "on"), (domain, "turn_on", {}))
            self.assertEqual(live.service_command("switch", f"{domain}.target", "off"), (domain, "turn_off", {}))
        for domain in ("text", "input_text"):
            self.assertEqual(live.service_command("short_text", f"{domain}.target", "FEUER"), (domain, "set_value", {"value": "FEUER"}))
        for kind, entity, value in (("switch", "lock.door", "on"), ("switch", "switch.target", "toggle"),
                                    ("long_text", "script.anything", "run"), ("switch", "all", "on")):
            with self.subTest(entity=entity), self.assertRaises(ValueError):
                live.service_command(kind, entity, value)


class LiveExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def make_manager(self, output=None, *, source_on=True, update_state=True):
        hass = inputs.FakeHass()
        hass.loop = asyncio.get_running_loop()
        hass.async_create_task = asyncio.create_task
        output = output or outputs.config.build_output(outputs.values())
        if output.entity_id:
            hass.values[output.entity_id] = "off" if output.kind == "switch" else "unknown"
        async def call(domain, service, data, **kwargs):
            if update_state:
                entity_id = kwargs["target"]["entity_id"]
                hass.set_state(entity_id, data["value"] if service == "set_value" else "on" if service == "turn_on" else "off")
        hass.services = types.SimpleNamespace(has_service=lambda *args: True, async_call=AsyncMock(side_effect=call))
        manager = old.manager_module.AlarmManager(hass, "integration")
        await manager.async_load()
        manager.running = True
        manager.rules = (rules.live_rule(ids=("a",)),)
        manager.outputs = (output,)
        manager.output_bindings = {"rule": [output.id]}
        await manager.async_process_inputs([sessions.source(status="matching" if source_on else "not_matching")])
        executor = live.LiveOutputExecutor(manager)
        manager.executor = executor
        self.addAsyncCleanup(self.shutdown, manager)
        return manager, output

    async def shutdown(self, manager):
        manager.running = False
        manager.stop_inputs()
        await manager.async_drain()

    async def test_switch_action_and_confirmed_delivery(self):
        manager, output = await self.make_manager()
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_awaited_once_with("input_boolean", "turn_on", {}, target={"entity_id": output.entity_id}, blocking=True)
        self.assertEqual(manager.hass.values[output.entity_id], "on")
        self.assertEqual(manager.session.executions[output.id]["status"], "confirmed")
        self.assertTrue(manager.session.executions[output.id]["owned"])
        statuses = [item["status"] for item in manager.session.delivery_history]
        self.assertEqual(statuses, ["pending", "confirmed"])

    async def test_text_value_is_really_sent_to_text_service(self):
        output = outputs.config.build_output(outputs.values("short_text", entity_id="input_text.display", alarm_value="{alarmtyp}"))
        manager, _ = await self.make_manager(output)
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_awaited_once_with("input_text", "set_value", {"value": "Feuer"}, target={"entity_id": "input_text.display"}, blocking=True)
        self.assertEqual(manager.hass.values["input_text.display"], "Feuer")

    async def test_initial_idle_target_is_not_overwritten(self):
        manager, output = await self.make_manager(source_on=False)
        manager.hass.values[output.entity_id] = "on"
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        self.assertEqual(manager.hass.values[output.entity_id], "on")
        self.assertEqual(manager.session.executions[output.id]["status"], "idle")

    async def test_preexisting_matching_state_does_not_claim_foreign_device(self):
        manager, output = await self.make_manager()
        manager.hass.values[output.entity_id] = "on"
        manager.executor.start()
        await manager.async_drain()
        self.assertFalse(manager.session.executions[output.id]["owned"])
        await manager.async_process_inputs([sessions.source(status="not_matching")])
        await manager.async_action("reset")
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        self.assertEqual(manager.hass.values[output.entity_id], "on")

    async def test_owned_target_is_cleared_after_reset(self):
        manager, output = await self.make_manager()
        manager.executor.start()
        await manager.async_drain()
        await manager.async_process_inputs([sessions.source(status="not_matching")])
        await manager.async_action("reset")
        await manager.async_drain()
        self.assertEqual(manager.hass.values[output.entity_id], "off")
        self.assertFalse(manager.session.executions[output.id]["owned"])

    async def test_disabling_output_releases_owned_target(self):
        manager, output = await self.make_manager()
        manager.executor.start()
        await manager.async_drain()
        disabled = outputs.config.build_output(outputs.values(enabled=False), output_id=output.id)
        manager.outputs = (disabled,)
        await manager.async_process_inputs([sessions.source()])
        await manager.async_drain()
        self.assertEqual(manager.hass.values[output.entity_id], "off")
        self.assertFalse(manager.session.executions[output.id]["owned"])

    async def test_no_feedback_is_sent_not_confirmed_and_no_blind_repeat(self):
        output = outputs.config.build_output(outputs.values("short_text", entity_id="text.display"))
        manager, _ = await self.make_manager(output, update_state=False)
        manager.executor.start()
        await manager.async_drain()
        self.assertEqual(manager.session.executions[output.id]["status"], "sent")
        manager.executor.schedule()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, 1)

    async def test_invalid_plan_never_calls_service(self):
        output = outputs.config.build_output(outputs.values("short_text", entity_id="text.display", alarm_value="{regel}"))
        manager, _ = await self.make_manager(output)
        manager.rules = (sessions.rule_module.AlarmRule("rule", "Regelname viel zu lang", ("a",), "any", "fire", True),)
        manager.session.alarms = {}
        await manager.async_process_inputs([sessions.source()])
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        self.assertEqual(manager.session.output_plan[output.id]["error"], "short_text_too_long")

    async def test_internal_text_needs_no_external_call(self):
        output = outputs.config.build_output(outputs.values("long_text", alarm_value="{quelle}"))
        manager, _ = await self.make_manager(output)
        manager.executor.start()
        await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        self.assertEqual(manager.session.executions[output.id]["status"], "internal")

    async def test_storage_failure_before_pending_prevents_command(self):
        manager, output = await self.make_manager()
        manager.store.fail = True
        manager.executor.start()
        with self.assertLogs(live._LOGGER, level="ERROR"):
            await manager.async_drain()
        manager.hass.services.async_call.assert_not_awaited()
        self.assertTrue(manager.delivery_error)

    async def test_result_storage_failure_does_not_claim_success_or_resend(self):
        manager, output = await self.make_manager()
        async def call(domain, service, data, **kwargs):
            manager.hass.set_state(output.entity_id, "on")
            manager.store.fail = True
        manager.hass.services.async_call.side_effect = call
        manager.executor.start()
        with self.assertLogs(live._LOGGER, level="ERROR"):
            await manager.async_drain()
        self.assertEqual(manager.session.executions[output.id]["status"], "pending")
        self.assertTrue(manager.delivery_error)
        manager.store.fail = False
        manager.executor.retry()
        await manager.async_drain()
        self.assertEqual(manager.session.executions[output.id]["status"], "confirmed")
        self.assertFalse(manager.delivery_error)
        self.assertEqual(manager.hass.services.async_call.await_count, 1)

    async def test_reset_during_inflight_call_settles_latest_value(self):
        manager, output = await self.make_manager()
        started, release = asyncio.Event(), asyncio.Event()
        async def call(domain, service, data, **kwargs):
            if service == "turn_on":
                started.set()
                await release.wait()
            manager.hass.set_state(output.entity_id, "on" if service == "turn_on" else "off")
        manager.hass.services.async_call.side_effect = call
        manager.executor.start()
        await asyncio.wait_for(started.wait(), 1)
        await manager.async_process_inputs([sessions.source(status="not_matching")])
        await manager.async_action("reset")
        release.set()
        await manager.async_drain()
        self.assertEqual(manager.hass.values[output.entity_id], "off")
        self.assertEqual([call.args[1] for call in manager.hass.services.async_call.await_args_list], ["turn_on", "turn_off"])

    async def test_no_more_than_four_distinct_target_calls_run_in_parallel(self):
        manager, _ = await self.make_manager()
        configured = tuple(outputs.config.build_output(outputs.values(name=f"Ziel {i}", entity_id=f"input_boolean.target_{i}")) for i in range(5))
        manager.outputs = configured
        manager.output_bindings = {"rule": [output.id for output in configured]}
        for output in configured:
            manager.hass.values[output.entity_id] = "off"
        await manager.async_process_inputs([sessions.source()])
        four_started, release = asyncio.Event(), asyncio.Event()
        active, maximum = 0, 0
        async def call(domain, service, data, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 4:
                four_started.set()
            await release.wait()
            manager.hass.set_state(kwargs["target"]["entity_id"], "on")
            active -= 1
        manager.hass.services.async_call.side_effect = call
        manager.executor.start()
        await asyncio.wait_for(four_started.wait(), 1)
        self.assertEqual(maximum, 4)
        release.set()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, 5)


    async def test_service_failure_is_visible_and_bounded_to_three_attempts(self):
        manager, output = await self.make_manager()
        manager.hass.services.async_call.side_effect = old.FakeHomeAssistantError("offline")
        with patch.object(live, "RETRY_DELAY", 0):
            manager.executor.start()
            await manager.async_drain()
            for _ in range(4):
                manager.executor.schedule()
                await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, 3)
        self.assertEqual(manager.session.executions[output.id]["status"], "failed")
        self.assertEqual(manager.session.executions[output.id]["error"], "offline")
        manager.executor.retry()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, 4)

    async def test_known_wrong_state_is_not_claimed_as_confirmed(self):
        manager, output = await self.make_manager(update_state=False)
        with patch.object(live, "RETRY_DELAY", 0):
            manager.executor.start()
            await manager.async_drain()
            for _ in range(4):
                manager.executor.schedule()
                await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, 3)
        self.assertEqual(manager.session.executions[output.id]["status"], "mismatch")

    async def test_stop_prevents_later_commands_and_does_not_switch_off(self):
        manager, output = await self.make_manager()
        manager.executor.start()
        await manager.async_drain()
        count = manager.hass.services.async_call.await_count
        manager.executor.stop()
        await manager.async_process_inputs([sessions.source(status="not_matching")])
        await manager.async_action("reset")
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, count)
        self.assertEqual(manager.hass.values[output.entity_id], "on")

    async def test_home_assistant_stop_event_disables_execution(self):
        manager, output = await self.make_manager()
        manager.start_shutdown_listener()
        manager.executor.start()
        await manager.async_drain()
        count = manager.hass.services.async_call.await_count
        manager.hass.bus.emit("homeassistant_stop", {})
        self.assertFalse(manager.running)
        self.assertFalse(manager.executor.running)
        manager.executor.schedule()
        await manager.async_drain()
        self.assertEqual(manager.hass.services.async_call.await_count, count)
        self.assertEqual(manager.hass.bus.callbacks, [])

    async def test_failed_input_retry_cannot_overwrite_new_delivery_state(self):
        manager, output = await self.make_manager()
        pending = deepcopy(manager.session)
        manager.executor.start()
        await manager.async_drain()
        manager._pending_session = pending
        await manager.async_process_inputs([sessions.source()])
        await manager.async_drain()
        self.assertEqual(manager.session.executions[output.id]["status"], "confirmed")
        self.assertEqual(manager.store.data["executions"][output.id]["status"], "confirmed")


class LiveMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_plan_status_is_relabelled_and_invalid_owned_record_rejected(self):
        output = outputs.config.build_output(outputs.values())
        current = outputs.engine.apply_output_plan(outputs.alarm_session(), [output], {"rule": [output.id]}, [rules.live_rule()], sessions.STAMP).to_dict()
        for key in ("execution_mode", "executions", "delivery_history"):
            current.pop(key)
        current["simulation"] = True
        current["output_plan"][output.id]["status"] = "simulation"
        for record in current["output_history"]:
            record["status"] = "simulation"
        migrated = await old.storage.AlarmStore()._async_migrate_func(4, 1, current)
        self.assertEqual(migrated["output_plan"][output.id]["status"], "planned")
        self.assertNotIn("simulation", str(migrated))
        record = {"output_id": output.id, "name": output.name, "entity_id": None, "target_id": None,
                  "value": None, "status": "pending", "error": None, "time": sessions.STAMP, "owned": True}
        migrated["executions"][output.id] = record
        with self.assertRaises(ValueError):
            sessions.session_module.AlarmSession.from_dict(migrated)

    async def test_v05_store_preserves_alarms_and_relabels_plans(self):
        legacy = outputs.alarm_session().to_dict()
        legacy.pop("execution_mode")
        legacy.pop("executions")
        legacy.pop("delivery_history")
        legacy["simulation"] = True
        migrated = await old.storage.AlarmStore()._async_migrate_func(4, 1, legacy)
        self.assertEqual(migrated["execution_mode"], "live")
        self.assertNotIn("simulation", migrated)
        self.assertEqual(migrated["source_alarms"], legacy["source_alarms"])
        self.assertEqual(migrated["executions"], {})

    async def test_owned_output_target_cannot_be_silently_changed(self):
        flow = inputs.flows.AlarmManagementOptionsFlow()
        flow.hass = inputs.FakeHass()
        flow.hass.values.update({"input_boolean.siren": "off", "input_boolean.other": "off"})
        await flow.async_step_init()
        await flow.async_step_output_add({"kind": "switch", "entity_id": "input_boolean.siren"})
        await flow.async_step_output_details(outputs.values())
        output = flow._outputs[0]
        flow.hass.entry.runtime_data = types.SimpleNamespace(session=types.SimpleNamespace(executions={output.id: {"owned": True}}))
        await flow.async_step_output_edit({"output_id": output.id})
        result = await flow.async_step_output_edit_details(outputs.values(entity_id="input_boolean.other"))
        self.assertEqual(result["errors"], {"entity_id": "output_owned"})
