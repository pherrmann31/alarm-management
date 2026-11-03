"""Read-only alarm, output and delivery status entities."""

import json

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, HISTORY_LIMIT, SIGNAL_INPUTS_UPDATED, SIGNAL_UPDATED, STATES, VERSION


def _bounded_records(records, budget=11000):
    """Keep recorder attributes modest; diagnostics contains the complete data."""
    result = []
    for record in records:
        size = len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        if size > budget:
            break
        result.append(record)
        budget -= size
    return result


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AlarmStatusSensor(entry), InputStatusSensor(entry),
                        AlarmDetailSensor(entry, "triggered_by"), AlarmDetailSensor(entry, "triggered_areas"),
                        AlarmDetailSensor(entry, "triggered_rules"), AlarmDetailSensor(entry, "journal"), RuleStatusSensor(entry),
                        OutputSummarySensor(entry), OutputLogSensor(entry),
                        *(OutputValueSensor(entry, output) for output in entry.runtime_data.outputs)])


class AlarmStatusSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATES)
    _attr_icon = "mdi:shield-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        self._manager = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
            entry_type=DeviceEntryType.SERVICE, sw_version=VERSION,
        )

    @property
    def native_value(self) -> str:
        return self._manager.session.state

    @property
    def icon(self):
        return {"idle": "mdi:shield-check-outline", "active": "mdi:shield-alert",
                "acknowledged": "mdi:shield-check"}[self._manager.session.state]

    @property
    def available(self) -> bool:
        return not self._manager.input_error

    @property
    def extra_state_attributes(self) -> dict:
        state = self._manager.state.to_dict()
        state.pop("state")
        return {"execution_mode": "live", "manual_test_state": self._manager.state.state,
                "alarm_count": len(self._manager.session.alarms),
                "alarm_sources": _bounded_records(self._manager.session.alarms.values()), **state}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._async_update)
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()


class InputStatusSensor(SensorEntity):
    """Number of matching inputs; detailed per-source status in attributes."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "inputs"
    _attr_icon = "mdi:import"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry) -> None:
        self._manager = entry.runtime_data
        self._monitor = entry.runtime_data.inputs
        self._attr_unique_id = f"{entry.entry_id}_inputs"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def native_value(self) -> int:
        return sum(item["status"] == "matching" for item in self._monitor.snapshot)

    @property
    def extra_state_attributes(self) -> dict:
        items = self._monitor.snapshot
        return {
            "execution_mode": "live", "configured_inputs": len(self._monitor.sources),
            "enabled_inputs": sum(item.enabled for item in self._monitor.sources),
            "unavailable_inputs": sum(item["status"] in ("unknown", "unavailable", "missing", "blocked") for item in items),
            "inputs": [dict(item) for item in items],
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_INPUTS_UPDATED, self._async_update))

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()


class AlarmDetailSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry, kind):
        self._manager = entry.runtime_data
        self._kind = kind
        self._attr_unique_id = f"{entry.entry_id}_{kind}"
        self._attr_translation_key = kind
        self._attr_icon = {"journal": "mdi:clipboard-text-clock-outline", "triggered_by": "mdi:motion-sensor",
                           "triggered_areas": "mdi:floor-plan", "triggered_rules": "mdi:source-branch"}[kind]
        if kind == "journal":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self):
        return not self._manager.input_error

    @property
    def native_value(self):
        session = self._manager.session
        if self._kind == "journal":
            value = session.history[-1]["message"] if session.history else "Keine Ereignisse"
        else:
            records = list(session.alarms.values())
            sources = {source["id"]: source for record in records for source in record["sources"]}
            if self._kind == "triggered_rules":
                values = [item["rule_name"] for item in records]
            elif self._kind == "triggered_by":
                values = [source["name"] for source in sources.values()]
            else:
                values = list(dict.fromkeys(source["area_name"] or "Ohne Bereich" for source in sources.values()))
            if session.manual.state != "idle":
                values.append("Ohne Bereich (Test)" if self._kind == "triggered_areas" else "Manueller Test")
            value = ", ".join(values) or "Keine"
        return value if len(value) <= 255 else value[:252] + "..."

    @property
    def extra_state_attributes(self):
        if self._kind == "journal":
            preview = []
            budget = 12000
            for event in reversed(self._manager.session.history):
                size = len(json.dumps(event, ensure_ascii=False).encode("utf-8"))
                if size > budget:
                    break
                preview.append(event)
                budget -= size
                if len(preview) == 10:
                    break
            return {"execution_mode": "live", "limit": HISTORY_LIMIT,
                    "history_count": len(self._manager.session.history),
                    "events": preview, "full_history": "Integration: Diagnose herunterladen"}
        live = {item["id"]: item["status"] for item in self._manager.evaluate()}
        return {"execution_mode": "live", "alarm_count": len(self._manager.session.alarms),
                "full_details": "Integration: Diagnose herunterladen",
                "alarm_sources": _bounded_records([dict(item, live_status=live.get(item["id"], "removed"))
                                                       for item in self._manager.session.alarms.values()])}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        for signal in (SIGNAL_UPDATED, SIGNAL_INPUTS_UPDATED):
            self.async_on_remove(async_dispatcher_connect(self.hass, signal, self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()


class RuleStatusSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "matching_rules"
    _attr_icon = "mdi:source-branch"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry):
        self._manager = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_matching_rules"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def native_value(self):
        return sum(item["status"] == "matching" for item in self._manager.evaluate())

    @property
    def extra_state_attributes(self):
        rules = self._manager.evaluate()
        return {"execution_mode": "live", "configured_rules": len(rules),
                "unknown_rules": sum(item["status"] == "unknown" for item in rules),
                "rules": _bounded_records([{key: item[key] for key in ("id", "name", "input_ids", "mode", "alarm_type", "enabled", "status")} for item in rules]),
                "full_details": "Integration: Diagnose herunterladen"}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_INPUTS_UPDATED, self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()


class OutputSummarySensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "output_plan"
    _attr_icon = "mdi:export"

    def __init__(self, entry):
        self._manager = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_output_plan"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self):
        return not self._manager.input_error

    @property
    def native_value(self):
        execution_errors = any(record["status"] in ("failed", "mismatch") for key, record in self._manager.session.executions.items() if key in self._manager.session.output_plan)
        if self._manager.delivery_error or execution_errors or any(item["status"] == "error" for item in self._manager.session.output_plan.values()):
            return "Ausgabefehler"
        statuses = [record["status"] for key, record in self._manager.session.executions.items() if key in self._manager.session.output_plan]
        if "pending" in statuses:
            return "Ausgabe läuft"
        return "Rückmeldung offen" if "sent" in statuses else "Bereit"

    @property
    def extra_state_attributes(self):
        plans = list(self._manager.session.output_plan.values())
        return {"execution_mode": "live", "configured_outputs": len(self._manager.outputs),
                "requested_outputs": sum(item["phase"] != "idle" and item["status"] == "planned" for item in plans),
                "output_errors": sum(item["status"] == "error" for item in plans),
                "execution_errors": sum(item["status"] in ("failed", "mismatch") for key, item in self._manager.session.executions.items() if key in self._manager.session.output_plan),
                "delivery_storage_error": self._manager.delivery_error,
                "plan": _bounded_records(plans), "full_details": "Integration: Diagnose herunterladen"}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()


class OutputLogSensor(OutputSummarySensor):
    _attr_translation_key = "output_log"
    _attr_icon = "mdi:history"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry):
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_output_log"

    @property
    def native_value(self):
        history = self._manager.session.delivery_history
        if not history:
            return "Keine Ausgaben"
        event = history[-1]
        labels = {"pending": "Vorgemerkt", "sent": "Gesendet", "confirmed": "Zustand bestätigt", "failed": "Fehler", "mismatch": "Zustand abweichend", "internal": "Intern aktualisiert", "idle": "Nicht angefordert"}
        return f"{event['name']}: {event['error'] or labels[event['status']]}"[:255]

    @property
    def extra_state_attributes(self):
        return {"execution_mode": "live", "history_count": len(self._manager.session.delivery_history),
                "events": _bounded_records(list(reversed(self._manager.session.delivery_history))[:10], budget=10000),
                "full_details": "Integration: Diagnose herunterladen"}


class OutputValueSensor(OutputSummarySensor):
    _attr_translation_key = None
    _attr_icon = "mdi:export-variant"

    def __init__(self, entry, output):
        super().__init__(entry)
        self._output_id = output.id
        self._output_kind = output.kind
        self._output_domain = output.entity_id.split(".", 1)[0] if output.entity_id else None
        self._attr_unique_id = f"{entry.entry_id}_output_{output.id}"
        label = {"switch": "Schalten", "short_text": "Kurztext", "long_text": "Langtext"}[output.kind]
        self._attr_name = f"{label} · {output.name}"

    @property
    def icon(self):
        if self.native_value == "Ausgabefehler":
            return "mdi:alert-circle-outline"
        if self._output_kind == "short_text":
            return "mdi:format-letter-case"
        if self._output_kind == "long_text":
            return "mdi:text-long"
        return {"siren": "mdi:bullhorn", "light": "mdi:lightbulb-outline"}.get(self._output_domain, "mdi:toggle-switch-outline")

    @property
    def native_value(self):
        plan = self._manager.session.output_plan.get(self._output_id)
        if plan is None:
            return None
        delivery = self._manager.session.executions.get(self._output_id, {})
        if self._output_id in self._manager.delivery_failures or delivery.get("status") in ("failed", "mismatch"):
            return "Ausgabefehler"
        if plan["status"] == "error":
            return "Ausgabefehler"
        if plan["status"] == "disabled":
            return "Rücksetzen ausstehend" if delivery.get("owned") else "Deaktiviert"
        if plan["entity_id"] and delivery.get("status") == "idle":
            return "Nicht angefordert"
        return (plan["value"] or "")[:255]

    @property
    def extra_state_attributes(self):
        plan = self._manager.session.output_plan.get(self._output_id)
        if plan is None:
            return {"execution_mode": "live"}
        value = plan["value"]
        delivery = self._manager.session.executions.get(self._output_id, {})
        preview = isinstance(value, str) and len(value.encode("utf-8")) > 8000
        errors = {"short_text_too_long": "Kurztext überschreitet 14 Byte.",
                  "short_text_invalid": "Kurztext enthält ungeeignete Steuerzeichen oder Zeilenumbrüche.",
                  "invalid_text_character": "Text enthält ein unzulässiges Nullzeichen.",
                  "unsupported_character": "Text enthält Zeichen außerhalb des gewählten Zeichensatzes.",
                  "text_too_long": "Langtext überschreitet 4096 Zeichen; angezeigter Wert ist nur eine Fehlervorschau.",
                  "target_text_length": "Text passt nicht zur Mindest-/Maximallänge der Zielentität.",
                  "target_unavailable": "Zielentität fehlt oder ist nicht verfügbar."}
        return {"execution_mode": "live", "phase": plan["phase"], "status": plan["status"],
                "target_entity_id": plan["entity_id"], "requesting_rule_count": len(plan["rules"]),
                "value": value[:255] if preview else value, "value_preview_only": preview,
                "error": plan["error"], "error_message": errors.get(plan["error"]),
                "delivery_status": delivery.get("status", "pending"), "delivery_error": delivery.get("error"),
                "target_owned": delivery.get("owned", False),
                "observed_value": (self._manager.output_targets.snapshot.get(self._output_id, {}).get("value") if self._manager.output_targets else None),
                "full_details": "Integration: Diagnose herunterladen"}
