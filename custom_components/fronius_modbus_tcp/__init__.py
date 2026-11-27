"""Fronius Modbus TCP Integration für Home Assistant."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .client_pool import async_acquire_client, async_release_client
from .const import CONF_EXTRA_METER_UNIT_IDS, CONF_METER_UNIT_ID, CONF_UNIT_ID
from .coordinator import FroniusConfigEntry, FroniusCoordinator, structure_store
from .entity import inverter_device_info

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Integration aus einem Config-Entry einrichten."""
    host, port = entry.data[CONF_HOST], entry.data[CONF_PORT]
    # Einträge am selben Gerät (mehrere Wechselrichter am Datamanager) teilen
    # sich eine Verbindung, damit ihre Abfragen nacheinander laufen
    client = async_acquire_client(hass, host, port)
    coordinator = FroniusCoordinator(
        hass,
        entry,
        client,
        inverter_unit=entry.data[CONF_UNIT_ID],
        meter_unit=entry.data.get(CONF_METER_UNIT_ID),
        extra_meter_units=entry.data.get(CONF_EXTRA_METER_UNIT_IDS),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # Gerätestruktur aus dem Speicher (Wechselrichter schläft): trotzdem
        # einrichten, die Entitäten sind bis zur ersten Antwort nicht verfügbar
        if not coordinator.started_from_cache:
            await async_release_client(hass, host, port)
            raise
    except Exception:
        await async_release_client(hass, host, port)
        raise

    # Host/Port merken, unter denen die Verbindung geholt wurde: Beim Entladen
    # nach einer Änderung (Reconfigure, neue IP per DHCP) stehen in entry.data
    # schon die neuen Werte – freigegeben werden muss aber die alte Verbindung.
    coordinator.client_key = (host, port)
    # Wechselrichter-Gerät vorab anlegen: Die Zähler verweisen über dessen
    # Registry-ID darauf (via_device_id), und die muss es schon geben, wenn die
    # Zähler-Entitäten entstehen.
    info = inverter_device_info(coordinator)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=info["identifiers"],
        name=info.get("name"),
        manufacturer=info.get("manufacturer"),
        model=info.get("model"),
        sw_version=info.get("sw_version"),
        serial_number=info.get("serial_number"),
    )
    coordinator.inverter_registry_id = device.id
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Optionen geändert (z. B. Steuerung erlaubt) → Entitäten neu anlegen
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: FroniusConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> bool:
    """Config-Entry entladen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await async_release_client(hass, *entry.runtime_data.client_key)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: FroniusConfigEntry) -> None:
    """Eintrag gelöscht: gespeicherte Gerätestruktur entfernen."""
    await structure_store(hass, entry.entry_id).async_remove()
