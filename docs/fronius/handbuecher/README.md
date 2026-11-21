# Fronius-Handbücher (PDF) – Referenz & Zusammenfassung

← [Gesamtindex](../README.md)

- `original/` – unveränderte PDFs
- `text/` – Textfassung (`pdftotext -layout`), per `grep` durchsuchbar. Seitenumbrüche = Formfeed (`\f`).
  Tabellen sind im Text teils zerrissen → im Zweifel das PDF ansehen (Read-Tool mit `pages`).

| Datei | Dokument | Stand | Umfang | Sprache |
|---|---|---|---|---|
| `42_0410_2049_Datamanager_Modbus_TCP_RTU_DE_EN.pdf` | **Fronius Datamanager – Modbus TCP & RTU** (Bedienungsanleitung 42,0410,2049) | 033-24022026 | 104 S. | DE S. 1–~52, EN danach |
| `42_0410_2649_GEN24_Modbus_TCP_RTU_DE_EN.pdf` | **Fronius GEN24 – Modbus TCP & RTU** (42,0410,2649) | 034-28092026 | 116 S. | DE S. 1–58, EN ab S. 59 |
| `42_0426_0191_Datamanager_2.0_Bedienungsanleitung_DE.pdf` | **Fronius Datamanager 2.0 / Datamanager Box 2.0** – Bedienungsanleitung (42,0426,0191,DE) | 032-24022026 | 96 S. | DE |

Die Registertabellen selbst stehen **nicht** in den Handbüchern (nur Verweise auf
fronius.com/QR-link/0006 bzw. /0024) → dafür `archiv_1.1.7/` und `archiv_1.2.7/` verwenden.
Die Handbücher erklären **Verhalten, Geräte-IDs, Einstellungen und Steuerung**.

---

## 1. Kapitelübersicht (Seitenzahlen = gedruckte Seiten)

### GEN24 Modbus TCP & RTU (`42_0410_2649`)
Protokoll & Funktionscodes 0x03/0x06/0x10, Exception Codes (S. 5–11) · **Allgemeines** (S. 12–19:
Antwortzeiten, Geräte-IDs, Registeradressen, nicht vorhandene Werte, Zeitverhalten, PF-Vorzeichen,
Skalierungsfaktoren, Schreibverhalten) · **Einstellungen Modbus** im Webinterface (S. 20–23) ·
Common & Inverter Model, SunSpec Operating Codes (S. 24) · 120 (S. 25) · 121 (S. 26) · 122 (S. 27) ·
**123 Immediate Controls** mit Beispielen (S. 28–32) · 160 (S. 33) · **124 Storage** mit Beispielen (S. 34–37) ·
7xx-DER-Modelle, nur US (S. 38–55) · **Meter Model** (S. 56) · End Block (S. 57).

### Datamanager Modbus TCP & RTU (`42_0410_2049`)
Wie GEN24, zusätzlich: **Geräte-IDs für String Control, Smart Meter, Sensor Card** (S. 16–17) ·
**Event Flags** (S. 17) · **Fronius Register 212–216, 500–513** (S. 31–32) · **Fronius Operating Codes** (S. 33–34) ·
160 mit Hybrid-Sonderfall (S. 43–44) · 124 (Symo Hybrid, S. 45–48) · String Combiner 403 (S. 49) ·
Meter (S. 50) · String Combiner Event Flags (S. 52).

### Datamanager 2.0 Bedienungsanleitung (`42_0426_0191`)
Hardware, Installation, Solar Net, Web-Oberfläche, Netzwerk/Firewall (S. 18–19), Solar.web,
IO-Zuordnung, Lastmanagement, **Einstellungen – Modbus** (S. 73–75), Zähler (S. 78–79),
**EVU-Editor / Steuerungs-Prioritäten** (S. 81–92).

---

## 2. Kernaussagen für die Integration

### Geräte-IDs (Unit-ID) – unterscheiden sich je Generation!

| | GEN24 / Tauro / Verto | Datamanager (Symo, Primo, Galvo, IG …) |
|---|---|---|
| Wechselrichter (TCP) | **immer 1** | = **Wechselrichter-Nummer** im Solar Net (01 → 1 … 99 → 99), **Nummer 00 → ID 100** |
| Smart Meter | **200** (Default, einstellbar „Zähleradresse“); Meter 1–5 → 200–204 | **240** (fest); Meter 1–5 → 240–244 |
| String Control | – | Offset (Default **101**) + Solar-Net-Adresse |
| Sensor Card | – | **245**–247 |
| Port | **502** oder **1502** | **502** (Default, einstellbar, nicht 80) |

Pro Unit-ID beginnt jeweils eine eigene SunSpec-Kette ab 40001 (eigener Common Block je Gerät).

### Abfrageverhalten
- Abfragen **sequenziell**, nicht parallel (GEN24: max. 2 parallel).
- Timeout: **GEN24 ≥ 1 s**, **Datamanager ≥ 10 s** (Antwort läuft über Solar Net; mehr Geräte → länger).
- Lieber viele Register in einer Anfrage als viele Einzelanfragen; nicht im Millisekunden-Takt pollen.
- Datamanager: erste Common-Block-Abfrage nach Neustart dauert länger. Max. 6 WR pro Datamanager empfohlen.

### Registeradressen
- **„Registeradressen bleiben nicht konstant“** → Modelle per Abfrage suchen, dann mit Offsets arbeiten
  (genau das macht `api.py::_scan_models`).
- Register beginnen bei 1; gesendete Adresse = Registernummer − 1 (40001 → 0x9C40 = 40000).
- Wechsel float ↔ int+SF verschiebt alle nachfolgenden Modelle.
- Nur Inverter- und Meter-Model sind float; **alle anderen Modelle bleiben int+SF**.

### Nicht vorhandene Werte (offizielle Liste)
int16 0x8000 · uint16 0xFFFF · acc16 0 · enum16 0xFFFF · bitfield16 0xFFFF · int32 0x80000000 ·
uint32 0xFFFFFFFF · acc32 0 · enum32 0xFFFFFFFF · bitfield32 0xFFFFFFFF · int64 0x8000000000000000 ·
uint64/acc64 0xFFFFFFFFFFFFFFFF bzw. 0 · string alles 0x0000 · float32 **0x7FC00000 (NaN)** · sunssf **0x8000**.
Auch „unterstützte“ Register können so einen Wert liefern (z. B. AphB/AphC bei einphasigem WR).

### Skalierungsfaktoren
**Nicht statisch** – auch im float-Modus vorhanden, können sich bei Firmware-Updates und (GEN24)
**zur Laufzeit** ändern (auto-scale). → Immer zusammen mit den Werten lesen, nie cachen.

### Power-Factor-Vorzeichen (EEI)
PF **negativ** bei positiver Blindleistung (übererregt, Q1), **positiv** bei negativer Blindleistung (untererregt, Q4).

### Schreiben / Steuerung
- Voraussetzung: im Webinterface **„Wechselrichter-Steuerung über Modbus“ / „Steuerung erlauben“** aktiv;
  optional **„Steuerung einschränken“** auf IP-Adressen/CIDR.
- Read-only oder nicht unterstützte Register beschreiben → **kein** Exception Code, Wert wird ignoriert.
- Modell 123/124 bei deaktivierter Steuerung → Exception. Ungültiger Wert → **Exception 3** (Illegal Data Value).
- Steuerungs-Prioritäten (IO-Steuerung, dynamische Leistungsreduzierung, Modbus) können Befehle verhindern.
- Datamanager: Modbus-Datenausgabe „aus“ setzt alle per Modbus gesendeten Vorgaben zurück.

### Zeitverhalten (Modell 123/124)
`WinTms` 0–300 s (zufälliger Start), `RvrtTms` 0–28800 s (Rückfallzeit; **jede Modbus-Nachricht startet den
Timer neu**; 0 = dauerhaft), `RmpTms` (Rampe; Datamanager erst ab FW 3.13.3-2 / Hybridmanager 1.11.3-2).

### Modell 123 – Immediate Controls
- `Conn` = 0 → Standby (keine Einspeisung), 1 → Einspeisebetrieb.
- `WMaxLimPct` 0–100 % (SF beachten, z. B. 3000 = 30 % bei SF −2), dann `WMaxLim_Ena` = 1.
  Werte bei aktiver Betriebsart ändern: neuen Wert schreiben **und** `WMaxLim_Ena` = 1 erneut schreiben.
- Effizient: 5 Register (`WMaxLimPct`, `_WinTms`, `_RvrtTms`, `_RmpTms`, `WMaxLim_Ena`) mit 0x10 in einem Befehl,
  z. B. 80 %: `8000, 0, 0, 0, 1`.
- Außerdem: konstanter PF (`OutPFSet`, `OutPFSet_Ena`) und konstante relative Blindleistung (`VArMaxPct`, `VArPct_Ena`).

### Modell 122 – Extended Measurements (GEN24)
`PVConn` Bit 0 verbunden / 1 ansprechbar / 2 speist ein · `ECPConn` 1 = speist ein ·
`StActCtl` Bit 0 Leistungsreduktion, 1 feste Blindleistung, 2 fester PF · `TmSrc` = „RTC“ ·
`Tms` = Sekunden seit 01.01.2000 UTC · `Ris` Isolationswiderstand.

### Modell 160 – MPPT
- Bei mehreren DC-Eingängen liefert das Inverter-Model nur `DCW` (Summe); `DCA`/`DCV` „not implemented“.
- **GEN24 mit Speicher:** zwei zusätzliche Blöcke (Laden = MPP3, Entladen = MPP4).
- **Symo Hybrid (Datamanager):** String 1 = PV, **String 2 = Speicher, nur Absolutwert**;
  Entladen: `DCW = 1_DCW + 2_DCW`, Laden: `DCW = 1_DCW − 2_DCW` → Lade-/Entladerichtung nur aus `DCW` ableitbar.

### Modell 124 – Basic Storage Control (GEN24 Plus, Symo Hybrid)
- Nur bei Geräten mit Speicher. Alle Vorgaben sind **Empfehlungen** (WR darf aus Sicherheitsgründen abweichen).
- `WChaMax` = max(MaxChaRte, MaxDisChaRte); **0 = kein Speicher vorhanden**.
- `ChaState` = SoC in % (Restkapazität / max. Kapazität). `ChaSt`: OFF = nicht verfügbar, EMPTY, DISCHARGING,
  CHARGING, FULL, HOLDING, TESTING (Kalibrier-/Serviceladung).
- Leistungsfenster: **negativ = Laden, positiv = Entladen**. `StorCtl_Mod` Bit 0 = Ladegrenze (`InWRte`) aktiv,
  Bit 1 = Entladegrenze (`OutWRte`) aktiv. Beispiele (WChaMax = 3300 W):
  nur Laden `OutWRte=0, Mod=2` · nur Entladen `InWRte=0, Mod=1` · weder noch `0/0, Mod=3` ·
  ±50 % `50/50, Mod=3` · Zwangsladen 50–75 % `InWRte=75, OutWRte=−50, Mod=3`.
- `MinRsvPct` = Mindest-SoC (wird in Solar.web als „Energiesparmodus“ sichtbar).
  Batterie im Standby wird geweckt, wenn MinRsvPct unter den letzten SoC gesetzt wird.
- `ChaGriSet` (Netzladung) ist **UND-verknüpft** mit „Batterieladung aus EVU-Netz erlauben“ im Webinterface.
- Änderungen an `InWRte`/`OutWRte`/`StorCtl_Mod` können in Solar.web „Erzwungene Nachladung“ auslösen.

### Meter Model (201–203 / 211–213)
Vorzeichen hängen von der **Meter-Location** ab:

| Location | 0 (Netz) | 1 (Verbrauch) | 3 (ext. Erzeuger) | 256–511 (Sub-Load) |
|---|---|---|---|---|
| `W` positiv | Bezug aus dem Netz | Produktion | Erzeugung | Last produziert |
| `W` negativ | Einspeisung ins Netz | normaler Verbrauch | Verbrauch | normaler Verbrauch |
| Energy plus (Import) | Netzbezug | Produktion* | Erzeugung | Produktion* |
| Energy minus (Export) | Netzeinspeisung | Verbrauch | Verbrauch | Verbrauch |

\* nur in Ausnahmefällen. Die Location selbst steht nicht in den SunSpec-Registern
(laut Smart-Meter-Map enthält `Opt` den Zählernamen, z. B. „<primary>“).

### End Block – Startadressen laut Handbuch
GEN24 WR: float 40313 / int+SF 40303 · String Control 40127 · Energiezähler: float 40195 / int+SF 40176.

### Nur Datamanager: Fronius-Register (unterhalb von 40001)
| Register | Name | Funktion |
|---|---|---|
| 212 | `F_Delete_Data` | 0xFFFF → gespeicherte Nennwerte dieses WR löschen |
| 213 | `F_Store_Data` | 0xFFFF → Nennwerte (120/121) aller WR dauerhaft speichern |
| 214 | `F_Active_State_Code` | aktuell anliegender **State Code** des WR |
| 215 | `F_Reset_All_Event_Flags` | 0xFFFF → State Code, Evt1/2, EvtVnd1–4 zurücksetzen |
| 216 | `F_ModelType` | 1 = float, 2 = int+SF; muss sofort mit erneutem Schreiben von **0x06** bestätigt werden |
| 500–501 | `F_Site_Power` | Anlagenleistung W (ohne SF) |
| 502–505 | `F_Site_Energy_Day` | Tagesenergie Wh |
| 506–509 | `F_Site_Energy_Year` | Jahresenergie Wh |
| 510–513 | `F_Site_Energy_Total` | Gesamtenergie Wh |

Event Flags bleiben aktiv, solange der State Code anliegt; einige werden nicht automatisch gelöscht
(→ Register 215). Mehrere State Codes können ein Event Flag teilen (Tabellen in `archiv_1.1.7`).

### Datamanager-Einstellungen
- Datamanager 2.0: Datenausgabe ab Werk auf **rtu**; Datamanager 1 hat kein RTU.
  Für Home Assistant muss **tcp** gewählt werden. Mit konfiguriertem Smart Meter ist „rtu“ nicht möglich.
- **Demo-Modus**: liefert feste Daten ohne angeschlossene Geräte – nützlich zum Testen der Integration.

### Sicherheit (Datamanager 2.0 Anleitung)
Modbus TCP ist eine **ungesicherte** Schnittstelle; Geräte nicht per Portweiterleitung ins Internet stellen;
Steuerung bei Bedarf per „Steuerung einschränken“ auf die IP von Home Assistant begrenzen.
