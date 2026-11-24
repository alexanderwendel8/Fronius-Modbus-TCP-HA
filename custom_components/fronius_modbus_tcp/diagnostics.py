"""Diagnosedaten für Fronius Modbus TCP.

Neben den dekodierten Werten enthält der Download die rohen Register aller
SunSpec-Modelle. Damit lässt sich ein fremdes Gerät aus der Ferne nachvollziehen,
auch Modelle, die die Integration (noch) nicht auswertet.
"""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import sunspec
from .api import FroniusModbusClient, FroniusModbusError, SunSpecDeviceInfo
from .coordinator import FroniusConfigEntry, FroniusCoordinator, structure_store

TO_REDACT = {CONF_HOST, "serial_number"}

# Seriennummer im Common Model: Register 48–63 des Rumpfs (SN, 16 Register)
_COMMON_SN = slice(48, 64)
# Fronius-Register der Datamanager-Geräte: (0-basierte Adresse, Anzahl)
_FRONIUS_BLOCKS = {
    "212-216": (211, 5),
    "500-513": (sunspec.FRONIUS_SITE_ADDRESS, sunspec.FRONIUS_SITE_COUNT),
}


def _hex(regs: list[int]) -> str:
    """Register als zusammenhängende Hex-Zeichenkette (4 Zeichen je Register)."""
    return "".join(f"{reg:04X}" for reg in regs)


async def _raw_models(
    client: FroniusModbusClient, info: SunSpecDeviceInfo
) -> dict[str, Any]:
    """Rohe Register aller Modelle eines Geräts; Lesefehler je Modell vermerkt."""
    raw: dict[str, Any] = {}
    for model_id, (start, length) in sorted(info.models.items()):
        entry: dict[str, Any] = {"start": start, "length": length}
        try:
            regs = await client.read(info.unit_id, start, length)
        except FroniusModbusError as err:
            entry["error"] = str(err)
        else:
            if model_id == sunspec.COMMON_MODEL:
                regs[_COMMON_SN] = [0] * len(regs[_COMMON_SN])
                entry["note"] = "serial number zeroed"
            entry["registers"] = _hex(regs)
        raw[str(model_id)] = entry
    return raw


async def _raw_fronius(client: FroniusModbusClient, unit: int) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for name, (address, count) in _FRONIUS_BLOCKS.items():
        try:
            raw[name] = _hex(await client.read(unit, address, count))
        except FroniusModbusError as err:
            raw[name] = {"error": str(err)}
    return raw


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


async def _not_loaded(hass: HomeAssistant, entry: FroniusConfigEntry) -> dict[str, Any]:
    """Eintrag nicht geladen (z. B. Gerät beim Start nicht erreichbar).

    Ohne laufende Abfrage gibt es keine Werte und keine Rohregister. Geliefert
    wird, was für die Fehlersuche trotzdem hilft: Eintrag, Zustand samt
    Fehlermeldung und die zuletzt gespeicherte Gerätestruktur.
    """
    stored = await structure_store(hass, entry.entry_id).async_load()
    # Die Fehlermeldung nennt den Host ("Verbindung zu <host>:502 fehlgeschlagen")
    reason = entry.reason
    host = entry.data.get(CONF_HOST)
    if reason and host:
        reason = reason.replace(str(host), "**REDACTED**")
    return {
        "loaded": False,
        "state": entry.state.value,
        "reason": reason,
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "pymodbus": _package_version("pymodbus"),
        "stored_structure": async_redact_data(stored, TO_REDACT) if stored else None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FroniusConfigEntry
) -> dict[str, Any]:
    coordinator: FroniusCoordinator | None = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return await _not_loaded(hass, entry)
    client = coordinator.client
    inverter = coordinator.inverter
    primary = coordinator.meter

    raw: dict[str, Any] = {"inverter": await _raw_models(client, inverter)}
    if inverter.has_site_registers:
        raw["fronius_registers"] = await _raw_fronius(client, inverter.unit_id)
    raw["meters"] = {
        str(unit): await _raw_models(client, meter)
        for unit, meter in coordinator.meters.items()
    }

    return {
        "loaded": True,
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "pymodbus": _package_version("pymodbus"),
        "scan_interval": coordinator.scan_interval_seconds,
        "last_update_success": coordinator.last_update_success,
        "inverter": async_redact_data(asdict(inverter), TO_REDACT),
        "meter": async_redact_data(asdict(primary), TO_REDACT) if primary else None,
        "extra_meters": [
            async_redact_data(asdict(m), TO_REDACT)
            for m in coordinator.meters.values()
            if m is not primary
        ],
        "values": coordinator.data.values if coordinator.data else None,
        # Hex, 4 Zeichen je Register, ab dem Rumpf des Modells (ohne ID und Länge)
        "raw_registers": raw,
    }
