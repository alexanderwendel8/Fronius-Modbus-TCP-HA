"""DataUpdateCoordinator für Fronius Modbus TCP."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    CONF_SCAN_INTERVAL,
    CONF_SITE_REGISTERS,
    DEFAULT_REVERT_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    METER_RETRY_INTERVAL,
    MIN_REVERT_SECONDS,
    REVERT_INTERVAL_FACTOR,
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
        self.scan_interval_seconds = int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval_seconds),
        )
        self.client = client
        self._inverter_unit = inverter_unit
        self._meter_unit = meter_unit
        self.meter = None
        self._meter_next_retry: datetime | None = None
        self._meter_failed = False
        # Rückfallzeit für Vorgaben; gesetzt/wiederhergestellt von der Number-Entität
        self.revert_seconds = max(DEFAULT_REVERT_SECONDS, self.min_revert_seconds)

    @property
    def min_revert_seconds(self) -> int:
        """Kleinste zulässige Rückfallzeit: muss mehrere Abfragen überdauern."""
        return max(
            MIN_REVERT_SECONDS, REVERT_INTERVAL_FACTOR * self.scan_interval_seconds
        )

    @property
    def control_allowed(self) -> bool:
        """Option "Steuerung erlauben" aktiv und Gerät hat Modell 123."""
        return bool(
            self.config_entry.options.get(CONF_ALLOW_CONTROL)
        ) and sunspec.CONTROLS_MODEL in self.inverter.models

    @property
    def storage_control_allowed(self) -> bool:
        """Steuerung erlaubt und ein Speicher (Modell 124) ist vorhanden."""
        return (
            bool(self.config_entry.options.get(CONF_ALLOW_CONTROL))
            and self.inverter.has_storage
        )

    async def _async_setup(self) -> None:
        """Einmalig beim ersten Refresh: Gerätestruktur erkennen."""
        entry = self.config_entry
        known = entry.data.get(CONF_SITE_REGISTERS)
        try:
            self.inverter = await self.client.read_inverter_info(
                self._inverter_unit, site_registers=known
            )
        except FroniusModbusError as err:
            raise UpdateFailed(f"Wechselrichter nicht erkannt: {err}") from err
        if known is None and self.inverter.site_registers_confirmed:
            # Einträge aus älteren Versionen: eindeutiges Ergebnis nachtragen, damit
            # ein späterer vorübergehender Fehler den Gerätetyp nicht mehr ändert.
            # Läuft vor dem Registrieren des Update-Listeners → kein Neuladen.
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_SITE_REGISTERS: self.inverter.has_site_registers,
                },
            )

        if self._meter_unit:
            try:
                self.meter = await self.client.read_meter_info(self._meter_unit)
            except FroniusModbusError as err:
                # Zähler fehlt: Wechselrichter trotzdem einrichten, später erneut suchen
                _LOGGER.warning(
                    "Smart Meter unter Unit-ID %s nicht gefunden: %s. "
                    "Die Suche wird alle %s Minuten wiederholt",
                    self._meter_unit,
                    err,
                    int(METER_RETRY_INTERVAL.total_seconds() // 60),
                )
                self._meter_next_retry = dt_util.utcnow() + METER_RETRY_INTERVAL

    async def _async_retry_meter(self) -> None:
        """Beim Start nicht gefundenen Zähler erneut suchen.

        Wird er gefunden, lädt der Eintrag neu, damit die Zähler-Entitäten
        angelegt werden.
        """
        now = dt_util.utcnow()
        if self._meter_next_retry is None or now < self._meter_next_retry:
            return
        self._meter_next_retry = now + METER_RETRY_INTERVAL
        try:
            await self.client.read_meter_info(self._meter_unit)
        except FroniusModbusError as err:
            _LOGGER.debug(
                "Smart Meter unter Unit-ID %s weiterhin nicht gefunden: %s",
                self._meter_unit,
                err,
            )
            return
        _LOGGER.info(
            "Smart Meter unter Unit-ID %s gefunden, Eintrag wird neu geladen",
            self._meter_unit,
        )
        self._meter_next_retry = None
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

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
                if not self._meter_failed:
                    _LOGGER.warning("Smart Meter antwortet nicht: %s", err)
                    self._meter_failed = True
            else:
                if self._meter_failed:
                    _LOGGER.info("Smart Meter antwortet wieder")
                    self._meter_failed = False
        elif self._meter_unit:
            await self._async_retry_meter()
        return data
