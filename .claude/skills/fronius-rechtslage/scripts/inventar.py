#!/usr/bin/env python3
"""Inventar der Fronius-Unterlagen im Repository mit Rechte- und Herkunftsvermerken.

Listet jede Datei unter docs/fronius/ (Originale und daraus abgeleitete CSV-/Textfassungen)
und sucht in den Originalen nach Vermerken zu Urheberrecht, Weitergabe und Vertraulichkeit:
- PDF: Metadaten (pdfinfo) und Volltext (pdftotext, sonst die Textfassung unter text/)
- xlsx: Dokumenteigenschaften (docProps) und alle Zellentexte
- txt/csv/json: Inhalt

Nur Standardbibliothek plus optional poppler-utils (pdfinfo/pdftotext).
Aufruf: python3 inventar.py [Repo-Wurzel] > inventar.md
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Begriffe, die auf Rechte, Weitergabebedingungen oder Vertraulichkeit hinweisen
MUSTER = re.compile(
    r"copyright|©|\(c\)\s*\d{4}|all rights reserved|alle rechte|urheber|"
    r"vervielfältig|nachdruck|reproduc|redistribut|weitergabe|weiterverbreit|"
    r"confidential|vertraulich|proprietary|licen[cs]e|lizenz|nutzungsbedingung|"
    r"terms of use|disclaimer|trademark|\bmarken?\b",
    re.IGNORECASE,
)
# Fehlalarme: Gerätebegriffe, die nur zufällig passen
IGNORIEREN = re.compile(r"markieren|markiert|license plate", re.IGNORECASE)


def treffer(text: str, quelle: str, limit: int = 12) -> list[str]:
    """Zeilen mit Rechtebegriffen, gekürzt und ohne Dubletten."""
    gefunden: list[str] = []
    for zeile in text.splitlines():
        zeile = " ".join(zeile.split())
        if not zeile or not MUSTER.search(zeile) or IGNORIEREN.search(zeile):
            continue
        eintrag = f"{quelle}: {zeile[:200]}"
        if eintrag not in gefunden:
            gefunden.append(eintrag)
        if len(gefunden) >= limit:
            break
    return gefunden


def pdf_vermerke(pfad: Path, wurzel: Path) -> list[str]:
    ergebnis: list[str] = []
    if shutil.which("pdfinfo"):
        info = subprocess.run(
            ["pdfinfo", str(pfad)], capture_output=True, text=True, check=False
        ).stdout
        for zeile in info.splitlines():
            if zeile.split(":", 1)[0] in ("Title", "Author", "Creator", "Producer",
                                          "CreationDate", "Subject", "Keywords"):
                ergebnis.append(f"Metadaten: {' '.join(zeile.split())}")
    text = ""
    if shutil.which("pdftotext"):
        text = subprocess.run(
            ["pdftotext", "-layout", str(pfad), "-"],
            capture_output=True, text=True, check=False,
        ).stdout
    if not text:
        fassung = pfad.parent.parent / "text" / (pfad.stem + ".txt")
        if fassung.exists():
            text = fassung.read_text(encoding="utf-8", errors="replace")
    ergebnis += treffer(text, "Text")
    return ergebnis


def xlsx_vermerke(pfad: Path) -> list[str]:
    ergebnis: list[str] = []
    with zipfile.ZipFile(pfad) as archiv:
        namen = archiv.namelist()
        for teil in ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml"):
            if teil not in namen:
                continue
            xml = archiv.read(teil).decode("utf-8", errors="replace")
            for tag in ("title", "creator", "Company", "Manager", "subject",
                        "description", "keywords", "lastModifiedBy"):
                for wert in re.findall(rf"<(?:\w+:)?{tag}>([^<]+)</", xml):
                    ergebnis.append(f"Eigenschaft {tag}: {wert.strip()[:200]}")
        zellen = []
        for teil in namen:
            if teil == "xl/sharedStrings.xml" or teil.startswith("xl/worksheets/"):
                xml = archiv.read(teil).decode("utf-8", errors="replace")
                zellen += re.findall(r"<t[^>]*>([^<]*)</t>", xml)
        ergebnis += treffer("\n".join(zellen), "Zelle")
    return ergebnis


def text_vermerke(pfad: Path) -> list[str]:
    return treffer(pfad.read_text(encoding="utf-8", errors="replace"), "Inhalt")


def main() -> None:
    wurzel = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    basis = wurzel / "docs" / "fronius"
    originale = sorted(p for p in basis.glob("*/original/*") if p.is_file())
    abgeleitet = sorted(
        p for p in basis.rglob("*")
        if p.is_file() and "original" not in p.parts and p.suffix in (".csv", ".txt")
    )
    eigene = sorted(p for p in basis.rglob("README.md"))

    print("# Inventar Fronius-Unterlagen\n")
    print(f"- Originale: {len(originale)}")
    print(f"- Abgeleitete Fassungen (CSV/Text aus den Originalen): {len(abgeleitet)}")
    print(f"- Eigene Zusammenfassungen (README.md): {len(eigene)}\n")

    print("## Originale\n")
    print("| Datei | Größe | SHA-256 (gekürzt) |")
    print("|---|---|---|")
    for p in originale:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        print(f"| `{p.relative_to(wurzel)}` | {p.stat().st_size // 1024} KiB | `{digest}` |")

    print("\n## Gefundene Vermerke je Original\n")
    for p in originale:
        if p.suffix.lower() == ".pdf":
            vermerke = pdf_vermerke(p, wurzel)
        elif p.suffix.lower() == ".xlsx":
            vermerke = xlsx_vermerke(p)
        else:
            vermerke = text_vermerke(p)
        print(f"### `{p.relative_to(wurzel)}`\n")
        if vermerke:
            for v in vermerke:
                print(f"- {v}")
        else:
            print("- keine Rechte- oder Herkunftsvermerke gefunden")
        print()

    print("## Abgeleitete Fassungen\n")
    ordner = sorted({p.parent.relative_to(wurzel) for p in abgeleitet})
    for o in ordner:
        anzahl = sum(1 for p in abgeleitet if p.parent.relative_to(wurzel) == o)
        print(f"- `{o}/` – {anzahl} Datei(en)")


if __name__ == "__main__":
    main()
