# Hinweise für Claude

Home-Assistant-Custom-Integration `fronius_modbus_tcp` (Fronius-Wechselrichter per Modbus TCP / SunSpec).
Code: `custom_components/fronius_modbus_tcp/`. Sprache in Code-Kommentaren und Doku: Deutsch.

## Herstellerdokumentation – immer zuerst hier nachschlagen

**Einstieg: [`docs/fronius/README.md`](docs/fronius/README.md)** – Gesamtindex: welches Dokument für
welches Gerät, Unterschiede zwischen den Gerätegenerationen, Bezug zum Code.

| Archiv | Inhalt | Zusammenfassung |
|---|---|---|
| `docs/fronius/archiv_1.1.7/` | Argeno, Datamanager-Geräte, **State Codes & Event Flags** | `archiv_1.1.7/README.md` |
| `docs/fronius/archiv_1.2.7/` | **GEN24**, Tauro, Verto, **Smart Meter**, **Batterie (124)** | `archiv_1.2.7/README.md` |
| `docs/fronius/handbuecher/` | Modbus-Handbücher Datamanager & GEN24, Datamanager 2.0 (PDF + Text) | `handbuecher/README.md` |

Schnellzugriff:
- GEN24-Register eines Modells: `docs/fronius/archiv_1.2.7/csv/Gen24_Primo_Symo_Inverter_Register_Map_Float_storage_ROW/<blatt>.csv`
  (`inverter_11x`, `mppt_160`, `storage_124`, `controls_123`, `nameplate_120` …, absolute Adressen in `Complete_Map.csv`)
- Smart Meter: `docs/fronius/archiv_1.2.7/csv/Smart_Meter_Register_Map_Float/ac_meter_21x.csv`
- Argeno: `docs/fronius/archiv_1.1.7/csv/Argeno_Register_Map/<Modellnummer>.csv`
- Status/Events Datamanager-Geräte: `docs/fronius/archiv_1.1.7/csv/Fronius_State_Codes_Event_Flags_1_0/`
- Verhalten, Geräte-IDs, Timeouts, Steuerungsabläufe, Batterie-Logik, Meter-Vorzeichen: `docs/fronius/handbuecher/README.md`,
  Volltext in `docs/fronius/handbuecher/text/*.txt` (PDF-Seiten bei Bedarf mit Read + `pages` ansehen)
- Suche: `grep -rn "WMaxLimPct" docs/fronius/*/csv/ docs/fronius/handbuecher/text/`

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

## Entwicklung

- SunSpec-Dekodierung ohne HA-Abhängigkeit in `sunspec.py`; Modbus-Zugriff in `api.py`.
- Neuer Sensor: Wert in `sunspec.py` dekodieren → Beschreibung in `sensor.py` →
  Namen in `strings.json`, `translations/en.json`, `translations/de.json`.
- Releases: Ablauf und wiederverwendbare Vorlage in `.claude/skills/release/SKILL.md`
  (Version in `manifest.json` + Abschnitt in `CHANGELOG.md`, dann Workflow `release.yml` manuell auf `main` starten).
