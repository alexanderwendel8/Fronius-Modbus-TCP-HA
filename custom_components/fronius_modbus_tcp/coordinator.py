"""DataUpdateCoordinator für Fronius Modbus TCP."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeviceInfo, FroniusData, FroniusModbusClient, FroniusModbusError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type FroniusConfigEntry = ConfigEntry[FroniusCoordinator]


class FroniusCoordinator(DataUpdateCoordinator[FroniusData]):
    """Fragt das Gerät zyklisch ab und verteilt die Daten an die Entitäten."""

    config_entry: FroniusConfigEntry
    device_info: DeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FroniusConfigEntry,
        client: FroniusModbusClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_setup(self) -> None:
        """Einmalig beim ersten Refresh: Geräteinformationen laden."""
        try:
            self.device_info = await self.client.read_device_info()
        except FroniusModbusError as err:
            raise UpdateFailed(f"Geräteinformationen nicht lesbar: {err}") from err

    async def _async_update_data(self) -> FroniusData:
        try:
            return await self.client.read_data()
        except FroniusModbusError as err:
            raise UpdateFailed(f"Fehler beim Lesen der Daten: {err}") from err
