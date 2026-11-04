"""Offline model, options-flow and monitor tests with explicit HA doubles."""

from copy import deepcopy
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
NAME = "alarm_inputs_test"
package = types.ModuleType(NAME)
package.__path__ = [str(ROOT / "custom_components/alarm_management")]
sys.modules[NAME] = package
model = importlib.import_module(f"{NAME}.input_config")


def payload(**updates):
    return {"name": "Flur", "entity_id": "input_boolean.test_alarm",
            "trigger_state": "on", "alarm_type": "house", "enabled": True, **updates}


class FakeMarker:
    def __init__(self, key, **kwargs):
        self.key = key
        self.default = kwargs.get("default")
        self.description = kwargs.get("description", {})


class FakeSchema:
    """Only a carrier for schema fields; not a probatio implementation."""
    def __init__(self, schema):
        self.schema = schema


class FakeSection:
    def __init__(self, schema, options):
        self.schema = schema
        self.options = options


class FakeSelector:
    def __init__(self, config):
        self.config = config


class FakeFlow:
    automatic_reload = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    @property
    def config_entry(self):
        return self.hass.entry

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_show_menu(self, **kwargs):
        return {"type": "menu", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **deepcopy(kwargs)}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass


class FakeRegistry:
    def __init__(self):
        self.entries = []

    def async_get(self, value):
        return next((item for item in self.entries if value in (item.id, item.entity_id)), None)

    def add(self, entity_id, registry_id="registered-source", config_entry_id="other"):
        item = types.SimpleNamespace(entity_id=entity_id, id=registry_id, config_entry_id=config_entry_id)
        self.entries.append(item)
        return item

    def async_remove(self, entity_id):
        self.entries = [item for item in self.entries if item.entity_id != entity_id]


class FakeBus:
    def __init__(self):
        self.callbacks = []

    def async_listen(self, event_type, callback):
        item = (event_type, callback)
        self.callbacks.append(item)
        return lambda: self.callbacks.remove(item)

    def emit(self, event_type, data):
        for kind, callback in list(self.callbacks):
            if kind == event_type:
                callback(types.SimpleNamespace(data=data))


class FakeHass:
    def __init__(self, options=None):
        self.entry = types.SimpleNamespace(entry_id="integration", options=options or {})
        self.registry = FakeRegistry()
        self.devices = {}
        self.services = types.SimpleNamespace(async_services=lambda:{'notify':{'mobile_app_phone':{},'pushover':{}}},has_service=lambda *args:True)
        self.values = {"input_boolean.test_alarm": "off"}
        self.states = types.SimpleNamespace(get=lambda item: types.SimpleNamespace(state=self.values[item], attributes={"friendly_name": "Test Alarm"}) if item in self.values else None)
        self.states.async_all = lambda domain: [types.SimpleNamespace(entity_id=key,attributes={'friendly_name':key}) for key in self.values if key.startswith(domain+'.')]
        self.bus = FakeBus()
        self.trackers = []

    def track(self, entities, callback):
        item = (entities, callback)
        self.trackers.append(item)
        return lambda: self.trackers.remove(item)

    def set_state(self, entity_id, value):
        if value is None:
            self.values.pop(entity_id, None)
        else:
            self.values[entity_id] = value
        for entities, callback in list(self.trackers):
            if entity_id in entities:
                callback(types.SimpleNamespace(data={"entity_id": entity_id}))


def import_adapters():
    modules = {name: types.ModuleType(name) for name in (
        "probatio", "homeassistant", "homeassistant.core", "homeassistant.config_entries", "homeassistant.data_entry_flow",
        "homeassistant.helpers", "homeassistant.helpers.entity_registry",
        "homeassistant.helpers.selector", "homeassistant.helpers.event",
        "homeassistant.helpers.area_registry", "homeassistant.helpers.device_registry",
    )}
    modules["homeassistant.data_entry_flow"].section = FakeSection
    modules["probatio"].Schema = FakeSchema
    modules["probatio"].Required = FakeMarker
    modules["probatio"].Optional = FakeMarker
    modules["homeassistant.core"].callback = lambda fn: fn
    for item in ("ConfigFlow", "OptionsFlowWithReload"):
        setattr(modules["homeassistant.config_entries"], item, FakeFlow)
    modules["homeassistant.config_entries"].ConfigFlowResult = dict
    registry = modules["homeassistant.helpers.entity_registry"]
    registry.async_get = lambda hass: hass.registry
    registry.async_entries_for_config_entry = lambda reg, entry_id: [item for item in reg.entries if item.config_entry_id == entry_id]
    registry.EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"
    registry.async_get_effective_area_id = lambda hass, entry: getattr(entry, "area_id", None)
    areas = modules["homeassistant.helpers.area_registry"]
    areas.async_get = lambda hass: types.SimpleNamespace(async_get_area=lambda area_id: types.SimpleNamespace(name="Flur"))
    areas.EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"
    modules["homeassistant.helpers.device_registry"].EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
    modules["homeassistant.helpers.device_registry"].async_get = lambda hass: types.SimpleNamespace(devices=hass.devices)
    for item in ("EntitySelector", "SelectSelector", "TextSelector"):
        setattr(modules["homeassistant.helpers.selector"], item, FakeSelector)
    modules["homeassistant.helpers.event"].async_track_state_change_event = lambda hass, ids, callback: hass.track(ids, callback)
    with patch.dict(sys.modules, modules):
        monitor = importlib.import_module(f"{NAME}.input_monitor")
        flows = importlib.import_module(f"{NAME}.config_flow")
        output_monitor = importlib.import_module(f"{NAME}.output_monitor")
    return monitor, flows, output_monitor


monitor_module, flows, output_monitor_module = import_adapters()


def options_for(sources):
    return {"input_config": model.serialize_sources(sources)}


class ModelTests(unittest.TestCase):
    def test_v01_options_default_to_empty_inputs(self):
        self.assertEqual(model.load_sources({}), ())

    def test_roundtrip_and_stable_id(self):
        source = model.build_source(payload())
        edited = model.build_source(payload(name="Neuer Name", entity_id="binary_sensor.smoke"), source_id=source.id)
        self.assertEqual(source.id, edited.id)
        self.assertEqual(model.load_sources(options_for([edited])), (edited,))

    def test_generated_ids_differ(self):
        self.assertNotEqual(model.build_source(payload()).id, model.build_source(payload()).id)

    def test_limit_ten_and_reject_eleventh(self):
        sources = [model.build_source(payload()) for _ in range(model.MAX_INPUTS)]
        self.assertEqual(len(model.load_sources(options_for(sources))), model.MAX_INPUTS)
        with self.assertRaises(ValueError):
            options_for(sources + [model.build_source(payload())])

    def test_duplicate_ids_are_rejected(self):
        source = model.build_source(payload())
        with self.assertRaises(ValueError):
            options_for([source, source])

    def test_invalid_fields(self):
        for field, value in (("name", " "), ("name", "x" * 81), ("entity_id", "invalid"),
                             ("trigger_state", ""), ("trigger_state", "unknown"),
                             ("trigger_state", "unavailable"), ("trigger_state", "x" * 256),
                             ("alarm_type", "other"), ("enabled", "true")):
            with self.subTest(field=field, value=value), self.assertRaises(model.InputValidationError):
                model.build_source(payload(**{field: value}))

    def test_unknown_schema_not_silently_replaced(self):
        for raw in ({"version": 2, "inputs": []}, {"version": True, "inputs": []}, None, {}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                model.load_sources({"input_config": raw})

    def test_exact_comparison_and_missing_states(self):
        source = model.build_source(payload())
        for value, expected in (("on", "matching"), ("off", "not_matching"),
                                ("ON", "not_matching"), (None, "missing"),
                                ("unknown", "unknown"), ("unavailable", "unavailable")):
            self.assertEqual(model.evaluate_source(source, value), expected)
        disabled = model.build_source(payload(enabled=False))
        self.assertEqual(model.evaluate_source(disabled, "on"), "disabled")


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def stage(self, flow, data):
        await flow.async_step_add({"entity_id": data["entity_id"]})
        return await flow.async_step_add_details(data)

    async def save_added(self, flow, data):
        await self.stage(flow, data)
        return await flow.async_step_finish()

    def create_flow(self, options=None):
        flow = flows.AlarmManagementOptionsFlow()
        flow.hass = FakeHass(options)
        return flow

    async def test_factory_and_empty_menu(self):
        flow = flows.AlarmManagementConfigFlow.async_get_options_flow(None)
        flow.hass = FakeHass()
        result = await flow.async_step_init()
        self.assertEqual(result["menu_options"], ["status", "groups", "inputs", "outputs", "rules", "notifications"])
        self.assertEqual((await flow.async_step_inputs())["menu_options"], ["add", "overview", "init"])

    async def test_existing_setup_still_requires_simulation_confirmation(self):
        flow = flows.AlarmManagementConfigFlow()
        result = await flow.async_step_user({"confirm_live": False})
        self.assertEqual(result["errors"], {"base": "live_required"})
        result = await flow.async_step_user({"confirm_live": True})
        self.assertEqual(result["data"], {"execution_mode": "live"})

    async def test_selector_excludes_integration_entities(self):
        flow = self.create_flow()
        flow.hass.registry.add("sensor.own", config_entry_id="integration")
        await flow.async_step_init()
        result = await flow.async_step_add()
        selector = next(value for key, value in result["data_schema"].schema.items() if key.key == "entity_id")
        self.assertEqual(selector.config["exclude_entities"], ["sensor.own"])

    async def test_add_preserves_other_namespaces_and_original_options(self):
        options = {"future_rules": {"keep": True}}
        flow = self.create_flow(options)
        await flow.async_step_init()
        await flow.async_step_add()
        self.assertEqual(flow.hass.entry.options, options)  # Opening/aborting is read-only.
        result = await self.save_added(flow, payload())
        self.assertEqual(result["data"]["future_rules"], {"keep": True})
        self.assertEqual(len(model.load_sources(result["data"])), 1)
        self.assertEqual(flow.hass.entry.options, options)

    async def test_registered_entity_reference_is_saved(self):
        flow = self.create_flow()
        flow.hass.registry.add("input_boolean.test_alarm")
        await flow.async_step_init()
        result = await self.save_added(flow, payload())
        source = model.load_sources(result["data"])[0]
        self.assertEqual(source.entity_registry_id, "registered-source")

    async def test_edit_replaces_entity_keeps_source_id(self):
        old = model.build_source(payload())
        flow = self.create_flow(options_for([old]))
        flow.hass.values["binary_sensor.smoke"] = "off"
        await flow.async_step_init()
        result = await flow.async_step_edit({"source_id": old.id})
        self.assertEqual(result["step_id"], "edit_input")
        result = await flow.async_step_edit_input(payload(entity_id="binary_sensor.smoke", enabled=False))
        edited = model.load_sources(result["data"])[0]
        self.assertEqual((edited.id, edited.entity_id, edited.enabled), (old.id, "binary_sensor.smoke", False))

    async def test_remove_requires_confirmation_and_keeps_other_source(self):
        sources = [model.build_source(payload()), model.build_source(payload(name="Zweiter"))]
        flow = self.create_flow({**options_for(sources), "rule_config": {"version": 1, "rules": []}})
        await flow.async_step_init()
        await flow.async_step_remove({"source_id": sources[0].id})
        result = await flow.async_step_confirm_remove({"confirm": False})
        self.assertEqual(result["errors"], {"base": "confirmation_required"})
        result = await flow.async_step_confirm_remove({"confirm": True})
        self.assertEqual(model.load_sources(result["data"]), (sources[1],))

    async def test_no_add_at_limit_and_server_enforces_limit(self):
        flow = self.create_flow(options_for([model.build_source(payload()) for _ in range(model.MAX_INPUTS)]))
        result = await flow.async_step_init()
        self.assertNotIn("add", result["menu_options"])
        self.assertEqual((await flow.async_step_add(payload()))["reason"], "max_inputs")

    async def test_invalid_entity_and_own_entity_rejected(self):
        flow = self.create_flow()
        await flow.async_step_init()
        result = await flow.async_step_add(payload(entity_id="sensor.missing"))
        self.assertEqual(result["errors"], {"entity_id": "entity_not_found"})
        flow.hass.registry.add("sensor.own", config_entry_id="integration")
        result = await flow.async_step_add(payload(entity_id="sensor.own"))
        self.assertEqual(result["errors"], {"entity_id": "own_entity"})

    async def test_invalid_form_remains_open(self):
        flow = self.create_flow()
        await flow.async_step_init()
        result = await self.stage(flow, payload(name="  "))
        self.assertEqual(result["errors"], {"name": "invalid_name"})
        self.assertEqual(flow.hass.entry.options, {})

    async def test_concurrent_change_is_not_overwritten(self):
        flow = self.create_flow()
        await flow.async_step_init()
        flow.hass.entry.options = options_for([model.build_source(payload())])
        result = await self.save_added(flow, payload())
        self.assertEqual(result["reason"], "configuration_changed")

    async def test_unknown_config_version_aborts(self):
        flow = self.create_flow({"input_config": {"version": 2, "inputs": []}})
        self.assertEqual((await flow.async_step_init())["reason"], "invalid_configuration")

    async def test_overview_does_not_save_or_reload(self):
        flow = self.create_flow()
        await flow.async_step_init()
        result = await flow.async_step_overview()
        self.assertEqual(result["description_placeholders"]["count"], "0")
        self.assertEqual((await flow.async_step_overview({}))["step_id"], "inputs")
        self.assertEqual(flow.hass.entry.options, {})


class MonitorTests(unittest.TestCase):
    def test_initial_snapshot_and_changes(self):
        hass = FakeHass()
        source = model.build_source(payload())
        monitor = monitor_module.InputMonitor(hass, "integration", [source])
        notify = Mock()
        monitor.start(notify)
        self.assertEqual(monitor.snapshot[0]["status"], "not_matching")
        hass.set_state(source.entity_id, "on")
        self.assertEqual(monitor.snapshot[0]["status"], "matching")
        calls = notify.call_count
        hass.set_state(source.entity_id, "on")
        self.assertEqual(notify.call_count, calls)  # Ignore redundant/attribute-only events.
        hass.set_state(source.entity_id, "unavailable")
        self.assertEqual(monitor.snapshot[0]["status"], "unavailable")
        hass.set_state(source.entity_id, None)
        self.assertEqual(monitor.snapshot[0]["status"], "missing")

    def test_disabled_inputs_are_not_subscribed(self):
        hass = FakeHass()
        source = model.build_source(payload(enabled=False))
        monitor = monitor_module.InputMonitor(hass, "integration", [source])
        monitor.start(Mock())
        self.assertEqual(hass.trackers, [])
        self.assertEqual(monitor.snapshot[0]["status"], "disabled")

    def test_empty_config_and_stop_cleanup(self):
        hass = FakeHass()
        monitor = monitor_module.InputMonitor(hass, "integration", [])
        monitor.start(Mock())
        self.assertEqual(monitor.snapshot, [])
        monitor.stop()
        monitor.stop()  # Idempotent cleanup.
        self.assertEqual(hass.trackers, [])
        self.assertEqual(hass.bus.callbacks, [])

    def test_rename_follows_registry_id_and_rebinds_subscription(self):
        hass = FakeHass()
        entry = hass.registry.add("input_boolean.test_alarm")
        source = model.build_source(payload(), registry_id=entry.id)
        monitor = monitor_module.InputMonitor(hass, "integration", [source])
        monitor.start(Mock())
        entry.entity_id = "input_boolean.renamed"
        hass.values[entry.entity_id] = "on"
        hass.bus.emit("entity_registry_updated", {"action": "update", "entity_id": entry.entity_id})
        self.assertEqual(monitor.snapshot[0]["entity_id"], entry.entity_id)
        self.assertEqual(monitor.snapshot[0]["status"], "matching")
        self.assertEqual(hass.trackers[0][0], [entry.entity_id])

    def test_deleted_registered_source_does_not_rebind_by_name(self):
        hass = FakeHass()
        entry = hass.registry.add("input_boolean.test_alarm")
        source = model.build_source(payload(), registry_id=entry.id)
        monitor = monitor_module.InputMonitor(hass, "integration", [source])
        monitor.start(Mock())
        hass.registry.entries.remove(entry)
        hass.registry.add("input_boolean.test_alarm", registry_id="new-device")
        hass.values["input_boolean.test_alarm"] = "on"
        hass.bus.emit("entity_registry_updated", {"action": "remove", "entity_id": entry.entity_id})
        self.assertEqual(monitor.snapshot[0]["status"], "missing")
        self.assertEqual(hass.trackers, [])

    def test_own_entity_is_blocked_even_for_manually_edited_options(self):
        hass = FakeHass()
        hass.registry.add("sensor.own", config_entry_id="integration")
        monitor = monitor_module.InputMonitor(hass, "integration", [model.build_source(payload(entity_id="sensor.own"))])
        monitor.start(Mock())
        self.assertEqual(monitor.snapshot[0]["status"], "blocked")
        self.assertEqual(hass.trackers, [])

    def test_restarting_monitor_does_not_duplicate_listeners(self):
        hass = FakeHass()
        monitor = monitor_module.InputMonitor(hass, "integration", [model.build_source(payload())])
        monitor.start(Mock())
        monitor.start(Mock())
        self.assertEqual(len(hass.trackers), 1)
        self.assertEqual(len(hass.bus.callbacks), 3)
        monitor.stop()
        self.assertEqual(hass.trackers, [])
        self.assertEqual(hass.bus.callbacks, [])


if __name__ == "__main__":
    unittest.main()
