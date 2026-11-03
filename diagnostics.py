"""Explicit user download of alarm and delivery diagnostics."""

from copy import deepcopy

from .const import VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    manager = entry.runtime_data
    return {"version": VERSION, "execution_mode": "live", "storage_error": manager.input_error,
            "delivery_storage_errors": sorted(manager.delivery_failures),
            "input_options": deepcopy(dict(entry.options)),
            "live_inputs": deepcopy(manager.inputs.snapshot),
            "live_rules": manager.evaluate(),
            "alarm_session": manager.session.to_dict()}
