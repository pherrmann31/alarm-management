"""Alarm Management: persistent alarms and restricted real outputs."""

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady, HomeAssistantError

<<<<<<< Updated upstream
from .const import DOMAIN, SERVICES
=======
from .const import DOMAIN, SERVICES, VERSION
from .configuration import prepare_configuration
from .groups import load_groups, expand_bindings, validate_catalogue
from .discovery import SmokeDiscovery
>>>>>>> Stashed changes
from .manager import AlarmManager
from .input_config import load_sources
from .input_monitor import InputMonitor
from .rule_config import ensure_rule_options, load_rules
from .output_config import ensure_output_options, load_output_config
from .output_monitor import OutputTargetMonitor, cleanup_output_entities
from .storage import create_store
from .output_executor import LiveOutputExecutor


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data.get("execution_mode") != "live" and entry.data.get("simulation") is not True:
        raise ConfigEntryError("Unsupported alarm configuration")
    manager = AlarmManager(hass, entry.entry_id)
    try:
<<<<<<< Updated upstream
        sources = load_sources(dict(entry.options))
        options = ensure_rule_options(dict(entry.options), sources)
        rules = load_rules(options, sources)
        options = ensure_output_options(options, rules)
        outputs, bindings = load_output_config(options, rules)
=======
        options, sources, rules, outputs, bindings = prepare_configuration(entry.options)
    except ValueError as err:
        raise ConfigEntryError(f"Alarm Management {VERSION}: {err}") from err
    try:
>>>>>>> Stashed changes
        await manager.async_load()
    except ValueError as err:
        raise ConfigEntryError(f"Alarm Management {VERSION}: gespeicherte Alarmvorfälle: {err}") from err
    except OSError as err:
        raise ConfigEntryNotReady("Alarm storage unavailable") from err
    updates = {"options": options, "data": {"execution_mode": "live"}}
    if getattr(entry, "title", None) == "Alarm Management Simulation":
        updates["title"] = "Alarm Management"
    hass.config_entries.async_update_entry(entry, **updates)
    manager.rules = rules
    manager.outputs, manager.output_bindings = outputs, bindings
    manager.inputs = InputMonitor(hass, entry.entry_id, sources)
    manager.output_targets = OutputTargetMonitor(hass, outputs, manager.inputs_changed)
    manager.executor = LiveOutputExecutor(manager)
    entry.runtime_data = manager
    try:
        manager.start_shutdown_listener()
        manager.inputs.start(manager.inputs_changed)
        manager.output_targets.start()
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR, Platform.BUTTON])
        manager.running = True
        await manager.async_process_inputs(manager.inputs.snapshot)
        cleanup_output_entities(hass, entry.entry_id, outputs)
    except Exception:
        manager.running = False
        manager.stop_inputs()
        await manager.async_drain()
        await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR, Platform.BUTTON])
        raise

    async def handle_action(call: ServiceCall) -> None:
        if call.service == "retry_outputs":
            manager.executor.retry()
        else:
            await manager.async_action(call.service)

    for service in (*SERVICES, "retry_outputs"):
        hass.services.async_register(
            DOMAIN, service, handle_action, schema=probatio.Schema({})
        )
    manager.executor.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = entry.runtime_data
    async with manager.lock:
        manager.running = False
        if not await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR, Platform.BUTTON]):
            manager.running = True
            manager.executor.schedule()
            return False
        manager.stop_inputs()
        for service in (*SERVICES, "retry_outputs"):
            hass.services.async_remove(DOMAIN, service)
    await manager.async_drain()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete only this entry's storage when the user removes the integration."""
    await create_store(hass, entry.entry_id).async_remove()
