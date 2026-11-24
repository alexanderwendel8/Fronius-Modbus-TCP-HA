"""Diagnosedaten für Fronius Modbus TCP."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import FroniusConfigEntry

TO_REDACT = {CONF_HOST, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FroniusConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    meter = coordinator.meter
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "inverter": async_redact_data(asdict(coordinator.inverter), TO_REDACT),
        "meter": async_redact_data(asdict(meter), TO_REDACT) if meter else None,
        "extra_meters": [
            async_redact_data(asdict(m), TO_REDACT)
            for m in coordinator.meters.values()
            if m is not meter
        ],
        "values": coordinator.data.values if coordinator.data else None,
    }
