"""DataUpdateCoordinator für Fronius Modbus TCP."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
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

STORAGE_VERSION = 1


def structure_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Speicher für die zuletzt erkannte Gerätestruktur eines Eintrags."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


def _restore_models(data: dict[str, Any]) -> dict[str, Any]:
    """JSON macht aus den Modell-IDs Zeichenketten und aus den Tupeln Listen."""
    return {
        **data,
        "models": {int(k): (v[0], v[1]) for k, v in data["models"].items()},
    }


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
        # (Host, Port) der gemeinsamen Verbindung, gesetzt beim Einrichten
        self.client_key: tuple[str, int] = ("", 0)
        # Registry-ID des Wechselrichter-Geräts (für via_device_id der Zähler)
        self.inverter_registry_id: str | None = None
        self._inverter_unit = inverter_unit
        # Hauptzähler (Werte ohne Präfix) und weitere Zähler, je eigene Unit-ID
        self._meter_unit = meter_unit
        self._meter_units: list[int] = list(
            dict.fromkeys(u for u in (meter_unit, *(extra_meter_units or [])) if u)
        )
        self.meters: dict[int, MeterInfo] = {}
        self._meter_next_retry: datetime | None = None
        self._meter_failed: set[int] = set()
        # Gerät beim Start nicht erreichbar (z. B. nachts) → mit der zuletzt
        # erkannten Struktur gestartet; nach der ersten Antwort wird neu geladen
        self.started_from_cache = False
        self._store = structure_store(hass, entry.entry_id)
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
        cached: dict[str, Any] = {}
        try:
            self.inverter = await self.client.read_inverter_info(
                self._inverter_unit, site_registers=known
            )
        except FroniusModbusError as err:
            cached = await self._store.async_load() or {}
            if "inverter" not in cached:
                raise UpdateFailed(f"Wechselrichter nicht erkannt: {err}") from err
            # Wechselrichter schläft (nachts) oder ist kurz nicht erreichbar: mit der
            # zuletzt erkannten Struktur starten, damit die Entitäten vorhanden sind
            self.inverter = InverterInfo(**_restore_models(cached["inverter"]))
            self.started_from_cache = True
            _LOGGER.warning(
                "Wechselrichter antwortet nicht (%s); Start mit der zuletzt erkannten "
                "Gerätestruktur. Die Entitäten bleiben bis zur ersten Antwort "
                "nicht verfügbar",
                err,
            )
        if (
            not self.started_from_cache
            and known is None
            and self.inverter.site_registers_confirmed
        ):
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

        cached_meters = cached.get("meters", {})
        for unit in self._meter_units:
            try:
                self.meters[unit] = await self.client.read_meter_info(unit)
            except FroniusModbusError as err:
                if self.started_from_cache and str(unit) in cached_meters:
                    self.meters[unit] = MeterInfo(
                        **_restore_models(cached_meters[str(unit)])
                    )
                    continue
                # Zähler fehlt: Wechselrichter trotzdem einrichten, später erneut suchen
                _LOGGER.warning(
                    "Smart Meter unter Unit-ID %s nicht gefunden: %s. "
                    "Die Suche wird alle %s Minuten wiederholt",
                    unit,
                    err,
                    int(METER_RETRY_INTERVAL.total_seconds() // 60),
                )
                self._meter_next_retry = dt_util.utcnow() + METER_RETRY_INTERVAL

        if not self.started_from_cache:
            # Zähler, die gerade fehlen, aus dem bisherigen Stand behalten
            previous = (await self._store.async_load() or {}).get("meters", {})
            await self._store.async_save(
                {
                    "inverter": asdict(self.inverter),
                    "meters": {
                        **{
                            unit: data
                            for unit, data in previous.items()
                            if int(unit) in self._meter_units
                        },
                        **{str(u): asdict(m) for u, m in self.meters.items()},
                    },
                }
            )

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
        if self.started_from_cache:
            # Gerät antwortet wieder → Struktur frisch erkennen (Firmware, Module,
            # Zähler können sich geändert haben) und Entitäten neu anlegen. Erst
            # jetzt, nach allen Abfragen: Das Neuladen schließt die Verbindung.
            self.started_from_cache = False
            _LOGGER.info("Wechselrichter antwortet wieder, Eintrag wird neu geladen")
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        elif len(self.meters) < len(self._meter_units):
            await self._async_retry_meter()
        return data
