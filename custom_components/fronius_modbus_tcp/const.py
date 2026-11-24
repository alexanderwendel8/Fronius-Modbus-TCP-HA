"""Konstanten für die Fronius Modbus TCP Integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "fronius_modbus_tcp"
MANUFACTURER: Final = "Fronius"

CONF_UNIT_ID: Final = "unit_id"
CONF_METER_UNIT_ID: Final = "meter_unit_id"
# Weitere Smart Meter (GEN24: 201–204, Datamanager: 241–244) als Liste von Unit-IDs
CONF_EXTRA_METER_UNIT_IDS: Final = "extra_meter_unit_ids"
# Gespeichertes Erkennungsergebnis: Fronius-Register 500-513 vorhanden (Datamanager)
CONF_SITE_REGISTERS: Final = "site_registers"
# Option: schreibende Entitäten (Leistungsbegrenzung, Standby …) anlegen
CONF_ALLOW_CONTROL: Final = "allow_control"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
# Option: Abfrageintervall in Sekunden
CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 10
MIN_SCAN_INTERVAL_SECONDS: Final = 5
MAX_SCAN_INTERVAL_SECONDS: Final = 60
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)
# Die Rückfallzeit muss mehrere Abfragen überdauern, sonst endet eine Vorgabe
# zwischen zwei Abfragen: Mindestwert = Faktor × Abfrageintervall
REVERT_INTERVAL_FACTOR: Final = 3

# Fronius: GEN24 ≥ 1 s, Datamanager ≥ 10 s (Antwort läuft über Solar Net)
DEFAULT_TIMEOUT: Final = 10
DEFAULT_RETRIES: Final = 1
METER_PROBE_TIMEOUT: Final = 3

# Smart-Meter-Unit-IDs: GEN24/Tauro/Verto 200 (Default), Datamanager 240 (fest)
METER_UNIT_ID_GEN24: Final = 200
METER_UNIT_ID_DATAMANAGER: Final = 240
METER_UNIT_ID_CANDIDATES: Final = [METER_UNIT_ID_GEN24, METER_UNIT_ID_DATAMANAGER]
METER_UNIT_ID_NONE: Final = 0  # im Formular: 0 = kein Smart Meter
# Beim Start nicht gefundener Zähler: Abstand zwischen den erneuten Suchen
METER_RETRY_INTERVAL: Final = timedelta(minutes=5)

# Rückfallzeit (RvrtTms) für Vorgaben: Fällt Home Assistant aus, kehrt der
# Wechselrichter danach von selbst in den Normalbetrieb zurück. Jede Modbus-
# Nachricht startet den Timer neu, solange die Integration läuft bleibt die
# Vorgabe also aktiv (Handbuch "Zeitverhalten der unterstützten Betriebsarten").
DEFAULT_REVERT_SECONDS: Final = 300
MIN_REVERT_SECONDS: Final = 60
MAX_REVERT_SECONDS: Final = 28800

# SunSpec-Basisadresse (0-basiert). An Adresse 40000 steht die Kennung "SunS".
SUNSPEC_BASE_ADDRESS: Final = 40000
