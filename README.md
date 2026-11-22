# Fronius Modbus TCP für Home Assistant

Custom Integration, die Fronius-Wechselrichter (SunSpec) lokal per Modbus TCP ausliest.

> Status: Frühe Entwicklungsversion – getestet gegen simulierte Geräte (GEN24 Plus mit Smart Meter,
> Symo Hybrid am Datamanager), noch nicht an echter Hardware.

## Funktionen

- Automatische Erkennung der SunSpec-Modelle (Adressen werden nicht fest vorgegeben)
- Beide Fronius-Einstellungen: **float** (111–113 / 211–214) und **int+SF** (101–103 / 201–204)
- GEN24 / Tauro / Verto **und** Datamanager-Geräte (Symo, Primo, Galvo, Eco, Symo Hybrid …)
- Ein-, zwei- und dreiphasige Geräte; Phasen-Sensoren werden passend angelegt
- **PV-Strings** (Modell 160) einzeln und als Summe
- **Batterie** (GEN24 Plus, Verto Plus, Symo Hybrid): Lade-/Entladeleistung, Spannung, Energiezähler,
  Ladezustand, Status, Mindestreserve, Ladequelle (Modell 124)
- **Fronius Smart Meter** als eigenes Gerät: Leistung, Bezug/Einspeisung, Ströme, Spannungen, Frequenz
- Diagnosedaten (Host und Seriennummern geschwärzt) für Fehlerberichte

### Sensoren

| Gerät | Bereich | Sensoren | Standardmäßig aktiv |
|---|---|---|---|
| Wechselrichter | AC | Leistung, Gesamtenergie, Strom, Spannung L-N je Phase, Netzfrequenz | ja |
| | AC | Strom je Phase, Spannung L-L, Schein-/Blindleistung, Leistungsfaktor | nein |
| | DC | Leistung; Strom und Spannung nur bei Geräten mit einem DC-Eingang* | ja |
| | PV | PV-Leistung und PV-Strom gesamt; Leistung, Strom, Spannung je String | ja |
| | PV | Energie je String | nein |
| | Batterie | Leistung (+ Entladen / − Laden), Lade- und Entladeleistung, Spannung, geladene/entladene Energie**, Ladezustand, Status, Mindestreserve | ja |
| | Batterie | Ladequelle, Maximalleistung (Diagnose); Steuermodus, Lade-/Entladegrenze | teils |
| | Status | Betriebszustand (SunSpec), Fronius-Zustand | ja |
| | Diagnose | Temperaturen, Ereignis-Flags | nein |
| Smart Meter | | Leistung, Energie Bezug, Energie Einspeisung, Strom, Spannung L-N je Phase, Frequenz | ja |
| | | Leistung/Strom/Energie je Phase, Spannung L-L, Schein-/Blindleistung, Leistungsfaktor | nein |

\* Bei mehreren DC-Eingängen liefert Fronius DC-Strom und DC-Spannung nur je String (Modell 160);
die Gesamtwerte im Wechselrichter-Modell sind dann „nicht unterstützt“ und werden nicht angelegt.

\*\* Energiezähler der Batterie nur bei GEN24/Verto (Symo Hybrid liefert keine).

Nicht unterstützte Werte (z. B. Temperaturen bei vielen Fronius-Geräten) werden als „unbekannt“ angezeigt.

**Vorzeichen:** Batterieleistung positiv = Entladen. Smart Meter wie vom Gerät geliefert – bei Einbau am
Netzanschlusspunkt ist positiv = Netzbezug, negativ = Einspeisung.

## Voraussetzungen

- Modbus TCP aktiviert:
  - **GEN24 / Tauro / Verto:** Weboberfläche → Kommunikation → Modbus → *TCP Server*
  - **Datamanager:** Weboberfläche → Einstellungen → Modbus → Datenausgabe **tcp** (Datamanager 2.0 steht ab Werk auf rtu)
- SunSpec Model Type: **float** oder **int+SF**
- Home Assistant 2025.2 oder neuer

## Installation

**HACS:** Dieses Repository als benutzerdefiniertes Repository (Typ *Integration*) hinzufügen, installieren, Home Assistant neu starten.

**Manuell:** `custom_components/fronius_modbus_tcp` nach `<config>/custom_components/` kopieren und neu starten.

Anschließend unter *Einstellungen → Geräte & Dienste → Integration hinzufügen* nach „Fronius Modbus TCP“ suchen:

| Feld | GEN24 / Tauro / Verto | Datamanager (Symo, Primo, Galvo …) |
|---|---|---|
| Host | IP des Wechselrichters | IP des Datamanagers |
| Port | 502 (oder 1502) | 502 |
| Modbus-Adresse Wechselrichter | **1** | **Wechselrichter-Nummer** (00 → 100) |
| Modbus-Adresse Smart Meter | leer = automatisch (200) | leer = automatisch (240) |

`0` als Smart-Meter-Adresse schaltet den Zähler ab. Bei mehreren Wechselrichtern am Datamanager
für jeden Wechselrichter einen eigenen Eintrag anlegen; der Smart Meter wird automatisch nur dem
ersten Eintrag zugeordnet.

## Struktur

| Datei | Zweck |
|---|---|
| `api.py` | Modbus-Client, Erkennung der Modellkette, Registerzugriff |
| `sunspec.py` | SunSpec-Modelldefinitionen und Dekodierung (ohne HA-Abhängigkeit) |
| `coordinator.py` | Zyklische Abfrage (`DataUpdateCoordinator`) |
| `config_flow.py` | Einrichtung über die UI inkl. Verbindungstest |
| `entity.py` | Basisentität mit Gerätezuordnung |
| `sensor.py` | Sensor-Definitionen |
| `diagnostics.py` | Diagnosedaten-Export |
| `strings.json`, `translations/` | Texte (EN/DE) |

## Neue Sensoren hinzufügen

1. Wert in der passenden `parse_*`-Funktion in `sunspec.py` dekodieren und unter `"<key>"` zurückgeben
   (für ein neues SunSpec-Modell zusätzlich in `FroniusModbusClient.read_inverter_data()` einlesen).
2. Passende `SensorEntityDescription` mit gleichem `key` in `sensor.py` ergänzen.
3. Namen unter `entity.sensor.<key>` in `strings.json` und `translations/*.json` eintragen.

## Tests

```bash
pip install -r requirements_test.txt
pytest
```

Die Tests starten simulierte Fronius-Geräte (`tests/simulator.py`) als echten Modbus-TCP-Server und
richten die Integration in einer Home-Assistant-Testinstanz ein.

## Herstellerdokumentation

Die Fronius-Registerkarten und State-Code-Tabellen liegen in [`docs/fronius/`](docs/fronius/README.md) –
mit Dateiindex und Zusammenfassung der für diese Integration relevanten Punkte.
