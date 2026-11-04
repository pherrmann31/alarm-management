"""Offline sensor/button/diagnostic and lifecycle wiring checks, with HA doubles."""
import asyncio
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

import test_inputs as inputs
import test_simulation as old
import test_session as sessions


class FakeEntity:
    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, callback):
        pass

    def async_write_ha_state(self):
        pass


def load_platforms():
    names = ("probatio", "homeassistant", "homeassistant.components", "homeassistant.components.sensor",
             "homeassistant.components.button", "homeassistant.config_entries", "homeassistant.core",
             "homeassistant.const", "homeassistant.exceptions", "homeassistant.helpers",
             "homeassistant.helpers.device_registry", "homeassistant.helpers.dispatcher", "homeassistant.helpers.entity_platform")
    modules = {name: types.ModuleType(name) for name in names}
    modules["probatio"].Schema = lambda data: data
    modules['probatio'].Required=inputs.FakeMarker
    modules["homeassistant.components.sensor"].SensorEntity = FakeEntity
    modules["homeassistant.components.sensor"].SensorDeviceClass = types.SimpleNamespace(ENUM="enum")
    modules["homeassistant.components.button"].ButtonEntity = FakeEntity
    modules["homeassistant.config_entries"].ConfigEntry = object
    modules["homeassistant.const"].EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
    modules["homeassistant.const"].Platform = types.SimpleNamespace(SENSOR="sensor", BUTTON="button")
    for name in ("HomeAssistant", "ServiceCall"):
        setattr(modules["homeassistant.core"], name, object)
    modules["homeassistant.core"].callback = lambda fn: fn
    for name in ("ConfigEntryError", "ConfigEntryNotReady", "HomeAssistantError", "ServiceValidationError"):
        setattr(modules["homeassistant.exceptions"], name, old.FakeHomeAssistantError)
    modules["homeassistant.helpers.device_registry"].DeviceInfo = lambda **data: data
    modules["homeassistant.helpers.device_registry"].DeviceEntryType = types.SimpleNamespace(SERVICE="service")
    modules["homeassistant.helpers.dispatcher"].async_dispatcher_connect = lambda *args: lambda: None
    modules["homeassistant.helpers.entity_platform"].AddConfigEntryEntitiesCallback = object
    modules[f"{old.PACKAGE}.input_monitor"] = inputs.monitor_module
    modules[f"{old.PACKAGE}.output_monitor"] = inputs.output_monitor_module
    modules[f"{old.PACKAGE}.manager"] = old.manager_module
    modules[f"{old.PACKAGE}.storage"] = old.storage
    with patch.dict(sys.modules, modules):
        sensor = importlib.import_module(f"{old.PACKAGE}.sensor")
        button = importlib.import_module(f"{old.PACKAGE}.button")
        diagnostics = importlib.import_module(f"{old.PACKAGE}.diagnostics")
        path = Path(old.package.__path__[0]) / "__init__.py"
        spec = importlib.util.spec_from_file_location(f"{old.PACKAGE}.lifecycle", path)
        lifecycle = importlib.util.module_from_spec(spec)
        lifecycle.__package__ = old.PACKAGE
        spec.loader.exec_module(lifecycle)
    return sensor, button, diagnostics, lifecycle


sensor, button, diagnostics, lifecycle = load_platforms()


class PlatformTests(unittest.IsolatedAsyncioTestCase):
    async def manager(self):
        manager = old.manager_module.AlarmManager(object(), "integration")
        await manager.async_load()
        manager.running = True
        manager.rules = (sessions.rule_module.AlarmRule("a", "Quelle a", ("a",), "any", "house", True),)
        manager.inputs = types.SimpleNamespace(snapshot=[], sources=[])
        return manager

    async def test_source_and_area_sensors_and_journal_preview(self):
        manager = await self.manager()
        await manager.async_process_inputs([sessions.source()])
        entry = types.SimpleNamespace(entry_id="integration", title="Simulation", runtime_data=manager)
        self.assertEqual(sensor.AlarmStatusSensor(entry).native_value, "active")
        self.assertEqual(sensor.AlarmDetailSensor(entry, "triggered_by").native_value, "Quelle a")
        self.assertEqual(sensor.AlarmDetailSensor(entry, "triggered_areas").native_value, "Flur")
        journal = sensor.AlarmDetailSensor(entry, "journal")
        self.assertEqual(journal.extra_state_attributes["events"][0]["event"], "rule_triggered")
        manager.input_error = True
        self.assertFalse(sensor.AlarmStatusSensor(entry).available)
        self.assertFalse(journal.available)

    async def test_buttons_call_only_own_manager_and_diagnostics_copy_data(self):
        manager = await self.manager()
        entry = types.SimpleNamespace(entry_id="integration", runtime_data=manager, options={})
        with patch.object(manager, "async_action", new_callable=AsyncMock) as action:
            await button.AlarmButton(entry, "reset").async_press()
            action.assert_awaited_once_with("reset")
        result = await diagnostics.async_get_config_entry_diagnostics(None, entry)
        result["alarm_session"]["history"].append({"changed": True})
        self.assertEqual(manager.session.history, [])

    async def test_setup_processes_inputs_and_unload_removes_listeners_and_services(self):
        source = inputs.model.build_source(inputs.payload())
        hass = inputs.FakeHass(inputs.options_for([source]))
        hass.entry.data = {"simulation": True}
        hass.config_entries = types.SimpleNamespace(async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True),
                                                    async_update_entry=lambda entry, **kw: setattr(entry, "options", kw["options"]))
        hass.async_create_task = asyncio.create_task
        hass.loop = asyncio.get_running_loop()
        services = {}
        hass.services = types.SimpleNamespace(async_register=lambda domain, name, handler, **kw: services.update({name: handler}),
                                             async_remove=lambda domain, name: services.pop(name))
        self.assertTrue(await lifecycle.async_setup_entry(hass, hass.entry))
        manager = hass.entry.runtime_data
        hass.set_state(source.entity_id, "on")
        await manager.async_drain()
        self.assertEqual(manager.session.state, "active")
        self.assertEqual(set(services), {"trigger_test", "acknowledge", "reset", "retry_outputs", "acknowledge_popup"})
        self.assertTrue(await lifecycle.async_unload_entry(hass, hass.entry))
        self.assertEqual(hass.trackers, [])
        self.assertEqual(hass.bus.callbacks, [])
        self.assertEqual(services, {})
        self.assertFalse(manager.running)
