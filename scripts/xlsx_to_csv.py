"""Fronius-Registerkarten (xlsx) blattweise als CSV exportieren.

Erzeugt für jede Arbeitsmappe einen Ordner unter csv/ mit einer CSV-Datei je Blatt,
damit die Tabellen per grep durchsuchbar sind. Ordner- und Dateinamen: Sonderzeichen
und Leerzeichen werden zu "_" (z. B. "ac_meter (21x)" -> ac_meter_21x.csv).

Aufruf: python3 scripts/xlsx_to_csv.py docs/fronius/archiv_1.1.7/original/<Datei>.xlsx ...
Ausgabe: docs/fronius/<archiv>/csv/<Mappe>/<Blatt>.csv
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import openpyxl


def name(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_")


def wert(zelle: object) -> object:
    # Ganzzahlige Gleitkommawerte wie in Excel ohne ".0" ausgeben
    if isinstance(zelle, float) and zelle.is_integer():
        return int(zelle)
    if isinstance(zelle, str):
        return zelle.strip()
    return "" if zelle is None else zelle


def export(xlsx: Path) -> Path:
    ziel = xlsx.parent.parent / "csv" / name(xlsx.stem)
    ziel.mkdir(parents=True, exist_ok=True)
    mappe = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    for blatt in mappe.worksheets:
        zeilen = []
        for zeile in blatt.iter_rows(values_only=True):
            werte = [wert(z) for z in zeile]
            while werte and werte[-1] == "":  # leere Zellen am Zeilenende weglassen
                werte.pop()
            zeilen.append(werte)
        while zeilen and not zeilen[-1]:
            zeilen.pop()
        with (ziel / f"{name(blatt.title)}.csv").open("w", newline="", encoding="utf-8") as datei:
            csv.writer(datei).writerows(zeilen)
    return ziel


if __name__ == "__main__":
    for pfad in sys.argv[1:]:
        print(export(Path(pfad)))
