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

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FroniusConfigEntry,
        client: FroniusModbusClient,
        inverter_unit: int,
        meter_unit: int | None,
        extra_meter_units: list[int] | None = None,
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
        # Hauptzähler (Werte ohne Präfix) und weitere Zähler, je eigene Unit-ID
        self._meter_unit = meter_unit
        self._meter_units: list[int] = list(
            dict.fromkeys(u for u in (meter_unit, *(extra_meter_units or [])) if u)
        )
        self.meters: dict[int, MeterInfo] = {}
        self._meter_next_retry: datetime | None = None
        self._meter_failed: set[int] = set()
        # Rückfallzeit für Vorgaben; gesetzt/wiederhergestellt von der Number-Entität
        self.revert_seconds = max(DEFAULT_REVERT_SECONDS, self.min_revert_seconds)

    @property
    def meter(self) -> MeterInfo | None:
        """Hauptzähler (am Netzanschlusspunkt), falls eingerichtet und gefunden."""
        return self.meters.get(self._meter_unit) if self._meter_unit else None

    def meter_key_prefix(self, meter: MeterInfo) -> str:
        """Präfix der Werte eines Zählers: leer für den Hauptzähler, sonst "<Unit-ID>:"."""
        return "" if meter.unit_id == self._meter_unit else f"{meter.unit_id}:"

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

    async def async_apply_revert_time(self) -> None:
        """Geänderte Rückfallzeit an alle gerade aktiven Vorgaben übertragen.

        Ohne das gälte der neue Wert erst beim nächsten Schreiben; eine laufende
        Vorgabe behielte bis dahin die alte Rückfallzeit. Grundlage ist der
        zuletzt gelesene Stand. Laut Handbuch ("Ändern der Rückkehrzeit bei
        aktiver Leistungsreduktion") wird die Zeit gesetzt und die Betriebsart
        mit Ena = 1 erneut gestartet.
        """
        values = self.data.values if self.data else {}
        revert = self.revert_seconds
        if self.control_allowed:
            percent = values.get("power_limit")
            if values.get("power_limit_active") is True and percent is not None:
                await self.client.set_power_limit(
                    self.inverter, percent, enabled=True, revert_seconds=revert
                )
            if values.get("feed_in_enabled") is False:
                await self.client.set_feed_in(
                    self.inverter, False, revert_seconds=revert
                )
        if self.storage_control_allowed and (
            values.get("battery_charge_limit_active")
            or values.get("battery_discharge_limit_active")
        ):
            # ohne weitere Angaben schreibt set_storage_limits nur die Rückfallzeit
            await self.client.set_storage_limits(self.inverter, revert_seconds=revert)

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

        for unit in self._meter_units:
            try:
                self.meters[unit] = await self.client.read_meter_info(unit)
            except FroniusModbusError as err:
                # Zähler fehlt: Wechselrichter trotzdem einrichten, später erneut suchen
                _LOGGER.warning(
                    "Smart Meter unter Unit-ID %s nicht gefunden: %s. "
                    "Die Suche wird alle %s Minuten wiederholt",
                    unit,
                    err,
                    int(METER_RETRY_INTERVAL.total_seconds() // 60),
                )
                self._meter_next_retry = dt_util.utcnow() + METER_RETRY_INTERVAL

    async def _async_retry_meter(self) -> None:
        """Beim Start nicht gefundene Zähler erneut suchen.

        Wird einer gefunden, lädt der Eintrag neu, damit seine Entitäten
        angelegt werden.
        """
        now = dt_util.utcnow()
        if self._meter_next_retry is None or now < self._meter_next_retry:
            return
        self._meter_next_retry = now + METER_RETRY_INTERVAL
        found = False
        for unit in self._meter_units:
            if unit in self.meters:
                continue
            try:
                await self.client.read_meter_info(unit)
            except FroniusModbusError as err:
                _LOGGER.debug(
                    "Smart Meter unter Unit-ID %s weiterhin nicht gefunden: %s",
                    unit,
                    err,
                )
                continue
            _LOGGER.info(
                "Smart Meter unter Unit-ID %s gefunden, Eintrag wird neu geladen", unit
            )
            found = True
        if found:
            self._meter_next_retry = None
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def _async_update_data(self) -> FroniusData:
        data = FroniusData()
        try:
            data.values.update(await self.client.read_inverter_data(self.inverter))
        except FroniusModbusError as err:
            raise UpdateFailed(f"Fehler beim Lesen des Wechselrichters: {err}") from err

        for unit, meter in self.meters.items():
            prefix = self.meter_key_prefix(meter)
            try:
                values = await self.client.read_meter_data(meter)
            except FroniusModbusError as err:
                # Entitäten dieses Zählers werden unavailable, der Rest bleibt verfügbar
                if unit not in self._meter_failed:
                    _LOGGER.warning(
                        "Smart Meter (Unit-ID %s) antwortet nicht: %s", unit, err
                    )
                    self._meter_failed.add(unit)
            else:
                data.values.update({f"{prefix}{k}": v for k, v in values.items()})
                if unit in self._meter_failed:
                    _LOGGER.info("Smart Meter (Unit-ID %s) antwortet wieder", unit)
                    self._meter_failed.discard(unit)
        if len(self.meters) < len(self._meter_units):
            await self._async_retry_meter()
        return data
