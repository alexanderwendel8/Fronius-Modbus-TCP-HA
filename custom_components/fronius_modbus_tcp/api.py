"""Schlanker asynchroner Modbus-TCP-Client für Fronius-Wechselrichter."""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass, field
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import SUNSPEC_BASE_ADDRESS

_LOGGER = logging.getLogger(__name__)


class FroniusModbusError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit dem Gerät."""


class FroniusConnectionError(FroniusModbusError):
    """Gerät nicht erreichbar."""


@dataclass
class DeviceInfo:
    """Statische Geräteinformationen aus dem SunSpec Common Model (Modell 1)."""

    manufacturer: str
    model: str
    version: str
    serial_number: str


@dataclass
class FroniusData:
    """Container für die zyklisch gelesenen Messwerte."""

    values: dict[str, Any] = field(default_factory=dict)


def _regs_to_str(registers: list[int]) -> str:
    raw = b"".join(struct.pack(">H", r) for r in registers)
    return raw.decode("ascii", errors="ignore").replace("\x00", "").strip()


def _regs_to_float32(registers: list[int]) -> float:
    return struct.unpack(">f", struct.pack(">HH", registers[0], registers[1]))[0]


class FroniusModbusClient:
    """Kapselt den Modbus-Zugriff, damit HA-Code frei von pymodbus-Details bleibt."""

    def __init__(self, host: str, port: int, unit_id: int) -> None:
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._client = AsyncModbusTcpClient(host, port=port, timeout=5)
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

    async def _read(self, address: int, count: int) -> list[int]:
        """Holding-Register lesen (0-basierte Adresse)."""
        async with self._lock:
            await self.connect()
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

    async def read_device_info(self) -> DeviceInfo:
        """SunSpec-Kennung prüfen und Common Model lesen."""
        header = await self._read(SUNSPEC_BASE_ADDRESS, 2)
        if _regs_to_str(header) != "SunS":
            raise FroniusModbusError("Keine SunSpec-Kennung gefunden")

        # Common Model: ID + Länge (2 Register), danach Mn(16), Md(16), Opt(8), Vr(8), SN(16)
        common = await self._read(SUNSPEC_BASE_ADDRESS + 2, 66)
        return DeviceInfo(
            manufacturer=_regs_to_str(common[2:18]),
            model=_regs_to_str(common[18:34]),
            version=_regs_to_str(common[42:50]),
            serial_number=_regs_to_str(common[50:66]),
        )

    async def read_data(self) -> FroniusData:
        """Zyklische Messwerte lesen.

        TODO: Registerbelegung vervollständigen. Das Beispiel geht von der
        Einstellung "float" (SunSpec-Modelle 111-113) im Wechselrichter aus;
        AC-Wirkleistung W liegt dann bei Register 40092 (1-basiert).
        Adressen bitte mit der Fronius-Modbus-Dokumentation abgleichen.
        """
        data = FroniusData()
        ac_power = await self._read(40091, 2)
        data.values["ac_power"] = round(_regs_to_float32(ac_power), 1)
        return data
