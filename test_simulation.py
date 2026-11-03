"""Offline unit tests with explicit HA doubles; not HA integration tests."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "alarm_starter_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "alarm_management")]
sys.modules[PACKAGE] = package
engine = importlib.import_module(f"{PACKAGE}.alarm_engine")
STAMP = "2026-11-03T10:00:00+00:00"


class FakeStore:
    """Memory store, explicitly substituting for Home Assistant disk storage."""

    def __init__(self, hass=None, version=None, key=None, **kwargs):
        self.data = None
        self.writes = 0
        self.fail = False

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, data):
        await asyncio.sleep(0)  # Allow concurrent callers to interleave.
        if self.fail:
            raise OSError("test disk failure")
        self.data = deepcopy(data)
        self.writes += 1


class FakeHomeAssistantError(Exception):
    pass


def load_adapters():
    """Import adapters with minimal doubles, without executing package setup."""
    modules = {}
    for name in (
        "homeassistant", "homeassistant.core", "homeassistant.const", "homeassistant.helpers",
        "homeassistant.helpers.storage", "homeassistant.helpers.dispatcher",
        "homeassistant.exceptions", "homeassistant.util", "homeassistant.util.dt",
    ):
        modules[name] = types.ModuleType(name)
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.core"].callback = lambda fn: fn
    modules["homeassistant.const"].EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
    modules["homeassistant.helpers.storage"].Store = FakeStore
    modules["homeassistant.helpers.dispatcher"].async_dispatcher_send = lambda *args: None
    modules["homeassistant.exceptions"].HomeAssistantError = FakeHomeAssistantError
    modules["homeassistant.exceptions"].ServiceValidationError = FakeHomeAssistantError
    modules["homeassistant.util.dt"].utcnow = lambda: datetime.now(timezone.utc)
    modules["homeassistant.util"].dt = modules["homeassistant.util.dt"]
    with patch.dict(sys.modules, modules):
        storage = importlib.import_module(f"{PACKAGE}.storage")
        manager = importlib.import_module(f"{PACKAGE}.manager")
    return storage, manager


storage, manager_module = load_adapters()


class StateMachineTests(unittest.TestCase):
    def test_initial_state(self):
        self.assertEqual(engine.AlarmState().state, "idle")
        self.assertEqual(engine.AlarmState().test_count, 0)

    def test_trigger_ack_reset(self):
        state = engine.transition(engine.AlarmState(), "trigger_test", STAMP)
        self.assertEqual((state.state, state.test_count), ("active", 1))
        state = engine.transition(state, "acknowledge", STAMP)
        self.assertEqual(state.state, "acknowledged")
        state = engine.transition(state, "reset", STAMP)
        self.assertEqual((state.state, state.test_count), ("idle", 1))
        self.assertEqual(state.last_triggered, STAMP)

    def test_repeated_trigger_is_single_alarm_and_counts(self):
        state = engine.AlarmState()
        for _ in range(5):
            state = engine.transition(state, "trigger_test", STAMP)
        self.assertEqual((state.state, state.test_count), ("active", 5))

    def test_trigger_reactivates_acknowledged_alarm(self):
        state = engine.AlarmState(state="acknowledged", test_count=4)
        state = engine.transition(state, "trigger_test", STAMP)
        self.assertEqual((state.state, state.test_count), ("active", 5))

    def test_idle_ack_reset_are_noops(self):
        state = engine.AlarmState()
        for action in ("acknowledge", "reset"):
            self.assertIs(engine.transition(state, action, STAMP), state)

    def test_repeated_acknowledgement_is_noop(self):
        state = engine.AlarmState(state="acknowledged")
        self.assertIs(engine.transition(state, "acknowledge", STAMP), state)

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValueError):
            engine.transition(engine.AlarmState(), "turn_on", STAMP)

    def test_roundtrip_and_invalid_storage(self):
        state = engine.transition(engine.AlarmState(), "trigger_test", STAMP)
        self.assertEqual(engine.AlarmState.from_dict(state.to_dict()), state)
        for key, bad in (
            ("state", "armed"), ("test_count", -1), ("test_count", True),
            ("last_triggered", "bad"), ("last_changed", "2026-11-03T10:00:00"),
            ("last_changed", 42),
        ):
            with self.subTest(key=key, bad=bad):
                data = state.to_dict()
                data[key] = bad
                with self.assertRaises(ValueError):
                    engine.AlarmState.from_dict(data)
        with self.assertRaises(ValueError):
            engine.AlarmState.from_dict({})


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_load_creates_simulation_store(self):
        store = FakeStore()
        state = await storage.async_load_state(store)
        self.assertEqual(state, engine.AlarmState())
        self.assertEqual(store.data["execution_mode"], "live")
        self.assertEqual(store.writes, 1)

    async def test_reload_restores_alarm(self):
        store = FakeStore()
        state = engine.transition(engine.AlarmState(), "trigger_test", STAMP)
        await storage.async_save_state(store, state)
        self.assertEqual(await storage.async_load_state(store), state)

    async def test_invalid_store_is_not_overwritten(self):
        for data in ({}, {"simulation": False, "alarm": {}}, [], {"simulation": True, "alarm": {}}):
            with self.subTest(data=data):
                store = FakeStore()
                store.data = data
                with self.assertRaises(ValueError):
                    await storage.async_load_state(store)
                self.assertEqual(store.writes, 0)


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = manager_module.AlarmManager(object(), "test_entry")
        await self.manager.async_load()
        self.manager.running = True

    async def test_concurrent_triggers_are_serialized(self):
        await asyncio.gather(*(self.manager.async_action("trigger_test") for _ in range(25)))
        self.assertEqual(self.manager.state.test_count, 25)
        self.assertEqual(self.manager.store.data["alarm"]["test_count"], 25)

    async def test_write_failure_keeps_state_and_suppresses_notification(self):
        before = self.manager.state
        self.manager.store.fail = True
        with patch.object(manager_module, "async_dispatcher_send") as notify:
            with self.assertRaises(FakeHomeAssistantError):
                await self.manager.async_action("trigger_test")
            notify.assert_not_called()
        self.assertEqual(self.manager.state, before)

    async def test_success_notifies_after_commit(self):
        observations = []
        def check(*args):
            observations.append(self.manager.store.data["alarm"] == self.manager.state.to_dict())
        with patch.object(manager_module, "async_dispatcher_send", side_effect=check):
            await self.manager.async_action("trigger_test")
        self.assertEqual(observations, [True])

    async def test_unloaded_manager_rejects_action(self):
        self.manager.running = False
        with self.assertRaises(FakeHomeAssistantError):
            await self.manager.async_action("trigger_test")
        self.assertEqual(self.manager.state.test_count, 0)

    async def test_noop_does_not_write_or_notify(self):
        writes = self.manager.store.writes
        with patch.object(manager_module, "async_dispatcher_send") as notify:
            await self.manager.async_action("acknowledge")
            await self.manager.async_action("reset")
            notify.assert_not_called()
        self.assertEqual(self.manager.store.writes, writes)

    async def test_new_manager_restores_saved_snapshot(self):
        await self.manager.async_action("trigger_test")
        await self.manager.async_action("acknowledge")
        restored = manager_module.AlarmManager(object(), "test_entry")
        restored.store.data = deepcopy(self.manager.store.data)
        await restored.async_load()
        self.assertEqual(restored.state, self.manager.state)


if __name__ == "__main__":
    unittest.main()
