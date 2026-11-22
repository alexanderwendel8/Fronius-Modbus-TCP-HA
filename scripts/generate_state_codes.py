"""State-Code-Tabellen aus der Fronius-Dokumentation erzeugen.

Quelle: docs/fronius/archiv_1.1.7/csv/Fronius_State_Codes_Event_Flags_1_0/<Familie>_State_Codes.csv
Ziel:   custom_components/fronius_modbus_tcp/state_codes.py

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


def read_family(name: str) -> dict[int, str]:
    codes: dict[int, str] = {}
    with open(SRC / f"{name}_State_Codes.csv", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2 and row[0].strip().isdigit() and row[1].strip():
                codes[int(row[0])] = " ".join(row[1].split())
    return codes


def main() -> None:
    tables = {name: read_family(name) for name in FAMILIES}
    lines = [
        '"""Fronius State Codes (Klartext) je Gerätefamilie.',
        "",
        "AUTOMATISCH ERZEUGT von scripts/generate_state_codes.py – nicht von Hand ändern.",
        "Quelle: Fronius State Codes & Event Flags 1.0 (docs/fronius/archiv_1.1.7).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    for name, codes in tables.items():
        lines.append(f"{name.upper()}: dict[int, str] = {pprint.pformat(codes, width=100, sort_dicts=True)}")
        lines.append("")
    lines += [
        "# Modellbezeichnung (Common Model Md) -> Tabelle; IG Plus vor IG prüfen",
        "FAMILIES: list[tuple[str, dict[int, str]]] = [",
        '    ("symo", SYMO),',
        '    ("primo", PRIMO),',
        '    ("galvo", GALVO),',
        '    ("ig plus", IGPLUS),',
        "]",
        "",
        "",
        "def table_for_model(model: str) -> dict[int, str]:",
        '    """Passende Tabelle zur Modellbezeichnung, sonst alle Familien zusammen."""',
        "    lower = model.lower()",
        "    for prefix, table in FAMILIES:",
        "        if prefix in lower:",
        "            return table",
        "    merged: dict[int, str] = {}",
        "    for _, table in reversed(FAMILIES):",
        "        merged.update(table)",
        "    return merged",
        "",
    ]
    DST.write_text("\n".join(lines))
    print(f"{DST.relative_to(ROOT)}: " + ", ".join(f"{k} {len(v)}" for k, v in tables.items()))


if __name__ == "__main__":
    main()
