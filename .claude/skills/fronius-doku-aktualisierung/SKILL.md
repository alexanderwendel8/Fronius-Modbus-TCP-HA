---
name: fronius-doku-aktualisierung
description: Bei Fronius nach neuen oder aktualisierten Modbus-TCP-/SunSpec-Unterlagen suchen (Registerarchive, Modbus-Handbücher, Datamanager-Anleitung) und mit docs/fronius/ abgleichen. Verwenden bei "gibt es neue Fronius-Doku", "sind die Registerkarten aktuell", "neues Fronius-Handbuch", "Fronius Modbus Update prüfen".
---

# Fronius-Modbus-Unterlagen auf Aktualität prüfen

Vergleicht die bei Fronius veröffentlichten Unterlagen mit `docs/fronius/` und sucht nach neuen
Dokumenten. Ergebnis ist ein kurzer Bericht an den Nutzer; **ins Repository wird nur nach Zustimmung
übernommen** (siehe Schritt 4).

## 0. Zugriff – wichtig

- `www.fronius.com` muss im Netz der Umgebung erlaubt sein (in der Default-Umgebung eingetragen).
- Fronius weist automatisierte Abrufe ab („Request Rejected“). **Diese Sperre nicht umgehen** (kein
  vorgetäuschter Browser-User-Agent, keine Header-Tricks). Die Dateien lädt der **Nutzer im Browser**.
  Seiten lesen geht über das WebFetch-Tool bzw. den `web-fetch`-Agenten; scheitert das, nicht
  wiederholen, sondern den Nutzer bitten.
- Downloads sind fremde Daten: in ein eigenes leeres Verzeichnis im Scratchpad legen, nur lesen,
  Python mit `-I` starten.

## 1. Bekannte Unterlagen abgleichen

```bash
python3 -I .claude/skills/fronius-doku-aktualisierung/scripts/pruefe_fronius_doku.py --links
```
zeigt die Download-Links (Ziele der QR-Links aus den Handbüchern und die Handbuch-PDFs):

| Unterlage | Link | im Repo |
|---|---|---|
| Registerarchiv Datamanager-Geräte, State Codes & Event Flags | `https://www.fronius.com/QR-link/0006` | `archiv_1.1.7/` |
| Registerarchiv GEN24, Tauro, Verto, Smart Meter | `https://www.fronius.com/QR-link/0024` | `archiv_1.2.7/` |
| GEN24 Modbus TCP & RTU (42,0410,2649) | `…/Operating%20Instructions/42,0410,2649.pdf` | `handbuecher/` |
| Datamanager Modbus TCP & RTU (42,0410,2049) | `…/Operating%20Instructions/42,0410,2049.pdf` | `handbuecher/` |
| Datamanager 2.0 Bedienungsanleitung (42,0426,0191,DE) | `…/Operating%20Instructions/42,0426,0191,DE.pdf` | `handbuecher/` |

Den Nutzer bitten, die Dateien im Browser in ein leeres Verzeichnis zu laden und es bereitzustellen
(z. B. hochladen oder in den Scratchpad kopieren). Dann:

```bash
python3 -I .claude/skills/fronius-doku-aktualisierung/scripts/pruefe_fronius_doku.py . <Download-Verzeichnis>
```

Der Bericht zeigt je Archiv die Version aus `_INFO.TXT`, geänderte Dateien, Dateien nur bei Fronius
und Dateien nur im Repository, je Handbuch den Ausgabestand (`0NN-TTMMJJJJ`) und ob der Inhalt
identisch ist. Exit-Code 1 = Abweichungen. Dateinamen werden ohne Sonderzeichen verglichen
(`Int&SF` ≙ `IntSF`, Leerzeichen ≙ `_`).

Bekannte Unterschiede (Stand 28.11.2026, keine Aktualisierung):
- `archiv_1.1.7` enthält nur einen Teil des Fronius-Archivs. Bei Fronius zusätzlich: Inverter-
  und Meter-Registerkarten der Datamanager-Geräte (`Inverter_Register_Map_*_with_SYMOHYBRID_MODEL_124`,
  `Meter_Register_Map_*_v1.0`), IG Sensor Card, `Evt1.csv`, `StVnd.csv`, `Symo_State_Codes.csv`,
  `all.json`, `igplus.json`, `symo.json`, `EvtVnd1-4_All.csv`. Die Argeno-Registerkarte stammt aus
  einem anderen Download.
- `archiv_1.2.7` enthält nicht alle Varianten (z. B. `…_Int&SF_storage_US`, `Smart_Meter_…_Int&SF`,
  `Tauro_…_Float_ROW`, einige Verto-3MPPT-Varianten).

## 2. Nach neuen Unterlagen suchen

Neue Dokumente haben keinen festen Link. Suchen über:
- **WebSearch** (`allowed_domains: ["www.fronius.com"]`), z. B. „Fronius Modbus TCP RTU“,
  „Modbus SunSpec Maps“, „Register Map“, „Modbus“ zusammen mit Gerätenamen (GEN24, Tauro, Verto,
  Argeno, Smart Meter, Wattpilot, Reserva, Ohmpilot).
- Die Fronius-Downloadseite (`https://www.fronius.com/de/downloads`, Bereich Solar Energy) über
  WebFetch; die Suche dort (`/search/getdownloadcenter`) ist in `robots.txt` gesperrt – nicht
  automatisiert abfragen, sondern dem Nutzer den Suchbegriff nennen.
- In neuen Handbuch-Ausgaben die Verweise auf Registerkarten (QR-Links `fronius.com/QR-link/…`)
  und das Kapitel „Änderungen“ bzw. `_CHANGELOG.TXT` der Archive lesen.

Treffer nur melden, wenn Dokumentnummer, Titel und Stand von der Fronius-Seite belegt sind.

## 3. Bericht an den Nutzer

Kurz: je Unterlage aktuell / neue Version (alt → neu) / neu gefunden, dazu was sich laut Changelog
ändert und welche Teile der Integration betroffen sein könnten (Modelle, Register, Verhalten).
Fragen, ob übernommen werden soll. **Ohne Zustimmung nichts ändern.**

## 4. Übernehmen (nur nach Zustimmung)

- Neue Archivversion als eigener Ordner `docs/fronius/archiv_<Version>/` mit `original/`
  (unverändert), `csv/` (jedes Blatt als CSV) und `README.md` nach dem Muster der vorhandenen Archive;
  bestehende Ordner bleiben, Originale werden nie verändert.
- Neue Handbuch-Ausgabe: PDF in `handbuecher/original/` ersetzen, Textfassung mit
  `pdftotext -layout` neu erzeugen, Tabelle „Stand“ in `handbuecher/README.md` anpassen.
- `docs/fronius/README.md` und die Tabelle in `CLAUDE.md` nachziehen.
- Changelog der Fronius-Unterlagen lesen und prüfen, ob Code betroffen ist (`sunspec.py`, `api.py`);
  Code-Änderungen sind eine eigene Aufgabe.
- Vor einer Übernahme weiterer Fronius-Dateien den Skill `fronius-rechtslage` beachten.
- CHANGELOG-Eintrag in beiden Sprachen (Abschnitt „Dokumentation“), dann wie gewohnt Commit und PR.
