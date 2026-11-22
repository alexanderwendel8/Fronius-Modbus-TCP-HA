"""Fronius Modbus TCP Integration für Home Assistant."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .api import FroniusModbusClient
from .const import CONF_METER_UNIT_ID, CONF_UNIT_ID
from .coordinator import FroniusConfigEntry, FroniusCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Integration aus einem Config-Entry einrichten."""
    client = FroniusModbusClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = FroniusCoordinator(
        hass,
        entry,
        client,
        inverter_unit=entry.data[CONF_UNIT_ID],
        meter_unit=entry.data.get(CONF_METER_UNIT_ID),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Config-Entry entladen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.close()
    return unloaded
