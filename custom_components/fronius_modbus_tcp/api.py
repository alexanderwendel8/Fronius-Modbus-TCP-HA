"""Asynchroner Modbus-TCP-Client für Fronius-Wechselrichter und Smart Meter (SunSpec)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from . import sunspec
from .const import (
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    METER_PROBE_TIMEOUT,
    SUNSPEC_BASE_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)

MAX_REGISTERS_PER_READ = 120


class FroniusModbusError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit dem Gerät."""


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
                f"Modbus-Fehler (Unit {unit}) beim Lesen von {address} (+{count}): {result}"
            )
        return result.registers

    async def read(self, unit: int, address: int, count: int) -> list[int]:
        """Holding-Register lesen (0-basierte Adresse), bei Bedarf in Blöcken."""
        async with self._lock:
            await self.connect()
            registers: list[int] = []
            while count > 0:
                chunk = min(count, MAX_REGISTERS_PER_READ)
                registers += await self._read_raw(unit, address, chunk)
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
            raise FroniusModbusError(f"Keine SunSpec-Kennung (Unit {unit})")

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

    async def read_inverter_info(self, unit: int) -> InverterInfo:
        """Wechselrichter erkennen: Inverter-Modell, MPPT-Module, Speicher."""
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
            raise FroniusModbusError(f"Kein Wechselrichter-Modell (Unit {unit})")

        if sunspec.STORAGE_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.STORAGE_MODEL)
            info.has_storage = sunspec.storage_available(regs)

        if sunspec.MPPT_MODEL in models:
            regs = await self.read_model(unit, models, sunspec.MPPT_MODEL)
            raw_names = sunspec.mppt_module_names(regs)
            info.mppt_roles = sunspec.mppt_roles(raw_names, info.has_storage)
            info.hybrid_storage = sunspec.ROLE_BATTERY_HYBRID in info.mppt_roles
            info.mppt_names = [
                name or f"MPPT {i}" for i, name in enumerate(raw_names, 1)
            ]
        return info

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
        raise FroniusModbusError(f"Kein Zähler-Modell (Unit {unit})")

    # --- Zyklisches Lesen ----------------------------------------------------

    async def read_inverter_data(self, info: InverterInfo) -> dict[str, Any]:
        """Alle Messwerte des Wechselrichters (inkl. MPPT und Speicher)."""
        unit, models = info.unit_id, info.models
        values: dict[str, Any] = {}

        model_id = info.inverter_model
        assert model_id is not None
        regs = await self.read_model(unit, models, model_id)
        if model_id in sunspec.INVERTER_FLOAT_MODELS:
            values.update(sunspec.parse_inverter_float(regs))
        else:
            values.update(sunspec.parse_inverter_int_sf(regs))

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

        return values

    async def read_meter_data(self, info: MeterInfo) -> dict[str, Any]:
        regs = await self.read_model(info.unit_id, info.models, info.meter_model)
        if info.meter_model in sunspec.METER_FLOAT_MODELS:
            return sunspec.parse_meter_float(regs)
        return sunspec.parse_meter_int_sf(regs)


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
                return await client.read_meter_info(unit)
            except FroniusConnectionError:
                # Kein Gerät unter dieser ID: Verbindung neu aufbauen und weiter
                await client.close()
            except (TimeoutError, FroniusModbusError):
                pass
        return None
    finally:
        await client.close()
