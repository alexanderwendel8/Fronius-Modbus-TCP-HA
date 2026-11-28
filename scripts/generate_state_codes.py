"""State-Code- und Event-Tabellen aus der Fronius-Dokumentation erzeugen.

Quellen (docs/fronius/archiv_1.1.7/csv/Fronius_State_Codes_Event_Flags_1_0/):
- <Familie>_State_Codes.csv   State Code -> Klartext
- EvtVnd1_4_<Familie>.csv     Bit in EvtVnd1-4 -> Fehlerklasse (Datamanager-Geräte)
Ziel: custom_components/fronius_modbus_tcp/state_codes.py

Aufruf: python3 scripts/generate_state_codes.py
"""

from __future__ import annotations

import csv
import pprint
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/fronius/archiv_1.1.7/csv/Fronius_State_Codes_Event_Flags_1_0"
DST = ROOT / "custom_components/fronius_modbus_tcp/state_codes.py"

# Reihenfolge = Priorität für die Fallback-Tabelle unbekannter Familien
FAMILIES = ["Symo", "Primo", "Galvo", "IGPlus"]


def read_state_codes(name: str) -> dict[int, str]:
    codes: dict[int, str] = {}
    with open(SRC / f"{name}_State_Codes.csv", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2 and row[0].strip().isdigit() and row[1].strip():
                codes[int(row[0])] = " ".join(row[1].split())
    return codes


def read_event_classes(name: str) -> dict[tuple[int, int], str]:
    """(Register 1-4, Bitwert) -> Fehlerklasse."""
    events: dict[tuple[int, int], str] = {}
    with open(SRC / f"EvtVnd1_4_{name}.csv", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 10 or not row[4].strip().isdigit():
                continue  # Kopfzeile / Leerzeile
            decimals = [int(v) if v.strip().isdigit() else 0 for v in row[4:8]]
            for register, value in enumerate(decimals, start=1):
                if value:
                    events[(register, value)] = " ".join(row[9].split())
    return events


def fmt(name: str, annotation: str, value: object) -> str:
    return f"{name}: {annotation} = {pprint.pformat(value, width=100, sort_dicts=True)}"


def main() -> None:
    codes = {name: read_state_codes(name) for name in FAMILIES}
    events = {name: read_event_classes(name) for name in [*FAMILIES, "All"]}
    lines = [
        '"""Fronius State Codes und Event-Klassen (Klartext) je Gerätefamilie.',
        "",
        "AUTOMATISCH ERZEUGT von scripts/generate_state_codes.py – nicht von Hand ändern.",
        "Quelle: Fronius State Codes & Event Flags 1.0 (docs/fronius/archiv_1.1.7).",
        "Texte © Fronius International GmbH, nicht unter der Projektlizenz.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    for name, table in codes.items():
        lines += [fmt(name.upper(), "dict[int, str]", table), ""]
    for name, table in events.items():
        lines += [fmt(f"EVENTS_{name.upper()}", "dict[tuple[int, int], str]", table), ""]
    lines += [
        "# Modellbezeichnung (Common Model Md) -> Tabellen",
        "FAMILIES: list[tuple[str, dict[int, str], dict[tuple[int, int], str]]] = [",
        '    ("symo", SYMO, EVENTS_SYMO),',
        '    ("primo", PRIMO, EVENTS_PRIMO),',
        '    ("galvo", GALVO, EVENTS_GALVO),',
        '    ("ig plus", IGPLUS, EVENTS_IGPLUS),',
        "]",
        "",
        "",
        "def table_for_model(model: str) -> dict[int, str]:",
        '    """State Codes zur Modellbezeichnung, sonst alle Familien zusammen."""',
        "    lower = model.lower()",
        "    for prefix, table, _ in FAMILIES:",
        "        if prefix in lower:",
        "            return table",
        "    merged: dict[int, str] = {}",
        "    for _, table, _ in reversed(FAMILIES):",
        "        merged.update(table)",
        "    return merged",
        "",
        "",
        "def events_for_model(model: str) -> dict[tuple[int, int], str]:",
        '    """EvtVnd1-4-Fehlerklassen zur Modellbezeichnung, sonst die Gesamtliste."""',
        "    lower = model.lower()",
        "    for prefix, _, events in FAMILIES:",
        "        if prefix in lower:",
        "            return events",
        "    return EVENTS_ALL",
        "",
    ]
    DST.write_text("\n".join(lines))
    print(
        f"{DST.relative_to(ROOT)}: State Codes "
        + ", ".join(f"{k} {len(v)}" for k, v in codes.items())
        + " | Events "
        + ", ".join(f"{k} {len(v)}" for k, v in events.items())
    )


if __name__ == "__main__":
    main()
