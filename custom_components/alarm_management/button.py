"""Alarm controls and output retries."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AlarmButton(entry, "acknowledge"), AlarmButton(entry, "reset"), AlarmButton(entry, "retry_outputs")])


class AlarmButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, action):
        self._manager = entry.runtime_data
        self._action = action
        self._attr_unique_id = f"{entry.entry_id}_{action}"
        self._attr_translation_key = action
        self._attr_icon = {"reset": "mdi:restore", "acknowledge": "mdi:check", "retry_outputs": "mdi:refresh"}[action]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_press(self):
        if self._action == "retry_outputs":
            self._manager.executor.retry()
        else:
            await self._manager.async_action(self._action)
