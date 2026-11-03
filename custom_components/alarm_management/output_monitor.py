"""Read-only target metadata. Never writes a target or invokes a service."""
import re

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event


@callback
def cleanup_output_entities(hass, entry_id, outputs):
    """Remove only stale status entities belonging to explicitly removed outputs."""
    registry = er.async_get(hass)
    prefix = f"{entry_id}_output_"
    valid = {f"{prefix}{output.id}" for output in outputs}
    for entry in er.async_entries_for_config_entry(registry, entry_id):
        unique_id = getattr(entry, "unique_id", "") or ""
        if (unique_id.startswith(prefix) and re.fullmatch(r"[0-9a-f]{32}", unique_id[len(prefix):])
                and unique_id not in valid):
            registry.async_remove(entry.entity_id)


class OutputTargetMonitor:
    def __init__(self, hass, outputs, notify):
        self.hass, self.outputs, self.notify = hass, outputs, notify
        self.snapshot = {}
        self._remove_states = self._remove_registry = None

    def _entity_id(self, output):
        if output.entity_registry_id:
            entry = er.async_get(self.hass).async_get(output.entity_registry_id)
            return entry.entity_id if entry else None
        return output.entity_id

    @callback
    def start(self):
        self.stop()
        self._bind()
        self._remove_registry = self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._registry_changed)

    @callback
    def stop(self):
        for remove in (self._remove_states, self._remove_registry):
            if remove:
                remove()
        self._remove_states = self._remove_registry = None

    @callback
    def _bind(self):
        if self._remove_states:
            self._remove_states()
            self._remove_states = None
        entities = {self._entity_id(output) for output in self.outputs if output.entity_id}
        entities.discard(None)
        if entities:
            self._remove_states = async_track_state_change_event(self.hass, list(entities), self.refresh)
        self.refresh()

    @callback
    def _registry_changed(self, event):
        self._bind()

    @callback
    def refresh(self, event=None):
        snapshot = {}
        for output in self.outputs:
            entity_id = self._entity_id(output)
            state = self.hass.states.get(entity_id) if entity_id else None
            attrs = getattr(state, "attributes", {}) or {}
            minimum, maximum = attrs.get("min", 0), attrs.get("max", 255)
            minimum = minimum if type(minimum) in (int, float) and 0 <= minimum <= 255 else 0
            maximum = maximum if type(maximum) in (int, float) and 0 <= maximum <= 255 else 255
            # A loaded text entity can be writable before it has its first value.
            # Do not equate unknown text content with an unavailable target.
            text_target = bool(entity_id and entity_id.split(".", 1)[0] in ("text", "input_text"))
            available = bool(state and state.state != "unavailable" and not attrs.get("restored", False)
                             and (text_target or state.state != "unknown"))
            snapshot[output.id] = {"entity_id": entity_id or output.entity_id,
                                   "available": not output.entity_id or available,
                                   "value": state.state if state else None,
                                   "min_length": minimum, "max_length": maximum}
        if snapshot != self.snapshot:
            self.snapshot = snapshot
            self.notify()
