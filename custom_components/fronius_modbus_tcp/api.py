"""Asynchroner Modbus-TCP-Client für Fronius-Wechselrichter und Smart Meter (SunSpec)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from . import state_codes, sunspec
from .const import (
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    METER_PROBE_TIMEOUT,
    SUNSPEC_BASE_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)

MAX_REGISTERS_PER_READ = 120


# Modbus-Exception-Codes, die "Funktion/Adresse gibt es nicht" bedeuten – im
# Unterschied zu vorübergehenden Fehlern (Gerät beschäftigt, Gateway-Timeout …)
EXC_ILLEGAL_FUNCTION = 1
EXC_ILLEGAL_ADDRESS = 2


class FroniusModbusError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit dem Gerät."""

    def __init__(self, message: str, exception_code: int | None = None) -> None:
        super().__init__(message)
        # Code der Modbus-Fehlerantwort, None bei anderen Fehlern
        self.exception_code = exception_code


class FroniusConnectionError(FroniusModbusError):
    """Gerät nicht erreichbar."""


@dataclass
class SunSpecDeviceInfo:
    """Common Model (1) und erkannte Modellkette eines Modbus-Geräts."""

    unit_id: int
    manufacturer: str
    model: str
    options: str
    version: str
    serial_number: str
    # Modell-ID -> (Startadresse des Rumpfs, Länge)
    models: dict[int, tuple[int, int]] = field(default_factory=dict)


@dataclass
class InverterInfo(SunSpecDeviceInfo):
    """Wechselrichter inklusive Speicher- und MPPT-Struktur."""

    inverter_model: int | None = None
    phases: int = 0
    mppt_names: list[str] = field(default_factory=list)
    mppt_roles: list[str] = field(default_factory=list)
    has_storage: bool = False
    hybrid_storage: bool = False
    # Fronius-Register 214 (State Code) und 500-513 (Anlagensummen) – nur Datamanager
    has_site_registers: bool = False
    # False: Ergebnis nicht eindeutig (Gerät hat auf die Probe nicht geantwortet)
    # → nicht dauerhaft speichern, beim nächsten Start erneut prüfen
    site_registers_confirmed: bool = True
    # Nennwerte aus Modell 120 (statisch, einmal beim Start gelesen)
    nameplate: dict[str, Any] = field(default_factory=dict)

    @property
    def has_battery(self) -> bool:
        return self.has_storage or any(
            role != sunspec.ROLE_PV for role in self.mppt_roles
        )


@dataclass
class MeterInfo(SunSpecDeviceInfo):
    """Fronius Smart Meter (eigene Unit-ID)."""

    meter_model: int = 0
    phases: int = 0


@dataclass
class FroniusData:
    """Container für die zyklisch gelesenen Messwerte."""

    values: dict[str, Any] = field(default_factory=dict)


class FroniusModbusClient:
    """Kapselt den Modbus-Zugriff, damit HA-Code frei von pymodbus-Details bleibt.

    Eine TCP-Verbindung bedient mehrere Unit-IDs (Wechselrichter, Smart Meter).
    Zugriffe laufen über einen Lock strikt nacheinander (Vorgabe Fronius).
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self._host = host
        self._port = port
        self._client = AsyncModbusTcpClient(
            host, port=port, timeout=timeout, retries=retries
        )
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Verbindung aufbauen (falls noch nicht verbunden)."""
        if self._client.connected:
            return
        if not await self._client.connect():
            raise FroniusConnectionError(
                f"Verbindung zu {self._host}:{self._port} fehlgeschlagen"
            )

    async def close(self) -> None:
        """Verbindung schließen."""
        self._client.close()

    async def _read_raw(self, unit: int, address: int, count: int) -> list[int]:
        try:
            try:
                result = await self._client.read_holding_registers(
                    address, count=count, device_id=unit
                )
            except TypeError:
                # pymodbus < 3.10 verwendet noch "slave"
                result = await self._client.read_holding_registers(
                    address, count=count, slave=unit
                )
        except ModbusException as err:
            raise FroniusConnectionError(str(err)) from err
        if result.isError():
            raise FroniusModbusError(
                f"Modbus-Fehler (Unit {unit}) beim Lesen von {address} (+{count}): {result}",
                getattr(result, "exception_code", None),
            )
        return result.registers

    async def _write_raw(self, unit: int, address: int, values: list[int]) -> None:
        try:
            try:
                result = await self._client.write_registers(
                    address, values=values, device_id=unit
                )
            except TypeError:
                # pymodbus < 3.10 verwendet noch "slave"
                result = await self._client.write_registers(
                    address, values=values, slave=unit
                )
        except ModbusException as err:
            raise FroniusConnectionError(str(err)) from err
        if result.isError():
            raise FroniusModbusError(
                f"Modbus-Fehler (Unit {unit}) beim Schreiben von {address} "
                f"({values}): {result}"
            )

    async def write(self, unit: int, address: int, values: list[int]) -> None:
        """Holding-Register schreiben (0-basierte Adresse, Funktionscode 0x10)."""
        async with self._lock:
            await self.connect()
            _LOGGER.debug("Unit %s: schreibe %s ab Adresse %s", unit, values, address)
            await self._write_raw(unit, address, values)

    async def read(self, unit: int, address: int, count: int) -> list[int]:
        """Holding-Register lesen (0-basierte Adresse), bei Bedarf in Blöcken."""
        async with self._lock:
            await self.connect()
            registers: list[int] = []
            while count > 0:
                chunk = min(count, MAX_REGISTERS_PER_READ)
                regs = await self._read_raw(unit, address, chunk)
                if len(regs) != chunk:
                    raise FroniusModbusError(
                        f"Unvollständige Antwort (Unit {unit}) beim Lesen von "
                        f"{address}: {len(regs)} statt {chunk} Register"
                    )
                registers += regs
                address += chunk
                count -= chunk
            return registers

    async def read_model(
        self, unit: int, models: dict[int, tuple[int, int]], model_id: int
    ) -> list[int]:
        start, length = models[model_id]
        return await self.read(unit, start, length)

    # --- Erkennung -----------------------------------------------------------

    async def scan_models(self, unit: int) -> dict[int, tuple[int, int]]:
        """SunSpec-Modellkette ab Basisadresse durchlaufen."""
        header = await self.read(unit, SUNSPEC_BASE_ADDRESS, 2)
        if sunspec.to_str(header) != "SunS":
            raise FroniusModbusError(
                f"Keine SunSpec-Kennung an Register 40001 (Unit {unit}): "
                f"gelesen {sunspec.to_str(header)!r} {[hex(r) for r in header]} statt 'SunS'"
            )

        models: dict[int, tuple[int, int]] = {}
        address = SUNSPEC_BASE_ADDRESS + 2
        for _ in range(50):  # Schutz gegen Endlosschleifen
            model_id, length = await self.read(unit, address, 2)
            if model_id == sunspec.END_MODEL or length == 0:
                break
            # Bei mehrfach vorkommenden Modellen zählt das erste
            models.setdefault(model_id, (address + 2, length))
            address += 2 + length
        if sunspec.COMMON_MODEL not in models:
            raise FroniusModbusError(f"SunSpec Common Model fehlt (Unit {unit})")
        # Zu kurze Modelle würden die Parser mit einem IndexError abbrechen lassen
        # und damit die gesamte Abfrage – sie werden wie "nicht vorhanden" behandelt.
        for model_id, (_, length) in list(models.items()):
            minimum = sunspec.MIN_MODEL_LENGTH.get(model_id, 0)
            if length < minimum:
                _LOGGER.warning(
                    "Unit %s: SunSpec-Modell %s ist mit %s Registern kürzer als "
                    "erwartet (mindestens %s) und wird nicht ausgewertet",
                    unit, model_id, length, minimum,
                )
                del models[model_id]
        _LOGGER.debug("Unit %s: erkannte SunSpec-Modelle %s", unit, models)
        return models

    async def _read_common(
        self, unit: int, models: dict[int, tuple[int, int]]
    ) -> dict[str, Any]:
        start, _ = models[sunspec.COMMON_MODEL]
        # Mn(16), Md(16), Opt(8), Vr(8), SN(16)
        common = await self.read(unit, start, 64)
        return {
            "unit_id": unit,
            "manufacturer": sunspec.to_str(common[0:16]),
            "model": sunspec.to_str(common[16:32]),
            "options": sunspec.to_str(common[32:40]),
            "version": sunspec.to_str(common[40:48]),
            "serial_number": sunspec.to_str(common[48:64]),
            "models": models,
        }

    async def read_inverter_info(
        self, unit: int, site_registers: bool | None = None
    ) -> InverterInfo:
        """Wechselrichter erkennen: Inverter-Modell, MPPT-Module, Speicher.

        site_registers: bereits bekanntes Ergebnis der Prüfung auf die
        Fronius-Register (aus dem Config-Eintrag); None = jetzt prüfen.
        """
        models = await self.scan_models(unit)
        info = InverterInfo(**await self._read_common(unit, models))

        # float zuerst prüfen (Argeno liefert 103 und 113 gleichzeitig)
        for model_id, phases in (
            sunspec.INVERTER_FLOAT_MODELS | sunspec.INVERTER_INT_SF_MODELS
        ).items():
            if model_id in models:
                info.inverter_model = model_id
                info.phases = phases
                break
        if info.inverter_model is None:
            raise FroniusModbusError(
                f"Kein Wechselrichter-Modell 101-103/111-113 (Unit {unit}), "
                f"gefundene Modelle: {sorted(models)}"
            )

        if sunspec.STORAGE_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.STORAGE_MODEL)
            info.has_storage = sunspec.storage_available(regs)

        if sunspec.MPPT_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.MPPT_MODEL)
            if not sunspec.mppt_complete(regs):
                _LOGGER.warning(
                    "Unit %s: Modell 160 kündigt %s Module an, ist aber nur %s "
                    "Register lang – MPPT-Werte werden nicht ausgewertet",
                    unit, sunspec.mppt_module_count(regs), len(regs),
                )
                del models[sunspec.MPPT_MODEL]
        if sunspec.MPPT_MODEL in models:
            raw_names = sunspec.mppt_module_names(regs)
            info.mppt_roles = sunspec.mppt_roles(raw_names, info.has_storage)
            info.hybrid_storage = sunspec.ROLE_BATTERY_HYBRID in info.mppt_roles
            info.mppt_names = [
                name or f"MPPT {i}" for i, name in enumerate(raw_names, 1)
            ]

        if sunspec.NAMEPLATE_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.NAMEPLATE_MODEL)
            info.nameplate = sunspec.parse_nameplate(regs)

        if site_registers is None:
            (
                info.has_site_registers,
                info.site_registers_confirmed,
            ) = await self._probe_site_registers(unit)
        else:
            info.has_site_registers = site_registers
        return info

    async def _probe_site_registers(self, unit: int) -> tuple[bool, bool]:
        """Prüfen, ob es die Fronius-Register 500-513 gibt (nur Datamanager).

        Rückgabe (vorhanden, eindeutig). Davon hängt ab, wie EvtVnd1-4 gedeutet
        werden und ob State Code und Anlagensummen gelesen werden – ein
        vorübergehender Fehler darf deshalb nicht als "nicht vorhanden" zählen:

        - Antwort mit Daten → vorhanden.
        - Fehlerantwort "unzulässige Adresse/Funktion" → nicht vorhanden
          (GEN24, Tauro, Verto).
        - Andere Fehlerantwort (Gerät beschäftigt …) → einmal wiederholen, dann
          Fehler melden; die Einrichtung wird später erneut versucht.
        - Keine Antwort, Gerät aber sonst erreichbar → nicht vorhanden, jedoch
          nicht eindeutig (wird beim nächsten Start erneut geprüft).
        """
        last_error: FroniusModbusError | None = None
        for _ in range(2):
            try:
                await self.read(
                    unit, sunspec.FRONIUS_SITE_ADDRESS, sunspec.FRONIUS_SITE_COUNT
                )
            except FroniusConnectionError as err:
                # Lebt das Gerät noch? Sonst ist es ein Verbindungsproblem.
                await self.close()
                await self.read(unit, SUNSPEC_BASE_ADDRESS, 2)
                _LOGGER.debug(
                    "Unit %s: keine Antwort auf Fronius-Register 500-513 (%s), "
                    "Gerät sonst erreichbar → als nicht vorhanden gewertet",
                    unit,
                    err,
                )
                return False, False
            except FroniusModbusError as err:
                if err.exception_code in (EXC_ILLEGAL_FUNCTION, EXC_ILLEGAL_ADDRESS):
                    _LOGGER.debug(
                        "Unit %s: keine Fronius-Register 500-513 (%s)", unit, err
                    )
                    return False, True
                last_error = err
            else:
                return True, True
        raise FroniusModbusError(
            f"Fronius-Register 500-513 (Unit {unit}) nicht prüfbar: {last_error}",
            last_error.exception_code if last_error else None,
        )

    async def read_meter_info(self, unit: int) -> MeterInfo:
        """Smart Meter unter der angegebenen Unit-ID erkennen."""
        models = await self.scan_models(unit)
        for model_id, phases in (
            sunspec.METER_FLOAT_MODELS | sunspec.METER_INT_SF_MODELS
        ).items():
            if model_id in models:
                return MeterInfo(
                    **await self._read_common(unit, models),
                    meter_model=model_id,
                    phases=phases,
                )
        raise FroniusModbusError(
            f"Kein Zähler-Modell 201-204/211-214 (Unit {unit}), "
            f"gefundene Modelle: {sorted(models)}"
        )

    # --- Zyklisches Lesen ----------------------------------------------------

    async def read_inverter_data(self, info: InverterInfo) -> dict[str, Any]:
        """Alle Messwerte des Wechselrichters (inkl. MPPT und Speicher)."""
        unit, models = info.unit_id, info.models
        values: dict[str, Any] = dict(info.nameplate)

        model_id = info.inverter_model
        assert model_id is not None
        regs = await self.read_model(unit, models, model_id)
        if model_id in sunspec.INVERTER_FLOAT_MODELS:
            values.update(sunspec.parse_inverter_float(regs))
        else:
            values.update(sunspec.parse_inverter_int_sf(regs))

        values.update(sunspec.parse_event_message(values["events"]))

        # EvtVnd1-4: Bedeutung hängt von der Gerätegeneration ab (CLAUDE.md)
        evt_vnd = values["evt_vnd"]
        if info.has_site_registers:
            values.update(
                sunspec.parse_vendor_event_classes(
                    evt_vnd, state_codes.events_for_model(info.model)
                )
            )
        else:
            values.update(sunspec.parse_severity_events(evt_vnd))

        if info.mppt_roles:
            regs = await self.read_model(unit, models, sunspec.MPPT_MODEL)
            values.update(
                sunspec.combine_mppt(
                    sunspec.parse_mppt(regs), info.mppt_roles, values.get("dc_power")
                )
            )

        if info.has_storage:
            regs = await self.read_model(unit, models, sunspec.STORAGE_MODEL)
            values.update(sunspec.parse_storage(regs))

        if sunspec.CONTROLS_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.CONTROLS_MODEL)
            values.update(sunspec.parse_controls(regs))

        if sunspec.STATUS_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.STATUS_MODEL)
            values.update(sunspec.parse_status(regs))

        if info.has_site_registers:
            regs = await self.read(
                unit, sunspec.FRONIUS_SITE_ADDRESS, sunspec.FRONIUS_SITE_COUNT
            )
            values.update(sunspec.parse_fronius_site(regs))
            (reg,) = await self.read(unit, sunspec.FRONIUS_STATE_CODE_ADDRESS, 1)
            values.update(
                sunspec.parse_fronius_state_code(
                    reg, state_codes.table_for_model(info.model)
                )
            )

        return values

    async def read_meter_data(self, info: MeterInfo) -> dict[str, Any]:
        regs = await self.read_model(info.unit_id, info.models, info.meter_model)
        if info.meter_model in sunspec.METER_FLOAT_MODELS:
            return sunspec.parse_meter_float(regs)
        return sunspec.parse_meter_int_sf(regs)


    # --- Steuerung (nur mit Option "Steuerung erlauben") ---------------------

    def _controls_start(self, info: InverterInfo) -> int:
        if sunspec.CONTROLS_MODEL not in info.models:
            raise FroniusModbusError("Gerät hat kein Modell 123 (Immediate Controls)")
        return info.models[sunspec.CONTROLS_MODEL][0]

    async def set_power_limit(
        self, info: InverterInfo, percent: float, *, enabled: bool, revert_seconds: int
    ) -> None:
        """Leistungsbegrenzung setzen; mit enabled=True wird sie (erneut) gestartet.

        Der Skalierungsfaktor wird vorher frisch gelesen (kann sich ändern).
        """
        start = self._controls_start(info)
        regs = await self.read_model(info.unit_id, info.models, sunspec.CONTROLS_MODEL)
        sf = sunspec.to_int16(regs[sunspec.CTRL_WMAXLIMPCT_SF])
        values = sunspec.encode_power_limit(percent, sf, revert_seconds, enabled)
        await self.write(info.unit_id, start + sunspec.CTRL_WMAXLIMPCT, values)

    async def disable_power_limit(self, info: InverterInfo) -> None:
        """Leistungsbegrenzung beenden (WMaxLim_Ena = 0)."""
        start = self._controls_start(info)
        await self.write(info.unit_id, start + sunspec.CTRL_WMAXLIM_ENA, [0])

    async def set_feed_in(
        self, info: InverterInfo, enabled: bool, *, revert_seconds: int
    ) -> None:
        """Einspeisung ein (Conn = 1) oder Standby (Conn = 0) mit Rückfallzeit."""
        start = self._controls_start(info)
        await self.write(
            info.unit_id,
            start + sunspec.CTRL_CONN_WIN_TMS,
            sunspec.encode_feed_in(enabled, revert_seconds),
        )

    async def reset_events(self, info: InverterInfo) -> None:
        """Event Flags und State Code zurücksetzen (nur Datamanager, Register 215)."""
        if not info.has_site_registers:
            raise FroniusModbusError("Ereignisse zurücksetzen nur beim Datamanager")
        await self.write(
            info.unit_id,
            sunspec.FRONIUS_RESET_EVENTS_ADDRESS,
            [sunspec.FRONIUS_RESET_VALUE],
        )


async def async_detect_meter(
    host: str, port: int, candidates: list[int]
) -> MeterInfo | None:
    """Smart Meter unter den Kandidaten-Unit-IDs suchen (kurzer Timeout).

    GEN24/Tauro/Verto: 200 (Default), Datamanager: 240 (fest).
    """
    client = FroniusModbusClient(
        host, port, timeout=METER_PROBE_TIMEOUT, retries=0
    )
    try:
        for unit in candidates:
            try:
                meter = await client.read_meter_info(unit)
            except FroniusConnectionError as err:
                # Kein Gerät unter dieser ID: Verbindung neu aufbauen und weiter
                _LOGGER.debug("Zählersuche %s:%s Unit %s: %s", host, port, unit, err)
                await client.close()
            except (TimeoutError, FroniusModbusError) as err:
                _LOGGER.debug("Zählersuche %s:%s Unit %s: %s", host, port, unit, err)
            else:
                _LOGGER.info(
                    "Smart Meter %s %s (Modell %s) unter Unit-ID %s gefunden",
                    meter.manufacturer, meter.model, meter.meter_model, unit,
                )
                return meter
        _LOGGER.info(
            "Kein Smart Meter unter %s:%s gefunden (geprüft: Unit-IDs %s)",
            host, port, candidates,
        )
        return None
    finally:
        await client.close()
