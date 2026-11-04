"""Pure output planning and offline HA dialog/monitor regressions."""
from copy import deepcopy
import importlib
import unittest
from unittest.mock import Mock, AsyncMock
import asyncio
import types

import test_inputs as inputs
import test_platforms as platforms
import test_rules as rules
import test_session as sessions
import test_simulation as old

config = importlib.import_module(f"{inputs.NAME}.output_config")
engine = importlib.import_module(f"{old.PACKAGE}.output_engine")
STAMP = sessions.STAMP


def values(kind="switch", **updates):
    data = {"name": "Sirene", "kind": kind, "entity_id": "input_boolean.siren" if kind == "switch" else None,
            "enabled": True, "encoding": "latin-1", "alarm_value": "on" if kind == "switch" else "FEUER",
            "acknowledged_value": "off" if kind == "switch" else "Quittiert", "idle_value": "off" if kind == "switch" else "Bereit"}
    if kind in ('notification','overlay'):
        data['notification']={'routes':['mobile_app:notify.mobile_app_phone'] if kind=='notification' else ['browser:'+'a'*32], 'title':'Alarm', 'devices':'', 'priority':0}
    return {**data, **updates}


def alarm_session():
    return sessions.session_module.reconcile(sessions.session_module.AlarmSession(),
        rules.engine.evaluate_rules([rules.live_rule(ids=("a",))], [sessions.source()]), STAMP)


def plan(output, session=None, *, targets=None, configured_rules=None):
    configured_rules = configured_rules or [rules.live_rule(ids=("a",))]
    return engine.plan_outputs([output], {"rule": [output.id]}, configured_rules, session or alarm_session(), targets)[output.id]


class OutputConfigTests(unittest.TestCase):
    def test_all_kinds_roundtrip_stable_ids(self):
        outputs = [config.build_output(values(kind, name=kind)) for kind in config.KINDS]
        payload = config.serialize_output_config(outputs, {}, [])
        loaded, _ = config.load_output_config({"output_config": payload}, [])
        self.assertEqual(tuple(outputs), loaded)
        edited = config.build_output(values(name="Neu"), output_id=outputs[0].id)
        self.assertEqual(edited.id, outputs[0].id)

    def test_short_text_exactly_fourteen_bytes_and_encoding(self):
        config.build_output(values("short_text", alarm_value="Ä" * 14))
        for text, encoding in (("a" * 15, "latin-1"), ("Ä", "ascii"), ("🔥", "latin-1")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                config.build_output(values("short_text", alarm_value=text, encoding=encoding))

    def test_templates_allow_only_named_placeholders_and_no_code(self):
        config.build_output(values("long_text", alarm_value="{regel}: {quelle}, {bereich}, {alarmtyp}, {status}"))
        for text in ("{unknown}", "{regel.__class__}", "{regel[0]}", "{regel!r}", "{regel:>20}", "{broken"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                config.build_output(values("long_text", alarm_value=text))

    def test_switch_target_required_and_domain_restricted(self):
        for data in (values(entity_id=None), values(entity_id="sensor.temperature"), values("short_text", entity_id="light.kitchen")):
            with self.assertRaises(ValueError):
                config.build_output(data)
        self.assertIsNone(config.build_output(values("long_text")).entity_id)

    def test_invalid_switch_values_and_text_boundaries(self):
        with self.assertRaises(ValueError):
            config.build_output(values(alarm_value="toggle"))
        with self.assertRaises(ValueError):
            config.build_output(values("long_text", alarm_value="x" * 4097))
        with self.assertRaises(ValueError):
            config.build_output(values("short_text", alarm_value="a\nb"))

    def test_empty_namespace_added_once_and_unknown_version_rejected(self):
        result = config.ensure_output_options({}, [])
        self.assertEqual(config.ensure_output_options(result, []), result)
        with self.assertRaises(ValueError):
            config.ensure_output_options({"output_config": {"version": 9, "outputs": [], "bindings": {}}}, [])

    def test_duplicate_targets_and_invalid_bindings_rejected(self):
        output = config.build_output(values())
        duplicate = config.build_output(values(name="Andere"), registry_id="registered")
        with self.assertRaises(ValueError):
            config.serialize_output_config([output, duplicate], {}, [])
        for bindings in ({"missing_rule": [output.id]}, {"rule": ["missing_output"]}, {"rule": [output.id, output.id]}):
            with self.assertRaises(ValueError):
                config.serialize_output_config([output], bindings, [rules.live_rule()])

    def test_output_limit(self):
        outputs = [config.build_output(values("long_text", name=f"Text {i}")) for i in range(20)]
        config.serialize_output_config(outputs, {}, [])
        with self.assertRaises(ValueError):
            config.serialize_output_config(outputs + [config.build_output(values("long_text"))], {}, [])


class OutputEngineTests(unittest.TestCase):
    def test_alarm_ack_idle_switch_states(self):
        output = config.build_output(values())
        session = alarm_session()
        self.assertEqual(plan(output, session)["value"], "on")
        for alarm in session.alarms.values():
            alarm["state"] = "acknowledged"
        self.assertEqual(plan(output, session)["value"], "off")
        session.alarms = {}
        self.assertEqual(plan(output, session)["value"], "off")
        self.assertEqual(plan(output, session)["phase"], "idle")

    def test_on_wins_for_shared_output_with_mixed_alarm_states(self):
        output = config.build_output(values())
        session = alarm_session()
        second = deepcopy(session.alarms["rule"])
        second.update(id="second", rule_id="second", rule_name="Zweite", state="acknowledged")
        session.alarms["second"] = second
        second_rule = sessions.rule_module.AlarmRule("second", "Zweite", ("a",), "any", "fire", True)
        result = engine.plan_outputs([output], {"rule": [output.id], "second": [output.id]}, [rules.live_rule(), second_rule], session)
        self.assertEqual(result[output.id]["value"], "on")
        self.assertEqual(len(result[output.id]["rules"]), 2)
        del session.alarms["second"]
        self.assertEqual(plan(output, session)["value"], "on")

    def test_disabled_output_or_rule_and_unassigned_output(self):
        output = config.build_output(values(enabled=False))
        self.assertEqual(plan(output)["status"], "disabled")
        output = config.build_output(values())
        self.assertEqual(plan(output, configured_rules=[rules.live_rule(enabled=False)])["phase"], "idle")
        result = engine.plan_outputs([output], {}, [rules.live_rule()], alarm_session())
        self.assertEqual(result[output.id]["phase"], "idle")

    def test_short_text_overflow_after_placeholder_is_error_not_cut(self):
        output = config.build_output(values("short_text", alarm_value="{regel}"))
        session = alarm_session()
        session.alarms["rule"]["rule_name"] = "Regel mit viel zu langem Namen"
        result = plan(output, session)
        self.assertEqual(result["error"], "short_text_too_long")
        self.assertEqual(result["value"], "Regel mit viel zu langem Namen")

    def test_runtime_unrepresentable_text_and_control_characters(self):
        output = config.build_output(values("short_text", alarm_value="{quelle}"))
        for name, expected in (("🔥", "unsupported_character"), ("a\nb", "short_text_invalid")):
            session = alarm_session()
            session.alarms["rule"]["sources"][0]["name"] = name
            self.assertEqual(plan(output, session)["error"], expected)

    def test_long_text_context_and_target_length(self):
        output = config.build_output(values("long_text", alarm_value="{regel}: {quelle} / {bereich} / {alarmtyp} / {status}"))
        result = plan(output)
        self.assertIn("Testregel: Quelle a / Flur / Feuer / aktiv", result["value"])
        output = config.build_output(values("long_text", entity_id="input_text.display", alarm_value="x" * 300))
        self.assertEqual(plan(output)["error"], "target_text_length")
        output = config.build_output(values("long_text", alarm_value="x" * 300))
        self.assertIsNone(plan(output)["error"])

    def test_missing_target_is_reported(self):
        output = config.build_output(values())
        result = plan(output, targets={output.id: {"entity_id": output.entity_id, "available": False}})
        self.assertEqual((result["status"], result["error"]), ("error", "target_unavailable"))

    def test_history_changes_only_and_restores(self):
        output = config.build_output(values())
        session = engine.apply_output_plan(alarm_session(), [output], {"rule": [output.id]}, [rules.live_rule()], STAMP)
        self.assertEqual(len(session.output_history), 1)
        again = engine.apply_output_plan(session, [output], {"rule": [output.id]}, [rules.live_rule()], STAMP)
        self.assertEqual(again, session)
        restored = sessions.session_module.AlarmSession.from_dict(session.to_dict())
        self.assertEqual(restored.output_plan, session.output_plan)
        removed = engine.apply_output_plan(session, [], {}, [], STAMP)
        self.assertEqual(removed.output_history[-1]["status"], "removed")

    def test_output_log_is_bounded(self):
        output = config.build_output(values())
        session = alarm_session()
        for i in range(120):
            session.alarms["rule"]["state"] = "active" if i % 2 else "acknowledged"
            session = engine.apply_output_plan(session, [output], {"rule": [output.id]}, [rules.live_rule()], STAMP)
        self.assertEqual(len(session.output_history), 100)


class OutputFlowTests(unittest.IsolatedAsyncioTestCase):
    def flow(self):
        flow = inputs.flows.AlarmManagementOptionsFlow()
        flow.hass = inputs.FakeHass()
        flow.hass.values["input_boolean.siren"] = "off"
        return flow

    async def test_add_multiple_outputs_then_finish(self):
        flow = self.flow()
        await flow.async_step_init()
        for kind in config.KINDS:
            await flow.async_step_output_add({"kind": kind, "entity_id": "input_boolean.siren"} if kind == "switch" else {"kind": kind})
            result = await flow.async_step_output_details(values(kind, name=kind))
            self.assertEqual(result["menu_options"], ["output_add", "output_finish"])
            self.assertEqual(flow.hass.entry.options, {})
        result = await flow.async_step_output_finish()
        outputs, _ = config.load_output_config(result["data"], [])
        self.assertEqual(len(outputs), len(config.KINDS))

    async def test_prefilled_target_name_and_edit_keeps_id(self):
        flow = self.flow()
        await flow.async_step_init()
        result = await flow.async_step_output_add({"kind": "switch", "entity_id": "input_boolean.siren"})
        self.assertEqual(next(key.default for key in result["data_schema"].schema if key.key == "name"), "Test Alarm")
        await flow.async_step_output_details(values())
        output = flow._outputs[0]
        await flow.async_step_output_edit({"output_id": output.id})
        result = await flow.async_step_output_edit_details(values(name="Neu", enabled=False))
        edited = config.load_output_config(result["data"], [])[0][0]
        self.assertEqual((edited.id, edited.name, edited.enabled), (output.id, "Neu", False))

    async def test_text_too_long_shows_field_error(self):
        flow = self.flow()
        await flow.async_step_init()
        await flow.async_step_output_add({"kind": "short_text"})
        result = await flow.async_step_output_details(values("short_text", alarm_value="x" * 15))
        self.assertEqual(result["errors"], {"alarm": "short_text_too_long"})

    async def test_rule_assignment_and_removal_guard(self):
        source = inputs.model.build_source(inputs.payload())
        flow = self.flow()
        flow.hass.entry.options = inputs.options_for([source])
        await flow.async_step_init()
        await flow.async_step_output_add({"kind": "switch", "entity_id": "input_boolean.siren"})
        await flow.async_step_output_details(values())
        output = flow._outputs[0]
        rule = flow._rules[0]
        await flow.async_step_rule_edit({"rule_id": rule.id})
        result = await flow.async_step_rule_edit_details({**rule.to_dict(), "output_ids": [output.id]})
        self.assertEqual(result["data"]["output_config"]["bindings"][rule.id], [output.id])
        await flow.async_step_output_remove({"output_id": output.id})
        result = await flow.async_step_output_confirm_remove({"confirm": True})
        self.assertEqual(result["errors"], {"base": "output_in_use"})
        await flow.async_step_rule_edit({"rule_id": rule.id})
        await flow.async_step_rule_edit_details({**rule.to_dict(), "output_ids": []})
        result = await flow.async_step_output_confirm_remove({"confirm": True})
        self.assertEqual(config.load_output_config(result["data"], flow._rules)[0], ())

    async def test_rule_removal_cleans_its_assignment(self):
        source = inputs.model.build_source(inputs.payload())
        flow = self.flow()
        flow.hass.entry.options = inputs.options_for([source])
        await flow.async_step_init()
        await flow.async_step_output_add({"kind": "long_text"})
        await flow.async_step_output_details(values("long_text"))
        rule = flow._rules[0]
        flow._bindings[rule.id] = [flow._outputs[0].id]
        await flow.async_step_rule_remove({"rule_id": rule.id})
        result = await flow.async_step_rule_confirm_remove({"confirm": True})
        self.assertEqual(result["data"]["output_config"]["bindings"], {})

    async def test_concurrent_output_change_not_overwritten(self):
        flow = self.flow()
        await flow.async_step_init()
        await flow.async_step_output_add({"kind": "long_text"})
        await flow.async_step_output_details(values("long_text"))
        flow.hass.entry.options["output_config"] = config.serialize_output_config([], {}, [])
        self.assertEqual((await flow.async_step_output_finish())["reason"], "configuration_changed")


class OutputMonitorTests(unittest.TestCase):
    def test_unknown_text_content_is_not_target_unavailability(self):
        for domain in ("input_text", "text"):
            with self.subTest(domain=domain):
                hass = inputs.FakeHass()
                entity_id = f"{domain}.test_display"
                hass.values[entity_id] = "unknown"
                output = config.build_output(values("short_text", entity_id=entity_id, alarm_value="{alarmtyp}"))
                monitor = inputs.output_monitor_module.OutputTargetMonitor(hass, [output], Mock())
                monitor.start()
                self.assertTrue(monitor.snapshot[output.id]["available"])
                self.assertEqual(plan(output, targets=monitor.snapshot)["value"], "Feuer")
                self.assertIsNone(plan(output, targets=monitor.snapshot)["error"])
                monitor.stop()

    def test_unavailable_or_missing_text_stays_blocked(self):
        hass = inputs.FakeHass()
        output = config.build_output(values("short_text", entity_id="input_text.test_display"))
        monitor = inputs.output_monitor_module.OutputTargetMonitor(hass, [output], Mock())
        monitor.start()
        for value in ("unavailable", None):
            hass.set_state(output.entity_id, value)
            self.assertFalse(monitor.snapshot[output.id]["available"])
            self.assertEqual(plan(output, targets=monitor.snapshot)["error"], "target_unavailable")
        monitor.stop()

    def test_restored_placeholder_text_stays_blocked(self):
        hass = inputs.FakeHass()
        output = config.build_output(values("short_text", entity_id="text.test_display"))
        hass.states = types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="unknown", attributes={"restored": True}))
        monitor = inputs.output_monitor_module.OutputTargetMonitor(hass, [output], Mock())
        monitor.start()
        self.assertFalse(monitor.snapshot[output.id]["available"])
        monitor.stop()

    def test_cleanup_removes_only_stale_own_output_status_entity(self):
        hass = inputs.FakeHass()
        output = config.build_output(values())
        old_status = hass.registry.add("sensor.removed_output", registry_id="status", config_entry_id="integration")
        old_status.unique_id = "integration_output_" + "a" * 32
        summary = hass.registry.add("sensor.plan", registry_id="summary", config_entry_id="integration")
        summary.unique_id = "integration_output_plan"
        target = hass.registry.add("input_boolean.siren", registry_id="target", config_entry_id="other")
        target.unique_id = "unrelated"
        inputs.output_monitor_module.cleanup_output_entities(hass, "integration", [output])
        self.assertIsNone(hass.registry.async_get(old_status.entity_id))
        self.assertIsNotNone(hass.registry.async_get(summary.entity_id))
        self.assertIsNotNone(hass.registry.async_get(target.entity_id))

    def test_target_rename_unavailability_and_cleanup(self):
        hass = inputs.FakeHass()
        registry = hass.registry.add("input_boolean.siren")
        hass.values[registry.entity_id] = "off"
        output = config.build_output(values(), registry_id=registry.id)
        notify = Mock()
        monitor = inputs.output_monitor_module.OutputTargetMonitor(hass, [output], notify)
        monitor.start()
        self.assertTrue(monitor.snapshot[output.id]["available"])
        hass.set_state(registry.entity_id, "unavailable")
        self.assertFalse(monitor.snapshot[output.id]["available"])
        registry.entity_id = "input_boolean.renamed"
        hass.values[registry.entity_id] = "off"
        hass.bus.emit("entity_registry_updated", {"entity_id": registry.entity_id})
        self.assertEqual(monitor.snapshot[output.id]["entity_id"], registry.entity_id)
        monitor.stop()
        self.assertEqual(hass.trackers, [])
        self.assertEqual(hass.bus.callbacks, [])


class OutputPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_setup_with_output_executes_absolute_command(self):
        source = inputs.model.build_source(inputs.payload())
        options = rules.model.ensure_rule_options(inputs.options_for([source]), [source])
        configured_rules = rules.model.load_rules(options, [source])
        output = config.build_output(values())
        options["output_config"] = config.serialize_output_config([output], {configured_rules[0].id: [output.id]}, configured_rules)
        hass = inputs.FakeHass(options)
        hass.entry.data = {"simulation": True}
        hass.values["input_boolean.siren"] = "off"
        hass.config_entries = types.SimpleNamespace(async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True),
                                                   async_update_entry=lambda entry, **kw: setattr(entry, "options", kw["options"]))
        hass.async_create_task, hass.loop = asyncio.create_task, asyncio.get_running_loop()
        async def real_call(domain, service, data, **kwargs):
            self.assertEqual(kwargs["target"], {"entity_id": "input_boolean.siren"})
            hass.set_state("input_boolean.siren", "on" if service == "turn_on" else "off")
        hass.services = types.SimpleNamespace(async_register=Mock(), async_remove=Mock(), has_service=lambda *args: True, async_call=AsyncMock(side_effect=real_call))
        self.assertTrue(await platforms.lifecycle.async_setup_entry(hass, hass.entry))
        manager = hass.entry.runtime_data
        hass.set_state(source.entity_id, "on")
        await manager.async_drain()
        self.assertEqual(manager.session.output_plan[output.id]["value"], "on")
        self.assertEqual(hass.values["input_boolean.siren"], "on")
        await platforms.lifecycle.async_unload_entry(hass, hass.entry)
        self.assertEqual(hass.trackers, [])
        self.assertEqual(hass.bus.callbacks, [])

    async def test_v04_store_upgrade_preserves_alarms_and_adds_empty_outputs(self):
        legacy = alarm_session().to_dict()
        legacy.pop("output_plan")
        legacy.pop("output_history")
        legacy.pop("executions")
        legacy.pop("delivery_history")
        legacy.pop("execution_mode")
        legacy["simulation"] = True
        upgraded = await old.storage.AlarmStore()._async_migrate_func(3, 1, legacy)
        self.assertEqual(upgraded["source_alarms"], legacy["source_alarms"])
        self.assertEqual(upgraded["output_plan"], {})

    async def test_manager_commits_alarm_and_output_together(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        manager.rules = (rules.live_rule(ids=("a",)),)
        output = config.build_output(values())
        manager.outputs = (output,)
        manager.output_bindings = {"rule": [output.id]}
        await manager.async_process_inputs([sessions.source()])
        self.assertEqual(manager.store.data["output_plan"][output.id]["value"], "on")
        self.assertEqual(manager.session.state, "active")
        await manager.async_action("acknowledge")
        self.assertEqual(manager.session.output_plan[output.id]["value"], "off")
        manager.store.fail = True
        before = deepcopy(manager.session)
        with self.assertRaises(old.FakeHomeAssistantError):
            await manager.async_action("trigger_test")
        self.assertEqual(manager.session, before)

    async def test_output_sensor_long_text_preview_and_error_display(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        manager.rules = (rules.live_rule(ids=("a",)),)
        output = config.build_output(values("long_text", alarm_value="x" * 500))
        manager.outputs, manager.output_bindings = (output,), {"rule": [output.id]}
        await manager.async_process_inputs([sessions.source()])
        entry = type("Entry", (), {"entry_id": "test", "runtime_data": manager})()
        sensor = platforms.sensor.OutputValueSensor(entry, output)
        self.assertEqual(len(sensor.native_value), 255)
        self.assertEqual(len(sensor.extra_state_attributes["value"]), 500)

    async def test_global_output_summary_exposes_errors_in_its_state(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        manager.rules = (rules.live_rule(ids=("a",)),)
        output = config.build_output(values("short_text", alarm_value="{regel}"))
        manager.outputs, manager.output_bindings = (output,), {"rule": [output.id]}
        snapshot = [sessions.source()]
        manager.rules = (sessions.rule_module.AlarmRule("rule", "Sehr langer Regelname", ("a",), "any", "fire", True),)
        await manager.async_process_inputs(snapshot)
        entry = type("Entry", (), {"entry_id": "test", "runtime_data": manager})()
        sensor = platforms.sensor.OutputSummarySensor(entry)
        self.assertEqual(sensor.native_value, "Ausgabefehler")
        self.assertEqual(sensor.extra_state_attributes["output_errors"], 1)
