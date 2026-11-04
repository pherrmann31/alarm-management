"""Regression tests for latching, reset, journal, migration and UI workflow."""
import asyncio
from copy import deepcopy
import importlib
import unittest
from unittest.mock import Mock, patch

import test_simulation as old
import test_inputs as inputs

session_module = importlib.import_module(f"{old.PACKAGE}.session")
rule_module = importlib.import_module(f"{old.PACKAGE}.rule_config")
STAMP = "2026-11-03T10:00:00+00:00"


def source(source_id="a", status="matching", **updates):
    return {"id": source_id, "name": f"Quelle {source_id}", "entity_id": f"input_boolean.{source_id}",
            "alarm_type": "house", "area_id": "hall", "area_name": "Flur", "enabled": True,
            "trigger_state": "on", "current_state": "on", "status": status, **updates}


class SessionTests(unittest.TestCase):
    def test_two_sources_latch_independently_and_record_names_areas(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source(), source("b", area_name="Keller")], STAMP)
        self.assertEqual(state.state, "active")
        self.assertEqual(len(state.alarms), 2)
        self.assertEqual(state.alarms["b"]["area_name"], "Keller")
        self.assertEqual(len(state.history), 2)
        self.assertEqual(state.history[0]["sources"][0]["name"], "Quelle a")

    def test_no_duplicate_events_while_source_remains_matching(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        self.assertEqual(session_module.reconcile(state, [source()], STAMP), state)

    def test_clear_keeps_alarm_until_reset(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        state = session_module.reconcile(state, [source(status="not_matching")], STAMP)
        self.assertEqual(state.state, "active")
        self.assertTrue(state.alarms["a"]["condition_cleared"])
        state, accepted = session_module.apply_action(state, "reset", [source(status="not_matching")], STAMP)
        self.assertTrue(accepted)
        self.assertEqual(state.state, "idle")
        self.assertEqual([item["event"] for item in state.history], ["source_triggered", "source_cleared", "reset"])

    def test_reset_blocked_for_matching_or_unknown_latched_source(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        for status in ("matching", "unavailable", "unknown", "missing"):
            with self.subTest(status=status):
                candidate, accepted = session_module.apply_action(state, "reset", [source(status=status)], STAMP)
                self.assertFalse(accepted)
                self.assertEqual(candidate.state, "active")
                self.assertEqual(candidate.history[-1]["event"], "reset_blocked")

    def test_disabled_or_removed_source_can_be_reset_intentionally(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        for snapshot in ([], [source(status="disabled", enabled=False)]):
            candidate, accepted = session_module.apply_action(state, "reset", snapshot, STAMP)
            self.assertTrue(accepted)
            self.assertEqual(candidate.state, "idle")

    def test_ack_then_new_source_reactivates_overall_alarm(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        state, _ = session_module.apply_action(state, "acknowledge", [source()], STAMP)
        self.assertEqual(state.state, "acknowledged")
        state = session_module.reconcile(state, [source(), source("b")], STAMP)
        self.assertEqual(state.state, "active")
        self.assertEqual(state.alarms["a"]["state"], "acknowledged")

    def test_same_source_new_edge_reactivates_after_ack(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        state, _ = session_module.apply_action(state, "acknowledge", [source()], STAMP)
        state = session_module.reconcile(state, [source(status="not_matching")], STAMP)
        state = session_module.reconcile(state, [source()], STAMP)
        self.assertEqual(state.state, "active")
        self.assertEqual(sum(item["event"] == "source_triggered" for item in state.history), 2)

    def test_unknown_does_not_fake_a_clear_and_retrigger(self):
        state = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP)
        state = session_module.reconcile(state, [source(status="unknown")], STAMP)
        state = session_module.reconcile(state, [source()], STAMP)
        self.assertEqual(len(state.history), 1)

    def test_manual_and_source_alarm_share_overall_state_and_history(self):
        state, _ = session_module.apply_action(session_module.AlarmSession(), "trigger_test", [], STAMP)
        state = session_module.reconcile(state, [source()], STAMP)
        state, _ = session_module.apply_action(state, "acknowledge", [source()], STAMP)
        self.assertEqual(state.state, "acknowledged")
        self.assertEqual(state.manual.test_count, 1)
        self.assertEqual([item["event"] for item in state.history], ["trigger_test", "source_triggered", "acknowledge"])

    def test_history_bounded_and_restores_full_session(self):
        state = session_module.AlarmSession()
        for _ in range(130):
            state, _ = session_module.apply_action(state, "trigger_test", [], STAMP)
        self.assertEqual(len(state.history), 100)
        self.assertEqual(session_module.AlarmSession.from_dict(state.to_dict()), state)

    def test_malformed_session_is_rejected(self):
        data = session_module.reconcile(session_module.AlarmSession(), [source()], STAMP).to_dict()
        data["source_alarms"]["a"]["condition_cleared"] = "yes"
        with self.assertRaises(ValueError):
            session_module.AlarmSession.from_dict(data)


class MigrationAndManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_v01_v02_store_migration_preserves_manual_counter(self):
        manual = old.engine.AlarmState(state="acknowledged", test_count=7, last_triggered=STAMP)
        migrated = await old.storage.AlarmStore()._async_migrate_func(1, 1, {"simulation": True, "alarm": manual.to_dict()})
        session = session_module.AlarmSession.from_dict(migrated)
        self.assertEqual(session.manual, manual)
        self.assertEqual(session.alarms, {})
        self.assertEqual(session.history, [])

    async def test_invalid_legacy_store_not_migrated(self):
        for version, data in ((3, {}), (1, {"simulation": False, "alarm": {}})):
            with self.assertRaises(ValueError):
                await old.storage.AlarmStore()._async_migrate_func(version, 1, data)

    async def manager(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        manager.rules = (rule_module.AlarmRule("a", "Quelle a", ("a",), "any", "house", True),)
        return manager

    async def test_source_alarm_is_persisted_and_restored(self):
        manager = await self.manager()
        await manager.async_process_inputs([source()])
        self.assertEqual(manager.session.state, "active")
        restored = await self.manager()
        restored.store.data = deepcopy(manager.store.data)
        await restored.async_load()
        self.assertEqual(restored.session, manager.session)

    async def test_source_write_failure_keeps_previous_session(self):
        manager = await self.manager()
        previous = deepcopy(manager.session)
        manager.store.fail = True
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_process_inputs([source()])
        self.assertEqual(manager.session, previous)

    async def test_failed_trigger_is_not_lost_when_source_clears_before_retry(self):
        manager = await self.manager()
        manager.store.fail = True
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_process_inputs([source()])
        manager.store.fail = False
        await manager.async_process_inputs([source(status="not_matching")])
        self.assertEqual(manager.session.state, "active")
        self.assertEqual([event["event"] for event in manager.session.history], ["rule_triggered", "rule_cleared"])

    async def test_reset_uses_latest_snapshot_and_rejects_stale_task(self):
        manager = await self.manager()
        manager._input_sequence = 1
        await manager.async_process_inputs([source()], sequence=1)
        manager.inputs = type("Monitor", (), {"snapshot": [source(status="not_matching")]})()
        manager._input_sequence = 2
        await manager.async_action("reset")
        await manager.async_process_inputs([source()], sequence=1)
        await manager.async_process_inputs([source(status="not_matching")], sequence=2)
        self.assertEqual(manager.session.state, "idle")

    async def test_reset_rejection_is_saved_in_journal(self):
        manager = await self.manager()
        await manager.async_process_inputs([source()])
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_action("reset")
        self.assertEqual(manager.store.data["history"][-1]["event"], "reset_blocked")
        self.assertEqual(manager.session.state, "active")

    async def test_parallel_input_updates_and_manual_test_do_not_lose_data(self):
        manager = await self.manager()
        await asyncio.gather(manager.async_process_inputs([source()]), manager.async_action("trigger_test"))
        self.assertEqual(manager.session.manual.test_count, 1)
        self.assertIn("a", manager.session.alarms)


class ImprovedFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_name_is_prefilled_from_entity_and_can_be_changed(self):
        flow = inputs.flows.AlarmManagementOptionsFlow()
        flow.hass = inputs.FakeHass()
        await flow.async_step_init()
        result = await flow.async_step_add({"entity_id": "input_boolean.test_alarm"})
        self.assertEqual(result["step_id"], "add_details")
        default = next(key.default for key in result["data_schema"].schema if key.key == "name")
        self.assertEqual(default, "Test Alarm")
        await flow.async_step_add_details(inputs.payload(name="Eigener Name"))
        result = await flow.async_step_finish()
        self.assertEqual(inputs.model.load_sources(result["data"])[0].name, "Eigener Name")

    async def test_multiple_inputs_staged_until_finish(self):
        flow = inputs.flows.AlarmManagementOptionsFlow()
        flow.hass = inputs.FakeHass()
        await flow.async_step_init()
        for name in ("Erster", "Zweiter", "Dritter"):
            await flow.async_step_add({"entity_id": "input_boolean.test_alarm"})
            result = await flow.async_step_add_details(inputs.payload(name=name))
            self.assertEqual(result["menu_options"], ["add", "finish"])
            self.assertEqual(flow.hass.entry.options, {})
        result = await flow.async_step_finish()
        self.assertEqual(len(inputs.model.load_sources(result["data"])), 3)

    async def test_tenth_staged_input_offers_finish_only(self):
        flow = inputs.flows.AlarmManagementOptionsFlow()
        existing = [inputs.model.build_source(inputs.payload()) for _ in range(inputs.model.MAX_INPUTS - 1)]
        flow.hass = inputs.FakeHass(inputs.options_for(existing))
        await flow.async_step_init()
        await flow.async_step_add({"entity_id": "input_boolean.test_alarm"})
        result = await flow.async_step_add_details(inputs.payload())
        self.assertEqual(result["menu_options"], ["finish"])

    async def test_area_is_in_live_snapshot(self):
        hass = inputs.FakeHass()
        entry = hass.registry.add("input_boolean.test_alarm")
        entry.area_id = "hall"
        monitor = inputs.monitor_module.InputMonitor(hass, "integration", [inputs.model.build_source(inputs.payload(), registry_id=entry.id)])
        monitor.start(Mock())
        self.assertEqual(monitor.snapshot[0]["area_name"], "Flur")
        monitor.stop()
