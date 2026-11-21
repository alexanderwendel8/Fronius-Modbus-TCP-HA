# Fronius Modbus TCP für Home Assistant

Custom Integration, die Fronius-Wechselrichter (SunSpec) lokal per Modbus TCP ausliest.

> Status: Grundgerüst – aktuell wird nur die AC-Wirkleistung als Beispiel gelesen.

## Voraussetzungen

- Modbus TCP am Wechselrichter aktiviert (Weboberfläche → Kommunikation → Modbus)
- SunSpec Model Type: **float**
- Home Assistant 2025.1 oder neuer

## Installation

**HACS:** Dieses Repository als benutzerdefiniertes Repository (Typ *Integration*) hinzufügen, installieren, Home Assistant neu starten.

**Manuell:** `custom_components/fronius_modbus_tcp` nach `<config>/custom_components/` kopieren und neu starten.

Anschließend unter *Einstellungen → Geräte & Dienste → Integration hinzufügen* nach „Fronius Modbus TCP“ suchen und Host, Port (502) sowie Modbus-Adresse (meist 1) eingeben.

## Struktur

| Datei | Zweck |
|---|---|
| `api.py` | Modbus-Client, Registerzugriff, Dekodierung |
| `coordinator.py` | Zyklische Abfrage (`DataUpdateCoordinator`) |
| `config_flow.py` | Einrichtung über die UI inkl. Verbindungstest |
| `entity.py` | Basisentität mit Gerätezuordnung |
| `sensor.py` | Sensor-Definitionen |
| `strings.json`, `translations/` | Texte (EN/DE) |

## Neue Sensoren hinzufügen

1. Register in `FroniusModbusClient.read_data()` (`api.py`) lesen und in `data.values["<key>"]` ablegen.
2. Passende `SensorEntityDescription` mit gleichem `key` in `sensor.py` ergänzen.
3. Namen unter `entity.sensor.<key>` in `strings.json` und `translations/*.json` eintragen.
