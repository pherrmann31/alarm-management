"""Read-only HA adapter; input snapshots never trigger actions or test alarms."""

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.event import async_track_state_change_event

from .input_config import evaluate_source


def resolve_entity_id(source, registry) -> str | None:
    if source.entity_registry_id is not None:
        entry = registry.async_get(source.entity_registry_id)
        # Do not silently bind to a different entity reusing an old name.
        return entry.entity_id if entry is not None else None
    return source.entity_id


class InputMonitor:
    def __init__(self, hass, entry_id: str, sources) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.sources = sources
        self._remove_states = None
        self._remove_registry = None
        self._notify = None
        self.snapshot = []
        self._extra_listeners = []

    @callback
    def start(self, notify) -> None:
        self.stop()
        self._notify = notify
        self._bind_states()
        self._remove_registry = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._registry_changed
        )
        self._extra_listeners = [self.hass.bus.async_listen(event, self._area_changed)
                                 for event in (ar.EVENT_AREA_REGISTRY_UPDATED, dr.EVENT_DEVICE_REGISTRY_UPDATED)]

    @callback
    def stop(self) -> None:
        for remove in (self._remove_states, self._remove_registry):
            if remove is not None:
                remove()
        self._remove_states = self._remove_registry = self._notify = None
        for remove in self._extra_listeners:
            remove()
        self._extra_listeners = []

    @callback
    def _area_changed(self, event):
        self.refresh()

    @callback
    def _bind_states(self) -> None:
        if self._remove_states is not None:
            self._remove_states()
            self._remove_states = None
        registry = er.async_get(self.hass)
        tracked = set()
        for source in self.sources:
            entity_id = resolve_entity_id(source, registry)
            entry = registry.async_get(entity_id) if entity_id else None
            if source.enabled and entity_id and not (entry and entry.config_entry_id == self.entry_id):
                tracked.add(entity_id)
        if tracked:
            self._remove_states = async_track_state_change_event(
                self.hass, list(tracked), self._state_changed
            )
        self.refresh()

    @callback
    def _registry_changed(self, event) -> None:
        ids = {source.entity_registry_id for source in self.sources if source.entity_registry_id}
        if event.data.get("entity_id") in {source.entity_id for source in self.sources}:
            self._bind_states()
        elif event.data.get("entity_id"):
            registry = er.async_get(self.hass)
            # A registered source may have just been renamed, removed, or disabled.
            if any((entry := registry.async_get(item)) and entry.entity_id == event.data["entity_id"] for item in ids):
                self._bind_states()
            elif event.data.get("action") == "remove":
                self._bind_states()

    @callback
    def _state_changed(self, event) -> None:
        self.refresh()

    @callback
    def refresh(self) -> None:
        registry = er.async_get(self.hass)
        snapshot = []
        for source in self.sources:
            entity_id = resolve_entity_id(source, registry)
            entry = registry.async_get(entity_id) if entity_id else None
            own_entity = bool(entry and entry.config_entry_id == self.entry_id)
            state = self.hass.states.get(entity_id) if source.enabled and entity_id and not own_entity else None
            value = state.state if state else None
            status = "blocked" if own_entity else evaluate_source(source, value)
            area_id = er.async_get_effective_area_id(self.hass, entry) if entry else None
            area = ar.async_get(self.hass).async_get_area(area_id) if area_id else None
            snapshot.append({
                "id": source.id, "name": source.name,
                "entity_id": entity_id or source.entity_id,
                "trigger_state": source.trigger_state,
                "enabled": source.enabled, "current_state": value, "status": status,
                "area_id": area_id, "area_name": area.name if area else None,
            })
        if snapshot != self.snapshot:
            self.snapshot = snapshot
            if self._notify:
                self._notify()
