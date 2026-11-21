"""Konstanten für die Fronius Modbus TCP Integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "fronius_modbus_tcp"
MANUFACTURER: Final = "Fronius"

CONF_UNIT_ID: Final = "unit_id"
CONF_METER_UNIT_ID: Final = "meter_unit_id"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=10)

# Fronius: GEN24 ≥ 1 s, Datamanager ≥ 10 s (Antwort läuft über Solar Net)
DEFAULT_TIMEOUT: Final = 10
DEFAULT_RETRIES: Final = 1
METER_PROBE_TIMEOUT: Final = 3

# Smart-Meter-Unit-IDs: GEN24/Tauro/Verto 200 (Default), Datamanager 240 (fest)
METER_UNIT_ID_GEN24: Final = 200
METER_UNIT_ID_DATAMANAGER: Final = 240
METER_UNIT_ID_CANDIDATES: Final = [METER_UNIT_ID_GEN24, METER_UNIT_ID_DATAMANAGER]
METER_UNIT_ID_NONE: Final = 0  # im Formular: 0 = kein Smart Meter

# SunSpec-Basisadresse (0-basiert). An Adresse 40000 steht die Kennung "SunS".
SUNSPEC_BASE_ADDRESS: Final = 40000
