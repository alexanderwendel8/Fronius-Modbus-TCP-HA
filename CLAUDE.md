# Hinweise für Claude

Home-Assistant-Custom-Integration `fronius_modbus_tcp` (Fronius-Wechselrichter per Modbus TCP / SunSpec).
Code: `custom_components/fronius_modbus_tcp/`. Sprache in Code-Kommentaren und Doku: Deutsch.

## Herstellerdokumentation – immer zuerst hier nachschlagen

**Einstieg: [`docs/fronius/README.md`](docs/fronius/README.md)** – Gesamtindex: welches Dokument für
welches Gerät, Unterschiede zwischen den Gerätegenerationen, Bezug zum Code.

| Archiv | Inhalt | Zusammenfassung |
|---|---|---|
| `docs/fronius/archiv_1.1.7/` | Datamanager-Geräte samt Smart Meter, Argeno, **State Codes & Event Flags** | `archiv_1.1.7/README.md` |
| `docs/fronius/archiv_1.2.7/` | **GEN24**, Tauro, Verto, **Smart Meter**, **Batterie (124)** | `archiv_1.2.7/README.md` |
| `docs/fronius/handbuecher/` | Modbus-Handbücher Datamanager & GEN24, Datamanager 2.0 (PDF + Text) | `handbuecher/README.md` |

Schnellzugriff:
- GEN24-Register eines Modells: `docs/fronius/archiv_1.2.7/csv/Gen24_Primo_Symo_Inverter_Register_Map_Float_storage_ROW/<blatt>.csv`
  (`inverter_11x`, `mppt_160`, `storage_124`, `controls_123`, `nameplate_120` …, absolute Adressen in `Complete_Map.csv`)
- Smart Meter: `docs/fronius/archiv_1.2.7/csv/Smart_Meter_Register_Map_Float/ac_meter_21x.csv`
- Datamanager-Geräte (Symo, Primo, Galvo, Symo Hybrid …): `docs/fronius/archiv_1.1.7/csv/Inverter_Register_Map_Float_v1_0_with_SYMOHYBRID_MODEL_124/<blatt>.csv`
  (`I11X_Inverter`, `I120_Nameplate` … `IC124_Basic_Storage_Control`, `Fronius_Register`), Smart Meter: `…/Meter_Register_Map_Float_v1_0/M21X_Meter.csv`
- Argeno: `docs/fronius/archiv_1.1.7/csv/Argeno_Register_Map/<Modellnummer>.csv`
- Status/Events Datamanager-Geräte: `docs/fronius/archiv_1.1.7/csv/Fronius_State_Codes_Event_Flags_1_0/`
- Verhalten, Geräte-IDs, Timeouts, Steuerungsabläufe, Batterie-Logik, Meter-Vorzeichen: `docs/fronius/handbuecher/README.md`,
  Volltext in `docs/fronius/handbuecher/text/*.txt` (PDF-Seiten bei Bedarf mit Read + `pages` ansehen)
- Suche: `grep -rn "WMaxLimPct" docs/fronius/*/csv/ docs/fronius/handbuecher/text/`

Helfer (Skills): `fronius-doku-aktualisierung` gleicht die Unterlagen mit den aktuellen Fronius-Downloads ab
und sucht neue; `fronius-rechtslage` prüft, ob sie wiederveröffentlicht werden dürfen.

Regeln:
- Adressen in der Fronius-Doku sind **1-basiert**, im Code **0-basiert** (−1).
- Archiv 1.2.7: Modellblätter haben **relative** Adressen (1 = ID, 2 = L) → Rumpf-Offset = relativ − 3.
- `EvtVnd*` und `StVnd` bedeuten bei GEN24/Tauro/Verto etwas anderes als bei Datamanager-Geräten.
- Bei Widersprüchen gelten xlsx/CSV, nicht `FroniusEventFlags.json`.
- Keine festen Registeradressen einbauen – Modelle werden zur Laufzeit gescannt.
- Unit-IDs: GEN24 WR = 1, Meter = 200; Datamanager WR = WR-Nummer (00 → 100), Meter = 240.
- Skalierungsfaktoren nie cachen – sie können sich zur Laufzeit ändern.
- Modbus-Abfragen sequenziell; Timeout Datamanager ≥ 10 s.
- „not supported“-Register liefern NaN / 0xFFFF / 0x8000 / acc32 0 → werden zu `None`.
- Originale in `original/` nie verändern; CSV-Exporte bei Bedarf neu erzeugen.

## Home-Assistant-Doku – offizielle Quelle

Aussagen über Home Assistant (Oberfläche, Menünamen, Marketplace/HACS, Integrations-Verhalten, Entwickler-APIs)
**immer gegen die offizielle Doku prüfen**, nicht aus dem Gedächtnis – Home Assistant ändert sich monatlich.
Die gesamte Doku liegt als Markdown im öffentlichen Repo `home-assistant/home-assistant.io` (sauberer als die
HTML-Seiten; www.home-assistant.io ist aus der Cloud-Umgebung zudem nicht erreichbar):

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/home-assistant/home-assistant.io /home/user/home-assistant/home-assistant.io
git -C /home/user/home-assistant/home-assistant.io sparse-checkout set source/_docs source/_integrations
grep -rli "marketplace" /home/user/home-assistant/home-assistant.io/source/_docs
```

- Integrationen: `source/_integrations/<domain>.markdown` (z. B. `marketplace.markdown`, `modbus.markdown`)
- Allgemeine Doku: `source/_docs/` (z. B. `apps-and-integrations.markdown`)
- Bei bestehendem Klon vorher `git -C … pull` (bzw. neu klonen), damit der Stand aktuell ist.
- Für öffentliche Texte (README, CHANGELOG) die Quelle verlinken: `https://www.home-assistant.io/<pfad>/`
  (`source/_integrations/x.markdown` → `/integrations/x/`, `source/_docs/y.markdown` → `/docs/y/`).
- Menü- und Schaltflächennamen so übernehmen, wie die Doku sie schreibt (englisch, fett), ggf. mit deutscher
  Erläuterung.

## Dokumentation zweisprachig (Deutsch und Englisch)

README und Changelog gibt es in zwei Fassungen, die **immer gleichlaufend gepflegt** werden:

| Deutsch | Englisch |
|---|---|
| `README.md` | `README.en.md` |
| `CHANGELOG.md` | `CHANGELOG.en.md` |

- Jede Änderung an einer Fassung kommt **im selben Commit** in die andere – inhaltlich gleich, gleicher
  Aufbau (Überschriften, Tabellenzeilen, Aufzählungspunkte, Codeblöcke). Keine Fassung darf nachhinken.
- `tests/test_docs.py` prüft das: gleiche Gliederung, gleiche Tabellen- und Punktzahl je Abschnitt,
  gleiche Versionsabschnitte, gegenseitige Sprachlinks in der ersten Zeile. Schlägt der Test fehl,
  fehlt in einer Fassung etwas.
- Deutsch ist die Quelle für die Workflows: Release Notes kommen aus `CHANGELOG.md` (`## X.Y.Z`),
  Vorabversionen aus `## Unveröffentlicht`; der Update-Check liest die Tabelle „Getestete Geräte“ aus
  `README.md`. Im englischen Changelog heißt dieser Abschnitt `## Unreleased`, die Versionsüberschriften
  sind identisch.
- Home-Assistant-Menünamen in beiden Fassungen englisch und fett wie in der offiziellen Doku;
  Fronius-Bezeichnungen im Englischen wie im englischen Teil der Handbücher
  (z. B. „Inverter control via Modbus“, „Allow Control“, „Restrict Control“, „Data output via Modbus“).
- Entitätsnamen im Englischen wie in `translations/en.json`.

## Entwicklung

- SunSpec-Dekodierung ohne HA-Abhängigkeit in `sunspec.py`; Modbus-Zugriff in `api.py`.
- Neuer Sensor: Wert in `sunspec.py` dekodieren → Beschreibung in `sensor.py` →
  Namen in `strings.json`, `translations/en.json`, `translations/de.json`.
- Vor jedem Commit: `ruff check .` und `mypy` müssen ohne Befund durchlaufen (Regeln und Einstellungen in
  `pyproject.toml`, CI-Job `lint`), dazu `pytest`.
- Releases: Ablauf und wiederverwendbare Vorlage in `.claude/skills/release/SKILL.md`
  (Version in `manifest.json` + Abschnitt in `CHANGELOG.md`, dann Workflow `release.yml` manuell auf `main` starten).

## Aktualisierungs-Issues

- Der Workflow `.github/workflows/update-check.yml` (Logik: `.github/scripts/check_updates.py`)
  legt wöchentlich für jede veraltete externe Komponente ein Issue mit dem Label
  `aktualisierung` an und schließt es, sobald die Komponente aktuell ist.
- Zu Beginn jeder Sitzung, vor der ersten Aufgabe, die offenen Issues mit dem Label
  `aktualisierung` über die GitHub-Tools abrufen und jedes prüfen:
  - Ist es noch zutreffend (Version im Repository mit dem Issue vergleichen)?
  - Gibt es dafür schon einen offenen Pull Request?
  - Was ist zu tun und wie riskant ist es (Release Notes bzw. Changelog der Komponente
    auf Breaking Changes und neue Anforderungen lesen)?
- Das Ergebnis kurz zusammenfassen und den Nutzer fragen, ob und welche Issues abgearbeitet
  werden sollen. **Ohne Zustimmung nichts ändern.** Gibt es keine offenen Issues, das nur
  in einem Satz erwähnen.
- Beim Abarbeiten gelten die übrigen Regeln (CHANGELOG-Eintrag in beiden Sprachen, Tests, CI-Matrix); im Pull
  Request das Issue mit `Closes #<Nummer>` verknüpfen.
- `pymodbus==3.11.2` in `requirements_test.txt` ist absichtlich die Mindestversion und trägt den
  Kommentar `# update-check: ignore`; so markierte Pins prüft der Workflow nicht.
