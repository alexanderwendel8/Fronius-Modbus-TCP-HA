"""Konstanten für die Fronius Modbus TCP Integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "fronius_modbus_tcp"
MANUFACTURER: Final = "Fronius"

CONF_UNIT_ID: Final = "unit_id"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=10)

# SunSpec-Basisadresse (0-basiert). An Adresse 40000 steht die Kennung "SunS".
SUNSPEC_BASE_ADDRESS: Final = 40000
