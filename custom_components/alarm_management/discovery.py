"""Controlled smoke discovery: stable registry identities, persisted before use."""

import asyncio
import logging
from datetime import datetime, timezone
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5

from homeassistant.core import callback

from .const import INPUT_CONFIG_KEY, MAX_INPUTS
from .groups import KEY, SMOKE_DEFAULT, load_groups
from .input_config import build_source, load_sources, serialize_sources

_LOGGER = logging.getLogger(__name__)


from .discovery_model import discover


def candidates(hass):
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers import device_registry as dr
    result = []
    for entry in er.async_get(hass).entities.values():
        if entry.platform == 'alarm_management':
            continue
        if entry.entity_id.split('.')[0] not in ('binary_sensor','sensor','event','input_boolean'):
            continue
        state = hass.states.get(entry.entity_id)
        device_class = entry.device_class or entry.original_device_class
        if device_class is None and state:
            device_class = state.attributes.get('device_class')
        result.append({'registry_id': entry.id, 'entity_id': entry.entity_id,
                       'name': entry.name or entry.original_name or (state.name if state else entry.entity_id),
                       'device_class': device_class, 'disabled': entry.disabled_by is not None,
                       'labels': list(set(entry.labels) | set(getattr(dr.async_get(hass).async_get(entry.device_id),'labels',set()) if entry.device_id else set())),
                       'event_types': state.attributes.get('event_types',[]) if state else []})
    return result


class SmokeDiscovery:
    def __init__(self, hass, entry, manager):
        self.hass, self.entry, self.manager = hass, entry, manager
        self._remove = []
        self._timer = None
        self._task = None
        self._stopped = False

    @callback
    def start(self):
        self._remove = [self.hass.bus.async_listen('entity_registry_updated', self.changed),
                        self.hass.bus.async_listen('device_registry_updated', self.changed),
                        self.hass.bus.async_listen('state_changed', self.changed)]
        self.changed(None)

    @callback
    def changed(self, event):
        if self._stopped:
            return
        if event and event.event_type == 'state_changed':
            state = event.data.get('new_state')
            if not state or (state.attributes.get('device_class') != 'smoke' and not self.entry.options.get(KEY,{}).get('auto_house')):
                return
        if self._timer is None:
            self._timer = self.hass.loop.call_later(1, self._schedule)

    @callback
    def _schedule(self):
        self._timer = None
        if not self._stopped and (self._task is None or self._task.done()):
            self._task = self.hass.async_create_task(self.refresh())

    async def refresh(self):
        try:
            async with self.manager.lock:
                if not self.manager.running or self._stopped:
                    return
                options = dict(self.entry.options)
                sources, groups, added = discover(load_sources(options), load_groups(options), candidates(self.hass))
                if groups == load_groups(options) and not added:
                    return
                options[KEY] = groups
                options[INPUT_CONFIG_KEY] = serialize_sources(sources)
                self.hass.config_entries.async_update_entry(self.entry, options=options)
                self.manager.groups = groups
                self.manager.inputs.sources = sources
                self.manager.inputs._bind_states()
                self.manager.inputs_changed()
                if added:
                    from .session import append_event
                    candidate = deepcopy(self.manager.session)
                    append_event(candidate, 'discovery_added', datetime.now(timezone.utc).isoformat(),
                                 [{'id':s.id,'name':s.name,'entity_id':s.entity_id} for s in added])
                    await self.manager._commit(candidate)
                for source in added:
                    _LOGGER.info('Automatically enrolled smoke detector %s (%s)', source.name, source.entity_id)
        except Exception:
            _LOGGER.exception('Smoke discovery failed; existing monitoring remains active')

    @callback
    def stop(self):
        self._stopped = True
        for remove in self._remove:
            remove()
        self._remove = []
        if self._timer:
            self._timer.cancel()
            self._timer = None

    async def drain(self):
        if self._task and not self._task.done():
            await asyncio.gather(self._task, return_exceptions=True)
