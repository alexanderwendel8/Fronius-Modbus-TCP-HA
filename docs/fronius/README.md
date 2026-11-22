# Fronius Modbus-Dokumentation – Gesamtindex

Herstellerunterlagen von Fronius zu Modbus TCP / SunSpec, aufgeteilt nach Fronius-Archiv.
Jedes Archiv hat `original/` (unverändert), `csv/` (jedes xlsx-Blatt als CSV, per `grep` durchsuchbar)
und eine eigene README mit Zusammenfassung. Die Handbücher liegen als PDF plus Textfassung (`text/`) vor.

**Registerkarten** (archiv_*) sagen *wo* ein Wert steht; die **Handbücher** sagen *wie* sich das Gerät
verhält (Geräte-IDs, Timeouts, Schreiben/Steuern, Vorzeichen, Batterie-Logik).

| Archiv | Geräte | Zusammenfassung |
|---|---|---|
| **1.1.7-0** | Datamanager-Geräte (Symo, Primo, Galvo, IG Plus …), **Argeno**, IG String Control, **State Codes & Event Flags** | [archiv_1.1.7/README.md](archiv_1.1.7/README.md) |
| **1.2.7-2** | **Primo/Symo GEN24 (Plus)**, **Tauro**, **Tauro ECO**, **Verto (Plus)**, **Smart Meter** | [archiv_1.2.7/README.md](archiv_1.2.7/README.md) |
| **Handbücher (PDF)** | Modbus TCP & RTU für **Datamanager** und **GEN24**, Bedienungsanleitung **Datamanager 2.0** – Geräte-IDs, Timeouts, Steuerung, Batterie, Vorzeichen | [handbuecher/README.md](handbuecher/README.md) |

---

## Welches Dokument für welches Gerät?

| Gerät | Registerkarte | Status/Events |
|---|---|---|
| Primo/Symo **GEN24** ohne Batterie | `archiv_1.2.7/csv/Gen24_Primo_Symo_Inverter_Register_Map_{Float,IntSF}_ROW/` | EvtVnd = Schweregrad-Bits (archiv_1.2.7 §3) |
| Primo/Symo **GEN24 Plus** (Batterie) | `archiv_1.2.7/csv/Gen24_…_{Float,IntSF}_storage_ROW/` (inkl. Modell 124) | wie GEN24 |
| GEN24 US-Varianten | `archiv_1.2.7/csv/Gen24_…_US/` (zusätzlich 701–713) | wie GEN24 |
| **Tauro / Tauro ECO** | `archiv_1.2.7/csv/Tauro_*` | wie GEN24 |
| **Verto / Verto Plus** | `archiv_1.2.7/csv/Verto_*` | wie GEN24 |
| **Smart Meter** (am GEN24/Tauro/Verto) | `archiv_1.2.7/csv/Smart_Meter_Register_Map_Float/` | – |
| **Argeno** | `archiv_1.1.7/csv/Argeno_Register_Map/<Modell>.csv` | St/StVnd/Evt1 aus archiv_1.1.7 |
| Symo, Primo, Galvo, Eco, IG Plus (**mit Datamanager**) | *Registerkarte nicht im Repo* – Modellaufbau wie SunSpec-Standard | `archiv_1.1.7/csv/Fronius_State_Codes_Event_Flags_1_0/` (EvtVnd1-4 je Familie) |
| IG String Control | `archiv_1.1.7/csv/IG_String_Control_Register_Map_Float_and_IntSF_v1_0/` | – |

Erkennbar ist die Geräteklasse zur Laufzeit am Common Model (`Md`, z. B. „Symo GEN24 10.0“) und
an der Modellkette (z. B. Modell 124 vorhanden → Batterie-fähig).

---

## Gemeinsame Konventionen

- **Adressen** in allen Fronius-Tabellen sind **1-basiert**; pymodbus/Code **0-basiert** (−1).
- Archiv 1.1.7 (Argeno): Modellblätter mit **absoluten** Adressen.
  Archiv 1.2.7: Modellblätter mit **relativen** Adressen (1 = ID, 2 = L, 3 = erstes Datenregister),
  absolute Adressen nur in `Complete_Map.csv`.
- Common-Model-Länge: GEN24/Tauro/Verto/Smart Meter/IG String Control **65**, Argeno **66**.
- Nicht unterstützte Werte: float NaN, uint16 0xFFFF, int16 0x8000, acc32 0.
- Bei Widersprüchen: xlsx/CSV vor `FroniusEventFlags.json` (archiv_1.1.7 §6).

### Unterschiede zwischen den Gerätegenerationen (wichtig für den Code)

| Thema | Datamanager / Argeno (1.1.7) | GEN24 / Tauro / Verto (1.2.7) |
|---|---|---|
| `StVnd` | eigene Fronius-Codes 1–13 | identisch mit `St` |
| `EvtVnd1`–`EvtVnd4` | Fehlerklassen-Bits (je Gerätefamilie) | `EvtVnd1`/`2` = Schweregrad (Bit 0 Fehler, 1 Warnung, 2 Info); `3`/`4` nicht unterstützt |
| `DCWH` in Modell 160 | Argeno/Hybrid: nicht unterstützt | geliefert |
| Batterie in Modell 160 | – | zusätzliche Module `StCha n` / `StDisCha n` |
| Modell 123 `*_WinTms`, `*_RmpTms` | nicht unterstützt (Argeno) | beschreibbar |
| Unit-ID Wechselrichter | = WR-Nummer im Solar Net (00 → 100) | immer 1 |
| Unit-ID Smart Meter | 240 (fest), 240–244 | 200 (Default), 200–204 |
| Empfohlener Timeout | ≥ 10 s | ≥ 1 s |
| Zusatzregister | Fronius-Register 212–216, 500–513 (State Code, Anlagensummen) | – |
| Batterie in Modell 160 | Symo Hybrid: String 2 = Speicher (nur Absolutwert) | eigene Module `StCha`/`StDisCha` |

---

## Bezug zum Code (`custom_components/fronius_modbus_tcp/`)

| Thema | Code | Stand laut Doku |
|---|---|---|
| Modellkette dynamisch scannen | `api.py::scan_models` | ✅ passt (L = 65/66, 103 + 113 parallel beim Argeno) |
| float bevorzugen | `api.py::read_inverter_info` | ✅ |
| Blöcke > 125 Register (160 mit N = 10 beim Argeno) | `api.py::read` | ✅ |
| Leistungsfaktor | `sensor.py` | ✅ Inverter in % („Pct“); Smart Meter als Faktor −1…1 (int+SF: Pct ÷ 100) |
| `StVnd`-Codes 9–13 | `sunspec.py::STATUS_VENDOR` | ✅ Datamanager; beim GEN24 identisch mit `St` |
| MPPT-Module | `sunspec.py::mppt_roles`, `combine_mppt` | ✅ `StCha`/`StDisCha` → Batterie; Symo Hybrid: String 2 = Speicher (Richtung aus DCW) |
| Batterie (Modell 124) | `sunspec.py::parse_storage` | ✅ lesend: SoC, Status, Mindestreserve, Ladequelle, Grenzen; `WChaMax` = 0 → kein Speicher |
| Smart Meter (201–204 / 211–214) | `sunspec.py::parse_meter_*`, `api.py::async_detect_meter` | ✅ Unit-ID automatisch (200, dann 240) oder manuell; Vorzeichen wie geliefert (Location „Netz“: + = Bezug) |
| Timeout | `const.py` (`DEFAULT_TIMEOUT = 10`, Suche 3 s) | ✅ |
| Skalierungsfaktoren | `sunspec.py` | ✅ werden bei jedem Lesen mitgelesen |
| Unit-ID im Config Flow | `config_flow.py`, `strings.json` | ✅ Hinweise GEN24 = 1, Datamanager = WR-Nummer (00 → 100) |
| `EvtVnd1-4` dekodieren | `sunspec.py::parse_severity_events` / `parse_vendor_event_classes`, `state_codes.py` | ✅ GEN24: Schweregrad (Fehler/Warnung); Datamanager: Fehlerklassen je Familie (Unterscheidung über Fronius-Register) |
| `Evt1` im Klartext | `sunspec.py::SUNSPEC_EVENTS` | ✅ 16 Bits laut `Evt1.csv` |
| Modell 122 | `sunspec.py::parse_status` | ✅ `ActWh` (eigener Sensor, genauer als `WH`), `Ris`; `StActCtl`, `PVConn` … ⏳ |
| Mehrere Smart Meter (200–204 / 240–244) | – | ⏳ derzeit nur einer |
| Fronius-Register 214 (State Code), 500–513 (Anlagensummen) | `sunspec.py::parse_fronius_*`, `state_codes.py` | ✅ nur Datamanager; Erkennung per Testlesen beim Start |
| Vorgaben lesen (Modell 123) | `sunspec.py::parse_controls`, `binary_sensor.py` | ✅ Leistungsbegrenzung, Standby, cos φ/Blindleistung (nur lesend) |
| Steuerung (Modell 123, 124 schreiben) | – | ⏳ nicht umgesetzt (Ablauf siehe handbuecher §2) |
| Nennwerte (Modell 120) | `sunspec.py::parse_nameplate` | ✅ WRtg, VARtg, ARtg; Batterie WHRtg, MaxChaRte, MaxDisChaRte; einmal beim Start gelesen |
