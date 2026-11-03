"""Versioned, atomic Home Assistant storage; no manual file writes."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .alarm_engine import AlarmState
from .session import AlarmSession, migrate_v2_session, migrate_v3_session, migrate_v4_session
from .const import DOMAIN, STORAGE_VERSION


class AlarmStore(Store):
    async def _async_migrate_func(self, old_major_version, old_minor_version, old_data):
        if old_major_version == 4:
            return migrate_v4_session(old_data)
        if old_major_version == 3:
            return migrate_v3_session(old_data)
        if old_major_version == 2:
            return migrate_v2_session(old_data)
        if old_major_version != 1:
            raise ValueError("Unsupported alarm store migration")
        if not isinstance(old_data, dict) or set(old_data) != {"simulation", "alarm"} or old_data["simulation"] is not True:
            raise ValueError("Invalid legacy alarm store")
        return AlarmSession(manual=AlarmState.from_dict(old_data["alarm"])).to_dict()


def create_store(hass: HomeAssistant, entry_id: str) -> Store:
    return AlarmStore(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}", atomic_writes=True)


async def async_load_state(store: Store) -> AlarmState:
    return (await async_load_session(store)).manual


async def async_load_session(store: Store) -> AlarmSession:
    data = await store.async_load()
    if data is None:
        state = AlarmSession()
        await store.async_save(state.to_dict())
        return state
    return AlarmSession.from_dict(data)


async def async_save_state(store: Store, state: AlarmState) -> None:
    session = await async_load_session(store)
    session.manual = state
    await store.async_save(session.to_dict())
