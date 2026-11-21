# Fronius Modbus TCP für Home Assistant

Custom Integration, die Fronius-Wechselrichter (SunSpec) lokal per Modbus TCP ausliest.

> Status: Frühe Entwicklungsversion – bisher nur gegen einen simulierten Wechselrichter getestet.

## Funktionen

- Automatische Erkennung der SunSpec-Modelle (Adressen werden nicht fest vorgegeben)
- Unterstützt beide Fronius-Einstellungen: **float** (Modelle 111–113) und **int+SF** (101–103)
- Ein-, zwei- und dreiphasige Wechselrichter; Phasen-Sensoren werden passend angelegt
- MPP-Tracker (Modell 160): Leistung, Strom, Spannung und Energie pro Eingang
- Diagnosedaten (Host und Seriennummer geschwärzt) für Fehlerberichte

### Sensoren

| Bereich | Sensoren | Standardmäßig aktiv |
|---|---|---|
| AC | Leistung, Gesamtenergie, Strom, Spannung L-N je Phase, Netzfrequenz | ja |
| AC | Strom je Phase, Spannung L-L, Schein-/Blindleistung, Leistungsfaktor | nein |
| DC | Leistung, Strom, Spannung | ja |
| MPPT | Leistung, Strom, Spannung je Eingang | ja |
| MPPT | Energie je Eingang | nein |
| Status | Betriebszustand (SunSpec), Fronius-Zustand | ja |
| Diagnose | Temperaturen, Ereignis-Flags | nein |

Nicht implementierte Werte (z. B. Temperaturen bei vielen Fronius-Geräten) werden als „unbekannt“ angezeigt.

## Voraussetzungen

- Modbus TCP am Wechselrichter aktiviert (Weboberfläche → Kommunikation → Modbus)
- SunSpec Model Type: **float** oder **int+SF**
- Home Assistant 2025.2 oder neuer

## Installation

**HACS:** Dieses Repository als benutzerdefiniertes Repository (Typ *Integration*) hinzufügen, installieren, Home Assistant neu starten.

**Manuell:** `custom_components/fronius_modbus_tcp` nach `<config>/custom_components/` kopieren und neu starten.

Anschließend unter *Einstellungen → Geräte & Dienste → Integration hinzufügen* nach „Fronius Modbus TCP“ suchen und Host, Port (502) sowie Modbus-Adresse (meist 1) eingeben.

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
   (für ein neues SunSpec-Modell zusätzlich in `FroniusModbusClient.read_data()` einlesen).
2. Passende `SensorEntityDescription` mit gleichem `key` in `sensor.py` ergänzen.
3. Namen unter `entity.sensor.<key>` in `strings.json` und `translations/*.json` eintragen.

## Herstellerdokumentation

Die Fronius-Registerkarten und State-Code-Tabellen liegen in [`docs/fronius/`](docs/fronius/README.md) –
mit Dateiindex und Zusammenfassung der für diese Integration relevanten Punkte.
