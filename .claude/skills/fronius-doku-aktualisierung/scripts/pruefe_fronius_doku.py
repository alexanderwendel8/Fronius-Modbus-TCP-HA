#!/usr/bin/env python3
"""Heruntergeladene Fronius-Modbus-Unterlagen mit dem Stand im Repository vergleichen.

Das Skript lädt selbst nichts herunter: Fronius weist automatisierte Abrufe ab
("Request Rejected"), diese Sperre wird nicht umgangen. Die Dateien lädt der Nutzer im
Browser (Links in SKILL.md bzw. Ausgabe von `--links`) in ein leeres Verzeichnis.

Verglichen wird mit docs/fronius/:
- Registerarchive (ZIP): Version aus _INFO.TXT, Dateiliste (neu / entfallen / geändert)
- Handbücher (PDF): SHA-256, Ausgabestand (z. B. 034-28092026)

Die Downloads sind fremde Daten: nur gelesen, nichts daraus ausgeführt.

Aufruf:
  python3 -I pruefe_fronius_doku.py --links
  python3 -I pruefe_fronius_doku.py <Repo-Wurzel> <Download-Verzeichnis>
Exit-Code 0 = alles aktuell, 1 = Abweichungen, 2 = Bedienfehler.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DL = "https://www.fronius.com/~/downloads/Solar%20Energy/Operating%20Instructions/"

# Registerarchive: Download (Ziel der QR-Links aus den Handbüchern) -> Ordner im Repository
ARCHIVE = {
    "SE_EI_Modbus_Sunspec_Maps_State_Codes_Events_EN.zip": (
        "Datamanager-Geräte, State Codes & Event Flags (QR-Link 0006)",
        "https://www.fronius.com/QR-link/0006",
        "archiv_1.1.7",
    ),
    "gen24-modbus-api-external-docs.zip": (
        "GEN24, Tauro, Verto, Smart Meter (QR-Link 0024)",
        "https://www.fronius.com/QR-link/0024",
        "archiv_1.2.7",
    ),
}
# Handbücher: Download-Dateiname -> Datei unter handbuecher/original/
HANDBUECHER = {
    "42,0410,2649.pdf": "42_0410_2649_GEN24_Modbus_TCP_RTU_DE_EN.pdf",
    "42,0410,2049.pdf": "42_0410_2049_Datamanager_Modbus_TCP_RTU_DE_EN.pdf",
    "42,0426,0191,DE.pdf": "42_0426_0191_Datamanager_2.0_Bedienungsanleitung_DE.pdf",
}


def schluessel(name: str) -> str:
    """Dateiname ohne Pfad, Groß-/Kleinschreibung und Sonderzeichen (Int&SF ~ IntSF)."""
    return re.sub(r"[^a-z0-9]", "", Path(name).name.lower())


def sha(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def info_version(text: str) -> str:
    m = re.search(r"Version\s+([\w.\-]+)", text)
    return m.group(1) if m else text.strip()


def finde(downloads: Path, name: str) -> Path | None:
    """Download suchen; Browser hängen bei Dubletten gern " (1)" an."""
    stamm, endung = schluessel(Path(name).stem), Path(name).suffix.lower()
    kandidaten = sorted(
        (p for p in downloads.iterdir()
         if schluessel(p.name).startswith(stamm) and p.suffix.lower() == endung),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return kandidaten[0] if kandidaten else None


def pruefe_archiv(zipdatei: Path, titel: str, ordner: Path) -> bool:
    print(f"## Registerarchiv: {titel}\n")
    print(f"- Datei: `{zipdatei.name}`")
    abweichung = False
    with zipfile.ZipFile(zipdatei) as archiv:
        dateien = {
            schluessel(i.filename): i
            for i in archiv.infolist()
            if not i.is_dir() and "/.~lock." not in "/" + i.filename
        }
        info = dateien.get("infotxt")
        fern = info_version(archiv.read(info).decode("utf-8", "replace")) if info else "?"
        lokal_info = ordner / "original" / "INFO.TXT"
        lokal_version = (
            info_version(lokal_info.read_text(encoding="utf-8", errors="replace"))
            if lokal_info.exists() else "?"
        )
        abweichung |= fern != lokal_version
        zeichen = "✅" if fern == lokal_version else "⚠️"
        print(f"- {zeichen} Version Fronius `{fern}`, Repository `{lokal_version}`")

        lokal = {schluessel(p.name): p for p in (ordner / "original").iterdir() if p.is_file()}
        geaendert = [
            lokal[k].name for k, i in dateien.items()
            if k in lokal and sha(archiv.read(i)) != sha(lokal[k].read_bytes())
        ]
        nur_fronius = sorted(i.filename for k, i in dateien.items() if k not in lokal)
        nur_repo = sorted(p.name for k, p in lokal.items() if k not in dateien)
    if geaendert:
        abweichung = True
        print(f"- ⚠️ Inhalt geändert ({len(geaendert)}): " + ", ".join(f"`{n}`" for n in geaendert))
    else:
        print("- ✅ Alle gemeinsamen Dateien inhaltsgleich")
    if nur_fronius:
        print(f"- ℹ️ Nur bei Fronius, nicht im Repository ({len(nur_fronius)}):")
        for n in nur_fronius:
            print(f"  - `{n}`")
    if nur_repo:
        print(f"- ℹ️ Nur im Repository, nicht im Download ({len(nur_repo)}): "
              + ", ".join(f"`{n}`" for n in nur_repo))
    print()
    return abweichung


def ausgabestand(pdf: Path) -> str:
    if not shutil.which("pdftotext"):
        return "?"
    text = subprocess.run(
        ["pdftotext", "-l", "3", str(pdf), "-"], capture_output=True, text=True, check=False
    ).stdout
    m = re.search(r"\b0\d{2}-\d{8}\b", text)
    return m.group(0) if m else "?"


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--links":
        print("Im Browser herunterladen (in ein leeres Verzeichnis):")
        for name, (titel, url, _) in ARCHIVE.items():
            print(f"- {titel}: {url}  → {name}")
        for name in HANDBUECHER:
            print(f"- Handbuch {name[:-4]}: {DL}{name}")
        return 0
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    basis = Path(sys.argv[1]).resolve() / "docs" / "fronius"
    downloads = Path(sys.argv[2]).resolve()
    print("# Abgleich Fronius-Modbus-Unterlagen\n")
    abweichung = False
    fehlend = []
    for name, (titel, _, ordner) in ARCHIVE.items():
        datei = finde(downloads, name)
        if datei is None:
            fehlend.append(name)
            continue
        abweichung |= pruefe_archiv(datei, titel, basis / ordner)

    print("## Handbücher\n")
    print("| Dokument | Stand Download | Stand Repository | Inhalt |")
    print("|---|---|---|---|")
    for name, ziel in HANDBUECHER.items():
        datei = finde(downloads, name)
        if datei is None:
            fehlend.append(name)
            continue
        lokal = basis / "handbuecher" / "original" / ziel
        gleich = lokal.exists() and sha(datei.read_bytes()) == sha(lokal.read_bytes())
        abweichung |= not gleich
        print(
            f"| {name[:-4]} | {ausgabestand(datei)} | "
            f"{ausgabestand(lokal) if lokal.exists() else 'fehlt'} | "
            f"{'✅ identisch' if gleich else '⚠️ abweichend'} |"
        )
    print()
    if fehlend:
        print("**Nicht im Download-Verzeichnis (nicht geprüft):** "
              + ", ".join(f"`{n}`" for n in fehlend) + "\n")
    print("**Ergebnis:** " + ("Abweichungen gefunden." if abweichung else "Keine Abweichungen."))
    return 1 if abweichung else 0


if __name__ == "__main__":
    sys.exit(main())
