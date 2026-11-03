"""HA setup and options for inputs, rules and outputs."""

from typing import Any
from copy import deepcopy

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import EntitySelector, SelectSelector, TextSelector

from .const import ALARM_TYPES, DOMAIN, INPUT_CONFIG_KEY, MAX_INPUTS, MAX_RULES, RULE_CONFIG_KEY
from .input_config import InputValidationError, build_source, load_sources, serialize_sources
from .input_monitor import resolve_entity_id
from .rule_config import build_rule, ensure_rule_options, load_rules, serialize_rules
from .const import MAX_OUTPUTS, OUTPUT_CONFIG_KEY
from .output_config import DOMAINS, KINDS, build_output, ensure_output_options, load_output_config, serialize_output_config
from .presentation import (DELIVERY_LABELS, KIND_LABELS, OUTPUT_SECTIONS, RULE_SECTIONS, STATUS_LABELS,
                           flatten_sections, markdown_text, runtime_summary, section_errors, selection_labels)


class AlarmManagementConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AlarmManagementOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            if user_input.get("confirm_live") is True:
                return self.async_create_entry(
                    title="Alarm Management", data={"execution_mode": "live"}
                )
            errors["base"] = "live_required"
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required("confirm_live", default=False): bool}
            ),
            errors=errors,
        )


class AlarmManagementOptionsFlow(OptionsFlowWithReload):
    """One operation per dialog; HA persists options and reloads on changes."""

    def __init__(self) -> None:
        self._sources = None
        self._original_config = None
        self._selected_id = None
        self._chosen_entity = None
        self._last_added = ""
        self._rules = None
        self._original_rules = None
        self._selected_rule_id = None
        self._outputs = None
        self._bindings = None
        self._original_outputs = None
        self._pending_output = None
        self._selected_output_id = None
        self._notification_mode = False

    def _ensure_sources(self) -> None:
        if self._sources is None:
            self._sources = list(load_sources(dict(self.config_entry.options)))
            self._original_config = deepcopy(self.config_entry.options.get(INPUT_CONFIG_KEY))
            self._original_rules = deepcopy(self.config_entry.options.get(RULE_CONFIG_KEY))
            options = ensure_rule_options(dict(self.config_entry.options), self._sources)
            self._rules = list(load_rules(options, self._sources))
            self._original_outputs = deepcopy(self.config_entry.options.get(OUTPUT_CONFIG_KEY))
            options = ensure_output_options(options, self._rules)
            outputs, self._bindings = load_output_config(options, self._rules)
            self._outputs = list(outputs)

    async def async_step_init(self, user_input=None):
        try:
            self._ensure_sources()
        except ValueError:
            return self.async_abort(reason="invalid_configuration")
        return self.async_show_menu(
            step_id="init", menu_options=["status", "inputs", "rules", "outputs", "notifications"],
            description_placeholders={"inputs": str(len(self._sources)), "rules": str(len(self._rules)),
                                      "outputs": str(sum(not item.notification for item in self._outputs)),
                                      "notifications":str(sum(bool(item.notification) for item in self._outputs)),
                                      **runtime_summary(getattr(self.config_entry, "runtime_data", None))},
        )

    async def async_step_status(self, user_input=None):
        self._ensure_sources()
        if user_input is not None:
            return await self.async_step_init()
        manager = getattr(self.config_entry, "runtime_data", None)
        summary = runtime_summary(manager)
        session = getattr(manager, "session", None)
        alarms = list(session.alarms.values()) if session else []
        rules = ", ".join(markdown_text(item["rule_name"]) for item in alarms) or "Keine"
        sources = ", ".join(dict.fromkeys(markdown_text(source["name"]) for alarm in alarms for source in alarm["sources"])) or "Keine"
        return self.async_show_form(step_id="status", data_schema=probatio.Schema({}), last_step=False,
                                    description_placeholders={**summary, "rules": rules, "sources": sources})

    async def async_step_inputs(self, user_input=None):
        self._ensure_sources()
        choices = []
        if len(self._sources) < MAX_INPUTS:
            choices.append("add")
        if self._sources:
            choices += ["edit", "remove"]
        choices += ["overview", "init"]
        return self.async_show_menu(
            step_id="inputs", menu_options=choices,
            description_placeholders={"count": str(len(self._sources)), "limit": str(MAX_INPUTS)},
        )

    def _finish(self, sources, rules=None, outputs=None):
        # Do not overwrite a simultaneous configuration change.
        current = dict(self.config_entry.options)
        if (current.get(INPUT_CONFIG_KEY) != self._original_config or
                current.get(RULE_CONFIG_KEY) != self._original_rules or
                current.get(OUTPUT_CONFIG_KEY) != self._original_outputs):
            return self.async_abort(reason="configuration_changed")
        current[INPUT_CONFIG_KEY] = serialize_sources(sources)
        rules = self._rules if rules is None else rules
        current[RULE_CONFIG_KEY] = serialize_rules(rules, sources)
        bindings = {rule_id: assigned for rule_id, assigned in self._bindings.items() if rule_id in {rule.id for rule in rules}}
        current[OUTPUT_CONFIG_KEY] = serialize_output_config(self._outputs if outputs is None else outputs, bindings, rules)
        return self.async_create_entry(title="", data=current)

    def _source_choices(self):
        labels = selection_labels(self._sources)
        return SelectSelector({"options": [
            {"value": source.id, "label": labels[source.id]}
            for source in self._sources
        ]})

    def _defaults(self, source=None):
        if source is None:
            entity_id = self._chosen_entity
            state = self.hass.states.get(entity_id) if entity_id else None
            entry = er.async_get(self.hass).async_get(entity_id) if entity_id else None
            name = ((getattr(state, "attributes", {}) or {}).get("friendly_name") or
                    getattr(entry, "name", None) or getattr(entry, "original_name", None) or
                    (entity_id.split(".", 1)[-1].replace("_", " ") if entity_id else ""))
            return {"name": name[:80], "entity_id": entity_id, "trigger_state": "on", "alarm_type": "house", "enabled": True}
        values = source.to_dict()
        values["entity_id"] = resolve_entity_id(source, er.async_get(self.hass)) or source.entity_id
        return values

    def _input_schema(self, values):
        registry = er.async_get(self.hass)
        excluded = [item.entity_id for item in er.async_entries_for_config_entry(registry, self.config_entry.entry_id)]
        entity_field = (probatio.Required("entity_id", default=values["entity_id"])
                        if values.get("entity_id") else probatio.Required("entity_id"))
        return probatio.Schema({
            probatio.Required("name", default=values["name"]): str,
            entity_field: EntitySelector({"exclude_entities": excluded}),
            probatio.Required("trigger_state", default=values["trigger_state"]): str,
            probatio.Required("enabled", default=values["enabled"]): bool,
        })

    async def _input_form(self, step_id, user_input, source=None):
        values = self._defaults(source)
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input.setdefault("alarm_type", values["alarm_type"])
            values.update(user_input)
            try:
                candidate = build_source(user_input, source_id=source.id if source else None)
                registry_entry = er.async_get(self.hass).async_get(candidate.entity_id)
                if registry_entry and registry_entry.config_entry_id == self.config_entry.entry_id:
                    raise InputValidationError("entity_id", "own_entity")
                if registry_entry is None and self.hass.states.get(candidate.entity_id) is None:
                    raise InputValidationError("entity_id", "entity_not_found")
                candidate = build_source(user_input, source_id=candidate.id,
                                         registry_id=registry_entry.id if registry_entry else None)
                sources = [candidate if old.id == candidate.id else old for old in self._sources]
                if source is None:
                    sources.append(candidate)
                    self._sources = sources
                    self._last_added = candidate.name
                    return await self.async_step_after_add()
                return self._finish(sources)
            except InputValidationError as err:
                errors[err.field] = err.key
        return self.async_show_form(step_id=step_id, data_schema=self._input_schema(values), errors=errors)

    async def async_step_add(self, user_input=None):
        self._ensure_sources()
        if len(self._sources) >= MAX_INPUTS:
            return self.async_abort(reason="max_inputs")
        errors = {}
        if user_input is not None:
            entity_id = user_input["entity_id"]
            entry = er.async_get(self.hass).async_get(entity_id)
            if entry and entry.config_entry_id == self.config_entry.entry_id:
                errors["entity_id"] = "own_entity"
            elif entry is None and self.hass.states.get(entity_id) is None:
                errors["entity_id"] = "entity_not_found"
            else:
                self._chosen_entity = entity_id
                return await self.async_step_add_details()
        registry = er.async_get(self.hass)
        excluded = [item.entity_id for item in er.async_entries_for_config_entry(registry, self.config_entry.entry_id)]
        return self.async_show_form(step_id="add", errors=errors, data_schema=probatio.Schema({
            probatio.Required("entity_id"): EntitySelector({"exclude_entities": excluded}),
        }))

    async def async_step_add_details(self, user_input=None):
        if self._chosen_entity is None:
            return self.async_abort(reason="configuration_changed")
        return await self._input_form("add_details", user_input)

    async def async_step_after_add(self, user_input=None):
        choices = ["add", "finish"] if len(self._sources) < MAX_INPUTS else ["finish"]
        return self.async_show_menu(
            step_id="after_add", menu_options=choices,
            description_placeholders={"name": self._last_added, "count": str(len(self._sources)), "limit": str(MAX_INPUTS)},
        )

    async def async_step_finish(self, user_input=None):
        return self._finish(self._sources)

    async def async_step_edit(self, user_input=None):
        self._ensure_sources()
        if not self._sources:
            return self.async_abort(reason="no_inputs")
        if user_input is not None:
            self._selected_id = user_input["source_id"]
            return await self.async_step_edit_input()
        return self.async_show_form(step_id="edit", data_schema=probatio.Schema({
            probatio.Required("source_id"): self._source_choices(),
        }))

    async def async_step_edit_input(self, user_input=None):
        source = next((item for item in self._sources if item.id == self._selected_id), None)
        if source is None:
            return self.async_abort(reason="configuration_changed")
        return await self._input_form("edit_input", user_input, source)

    async def async_step_remove(self, user_input=None):
        self._ensure_sources()
        if not self._sources:
            return self.async_abort(reason="no_inputs")
        if user_input is not None:
            self._selected_id = user_input["source_id"]
            return await self.async_step_confirm_remove()
        return self.async_show_form(step_id="remove", data_schema=probatio.Schema({
            probatio.Required("source_id"): self._source_choices(),
        }))

    async def async_step_confirm_remove(self, user_input=None):
        source = next((item for item in self._sources if item.id == self._selected_id), None)
        if source is None:
            return self.async_abort(reason="configuration_changed")
        errors = {}
        if user_input is not None:
            if user_input.get("confirm") is True:
                if any(source.id in rule.input_ids for rule in self._rules):
                    errors["base"] = "input_in_use"
                else:
                    return self._finish([item for item in self._sources if item.id != source.id])
            else:
                errors["base"] = "confirmation_required"
        return self.async_show_form(
            step_id="confirm_remove", errors=errors,
            description_placeholders={"name": source.name,
                                      "rules": ", ".join(rule.name for rule in self._rules if source.id in rule.input_ids) or "—"},
            data_schema=probatio.Schema({probatio.Required("confirm", default=False): bool}),
        )

    async def async_step_overview(self, user_input=None):
        self._ensure_sources()
        if user_input is not None:
            # Closing an overview does not change options or cause a reload.
            return await self.async_step_inputs()
        registry = er.async_get(self.hass)
        lines = []
        for item in self._sources:
            rules = ", ".join(rule.name for rule in self._rules if item.id in rule.input_ids) or "Noch keiner Regel zugeordnet"
            manager = getattr(self.config_entry, "runtime_data", None)
            live = next((value for value in manager.inputs.snapshot if value["id"] == item.id), None) if manager else None
            state = STATUS_LABELS.get(live["status"], "—") if live else "—"
            area = live.get("area_name") or "Ohne Bereich" if live else "Ohne Bereich"
            lines.append(f"**{markdown_text(item.name)}** · {'Aktiviert' if item.enabled else 'Deaktiviert'}\n\n"
                         f"Zustand: {state} · Bereich: {markdown_text(area)}\n\n"
                         f"Auslösung bei: `{markdown_text(item.trigger_state)}`\n\nRegeln: {markdown_text(rules)}")
        return self.async_show_form(
            step_id="overview", data_schema=probatio.Schema({}), last_step=False,
            description_placeholders={"count": str(len(self._sources)), "limit": str(MAX_INPUTS),
                                      "sources": "\n\n---\n\n".join(lines) or "Noch keine Eingänge. Über Hinzufügen eine HA-Entität auswählen."},
        )

    async def async_step_rules(self, user_input=None):
        self._ensure_sources()
        choices = []
        if self._sources and len(self._rules) < MAX_RULES:
            choices.append("rule_add")
        if self._rules:
            choices += ["rule_edit", "rule_remove"]
        choices += ["rule_overview", "init"]
        return self.async_show_menu(step_id="rules", menu_options=choices,
                                    description_placeholders={"count": str(len(self._rules)), "limit": str(MAX_RULES)})

    def _rule_choices(self):
        return SelectSelector({"options": [
            {"value": rule.id, "label": rule.name + (' (deaktiviert)' if not rule.enabled else '')} for rule in self._rules
        ], "mode": "dropdown"})

    def _rule_schema(self, values):
        flat = {
            probatio.Required("name", default=values["name"]): str,
            probatio.Required("input_ids", default=values["input_ids"]): SelectSelector({
                "options": [{"value": item.id, "label": selection_labels(self._sources)[item.id]} for item in self._sources],
                "multiple": True, "mode": "list",
            }),
            probatio.Required("mode", default=values["mode"]): SelectSelector({
                "options": ["any", "all"], "translation_key": "rule_mode", "mode": "list",
            }),
            probatio.Required("alarm_type", default=values["alarm_type"]): SelectSelector({
                "options": list(ALARM_TYPES), "translation_key": "alarm_type", "mode": "list",
            }),
            probatio.Required("enabled", default=values["enabled"]): bool,
        }
        actuators=[item for item in self._outputs if not item.notification]
        notifications=[item for item in self._outputs if item.notification]
        if actuators:
            flat[probatio.Optional("output_ids", default=values.get("output_ids", []))] = SelectSelector({
                "options": [{"value": item.id, "label": item.name} for item in actuators], "multiple": True, "mode": "list"})
        if notifications:
            flat[probatio.Optional('notification_ids',default=values.get('notification_ids',[]))] = SelectSelector({
                'options':[{'value':item.id,'label':item.name} for item in notifications],'multiple':True,'mode':'list'})
        schema = {key: value for key, value in flat.items() if str(getattr(key, "schema", getattr(key, "key", key))) in ("name", "enabled")}
        for name, fields in RULE_SECTIONS.items():
            grouped = {key: value for key, value in flat.items() if str(getattr(key, "schema", getattr(key, "key", key))) in fields}
            schema[probatio.Required(name)] = section(probatio.Schema(grouped), {"collapsed": False})
        return probatio.Schema(schema)

    async def _rule_form(self, step_id, user_input, rule=None):
        values = rule.to_dict() if rule else {"name": "", "input_ids": [], "mode": "any", "alarm_type": "house", "enabled": True}
        assigned_ids=self._bindings.get(rule.id,[]) if rule else []
        values['output_ids']=[item.id for item in self._outputs if not item.notification and item.id in assigned_ids]
        values['notification_ids']=[item.id for item in self._outputs if item.notification and item.id in assigned_ids]
        errors = {}
        if user_input is not None:
            try:
                user_input = flatten_sections(user_input, RULE_SECTIONS)
                values.update(user_input)
                candidate = build_rule(user_input, {item.id for item in self._sources}, rule_id=rule.id if rule else None)
                assigned = user_input.get("output_ids", [])
                notifications=user_input.get('notification_ids',[])
                if not isinstance(notifications,list) or not all(isinstance(item,str) for item in notifications):
                    raise InputValidationError('notification_ids','invalid_output_assignment')
                if len(set(notifications))!=len(notifications) or not set(notifications)<={item.id for item in self._outputs if item.notification}:
                    raise InputValidationError('notification_ids','invalid_output_assignment')
                if (not isinstance(assigned, list) or not all(isinstance(item, str) for item in assigned)
                        or len(set(assigned)) != len(assigned) or not set(assigned) <= {item.id for item in self._outputs if not item.notification}):
                    raise InputValidationError("output_ids", "invalid_output_assignment")
                assigned=assigned+notifications
                if assigned:
                    self._bindings[candidate.id] = list(assigned)
                else:
                    self._bindings.pop(candidate.id, None)
                rules = [candidate if item.id == candidate.id else item for item in self._rules]
                if rule is None:
                    rules.append(candidate)
                    self._rules = rules
                    self._last_added = candidate.name
                    return await self.async_step_rule_after_add()
                return self._finish(self._sources, rules)
            except InputValidationError as err:
                errors[err.field] = err.key
        return self.async_show_form(step_id=step_id, data_schema=self._rule_schema(values), errors=section_errors(errors, RULE_SECTIONS))

    async def async_step_rule_add(self, user_input=None):
        self._ensure_sources()
        if not self._sources:
            return self.async_abort(reason="no_inputs_for_rules")
        if len(self._rules) >= MAX_RULES:
            return self.async_abort(reason="max_rules")
        return await self._rule_form("rule_add", user_input)

    async def async_step_rule_after_add(self, user_input=None):
        choices = ["rule_add", "rule_finish"] if len(self._rules) < MAX_RULES else ["rule_finish"]
        return self.async_show_menu(step_id="rule_after_add", menu_options=choices,
                                    description_placeholders={"name": self._last_added, "count": str(len(self._rules))})

    async def async_step_rule_finish(self, user_input=None):
        return self._finish(self._sources)

    async def async_step_rule_edit(self, user_input=None):
        self._ensure_sources()
        if not self._rules:
            return self.async_abort(reason="no_rules")
        if user_input is not None:
            self._selected_rule_id = user_input["rule_id"]
            return await self.async_step_rule_edit_details()
        return self.async_show_form(step_id="rule_edit", data_schema=probatio.Schema({
            probatio.Required("rule_id"): self._rule_choices(),
        }))

    async def async_step_rule_edit_details(self, user_input=None):
        rule = next((item for item in self._rules if item.id == self._selected_rule_id), None)
        if rule is None:
            return self.async_abort(reason="configuration_changed")
        return await self._rule_form("rule_edit_details", user_input, rule)

    async def async_step_rule_remove(self, user_input=None):
        self._ensure_sources()
        if not self._rules:
            return self.async_abort(reason="no_rules")
        if user_input is not None:
            self._selected_rule_id = user_input["rule_id"]
            return await self.async_step_rule_confirm_remove()
        return self.async_show_form(step_id="rule_remove", data_schema=probatio.Schema({
            probatio.Required("rule_id"): self._rule_choices(),
        }))

    async def async_step_rule_confirm_remove(self, user_input=None):
        rule = next((item for item in self._rules if item.id == self._selected_rule_id), None)
        if rule is None:
            return self.async_abort(reason="configuration_changed")
        errors = {}
        if user_input is not None:
            if user_input.get("confirm") is True:
                return self._finish(self._sources, [item for item in self._rules if item.id != rule.id])
            errors["base"] = "confirmation_required"
        return self.async_show_form(step_id="rule_confirm_remove", errors=errors,
                                    description_placeholders={"name": rule.name},
                                    data_schema=probatio.Schema({probatio.Required("confirm", default=False): bool}))

    async def async_step_rule_overview(self, user_input=None):
        self._ensure_sources()
        if user_input is not None:
            return await self.async_step_rules()
        names = {item.id: item.name for item in self._sources}
        types = {"house": "Hausalarm", "fire": "Feuer", "intrusion": "Einbruch"}
        lines = []
        for rule in self._rules:
            condition='Mindestens ein Eingang' if rule.mode=='any' else 'Alle Eingänge gleichzeitig'
            inputs=', '.join(markdown_text(names[input_id]) for input_id in rule.input_ids)
            state = "Aktiviert" if rule.enabled else "Deaktiviert"
            lines.append(f"**{markdown_text(rule.name)}** · {state}\n\n**Bedingung:** {condition}\n\n**Eingänge:** {inputs}\n\n**Dann:** {types[rule.alarm_type]}")
            assigned = ", ".join(item.name for item in self._outputs if not item.notification and item.id in self._bindings.get(rule.id, [])) or "Keine Ausgänge"
            lines[-1] += f"\n\n**Ausgänge:** {markdown_text(assigned)}"
            notifications=', '.join(item.name for item in self._outputs if item.notification and item.id in self._bindings.get(rule.id,[])) or 'Keine Benachrichtigungen'
            lines[-1] += f'\n\n**Benachrichtigungen:** {markdown_text(notifications)}'
        return self.async_show_form(step_id="rule_overview", data_schema=probatio.Schema({}), last_step=False,
                                    description_placeholders={"count": str(len(self._rules)), "rules": "\n\n---\n\n".join(lines) or "Noch keine Regeln. Zuerst Eingänge anlegen, dann eine Regel hinzufügen."})

    async def async_step_outputs(self, user_input=None):
        self._notification_mode=False
        return self._show_output_menu()

    async def async_step_notifications(self, user_input=None):
        self._notification_mode=True
        return self._show_output_menu()

    def _visible_outputs(self):
        return [item for item in self._outputs if bool(item.notification)==self._notification_mode]

    def _output_step(self, suffix):
        return ('notification_' if self._notification_mode else 'output_')+suffix

    def _show_output_menu(self):
        self._ensure_sources()
        choices = [self._output_step('add')] if len(self._outputs) < MAX_OUTPUTS else []
        if self._visible_outputs():
            choices += [self._output_step('edit'),self._output_step('remove')]
        choices += [self._output_step('overview'), 'init']
        return self.async_show_menu(step_id='notifications' if self._notification_mode else 'outputs',menu_options=choices,
                                    description_placeholders={"count": str(len(self._visible_outputs())), "limit": str(MAX_OUTPUTS)})

    def _output_choices(self):
        return SelectSelector({"options": [{"value": item.id, "label": f"{item.name} · {KIND_LABELS[item.kind]} · {'aktiviert' if item.enabled else 'deaktiviert'}"} for item in self._visible_outputs()], "mode": "dropdown"})

    def _validate_output_target(self, data, output_id=None):
        candidate = build_output(data, output_id=output_id)
        entry = er.async_get(self.hass).async_get(candidate.entity_id) if candidate.entity_id else None
        if entry and entry.config_entry_id == self.config_entry.entry_id:
            raise InputValidationError("entity_id", "own_entity")
        if candidate.entity_id and entry is None and self.hass.states.get(candidate.entity_id) is None:
            raise InputValidationError("entity_id", "entity_not_found")
        candidate = build_output(data, output_id=candidate.id, registry_id=entry.id if entry else None)
        for existing in self._outputs:
            if existing.id != candidate.id and candidate.entity_id:
                same_registry = candidate.entity_registry_id and existing.entity_registry_id == candidate.entity_registry_id
                if same_registry or existing.entity_id == candidate.entity_id:
                    raise InputValidationError("entity_id", "duplicate_output_target")
        return candidate

    def _output_owned(self, output_id):
        manager = getattr(self.config_entry, "runtime_data", None)
        session = getattr(manager, "session", None)
        return bool(session and session.executions.get(output_id, {}).get("owned"))

    def _output_defaults(self, kind, entity_id):
        state = self.hass.states.get(entity_id) if entity_id else None
        entry = er.async_get(self.hass).async_get(entity_id) if entity_id else None
        name = ((getattr(state, "attributes", {}) or {}).get("friendly_name") or getattr(entry, "name", None)
                or getattr(entry, "original_name", None) or KIND_LABELS[kind])
        values = {"name": name[:80], "kind": kind, "entity_id": entity_id, "encoding": "latin-1", "enabled": True,
                "alarm_value": "on" if kind == "switch" else "{alarmtyp}" if kind == "short_text" else "{alarmtyp}: {regel} – {quelle} ({bereich})",
                "acknowledged_value": "off" if kind == "switch" else "Quittiert" if kind == "short_text" else "Quittiert: {regel}",
                "idle_value": "off" if kind == "switch" else "Bereit"}
        if kind in ('notification','overlay'):
            values.update(entity_id=None,alarm_value='{alarmtyp}: {regel}\nQuelle: {quelle}\nBereich: {bereich}',
                          acknowledged_value='Alarm quittiert: {regel}\nQuelle: {quelle}',idle_value='Reset erfolgreich. Alarmverwaltung ist bereit.',
                          notification={'routes':[], 'title':'Alarm Management', 'devices':'', 'priority':0})
        return values

    def _notification_choices(self, kind, selected):
        choices = {}
        if kind == 'overlay':
            registry = dr.async_get(self.hass)
            for device in registry.devices.values():
                if any(domain=='browser_mod' for domain,_ in device.identifiers):
                    choices['browser:'+device.id] = device.name_by_user or device.name or device.id
        else:
            registry = er.async_get(self.hass)
            for entity in self.hass.states.async_all('notify'):
                registered = registry.async_get(entity.entity_id)
                if registered and registered.platform == 'mobile_app':
                    choices['entity:'+entity.entity_id] = (entity.attributes.get('friendly_name') or entity.entity_id)+' · HA-App'
            services = self.hass.services.async_services().get('notify',{})
            for name in services:
                if name.startswith('mobile_app_') and not any(key.startswith('entity:') for key in choices):
                    choices['mobile_app:notify.'+name] = name+' · HA-App (Aktion)'
                elif name=='pushover' or name.startswith('pushover_'):
                    choices['pushover:notify.'+name] = name+' · Pushover'
        for route in selected:
            choices.setdefault(route,route+' · gespeichert / derzeit nicht gefunden')
        return SelectSelector({'options':[{'value':key,'label':value} for key,value in choices.items()], 'multiple':True, 'mode':'list'})

    async def async_step_output_add(self, user_input=None):
        self._ensure_sources()
        if len(self._outputs) >= MAX_OUTPUTS:
            return self.async_abort(reason="max_outputs")
        errors = {}
        kinds=('notification','overlay') if self._notification_mode else ('switch','short_text','long_text')
        if user_input is not None:
            kind = user_input.get("kind")
            if kind not in kinds:
                errors["kind"] = "invalid_output"
            else:
                values = self._output_defaults(kind, user_input.get("entity_id") or None)
                try:
                    if kind not in ('notification','overlay'):
                        self._validate_output_target(values)
                    self._pending_output = values
                    return await self.async_step_output_details()
                except InputValidationError as err:
                    errors[err.field] = err.key
        schema={probatio.Required('kind',default=kinds[0]):SelectSelector({'options':list(kinds),'translation_key':'output_kind','mode':'list'})}
        if not self._notification_mode:
            schema[probatio.Optional('entity_id')]=EntitySelector({'filter':{'domain':sorted({domain for domains in DOMAINS.values() for domain in domains})}})
        return self.async_show_form(step_id=self._output_step('add'),errors=errors,data_schema=probatio.Schema(schema))

    def _output_schema(self, values):
        entity_field = probatio.Required if values["kind"] == "switch" else probatio.Optional
        marker = (entity_field("entity_id", default=values["entity_id"]) if values["kind"] == "switch" and values.get("entity_id") else
                  entity_field("entity_id", description={"suggested_value": values["entity_id"]}) if values.get("entity_id") else entity_field("entity_id"))
        schema = {probatio.Required("name", default=values["name"]): str}
        if values['kind'] not in ('notification','overlay'):
            schema[marker] = EntitySelector({"filter": {"domain": list(DOMAINS[values["kind"]])}})
        if values["kind"] == "short_text":
            schema[probatio.Required("encoding", default=values["encoding"])] = SelectSelector({
                "options": ["latin-1", "ascii"], "translation_key": "output_encoding", "mode": "dropdown"})
        format_fields = {key: value for key, value in schema.items() if str(getattr(key, "schema", getattr(key, "key", key))) == "encoding"}
        schema = {key: value for key, value in schema.items() if str(getattr(key, "schema", getattr(key, "key", key))) != "encoding"}
        schema[probatio.Required("enabled", default=values["enabled"])] = bool
        if values['kind'] in ('notification','overlay'):
            schema = {key:value for key,value in schema.items() if str(getattr(key,'schema',getattr(key,'key',key)))!='entity_id'}
            config = values['notification']
            delivery = {probatio.Required('routes',default=config['routes']): self._notification_choices(values['kind'],config['routes']),
                        probatio.Optional('title',default=config['title']): str}
            schema[probatio.Required('delivery')] = section(probatio.Schema(delivery),{'collapsed':False})
            if values['kind']=='notification':
                pushover = {probatio.Optional('devices',default=config['devices']):str,
                    probatio.Required('priority',default=str(config['priority'])):SelectSelector({'options':['-2','-1','0','1'],'translation_key':'notification_priority','mode':'dropdown'})}
                schema[probatio.Required('pushover')] = section(probatio.Schema(pushover),{'collapsed':True})
        for group, field in (("alarm", "alarm_value"), ("acknowledged", "acknowledged_value"), ("idle", "idle_value")):
            field_type = probatio.Required if values["kind"] == "switch" else probatio.Optional
            selector = (SelectSelector({"options": ["on", "off"], "translation_key": "switch_value", "mode": "list"})
                                                                      if values["kind"] == "switch" else TextSelector({"multiline": values["kind"] == "long_text"}))
            schema[probatio.Required(group)] = section(probatio.Schema({field_type(field, default=values[field]): selector}), {"collapsed": group != "alarm"})
        if format_fields:
            schema[probatio.Required("format")] = section(probatio.Schema(format_fields), {"collapsed": True})
        return probatio.Schema(schema)

    async def _output_form(self, step_id, user_input, output=None):
        values = output.to_dict() if output else dict(self._pending_output)
        if output and output.entity_registry_id:
            entry = er.async_get(self.hass).async_get(output.entity_registry_id)
            if entry:
                values["entity_id"] = entry.entity_id
        errors = {}
        if user_input is not None:
            try:
                user_input = flatten_sections(user_input, OUTPUT_SECTIONS)
            except InputValidationError as err:
                return self.async_show_form(step_id=step_id, data_schema=self._output_schema(values), errors={"base": err.key},
                                            description_placeholders={"beispiel": "`{regel}`"})
            if user_input.get('kind',values['kind'])!=values['kind']:
                return self.async_show_form(step_id=step_id,data_schema=self._output_schema(values),errors={'base':'invalid_output'},
                    description_placeholders={'beispiel':'`{regel}`'})
            values.update(user_input)
            if values['kind'] in ('notification','overlay'):
                config = dict(values['notification'])
                for field in ('routes','title','devices','priority'):
                    if field in user_input:
                        config[field] = user_input.pop(field)
                        values.pop(field,None)
                try:
                    config['priority'] = int(config['priority'])
                except (ValueError,TypeError):
                    config['priority'] = None
                values['notification'] = config
            # Optional text target can deliberately be cleared.
            if "entity_id" not in user_input:
                values["entity_id"] = None
            try:
                candidate = self._validate_output_target(values, output_id=output.id if output else None)
                if (output and self._output_owned(output.id) and
                        (candidate.entity_registry_id or candidate.entity_id) != (output.entity_registry_id or output.entity_id)):
                    raise InputValidationError("entity_id", "output_owned")
                outputs = [candidate if item.id == candidate.id else item for item in self._outputs]
                if output is None:
                    outputs.append(candidate)
                    self._outputs = outputs
                    self._last_added = candidate.name
                    return await self.async_step_output_after_add()
                return self._finish(self._sources, outputs=outputs)
            except InputValidationError as err:
                errors[err.field] = err.key
        schema = self._output_schema(values)
        ui_errors = section_errors(errors, OUTPUT_SECTIONS)
        for key, value in schema.schema.items():
            if str(getattr(key, "schema", getattr(key, "key", key))) in ui_errors and isinstance(value, section):
                value.options["collapsed"] = False
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=ui_errors,
                                    description_placeholders={"beispiel": "`{regel}`"})

    async def async_step_output_details(self, user_input=None):
        if self._pending_output is None:
            return self.async_abort(reason="configuration_changed")
        return await self._output_form(self._output_step('details'), user_input)

    async def async_step_output_after_add(self, user_input=None):
        return self.async_show_menu(step_id=self._output_step('after_add'),
                                    menu_options=[self._output_step('add'), self._output_step('finish')] if len(self._outputs) < MAX_OUTPUTS else [self._output_step('finish')],
                                    description_placeholders={"name": self._last_added, "count": str(len(self._visible_outputs()))})

    async def async_step_output_finish(self, user_input=None):
        return self._finish(self._sources)

    async def async_step_output_edit(self, user_input=None):
        self._ensure_sources()
        if not self._visible_outputs():
            return self.async_abort(reason="no_outputs")
        if user_input is not None:
            self._selected_output_id = user_input["output_id"]
            return await self.async_step_output_edit_details()
        return self.async_show_form(step_id=self._output_step('edit'), data_schema=probatio.Schema({probatio.Required("output_id"): self._output_choices()}))

    async def async_step_output_edit_details(self, user_input=None):
        output = next((item for item in self._visible_outputs() if item.id == self._selected_output_id), None)
        if output is None:
            return self.async_abort(reason="configuration_changed")
        return await self._output_form(self._output_step('edit_details'), user_input, output)

    async def async_step_output_remove(self, user_input=None):
        self._ensure_sources()
        if not self._visible_outputs():
            return self.async_abort(reason="no_outputs")
        if user_input is not None:
            self._selected_output_id = user_input["output_id"]
            return await self.async_step_output_confirm_remove()
        return self.async_show_form(step_id=self._output_step('remove'), data_schema=probatio.Schema({probatio.Required("output_id"): self._output_choices()}))

    async def async_step_output_confirm_remove(self, user_input=None):
        output = next((item for item in self._visible_outputs() if item.id == self._selected_output_id), None)
        if output is None:
            return self.async_abort(reason="configuration_changed")
        used = [rule.name for rule in self._rules if output.id in self._bindings.get(rule.id, [])]
        errors = {}
        if user_input is not None:
            if user_input.get("confirm") is not True:
                errors["base"] = "confirmation_required"
            elif used:
                errors["base"] = "output_in_use"
            elif self._output_owned(output.id):
                errors["base"] = "output_owned"
            else:
                return self._finish(self._sources, outputs=[item for item in self._outputs if item.id != output.id])
        return self.async_show_form(step_id=self._output_step('confirm_remove'), errors=errors,
                                    description_placeholders={"name": output.name, "rules": ", ".join(used) or "—"},
                                    data_schema=probatio.Schema({probatio.Required("confirm", default=False): bool}))

    async def async_step_output_overview(self, user_input=None):
        self._ensure_sources()
        if user_input is not None:
            return await (self.async_step_notifications() if self._notification_mode else self.async_step_outputs())
        labels = {**KIND_LABELS, "short_text": "Kurztext · 14 Byte"}
        lines = []
        for item in self._visible_outputs():
            used = ", ".join(rule.name for rule in self._rules if item.id in self._bindings.get(rule.id, [])) or "Noch keiner Regel zugeordnet"
            manager = getattr(self.config_entry, "runtime_data", None)
            delivery = manager.session.executions.get(item.id, {}) if manager else {}
            state = DELIVERY_LABELS.get(delivery.get("status"), "Noch nicht angefordert")
            lines.append(f"**{markdown_text(item.name)}** · {labels[item.kind]} · {'Aktiviert' if item.enabled else 'Deaktiviert'}\n\n"
                         f"**Ziel:** {markdown_text(', '.join(item.notification['routes']) if item.notification else item.entity_id or 'Eigene Statusentität')}\n\n"
                         f"**Regeln:** {markdown_text(used)}\n\n**Ausführung:** {state}")
        return self.async_show_form(step_id=self._output_step('overview'), data_schema=probatio.Schema({}), last_step=False,
                                    description_placeholders={"count": str(len(self._visible_outputs())), "outputs": "\n\n---\n\n".join(lines) or "Noch keine Einträge. Einen Eintrag hinzufügen und einer Regel zuordnen."})

    async def async_step_notification_add(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_add(user_input)

    async def async_step_notification_details(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_details(user_input)

    async def async_step_notification_after_add(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_after_add(user_input)

    async def async_step_notification_finish(self, user_input=None):
        return await self.async_step_output_finish(user_input)

    async def async_step_notification_edit(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_edit(user_input)

    async def async_step_notification_edit_details(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_edit_details(user_input)

    async def async_step_notification_remove(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_remove(user_input)

    async def async_step_notification_confirm_remove(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_confirm_remove(user_input)

    async def async_step_notification_overview(self, user_input=None):
        self._notification_mode=True
        return await self.async_step_output_overview(user_input)
