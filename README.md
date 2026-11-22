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
| | Status (Datamanager) | Statuscode und Statusmeldung im Klartext (z. B. „306 Power Low“) | ja |
| | Fehler | Binärsensor Fehler; GEN24/Tauro/Verto zusätzlich Warnung; Datamanager: aktive Fehlerklassen im Klartext („Power low“/„DC low“ beim Ab- und Anschalten zählen nicht als Fehler) | ja |
| | Ereignisse | SunSpec-Ereignisse im Klartext (z. B. „Over temperature“) | ja |
| | Modell 122 | Gesamtenergie (genau, 64-bit-Zähler; GEN24 und Datamanager); Isolationswiderstand (Diagnose, GEN24) | ja |
| | Anlage (Datamanager) | Anlagenleistung, Energie heute, Energie dieses Jahr, Anlagen-Gesamtenergie | ja |
| | Vorgaben (Modell 123, nur lesend) | Leistungsbegrenzung in %, Leistungsbegrenzung aktiv, Einspeisung freigegeben | ja |
| | Vorgaben (Diagnose) | Leistungsfaktor- und Blindleistungs-Vorgabe und ob aktiv | nein |
| | Nennwerte (Modell 120) | Nennleistung; Batteriekapazität; max. Lade-/Entladeleistung | ja (Diagnose) |
| | Nennwerte (Diagnose) | Nenn-Scheinleistung, Nennstrom | nein |
| | Diagnose | Temperaturen, Ereignis-Flags (Rohwert) | nein |
| Smart Meter | | Leistung, Energie Bezug, Energie Einspeisung, Strom, Spannung L-N je Phase, Frequenz | ja |
| | | Leistung/Strom/Energie je Phase, Spannung L-L, Schein-/Blindleistung, Leistungsfaktor | nein |

\* Bei mehreren DC-Eingängen liefert Fronius DC-Strom und DC-Spannung nur je String (Modell 160);
die Gesamtwerte im Wechselrichter-Modell sind dann „nicht unterstützt“ und werden nicht angelegt.

\*\* Energiezähler der Batterie nur bei GEN24/Verto (Symo Hybrid liefert keine).

Optionale Werte, die das Gerät beim Start als „nicht unterstützt“ meldet (Temperaturen, Ereignis-Flags,
Energie je String, einzelne Smart-Meter-Werte), werden gar nicht erst angelegt; ältere Einträge dafür
entfernt die Integration selbst. Unterstützt eine neue Firmware den Wert später, erscheint der Sensor nach
dem nächsten Neustart. Kernwerte wie Leistung, Strom und Spannung werden immer angelegt, auch wenn sie
vorübergehend „unbekannt“ sind (z. B. nachts).

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

## Steuerung (optional)

Standardmäßig liest die Integration nur. Schreibende Entitäten gibt es erst nach
*Einstellungen → Geräte & Dienste → Fronius Modbus TCP → Konfigurieren → „Steuerung erlauben“*.

**Voraussetzung am Gerät:** In der Fronius-Weboberfläche muss „Wechselrichter-Steuerung über Modbus“
(Datamanager) bzw. „Steuerung erlauben“ (GEN24) aktiv sein. Empfehlenswert: „Steuerung einschränken“
auf die IP-Adresse von Home Assistant. Vorgaben des Netzbetreibers (Steuerungs-Prioritäten im
EVU-Editor) haben Vorrang.

| Entität | Typ | Wirkung |
|---|---|---|
| Leistungsbegrenzung | Zahl 0–100 % | Maximale Ausgangsleistung in % der Nennleistung. Bei aktiver Begrenzung wirkt ein neuer Wert sofort, sonst wird er nur hinterlegt. |
| Leistungsbegrenzung aktiv | Schalter | Begrenzung ein/aus |
| Einspeisung | Schalter | Aus = Standby (keine Einspeisung) |
| Rückfallzeit Vorgaben | Zahl (s), Konfiguration | Standard 300 s, siehe unten |
| Ereignisse zurücksetzen | Taste, nur Datamanager | Löscht hängengebliebene Event Flags und den Statuscode |

Ist die Steuerung erlaubt, ersetzen „Leistungsbegrenzung“, „Leistungsbegrenzung aktiv“ und
„Einspeisung“ die gleichnamigen reinen Anzeige-Entitäten.

**Rückfallzeit:** Jede Vorgabe wird mit einer Rückfallzeit geschrieben. Da jede Modbus-Abfrage den Timer
im Wechselrichter neu startet, bleibt eine Vorgabe aktiv, solange Home Assistant läuft. Fällt Home Assistant
aus, kehrt der Wechselrichter nach dieser Zeit von selbst in den Normalbetrieb zurück – eine Drosselung
oder ein Standby kann also nicht „hängen bleiben“.

Beispiel-Automation: bei negativem Strompreis auf 0 % drosseln:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.strompreis
    below: 0
actions:
  - action: number.set_value
    target: {entity_id: number.symo_3_0_3_m_power_limit}
    data: {value: 0}
  - action: switch.turn_on
    target: {entity_id: switch.symo_3_0_3_m_power_limit_active}
```

## Struktur

| Datei | Zweck |
|---|---|
| `api.py` | Modbus-Client, Erkennung der Modellkette, Registerzugriff |
| `sunspec.py` | SunSpec-Modelldefinitionen und Dekodierung (ohne HA-Abhängigkeit) |
| `coordinator.py` | Zyklische Abfrage (`DataUpdateCoordinator`) |
| `config_flow.py` | Einrichtung über die UI inkl. Verbindungstest |
| `entity.py` | Basisentität mit Gerätezuordnung |
| `sensor.py` | Sensor-Definitionen |
| `binary_sensor.py` | Binärsensoren (Fehler, Warnung, Vorgaben aus Modell 123) |
| `number.py`, `switch.py`, `button.py` | Steuerung (nur mit Option „Steuerung erlauben“) |
| `state_codes.py` | Fronius State Codes im Klartext (erzeugt mit `scripts/generate_state_codes.py`) |
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
