"""Asynchroner Modbus-TCP-Client für Fronius-Wechselrichter (SunSpec)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from . import sunspec
from .const import SUNSPEC_BASE_ADDRESS

_LOGGER = logging.getLogger(__name__)

MAX_REGISTERS_PER_READ = 120


class FroniusModbusError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit dem Gerät."""


class FroniusConnectionError(FroniusModbusError):
    """Gerät nicht erreichbar."""


@dataclass
class DeviceInfo:
    """Geräteinformationen und erkannte SunSpec-Struktur."""

    manufacturer: str
    model: str
    version: str
    serial_number: str
    # Modell-ID -> (Startadresse des Rumpfs, Länge)
    models: dict[int, tuple[int, int]] = field(default_factory=dict)
    inverter_model: int | None = None
    phases: int = 0
    mppt_names: list[str] = field(default_factory=list)


@dataclass
class FroniusData:
    """Container für die zyklisch gelesenen Messwerte."""

    values: dict[str, Any] = field(default_factory=dict)


class FroniusModbusClient:
    """Kapselt den Modbus-Zugriff, damit HA-Code frei von pymodbus-Details bleibt."""

    def __init__(self, host: str, port: int, unit_id: int) -> None:
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._client = AsyncModbusTcpClient(host, port=port, timeout=5)
        self._lock = asyncio.Lock()
        self._device: DeviceInfo | None = None

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

    async def _read_raw(self, address: int, count: int) -> list[int]:
        try:
            try:
                result = await self._client.read_holding_registers(
                    address, count=count, device_id=self._unit_id
                )
            except TypeError:
                # pymodbus < 3.10 verwendet noch "slave"
                result = await self._client.read_holding_registers(
                    address, count=count, slave=self._unit_id
                )
        except ModbusException as err:
            raise FroniusConnectionError(str(err)) from err
        if result.isError():
            raise FroniusModbusError(
                f"Modbus-Fehler beim Lesen von {address} (+{count}): {result}"
            )
        return result.registers

    async def _read(self, address: int, count: int) -> list[int]:
        """Holding-Register lesen (0-basierte Adresse), bei Bedarf in Blöcken."""
        async with self._lock:
            await self.connect()
            registers: list[int] = []
            while count > 0:
                chunk = min(count, MAX_REGISTERS_PER_READ)
                registers += await self._read_raw(address, chunk)
                address += chunk
                count -= chunk
            return registers

    async def _scan_models(self) -> dict[int, tuple[int, int]]:
        """SunSpec-Modellkette ab Basisadresse durchlaufen."""
        header = await self._read(SUNSPEC_BASE_ADDRESS, 2)
        if sunspec.to_str(header) != "SunS":
            raise FroniusModbusError("Keine SunSpec-Kennung gefunden")

        models: dict[int, tuple[int, int]] = {}
        address = SUNSPEC_BASE_ADDRESS + 2
        for _ in range(50):  # Schutz gegen Endlosschleifen
            model_id, length = await self._read(address, 2)
            if model_id == sunspec.END_MODEL or length == 0:
                break
            # Bei mehrfach vorkommenden Modellen zählt das erste
            models.setdefault(model_id, (address + 2, length))
            address += 2 + length
        return models

    async def read_device_info(self) -> DeviceInfo:
        """Geräteinformationen lesen und Modellstruktur erkennen."""
        models = await self._scan_models()
        if sunspec.COMMON_MODEL not in models:
            raise FroniusModbusError("SunSpec Common Model fehlt")

        start, _ = models[sunspec.COMMON_MODEL]
        # Mn(16), Md(16), Opt(8), Vr(8), SN(16)
        common = await self._read(start, 64)
        info = DeviceInfo(
            manufacturer=sunspec.to_str(common[0:16]),
            model=sunspec.to_str(common[16:32]),
            version=sunspec.to_str(common[40:48]),
            serial_number=sunspec.to_str(common[48:64]),
            models=models,
        )

        for model_id, phases in (
            sunspec.INVERTER_FLOAT_MODELS | sunspec.INVERTER_INT_SF_MODELS
        ).items():
            if model_id in models:
                info.inverter_model = model_id
                info.phases = phases
                break

        if sunspec.MPPT_MODEL in models:
            start, length = models[sunspec.MPPT_MODEL]
            info.mppt_names = sunspec.mppt_module_names(await self._read(start, length))

        _LOGGER.debug("Erkannte SunSpec-Modelle: %s", models)
        self._device = info
        return info

    async def read_data(self) -> FroniusData:
        """Alle unterstützten Messwerte lesen."""
        device = self._device or await self.read_device_info()
        data = FroniusData()

        if (model_id := device.inverter_model) is not None:
            start, length = device.models[model_id]
            regs = await self._read(start, length)
            if model_id in sunspec.INVERTER_FLOAT_MODELS:
                data.values.update(sunspec.parse_inverter_float(regs))
            else:
                data.values.update(sunspec.parse_inverter_int_sf(regs))

        if device.mppt_names:
            start, length = device.models[sunspec.MPPT_MODEL]
            data.values.update(sunspec.parse_mppt(await self._read(start, length)))

        return data
