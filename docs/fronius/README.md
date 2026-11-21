# Fronius Modbus-Dokumentation – Referenz & Zusammenfassung

Herstellerunterlagen von Fronius zu Modbus TCP / SunSpec (Archivversion **1.1.7-0**, siehe
[`original/INFO.TXT`](original/INFO.TXT) und [`original/CHANGELOG.TXT`](original/CHANGELOG.TXT)).

- `original/` – unveränderte Originaldateien (xlsx, csv, json, txt)
- `csv/` – jedes Tabellenblatt der xlsx-Dateien als CSV (durchsuchbar mit `grep`).
  Inhaltlich identisch zu den Originalen, nur das Format ist anders.

> **Adressierung:** Alle Adressen in den Fronius-Tabellen sind **1-basiert** („Start“-Spalte,
> z. B. `40001` = „SunS“). pymodbus und der Code dieser Integration arbeiten **0-basiert**
> (`SUNSPEC_BASE_ADDRESS = 40000`). Also: Code-Adresse = Dokument-Adresse − 1.

---

## 1. Dateiindex

| Datei (in `original/`) | CSV-Export | Inhalt | Wofür nachschlagen |
|---|---|---|---|
| `Argeno_Register_Map.xlsx` | `csv/Argeno_Register_Map/<Modell>.csv` | Komplette SunSpec-Registerkarte des **Fronius Argeno** (Model „Argeno 125“), ein Blatt pro Modell + `Index` | Registerbelegung, Datentypen, Einheiten, „not supported“-Hinweise, Lese-/Schreibrechte |
| `Fronius_State_Codes__Event_Flags_1.0.xlsx` | `csv/Fronius_State_Codes_Event_Flags_1_0/*.csv` | Bedeutung von `St`, `StVnd`, `Evt1`, `EvtVnd1-4` und die State-Code-Listen je Gerätefamilie | Status-/Fehlerdekodierung |
| `IG_String_Control_Register_Map_Float_and_IntSF_v1.0.xlsx` | `csv/IG_String_Control_Register_Map_Float_and_IntSF_v1_0/*.csv` | Fronius IG String Control (Modelle 1 + 403 String Combiner) | Nur relevant, falls String-Combiner unterstützt werden sollen |
| `St.csv` | – | SunSpec-Betriebszustand `St` (1–8) | = Blatt `St` |
| `EvtVnd1-4_{Galvo,Symo,Primo,IGPlus}.csv` | – | Bit → Fehlerklasse → State Codes je Familie | = Blätter `EvtVnd1-4 <Familie>` |
| `{Galvo,Primo,IGPlus}_State_Codes.csv` | – | State Code → Klartext | = Blätter `<Familie> State Codes` (Symo nur im xlsx/`csv/`) |
| `FroniusEventFlags.json` | – | EvtVnd1–3 als JSON für `all`, `symo`, `galvo`, `primo`, `igplus` | Maschinenlesbare Quelle für Event-Mapping (Fehler beachten, Abschnitt 6) |
| `galvo.json`, `primo.json` | – | Auszug aus `FroniusEventFlags.json` | – |

Die CSV-Dateien von Galvo und IGPlus haben **keine Kopfzeile**; Primo und Symo haben eine
mehrzeilige Kopfzeile. Spalten jeweils:
`EvtFlags1-4 (hex), EvtFlags1-4 (dec), State Codes (;-getrennt), Fehlerklasse, Name`.

---

## 2. SunSpec-Struktur (Beispiel Argeno, aus `csv/Argeno_Register_Map/Index.csv`)

| Modell | Bezeichnung | Start (1-basiert) | Länge | Für Integration |
|---|---|---|---|---|
| – | „SunS“-Kennung | 40001 | 2 | ✅ genutzt |
| 1 | Common | 40003 | **66** | ✅ Hersteller, Modell, Version, Seriennummer |
| 103 | Inverter Drehstrom (int+SF) | 40071 | 50 | ✅ |
| 113 | Inverter Drehstrom (float) | 40123 | 60 | ✅ (bevorzugt) |
| 120 | Nameplate (Nennwerte) | 40185 | 26/27 | ⏳ z. B. `WRtg` Nennleistung |
| 121 | Basic Settings | 40213 | 30 | ⏳ |
| 122 | Extended Measurements & Status | 40245 | 44 | ⏳ fast alles „not supported“, nur `TmSrc`, `Tms` |
| 123 | Immediate Controls (**schreibbar**) | 40291 | 24 | ⏳ Leistungsbegrenzung `WMaxLimPct`, `Conn`, `OutPFSet` |
| 126, 129, 130, 132, 135, 136, 145 | Netzstützungskurven / Ride-Through / Extended Settings | 40317–41030 | – | ❌ |
| 160 | Multiple MPPT Extension | 41031 | 208 (N = 10) | ✅ |
| 701–714 | SunSpec-2018 „DER“-Modelle (AC/DC-Messung, Capacity, Trips, Droop …) | 41241–42337 | – | ❌ (714 = DC-Messung pro Port, Alternative zu 160) |

**Wichtig:** Beim Argeno ist das Common Model **66** Register lang (mit `Pad`), beim IG String
Control **65**. Beim Argeno sind **103 und 113 gleichzeitig** vorhanden. Feste Adressen sind daher
nicht übertragbar → die Integration durchläuft die Modellkette dynamisch (`api.py::_scan_models`).

### Common Model (1)
`Mn` string16 @+0, `Md` string16 @+16, `Opt` string8 @+32, `Vr` string8 @+40, `SN` string16 @+48,
`DA` uint16 @+64 (Offsets relativ zum Rumpf, also nach ID/L).

### Inverter-Modell 113 (float) – Argeno-Besonderheiten
Layout = SunSpec-Standard (siehe `sunspec.py::parse_inverter_float`). Laut Fronius **nicht unterstützt**:
`DCA`, `DCV`, `TmpSnk`, `TmpTrns`, `TmpOt`, `Evt2` (reserviert). `PF` hat Einheit **Pct**.
`WH` (AC-Lebensdauerenergie) ist laut Changelog 1.1.1 „may be imprecise“.

### Modell 160 (MPPT)
Kopf: `DCA_SF`, `DCV_SF`, `DCW_SF`, `DCWH_SF`, `Evt`(2), `N`, `TmsPer` = 8 Register;
je Modul 20 Register: `ID`, `IDStr`(8), `DCA`, `DCV`, `DCW`, `DCWH`(acc32), `Tms`(2), `Tmp`, `DCSt`, `DCEvt`(2).
Nicht unterstützt (Argeno): `DCWH_SF`, `DCWH`, `Evt`, `TmsPer`, `Tms`, `Tmp`, `DCSt`, `DCEvt`.
Changelog: `DCWH` auch bei **Fronius-Hybrid-Wechselrichtern** nicht unterstützt.
Länge 208 > 125 Register → muss in mehreren Requests gelesen werden (`MAX_REGISTERS_PER_READ`).

### Modell 123 (Immediate Controls, schreibbar)
`Conn` (0/1), `WMaxLimPct` + `WMaxLimPct_RvrtTms` + `WMaxLim_Ena`, `OutPFSet` + `_RvrtTms` + `_Ena`,
`VArWMaxPct`, `VArMaxPct`, `VArPct_Mod`, `VArPct_Ena`, Scale Factors am Ende.
`*_WinTms` und `*_RmpTms` nicht unterstützt.

---

## 3. Betriebszustand `St` und `StVnd`

Fronius empfiehlt, **`StVnd` statt `St`** zu lesen (Blatt `Index`).

| Wert | Name | Bedeutung | in `St` unterstützt |
|---|---|---|---|
| 1 | I_STATUS_OFF | Aus | ja |
| 2 | I_STATUS_SLEEPING | Ruhemodus (Auto-Shutdown) | **nein** |
| 3 | I_STATUS_STARTING | Startet | ja |
| 4 | I_STATUS_MPPT | MPP-Tracking | ja |
| 5 | I_STATUS_THROTTLED | Leistungsreduktion erzwungen | ja |
| 6 | I_STATUS_SHUTTING_DOWN | Fährt herunter | **nein** |
| 7 | I_STATUS_FAULT | Fehler | ja |
| 8 | I_STATUS_STANDBY | Standby (Service) – Details evtl. in Events | ja |
| 9 | I_STATUS_NO_BUSINIT | Keine Solar-Net-Kommunikation | nur `StVnd` |
| 10 | I_STATUS_NO_COMM_INV | Keine Kommunikation mit Wechselrichter | nur `StVnd` |
| 11 | I_STATUS_SN_OVERCURRENT | Überstrom am Solar-Net-Stecker | nur `StVnd` |
| 12 | I_STATUS_BOOTLOAD | Firmware-Update | nur `StVnd` |
| 13 | I_STATUS_AFCI | AFCI-Ereignis (Lichtbogen) | nur `StVnd` |

Umgesetzt in `sunspec.py::STATUS` / `STATUS_VENDOR`.

---

## 4. Event-Register

### `Evt1` (SunSpec, bitfield32) – `csv/.../Evt1.csv`
`Evt2` wird nicht genutzt (immer 0).

| Bit (hex) | Name | Auslösende State Codes |
|---|---|---|
| 0x1 | GROUND_FAULT | 471, 472, 474, 475, 494, 502 |
| 0x2 | DC_OVER_VOLT | 309, 313 |
| 0x4 | AC_DISCONNECT | 107, 117, 127, 137 |
| 0x8 | DC_DISCONNECT | – |
| 0x10 | GRID_DISCONNECT | – |
| 0x20 | CABINET_OPEN | – |
| 0x40 | MANUAL_SHUTDOWN | – |
| 0x80 | OVER_TEMP | 303, 304, 531 |
| 0x100 | OVER_FREQUENCY | 104, 105, 115, 125, 135, 203, 204 |
| 0x200 | UNDER_FREQUENCY | 104, 106, 116, 126, 136, 203, 204 |
| 0x400 | AC_OVER_VOLT | 101, 102, 112, 122, 132, 201, 202 |
| 0x800 | AC_UNDER_VOLT | 101, 103, 113, 123, 133, 201, 202 |
| 0x1000 | BLOWN_STRING_FUSE | 550, 551 |
| 0x2000 | UNDER_TEMP | – |
| 0x4000 | MEMORY_LOSS (generischer Speicher-/Kommunikationsfehler) | viele, siehe CSV |
| 0x8000 | HW_TEST_FAILURE | 245, 406, 407, 457, 469, 478, 515, 532, 533, 535, 555 |

State Codes 101, 104, 201–204 setzen **zwei** Bits gleichzeitig (z. B. 0x300, 0xC00).

### `EvtVnd1`–`EvtVnd4` (Fronius, je bitfield32)
Ein Bit steht für eine **Fehlerklasse**, die aus mehreren State Codes entstehen kann.
Die State Codes sind je Gerätefamilie unterschiedlich → Familie-spezifische Tabellen verwenden.
`EvtVnd4` ist in allen Tabellen leer (immer 0).

Kurzüberblick (gemeinsame Belegung, Details in `EvtVnd1-4_*.csv`):

- **EvtVnd1** – 0x1 Isolationsfehler · 0x2 Netzfehler · 0x4 AC-Überstrom · 0x8 DC-Überstrom ·
  0x10 Übertemperatur · 0x20 Leistung zu gering · 0x40 DC zu gering · 0x80 Zwischenkreisfehler ·
  0x100/0x200 Frequenz zu hoch/niedrig · 0x400/0x800 AC-Spannung zu hoch/niedrig · 0x1000 DC-Einspeisung ·
  0x2000 Relais · 0x4000 Leistungsteil · 0x8000 Regelung · 0x10000/0x20000 Guard Controller Spannung/Frequenz ·
  0x40000 Energieübertragung · 0x80000 Referenzquelle · 0x100000 Anti-Islanding-Test ·
  0x200000 Fixspannung < MPP · 0x400000 Speicher · 0x800000 Display · 0x1000000 interne Kommunikation ·
  0x2000000 Temperatursensoren · 0x4000000 DC/AC-Board (IG Plus: DSP) · 0x8000000 ENS ·
  0x10000000 Lüfter · 0x20000000 Sicherung · 0x40000000 Ausgangsdrossel verpolt · 0x80000000 Buck-Relais
- **EvtVnd2** – 0x1 keine Solar-Net-Kommunikation · 0x2 WR-Adresse falsch · 0x4 24 h keine Einspeisung ·
  0x8 Steckverbindung (Primo: keine Kommunikation mit Filter) · 0x10 Phasenzuordnung · 0x20 Netzleiter offen ·
  0x40 Software inkompatibel · 0x80 Derating wegen Übertemperatur (IG Plus: Master-Wechsel) ·
  0x100 Jumper · 0x200 inkompatibles Feature (IG Plus: LVRT) · 0x400 Lüfter/Lüftung · 0x800 Leistungsreduktion ·
  0x1000 Lichtbogen erkannt · 0x2000 AFCI-Selbsttest fehlgeschlagen · 0x4000 Stromsensor · 0x8000 DC-Schalter ·
  0x10000 AFCI defekt · 0x20000 AFCI-Handtest OK · 0x40000 Leistungsteil-Versorgung fehlt · 0x80000 AFCI-Kommunikation ·
  0x100000 AFCI-Handtest fehlgeschlagen · 0x200000 AC verpolt · 0x400000 AC-Messgerät · 0x800000 Flash ·
  0x1000000 allgemeiner Fehler · 0x2000000 Erdung · 0x4000000 Leistungsbegrenzung · 0x8000000 externer Kontakt offen ·
  0x10000000 Überspannungsschutz · 0x20000000 Prozessor-Programmstatus · 0x40000000 Solar Net · 0x80000000 Versorgungsspannung
- **EvtVnd3** – 0x1 Uhrzeit · 0x2 USB · 0x4 DC zu hoch · 0x8 Init-Fehler (Installationsassistent abgebrochen, Code 482)

### State Codes (Klartext)
`csv/Fronius_State_Codes_Event_Flags_1_0/{Galvo,Symo,Primo,IGPlus}_State_Codes.csv` – Code, Text.
Symo hat die längste Liste (130 Einträge) und liegt nur in der xlsx bzw. im CSV-Export vor.

---

## 5. IG String Control (Modell 403)
Common Model (L = 65) ab 40003, String Combiner 403 ab 40070, L = 56 (16 + 5 × 8, bis zu 5 Eingänge).
`DCA_SF` = −2, `DCAhr_SF` = −3, `DCV_SF` nicht unterstützt. `Evt`/`EvtVnd` Bit 15 = COMM_ERROR.
Wird von der Integration derzeit **nicht** unterstützt.

---

## 6. Bekannte Fehler / Widersprüche in den Quellen

- `FroniusEventFlags.json`: Bei **allen** Familien fehlt in `EvtVnd1` Bit **0x1** (Isolationsfehler) und in
  `EvtVnd3` Bit **0x8** (Init-Fehler). Die CSV/xlsx-Tabellen enthalten beide → **CSV/xlsx sind maßgeblich**.
- `FroniusEventFlags.json`, Abschnitt `igplus`: bei allen `class`-Texten fehlt das letzte Zeichen
  („Grid erro“, „LVR“ …), und `EvtVnd3` fehlt dort komplett.
- Familienabhängige Bedeutungen in `EvtVnd2`: 0x8, 0x80, 0x200 (siehe oben) und `EvtVnd1` 0x4000000.
- Common-Model-Länge 65 vs. 66 je nach Gerät (siehe Abschnitt 2).

---

## 7. Was fehlt (noch nicht im Repo)

- Registerkarten für **Symo, Primo, Galvo, Eco, Tauro, GEN24** (hier nur Argeno)
- Registerkarte **Fronius Smart Meter** (Modelle 201–203 / 211–213, eigene Unit-ID, meist 200+)
- Speicher-Modell **124** (Basic Storage Controls, z. B. Symo Hybrid / GEN24)

---

## 8. Bezug zum Code

| Thema | Code | Status gemäß dieser Doku |
|---|---|---|
| Modellkette dynamisch scannen | `api.py::_scan_models` | ✅ passt (Common-Länge 65/66, 103+113 parallel) |
| float bevorzugen, wenn 103 und 113 existieren | `api.py::read_device_info` | ✅ (float-Modelle werden zuerst geprüft) |
| Blöcke > 125 Register (Modell 160 mit N = 10) | `api.py::_read` | ✅ Aufteilung in 120er-Blöcke |
| `St` / `StVnd` | `sunspec.py::STATUS*` | ✅ entspricht Abschnitt 3 |
| Leistungsfaktor-Einheit | `sensor.py` (`PERCENTAGE`) | ✅ Doku: „Pct“ |
| `Evt1` / `EvtVnd1-4` dekodieren | – | ⏳ derzeit nur `Evt1` als Rohwert |
| Steuerung über Modell 123 | – | ⏳ nicht umgesetzt |
| Nennleistung aus Modell 120 | – | ⏳ nicht umgesetzt |
