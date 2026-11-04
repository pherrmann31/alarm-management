"""Rule model, three-valued evaluation, migration, UI and runtime regressions."""
from copy import deepcopy
import importlib
import unittest

import test_inputs as inputs
import test_session as sessions
import test_simulation as old

model = importlib.import_module(f"{inputs.NAME}.rule_config")
engine = importlib.import_module(f"{old.PACKAGE}.rule_engine")
STAMP = sessions.STAMP


def rule_data(source_ids, **updates):
    return {"name": "Testregel", "input_ids": list(source_ids), "mode": "any", "alarm_type": "fire", "enabled": True, **updates}


def live_rule(mode="any", enabled=True, ids=("a", "b")):
    return sessions.rule_module.AlarmRule("rule", "Testregel", tuple(ids), mode, "fire", enabled)


class RuleModelTests(unittest.TestCase):
    def setUp(self):
        self.sources = [inputs.model.build_source(inputs.payload()), inputs.model.build_source(inputs.payload(name="Keller", enabled=False))]
        self.ids = [source.id for source in self.sources]

    def test_default_generation_once_with_stable_ids_and_existing_types(self):
        options = inputs.options_for(self.sources)
        result = model.ensure_rule_options(options, self.sources)
        rules = model.load_rules(result, self.sources)
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].id, model.default_rule_id(self.ids[0]))
        self.assertTrue(rules[0].enabled)
        self.assertFalse(rules[1].enabled)
        self.assertEqual(model.ensure_rule_options(result, self.sources), result)
        self.assertNotIn("rule_config", options)

    def test_empty_rules_never_regenerated_including_after_new_input(self):
        options = {"rule_config": {"version": 1, "rules": []}}
        self.assertEqual(model.load_rules(model.ensure_rule_options(options, self.sources), self.sources), ())

    def test_roundtrip_and_edit_preserves_id(self):
        rule = model.build_rule(rule_data(self.ids), self.ids)
        edited = model.build_rule(rule_data(self.ids[:1], name="Geändert", enabled=False), self.ids, rule_id=rule.id)
        self.assertEqual(edited.id, rule.id)
        options = {"rule_config": model.serialize_rules([edited], self.sources)}
        self.assertEqual(model.load_rules(options, self.sources), (edited,))

    def test_invalid_rule_fields_rejected(self):
        for field, bad in (("name", " "), ("name", "x" * 81), ("input_ids", []),
                           ("input_ids", [self.ids[0], self.ids[0]]), ("input_ids", ["missing"]),
                           ("mode", "xor"), ("alarm_type", "other"), ("enabled", "true")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                model.build_rule(rule_data(self.ids, **{field: bad}), self.ids)

    def test_unknown_namespace_version_rejected_without_defaults(self):
        for raw in (None, {"version": 9, "rules": []}, {"version": True, "rules": []}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                model.ensure_rule_options({"rule_config": raw}, self.sources)

    def test_duplicate_ids_and_limit(self):
        rule = model.build_rule(rule_data(self.ids), self.ids)
        with self.assertRaises(ValueError):
            model.serialize_rules([rule, rule], self.sources)
        rules = [model.build_rule(rule_data(self.ids), self.ids) for _ in range(model.MAX_RULES)]
        self.assertEqual(len(model.load_rules({"rule_config": model.serialize_rules(rules, self.sources)}, self.sources)), model.MAX_RULES)
        with self.assertRaises(ValueError):
            model.serialize_rules(rules + [rule], self.sources)

    def test_dangling_references_are_rejected(self):
        rule = model.build_rule(rule_data(self.ids), self.ids)
        options = {"rule_config": model.serialize_rules([rule], self.sources)}
        with self.assertRaises(ValueError):
            model.load_rules(options, self.sources[:1])


class RuleEvaluationTests(unittest.TestCase):
    def test_or_and_truth_tables(self):
        table = {
            ("matching", "matching"): ("matching", "matching"),
            ("matching", "not_matching"): ("matching", "not_matching"),
            ("matching", "unknown"): ("matching", "unknown"),
            ("not_matching", "matching"): ("matching", "not_matching"),
            ("not_matching", "not_matching"): ("not_matching", "not_matching"),
            ("not_matching", "unknown"): ("unknown", "not_matching"),
            ("unknown", "matching"): ("matching", "unknown"),
            ("unknown", "not_matching"): ("unknown", "not_matching"),
            ("unknown", "unknown"): ("unknown", "unknown"),
        }
        for (a, b), expected in table.items():
            snapshot = [sessions.source("a", a), sessions.source("b", b)]
            with self.subTest(a=a, b=b):
                self.assertEqual(tuple(engine.evaluate_rules([live_rule(mode)], snapshot)[0]["status"] for mode in ("any", "all")), expected)

    def test_disabled_and_missing_input_never_complete_and(self):
        for status in ("disabled", "missing", "unknown", "unavailable", "blocked"):
            snapshot = [sessions.source(), sessions.source("b", status)]
            self.assertEqual(engine.evaluate_rules([live_rule("all")], snapshot)[0]["status"], "unknown")
        self.assertEqual(engine.evaluate_rules([live_rule("all")], [sessions.source()])[0]["status"], "unknown")

    def test_disabled_rule_and_explicit_empty_rules_do_not_trigger(self):
        self.assertEqual(engine.evaluate_rules([live_rule(enabled=False)], [sessions.source(), sessions.source("b")])[0]["status"], "disabled")
        self.assertEqual(engine.evaluate_rules([], [sessions.source()]), [])

    def test_only_matching_contributors_and_rule_alarm_type(self):
        result = engine.evaluate_rules([live_rule()], [sessions.source(), sessions.source("b", "not_matching")])[0]
        self.assertEqual([source["id"] for source in result["sources"]], ["a"])
        self.assertEqual(result["alarm_type"], "fire")
        self.assertEqual((result["rule_id"], result["rule_name"]), ("rule", "Testregel"))

    def test_unselected_inputs_are_ignored(self):
        result = engine.evaluate_rules([live_rule(ids=("a",))], [sessions.source("a", "not_matching"), sessions.source("b")])
        self.assertEqual(result[0]["status"], "not_matching")


class RuleSessionTests(unittest.TestCase):
    def test_multiple_rules_and_recorded_rule_names(self):
        rules = [live_rule(ids=("a",)), sessions.rule_module.AlarmRule("second", "Zweite Regel", ("b",), "any", "house", True)]
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), engine.evaluate_rules(rules, [sessions.source(), sessions.source("b")]), STAMP)
        self.assertEqual(len(state.alarms), 2)
        self.assertIn("Testregel", state.history[0]["message"])
        self.assertEqual(state.alarms["rule"]["sources"][0]["name"], "Quelle a")

    def test_additional_or_source_reactivates_acknowledged_alarm(self):
        snapshot = [sessions.source(), sessions.source("b", "not_matching")]
        evaluations = engine.evaluate_rules([live_rule()], snapshot)
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), evaluations, STAMP)
        state, _ = sessions.session_module.apply_action(state, "acknowledge", evaluations, STAMP)
        evaluations = engine.evaluate_rules([live_rule()], [sessions.source(), sessions.source("b")])
        state = sessions.session_module.reconcile(state, evaluations, STAMP)
        self.assertEqual(state.state, "active")
        self.assertEqual(len(state.alarms["rule"]["sources"]), 2)
        self.assertEqual(state.history[-1]["event"], "rule_source_added")

    def test_same_or_source_new_edge_reactivates_while_other_stays_on(self):
        evaluations = engine.evaluate_rules([live_rule()], [sessions.source(), sessions.source("b")])
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), evaluations, STAMP)
        state, _ = sessions.session_module.apply_action(state, "acknowledge", evaluations, STAMP)
        state = sessions.session_module.reconcile(state, engine.evaluate_rules([live_rule()], [sessions.source(), sessions.source("b", "not_matching")]), STAMP)
        state = sessions.session_module.reconcile(state, evaluations, STAMP)
        self.assertEqual(state.state, "active")
        self.assertEqual(len(state.alarms["rule"]["sources"]), 2)

    def test_and_reset_uses_rule_truth_not_individual_matching_input(self):
        rules = [live_rule("all")]
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), engine.evaluate_rules(rules, [sessions.source(), sessions.source("b")]), STAMP)
        evaluations = engine.evaluate_rules(rules, [sessions.source(), sessions.source("b", "not_matching")])
        state, accepted = sessions.session_module.apply_action(state, "reset", evaluations, STAMP)
        self.assertTrue(accepted)
        self.assertEqual(state.state, "idle")

    def test_or_source_recovery_does_not_fake_a_new_edge(self):
        initial = engine.evaluate_rules([live_rule()], [sessions.source(), sessions.source("b")])
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), initial, STAMP)
        state, _ = sessions.session_module.apply_action(state, "acknowledge", initial, STAMP)
        state = sessions.session_module.reconcile(state, engine.evaluate_rules([live_rule()], [sessions.source(), sessions.source("b", "unavailable")]), STAMP)
        state = sessions.session_module.reconcile(state, initial, STAMP)
        self.assertEqual(state.state, "acknowledged")
        self.assertEqual(len(state.history), 2)

    def test_unknown_rule_blocks_reset_but_disabled_rule_allows_it(self):
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), engine.evaluate_rules([live_rule("all")], [sessions.source(), sessions.source("b")]), STAMP)
        unknown = engine.evaluate_rules([live_rule("all")], [sessions.source(), sessions.source("b", "unavailable")])
        self.assertFalse(sessions.session_module.apply_action(state, "reset", unknown, STAMP)[1])
        disabled = engine.evaluate_rules([live_rule("all", enabled=False)], [sessions.source(), sessions.source("b")])
        self.assertTrue(sessions.session_module.apply_action(state, "reset", disabled, STAMP)[1])

    def test_rule_edit_with_new_references_stays_restorable(self):
        state = sessions.session_module.reconcile(sessions.session_module.AlarmSession(), engine.evaluate_rules([live_rule(ids=("a",))], [sessions.source()]), STAMP)
        state = sessions.session_module.reconcile(state, engine.evaluate_rules([live_rule(ids=("b",))], [sessions.source("b")]), STAMP)
        self.assertEqual(sessions.session_module.AlarmSession.from_dict(state.to_dict()), state)
        self.assertEqual(state.alarms["rule"]["input_ids"], ["a", "b"])


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_v03_alarm_maps_to_same_default_rule_without_retrigger(self):
        source = inputs.model.build_source(inputs.payload())
        record = {"id": source.id, "name": source.name, "entity_id": source.entity_id, "alarm_type": source.alarm_type,
                  "area_id": "hall", "area_name": "Flur", "state": "acknowledged", "triggered_at": STAMP, "condition_cleared": False}
        legacy = {"simulation": True, "alarm": old.engine.AlarmState(test_count=7).to_dict(), "source_alarms": {source.id: record}, "history": []}
        migrated = await old.storage.AlarmStore()._async_migrate_func(2, 1, legacy)
        state = sessions.session_module.AlarmSession.from_dict(migrated)
        options = model.ensure_rule_options({}, [source])
        rules = model.load_rules(options, [source])
        snapshot = [{**record, "status": "matching", "enabled": True}]
        state = sessions.session_module.reconcile(state, engine.evaluate_rules(rules, snapshot), STAMP)
        self.assertEqual(state.state, "acknowledged")
        self.assertEqual(state.history, [])
        self.assertEqual(state.manual.test_count, 7)
        self.assertIn(rules[0].id, state.alarms)

    async def test_invalid_v2_store_is_not_replaced(self):
        with self.assertRaises(ValueError):
            await old.storage.AlarmStore()._async_migrate_func(2, 1, {"simulation": True})


class RuleFlowTests(unittest.IsolatedAsyncioTestCase):
    def flow(self, source_count=2, *, empty=False):
        sources = [inputs.model.build_source(inputs.payload(name=f"Eingang {i+1}")) for i in range(source_count)]
        options = inputs.options_for(sources)
        if empty:
            options["rule_config"] = {"version": 1, "rules": []}
        flow = inputs.flows.AlarmManagementOptionsFlow()
        flow.hass = inputs.FakeHass(options)
        return flow, sources

    async def test_add_several_rules_then_finish(self):
        flow, sources = self.flow(empty=True)
        await flow.async_step_init()
        for name in ("Erste Regel", "Zweite Regel"):
            result = await flow.async_step_rule_add(rule_data([source.id for source in sources], name=name, mode="all"))
            self.assertEqual(result["menu_options"], ["rule_add", "rule_finish"])
            self.assertEqual(flow.hass.entry.options["rule_config"]["rules"], [])
        result = await flow.async_step_rule_finish()
        rules = model.load_rules(result["data"], sources)
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].mode, "all")

    async def test_multiselect_is_checkbox_list(self):
        flow, _ = self.flow()
        await flow.async_step_init()
        result = await flow.async_step_rule_add()
        group = next(value for field, value in result["data_schema"].schema.items() if field.key == "when")
        selector = next(value for field, value in group.schema.schema.items() if field.key == "input_ids")
        self.assertTrue(selector.config["multiple"])
        self.assertEqual(selector.config["mode"], "list")

    async def test_edit_and_disable_keeps_rule_id(self):
        flow, sources = self.flow()
        await flow.async_step_init()
        original = flow._rules[0]
        await flow.async_step_rule_edit({"rule_id": original.id})
        result = await flow.async_step_rule_edit_details(rule_data([source.id for source in sources], enabled=False, mode="all"))
        rule = model.load_rules(result["data"], sources)[0]
        self.assertEqual((rule.id, rule.enabled, rule.mode), (original.id, False, "all"))

    async def test_rule_removal_requires_confirmation(self):
        flow, sources = self.flow()
        await flow.async_step_init()
        await flow.async_step_rule_remove({"rule_id": flow._rules[0].id})
        self.assertEqual((await flow.async_step_rule_confirm_remove({"confirm": False}))["errors"], {"base": "confirmation_required"})
        result = await flow.async_step_rule_confirm_remove({"confirm": True})
        self.assertEqual(len(model.load_rules(result["data"], sources)), 1)

    async def test_referenced_input_cannot_be_removed(self):
        flow, sources = self.flow()
        await flow.async_step_init()
        await flow.async_step_remove({"source_id": sources[0].id})
        result = await flow.async_step_confirm_remove({"confirm": True})
        self.assertEqual(result["errors"], {"base": "input_in_use"})
        self.assertEqual(len(inputs.model.load_sources(flow.hass.entry.options)), 2)

    async def test_new_input_gets_no_hidden_rule(self):
        flow, sources = self.flow()
        await flow.async_step_init()
        await flow.async_step_add({"entity_id": "input_boolean.test_alarm"})
        await flow.async_step_add_details(inputs.payload())
        result = await flow.async_step_finish()
        new_sources = inputs.model.load_sources(result["data"])
        self.assertEqual(len(new_sources), 3)
        self.assertEqual(len(model.load_rules(result["data"], new_sources)), 2)

    async def test_missing_selection_returns_helpful_error(self):
        flow, _ = self.flow()
        await flow.async_step_init()
        result = await flow.async_step_rule_add(rule_data([]))
        self.assertEqual(result["errors"], {"when": "choose_inputs"})

    async def test_rule_overview_is_read_only_and_lists_logic(self):
        flow, _ = self.flow()
        await flow.async_step_init()
        result = await flow.async_step_rule_overview()
        self.assertIn("Einzelregel", result["description_placeholders"]["rules"])
        self.assertEqual((await flow.async_step_rule_overview({}))["step_id"], "rules")
        self.assertNotIn("rule_config", flow.hass.entry.options)

    async def test_concurrent_rule_change_is_not_overwritten(self):
        flow, sources = self.flow(empty=True)
        await flow.async_step_init()
        await flow.async_step_rule_add(rule_data([source.id for source in sources]))
        flow.hass.entry.options["rule_config"] = {"version": 1, "rules": [model.build_rule(rule_data([sources[0].id]), {source.id for source in sources}).to_dict()]}
        self.assertEqual((await flow.async_step_rule_finish())["reason"], "configuration_changed")

    async def test_empty_sources_can_prepare_group_rule(self):
        flow, _ = self.flow(source_count=0)
        await flow.async_step_init()
        self.assertIn("rule_add", (await flow.async_step_rules())["menu_options"])
        self.assertEqual((await flow.async_step_rule_add())["type"], "form")


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_action_recovers_unavailable_alarm_display(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        manager.input_error = True
        await manager.async_action("trigger_test")
        self.assertFalse(manager.input_error)
        self.assertEqual(manager.session.state, "active")

    async def test_unreferenced_input_does_not_activate_alarm(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        await manager.async_process_inputs([sessions.source()])
        self.assertEqual(manager.session.state, "idle")
        manager.rules = (live_rule(ids=("a",)),)
        await manager.async_process_inputs([sessions.source()])
        self.assertEqual(manager.session.state, "active")

    async def test_disabled_rule_allows_reset_of_latched_alarm(self):
        manager = old.manager_module.AlarmManager(object(), "test")
        await manager.async_load()
        manager.running = True
        manager.rules = (live_rule(ids=("a",)),)
        await manager.async_process_inputs([sessions.source()])
        manager.rules = (live_rule(ids=("a",), enabled=False),)
        await manager.async_action("reset")
        self.assertEqual(manager.session.state, "idle")
