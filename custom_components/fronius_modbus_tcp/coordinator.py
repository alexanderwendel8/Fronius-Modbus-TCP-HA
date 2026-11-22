"""DataUpdateCoordinator für Fronius Modbus TCP."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import sunspec
from .api import (
    FroniusData,
    FroniusModbusClient,
    FroniusModbusError,
    InverterInfo,
    MeterInfo,
)
from .const import (
    CONF_ALLOW_CONTROL,
    DEFAULT_REVERT_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type FroniusConfigEntry = ConfigEntry[FroniusCoordinator]


class FroniusCoordinator(DataUpdateCoordinator[FroniusData]):
    """Fragt Wechselrichter und optional Smart Meter zyklisch ab."""

    config_entry: FroniusConfigEntry
    inverter: InverterInfo
    meter: MeterInfo | None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FroniusConfigEntry,
        client: FroniusModbusClient,
        inverter_unit: int,
        meter_unit: int | None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self._inverter_unit = inverter_unit
        self._meter_unit = meter_unit
        self.meter = None
        # Rückfallzeit für Vorgaben; gesetzt/wiederhergestellt von der Number-Entität
        self.revert_seconds = DEFAULT_REVERT_SECONDS

    @property
    def control_allowed(self) -> bool:
        """Option "Steuerung erlauben" aktiv und Gerät hat Modell 123."""
        return bool(
            self.config_entry.options.get(CONF_ALLOW_CONTROL)
        ) and sunspec.CONTROLS_MODEL in self.inverter.models

    async def _async_setup(self) -> None:
        """Einmalig beim ersten Refresh: Gerätestruktur erkennen."""
        try:
            self.inverter = await self.client.read_inverter_info(self._inverter_unit)
        except FroniusModbusError as err:
            raise UpdateFailed(f"Wechselrichter nicht erkannt: {err}") from err

        if self._meter_unit:
            try:
                self.meter = await self.client.read_meter_info(self._meter_unit)
            except FroniusModbusError as err:
                # Zähler fehlt: Wechselrichter trotzdem einrichten
                _LOGGER.warning(
                    "Smart Meter unter Unit-ID %s nicht gefunden: %s",
                    self._meter_unit,
                    err,
                )

    async def _async_update_data(self) -> FroniusData:
        data = FroniusData()
        try:
            data.values.update(await self.client.read_inverter_data(self.inverter))
        except FroniusModbusError as err:
            raise UpdateFailed(f"Fehler beim Lesen des Wechselrichters: {err}") from err

        if self.meter is not None:
            try:
                data.values.update(await self.client.read_meter_data(self.meter))
            except FroniusModbusError as err:
                # Zähler-Entitäten werden unavailable, Wechselrichter bleibt verfügbar
                _LOGGER.debug("Fehler beim Lesen des Smart Meters: %s", err)
        return data
