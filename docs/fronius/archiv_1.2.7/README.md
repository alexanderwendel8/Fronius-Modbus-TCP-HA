# Archiv 1.2.7-2 – GEN24 (Primo/Symo), Tauro, Tauro ECO, Verto, Smart Meter

← [Gesamtindex](../README.md)

Herstellerunterlagen von Fronius, Archivversion **1.2.7-2** (gebündelt mit GEN24-Firmware 1.36.x),
siehe [`original/INFO.TXT`](original/INFO.TXT) und [`original/CHANGELOG.TXT`](original/CHANGELOG.TXT).

- `original/` – unveränderte xlsx-Dateien
- `csv/<Datei>/<Blatt>.csv` – jedes Tabellenblatt als CSV

> **Adressierung in diesem Archiv:**
> - Blatt **`Complete_Map.csv`**: absolute Adressen, **1-basiert** (40001 = „SunS“).
> - Blätter der **einzelnen Modelle** (`inverter_11x.csv`, `mppt_160.csv` …): **relative** Adressen,
>   `1` = Modell-ID, `2` = Länge L, `3` = erstes Datenregister.
>   → Offset im Modellrumpf (wie in `sunspec.py`) = relative Adresse − 3.
>
> Spalten: `Start, End, Size, R/W, Function codes, Name, Description, Type, Units, Scale Factor, Range of values`.
> Die Spalte „Range of values“ enthält die Fronius-Hinweise („not supported“, Wertebereiche, Firmware-Abhängigkeiten).

---

## 1. Dateiindex

| Gerät | Format | Variante | Datei (ohne `.xlsx`) | Modelle |
|---|---|---|---|---|
| Primo/Symo GEN24 | float | ROW | `Gen24_Primo_Symo_Inverter_Register_Map_Float_ROW` | 1, 111/113, 120–123, 160 (N=2) |
| Primo/Symo GEN24 Plus (Batterie) | float | ROW | `Gen24_Primo_Symo_Inverter_Register_Map_Float_storage_ROW` | + 160 (N=4), **124** |
| Primo/Symo GEN24 | int+SF | ROW | `Gen24_Primo_Symo_Inverter_Register_Map_IntSF_ROW` | 1, 101/103, 120–123, 160 (N=2) |
| Primo/Symo GEN24 Plus (Batterie) | int+SF | ROW | `Gen24_Primo_Symo_Inverter_Register_Map_IntSF_storage_ROW` | + 160 (N=4), **124** |
| Primo/Symo GEN24 | float | US | `Gen24_Primo_Symo_Inverter_Register_Map_Float_US` | + 124, 701–713 |
| Primo/Symo GEN24 Plus | float | US | `Gen24_Primo_Symo_Inverter_Register_Map_Float_storage_US` | + 124, 701–713 |
| Primo/Symo GEN24 | int+SF | US | `Gen24_Primo_Symo_Inverter_Register_Map_IntSF_US` | + 124, 701–713 |
| Primo/Symo GEN24 Plus | int+SF | US | `Gen24_Primo_Symo_Inverter_Register_Map_IntSF_storage_US` | + 124, 701–713 |
| Tauro | float | ROW | `Tauro_Inverter_Register_Map_Float_ROW` | 1, 113, 120–123, 160 (N=3) |
| Tauro | int+SF | ROW | `Tauro_Inverter_Register_Map_IntSF_ROW` | 1, 103, 120–123, 160 (N=3) |
| Tauro ECO | float | ROW | `Tauro_ECO_Inverter_Register_Map_Float_ROW` | 1, 113, 120–123, 160 (N=1) |
| Tauro ECO | int+SF | ROW | `Tauro_ECO_Inverter_Register_Map_IntSF_ROW` | 1, 103, 120–123, 160 (N=1) |
| Verto (4 MPPT) | float | ROW | `Verto_Inverter_Register_Map_4MPPT_Float_ROW` | 1, 113, 120–123, 160 (N=4) |
| Verto (4 MPPT) | int+SF | ROW | `Verto_Inverter_Register_Map_4MPPT_IntSF_ROW` | 1, 103, 120–123, 160 (N=4) |
| Verto (3 MPPT) | float | ROW | `Verto_Inverter_Register_Map_3MPPT_Float_ROW` | 1, 113, 120–123, 160 (N=3) |
| Verto (3 MPPT) | int+SF | ROW | `Verto_Inverter_Register_Map_3MPPT_IntSF_ROW` | 1, 103, 120–123, 160 (N=3) |
| Verto Plus (3 MPPT + Batterie) | float | ROW | `Verto_Inverter_Register_Map_3MPPT_Float_storage_ROW` | 1, 113, 120–123, 160 (N=5), **124** |
| Verto Plus (3 MPPT + Batterie) | int+SF | ROW | `Verto_Inverter_Register_Map_3MPPT_IntSF_storage_ROW` | 1, 103, 120–123, 160 (N=5), **124** |
| Fronius Smart Meter | float | – | `Smart_Meter_Register_Map_Float` | 1, **211/212/213/214** |
| Fronius Smart Meter | int+SF | – | `Smart_Meter_Register_Map_IntSF` | 1, **201/202/203/204** |

ROW = „Rest of World“ (Europa usw.), US = Nordamerika (zusätzlich SunSpec-DER-Modelle 701–713,
Modell 124 auch ohne Batterie vorhanden, dann alle Register „not supported“).

Nicht im Upload enthalten: Smart Meter **int+SF** (Modelle 201–204), Tauro **float**, Verto 3 MPPT **float**,
GEN24 int+SF storage **US**.

---

## 2. Absolute Startadressen (1-basiert, aus `Complete_Map.csv`)

Allen Geräten gemeinsam: `SunS` @40001, Common (1) @40003 mit **L = 65**, Inverter-Modell @**40070**.

| Datei | 1xx | 120 | 121 | 122 | 123 | 160 (L) | 124 | Ende 0xFFFF |
|---|---|---|---|---|---|---|---|---|
| GEN24 Float ROW | 40070 (111/113, L=60) | 40132 | 40160 | 40192 | 40238 | 40264 (48) | – | 40314 |
| GEN24 Float storage ROW | 40070 | 40132 | 40160 | 40192 | 40238 | 40264 (88) | 40354 | 40380 |
| GEN24 IntSF ROW | 40070 (101/103, L=50) | 40122 | 40150 | 40182 | 40228 | 40254 (48) | – | 40304 |
| GEN24 IntSF storage ROW | 40070 | 40122 | 40150 | 40182 | 40228 | 40254 (88) | 40344 | 40370 |
| GEN24 Float US / storage US | 40070 | 40132 | 40160 | 40192 | 40238 | 40264 (88) | 40354 | 41900 (nach 701–713) |
| GEN24 IntSF US | 40070 | 40122 | 40150 | 40182 | 40228 | 40254 (88) | 40344 | 41890 |
| Tauro IntSF | 40070 (103) | 40122 | 40150 | 40182 | 40228 | 40254 (68) | – | 40324 |
| Tauro ECO Float / IntSF | 40070 (113 / 103) | 40132 / 40122 | … | … | … | 40264 / 40254 (28) | – | 40294 / 40284 |
| Verto 4MPPT Float / IntSF | 40070 (113 / 103) | 40132 / 40122 | … | … | … | 40264 / 40254 (88) | – | 40354 / 40344 |
| Verto 3MPPT IntSF storage | 40070 (103) | 40122 | 40150 | 40182 | 40228 | 40254 (108) | 40364 | 40390 |
| Smart Meter Float | 40070 (211–214, L=124) | – | – | – | – | – | – | 40196 |

Die Länge von Modell 160 = 8 + 20 × N.

---

## 3. Wechselrichter-Modell 10x/11x – Besonderheiten

Quelle: `csv/<Datei>/inverter_11x.csv` bzw. `inverter_10x.csv` / `inverter_103.csv` / `inverter_113.csv`.

- Phasenwerte B/C und Leiter-Leiter-Spannungen: „supported/not-supported depending on the grid connection“.
- `DCA`, `DCV`: **nicht unterstützt bei mehreren DC-Eingängen** → Werte aus Modell 160 verwenden. `DCW` wird geliefert.
- `TmpCab` unterstützt; `TmpSnk`, `TmpTrns`, `TmpOt` nicht unterstützt.
- `St`: siehe „SunSpec Operating Codes“ im Modbus-TCP-&-RTU-Benutzerhandbuch (nicht im Repo).
  `StVnd`: **„same as register St“** (keine eigenen Fronius-Codes wie beim Datamanager).
- **`EvtVnd1` / `EvtVnd2` haben beim GEN24 eine ganz andere Bedeutung als beim Datamanager:**
  Es sind Bitfelder nach **Schweregrad**, keine Fehlerklassen:
  - `EvtVnd1` = Sicht „Customer“, `EvtVnd2` = Sicht „Technician“ (Obermenge von Customer)
  - Bit 0 = mindestens ein aktiver **Fehler**, Bit 1 = **Warnung**, Bit 2 = **Info**
  - `EvtVnd3`, `EvtVnd4`: nicht unterstützt
  - → Die Tabellen `EvtVnd1-4_*.csv` aus Archiv 1.1.7 gelten **nicht** für GEN24/Tauro/Verto.
- `PF` Einheit „Pct“, `WH` = AC-Lebensdauerenergie.

## 4. MPPT-Modell 160

Quelle: `csv/<Datei>/mppt_160.csv`. Register-Namen im Format `module/<n>/<Feld>`.

- Scale Factors „auto-scaled“ (können sich ändern → bei jedem Lesen mitlesen).
- `Evt`, `TmsPer`, je Modul `Tmp`, `DCSt`, `DCEvt`: nicht unterstützt. `Tms` = Sekunden seit 01.01.2000.
- `DCWH` (Lebensdauerenergie je Eingang) **wird geliefert** (anders als beim Argeno).
- **Batterie-Geräte** (storage): zusätzliche Module für den Batterieanschluss:
  - GEN24 Plus: Modul 3 `StCha 3` (Laden), Modul 4 `StDisCha 4` (Entladen)
  - Verto Plus: Modul 4 `StCha 4`, Modul 5 `StDisCha 5` (N = MPPT + 2 × Batterieeingänge)
  - Beim Entladen ist das Lade-Modul 0 und umgekehrt (`DCA`, `DCW`).
  - `DCV` und `DCWH` bis Firmware 1.30 ebenfalls 0 im inaktiven Modul;
    **ab 1.31** immer Batteriespannung bzw. Lade-/Entladezähler.
  - → Batteriemodule dürfen **nicht** zur PV-Leistung addiert werden.
- **US ohne Batterie:** N = 4, aber Module 3/4 „not supported“.

## 5. Speicher-Modell 124 (Basic Storage Controls)

Quelle: `csv/<Datei>/storage_124.csv`. Relevante Register (relativ):

| Rel. | Name | R/W | Bedeutung |
|---|---|---|---|
| 3 | `WChaMax` | R | Bezugswert für max. Lade-/Entladeleistung (W, `WChaMax_SF` = 0) |
| 6 | `StorCtl_Mod` | **RW** | Bit 0 = Ladegrenze aktiv, Bit 1 = Entladegrenze aktiv |
| 8 | `MinRsvPct` | **RW** | Mindestreserve in % (`MinRsvPct_SF` = −2) |
| 9 | `ChaState` | R | **Ladezustand (SoC)** in % (`ChaState_SF` = −2) |
| 12 | `ChaSt` | R | 1 OFF, 2 EMPTY, 3 DISCHARGING, 4 CHARGING, 5 FULL, 6 HOLDING, 7 TESTING (Kalibrierung/Service) |
| 13 | `OutWRte` | **RW** | max. Entladeleistung in % von `WChaMax` (−100…+100 %, `InOutWRte_SF` = −2) |
| 14 | `InWRte` | **RW** | max. Ladeleistung in % von `WChaMax` (−100…+100 %) |
| 16 | `InOutWRte_RvrtTms` | **RW** | Rückfallzeit 0–28800 s |
| 18 | `ChaGriSet` | **RW** | 0 = nur PV, 1 = Laden aus dem Netz erlaubt |

Nicht unterstützt: `StorAval`, `InBatV`, `VAChaMax_SF`, `InOutWRte_WinTms`, `InOutWRte_RmpTms`.
Ungültiges Leistungsfenster (`StorCtl_Mod` = 3 und `-InWRte > OutWRte`) → Modbus-Exception 3.

## 6. Steuerung (Modell 123) und Nennwerte (Modell 120)

- **123** (`controls_123.csv`): `Conn`, `WMaxLimPct` (0–100 %, SF −2) mit `_WinTms`/`_RvrtTms`/`_RmpTms`/`WMaxLim_Ena`,
  `OutPFSet` (SF −3) mit `_Ena`, `VArMaxPct` (−100…+100 %), `VArPct_Mod` fest = 2 (in % von VArMax).
  Beim GEN24 sind – anders als beim Argeno – auch `*_WinTms` und `*_RmpTms` beschreibbar.
- **120** (`nameplate_120.csv`): `DERTyp` = 4 (PV), `WRtg` (Nennleistung, SF 1), `VARtg`, `ARtg` (SF −2),
  `PFRtgQ1/Q4` (SF −3). Speicherwerte (`WHRtg`, `AhrRtg`, `MaxChaRte` …) nicht unterstützt.

## 7. Smart Meter (Modelle 211–214, float)

Quelle: `csv/Smart_Meter_Register_Map_Float/ac_meter_21x.csv`.

- Modell-ID: 211 einphasig, 212 Split-Phase, 213 Drehstrom Stern (ABCN), 214 Drehstrom Dreieck (ABC); L = 124.
- Common Model: `Mn`, `Md` (z. B. „Smart Meter 63A“), `Opt` = Zählername (z. B. „<primary>“), `Vr`, `SN`.
- Werte: Ströme, Spannungen (L-N, L-L, Mittelwerte), `Hz`, Wirk-/Schein-/Blindleistung gesamt und je Phase,
  Leistungsfaktor (Einheit „PF“, nicht %), **Energiezähler** `TotWhExp`/`TotWhImp` (+ je Phase),
  `TotVAhExp`/`TotVAhImp` (+ je Phase; seit Archiv 1.2.6-2 unterstützt).
- Nicht unterstützt: alle Blindenergiezähler `TotVArh*`. `Evt` fest 0.
- Phasenwerte abhängig von Netzanschluss und Zählertyp.
- Die **Modbus-Unit-ID** des Zählers steht nicht in der Registerkarte (`DA`: 1–247), aber im
  GEN24-Handbuch: Default **200** (Zähler 1–5 → 200–204, einstellbar), siehe [`../handbuecher/README.md`](../handbuecher/README.md).
- Vorzeichen von `W` und Bedeutung von Import/Export hängen von der Meter-Location ab (Handbuch, Abschnitt Meter Model).

## 8. Wichtige Änderungen laut Changelog

- 1.1.4: Beschreibung `EvtVnd1-2` ergänzt, `EvtVnd3-4` nicht unterstützt
- 1.1.5: MPPT-Registernamen jetzt `module/1/ID` statt `1_ID`
- 1.2.1: Batteriespannung und -energie in Modell 160 immer gemeldet (`module/X/DCV`, `module/X/DCWH`)
- 1.2.3: Hinweis zum Wertebereich von `St` im Modell 11x
- 1.2.4: Aufteilung in US- und ROW-Dateien, 7xx-Modelle für US
- 1.2.6-1: US: 160.N = 4; Modell 124 (alles „not supported“) für US-Geräte ohne Batterie
- 1.2.6-2: Smart Meter: Wirk-/Scheinenergie je Phase jetzt unterstützt
- 1.2.7: Verto/Tauro MPPT 3/4 „not supported“-Kennzeichnung korrigiert; MPPT-Anzahl ROW/US korrigiert
