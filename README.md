**Deutsch** | [English](README.en.md)

# Fronius Modbus TCP für Home Assistant

Custom Integration, die Fronius-Wechselrichter lokal per **Modbus TCP (SunSpec)** ausliest – ohne Cloud
und ohne Solar.web. Unterstützt werden GEN24/Tauro/Verto sowie ältere Geräte am Datamanager
(Symo, Primo, Galvo, Eco, Symo Hybrid …), jeweils mit PV-Strings, Batterie und Fronius Smart Meter.
Optional lassen sich Leistungsbegrenzung und Einspeisung aus Home Assistant steuern.

> **Status:** Version 0.2 – im Einsatz an einem echten Symo 3.0-3-M am Datamanager 2.0
> (siehe [Getestete Geräte](#getestete-geräte)); GEN24, Batterie und Smart Meter bisher nur gegen
> simulierte Geräte. Rückmeldungen zu weiteren Geräten sind willkommen.

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
Energie je String, einzelne Smart-Meter-Werte), werden gar nicht erst angelegt. Unterstützt eine neue Firmware
den Wert später, erscheint der Sensor nach dem nächsten Neustart. Ein Sensor, der schon einmal einen Wert
geliefert hat, bleibt erhalten, auch wenn der Wert bei einem späteren Start fehlt – er zeigt dann „unbekannt“. Kernwerte wie Leistung, Strom und Spannung werden immer angelegt, auch wenn sie
vorübergehend „unbekannt“ sind (z. B. nachts).

**Vorzeichen:** Batterieleistung positiv = Entladen. Smart Meter wie vom Gerät geliefert – bei Einbau am
Netzanschlusspunkt ist positiv = Netzbezug, negativ = Einspeisung.

## Getestete Geräte

| Gerät | Anbindung | Firmware WR | Integration | Home Assistant | Ergebnis |
|---|---|---|---|---|---|
| **Symo 3.0-3-M** (echtes Gerät) | Datamanager 2.0, Modbus TCP, Unit-ID 1 | 0.3.30.2 | 0.1.0 | 2026.11.2 (HA OS 18.4) | ✅ Messwerte, Anlagenwerte, Statuscode, Fehlerklassen, Modell 120/122/123 lesend · ✅ Steuerung: Leistungsbegrenzung und Einspeisung aus/ein (23.11.2026) |
| GEN24 Plus mit Batterie und Smart Meter | simuliert (Tests) | – | 0.2.0 | Testumgebung | ✅ automatisierte Tests |
| Symo Hybrid mit Batterie (Datamanager) | simuliert (Tests) | – | 0.2.0 | Testumgebung | ✅ automatisierte Tests |
| GEN24 ohne Batterie, Gerät mit einem DC-Eingang | simuliert (Tests) | – | 0.2.0 | Testumgebung | ✅ automatisierte Tests |
| Smart Meter 203 (int+SF) / 213 (float) | simuliert (Tests) | – | 0.2.0 | Testumgebung | ✅ automatisierte Tests |

Beobachtungen am echten Symo: liefert `ActWh` (Modell 122), aber keinen Isolationswiderstand und keine
Temperaturen – diese Sensoren werden daher nicht angelegt.

Steuerungstest am Symo (bei nur ca. 40 W PV-Leistung):
- **Leistungsbegrenzung 1 % (= 30 W):** nach ca. 7 s Betriebszustand *throttled*, AC-Leistung 33 → 29 W.
- **Einspeisung aus:** nach ca. 15 s 0 W, Betriebszustand *standby*, kein Fehler.
- **Einspeisung wieder ein, Begrenzung aus:** der Wechselrichter startet neu; bei sehr wenig Licht kann das
  einige Minuten dauern (wiederholte Startversuche mit Statuscode *306 Power Low*, im Test ca. 9 Minuten).
  Der Binärsensor *Fehler* bleibt dabei aus.
- Die Schalter zeigen den vom Gerät zurückgelesenen Zustand. Weitere Geräte gern per Issue melden
(Modell, Firmware, Anbindung, Home-Assistant-Version, Diagnose-Export).

## Voraussetzungen

- Modbus TCP aktiviert:
  - **GEN24 / Tauro / Verto:** Weboberfläche → Kommunikation → Modbus → *TCP Server*
  - **Datamanager:** Weboberfläche → Einstellungen → Modbus → Datenausgabe **tcp** (Datamanager 2.0 steht ab Werk auf rtu)
- SunSpec Model Type: **float** oder **int+SF**
- Home Assistant 2026.2 oder neuer

## Installation

**Marketplace (ab Home Assistant 2026.11):** Seit 2026.11 ersetzt der eingebaute *Marketplace* HACS
([offizielle Doku](https://www.home-assistant.io/integrations/marketplace/)). Er ist unter
*Settings → Marketplace* zu finden (nur für Administratoren), eine eigene HACS-Installation ist nicht nötig.
Die Integration steht (noch) nicht im Katalog und wird als benutzerdefiniertes Repository hinzugefügt:

1. *Settings → Marketplace* öffnen; beim ersten Öffnen den Warnhinweis akzeptieren
   (ohne Zustimmung kann der Marketplace nichts installieren).
2. Oben rechts **Add from link** wählen, unter **GitHub link** `alexanderwendel8/Fronius-Modbus-TCP-HA`
   eintragen, **Add**. Falls noch nicht geschehen, fragt der Marketplace jetzt nach einer GitHub-Verbindung
   (Anmeldung per Code auf github.com; nur Lesezugriff auf öffentliche Daten) – sie ist für benutzerdefinierte
   Repositories Pflicht.
3. Das Repository in der Liste öffnen, **Install** wählen, Version prüfen (neuestes Release, z. B. `v0.2.0`),
   **Install**. Ist ein Neustart nötig, erinnert eine Reparaturmeldung unter *Settings → System → Repairs* daran.

Updates erscheinen unter *Settings → Updates* (mit Release Notes); benutzerdefinierte Repositories prüft der
Marketplace mit GitHub-Verbindung alle 48 Stunden. Nach einem Update Home Assistant neu starten – auch hier
erinnert eine Reparaturmeldung. Eine HACS-Installation wird beim ersten Start von 2026.11 automatisch
übernommen, einschließlich dieses Repositories und seiner Update-Entität.

**HACS (Home Assistant vor 2026.11):** Dieses Repository als benutzerdefiniertes Repository (Typ *Integration*)
hinzufügen, installieren, Home Assistant neu starten.

**Manuell:** `custom_components/fronius_modbus_tcp` nach `<config>/custom_components/` kopieren und neu starten.

Anschließend unter *Einstellungen → Geräte & Dienste → Integration hinzufügen* nach „Fronius Modbus TCP“ suchen:
(Meldet sich ein Fronius-Gerät per DHCP im Netzwerk und antwortet es per Modbus TCP auf Port 502 unter
Adresse 1, schlägt Home Assistant die Einrichtung von selbst vor. Bekommt ein bereits eingerichtetes Gerät
auf diesem Weg eine neue IP-Adresse, wird sie automatisch übernommen.)


| Feld | GEN24 / Tauro / Verto | Datamanager (Symo, Primo, Galvo …) |
|---|---|---|
| Host | IP des Wechselrichters | IP des Datamanagers |
| Port | 502 (oder 1502) | 502 |
| Modbus-Adresse Wechselrichter | **1** | **Wechselrichter-Nummer** (00 → 100) |
| Modbus-Adresse Smart Meter | leer = automatisch (200) | leer = automatisch (240) |
| Weitere Smart Meter | z. B. `201, 202` | z. B. `241, 242` |

`0` als Smart-Meter-Adresse schaltet den Zähler ab. Bei mehreren Wechselrichtern am Datamanager
für jeden Wechselrichter einen eigenen Eintrag anlegen; der Smart Meter wird automatisch nur dem
ersten Eintrag zugeordnet. Alle Einträge am selben Datamanager teilen sich eine Modbus-Verbindung und fragen
nacheinander ab.

**Mehrere Smart Meter:** Zusätzliche Zähler (z. B. Verbraucher- oder Erzeugerzähler) werden im Feld
„Weitere Smart Meter“ mit ihren Modbus-Adressen eingetragen, durch Komma getrennt. Jeder Zähler erscheint
als eigenes Gerät mit denselben Sensoren; bei gleichem Modell trägt der Gerätename die Adresse in Klammern.
Der Zähler im Feld „Modbus-Adresse Smart Meter“ bleibt der Hauptzähler am Netzanschlusspunkt.

**Verbindungsdaten ändern:** Bekommt der Wechselrichter eine neue IP-Adresse oder soll der Smart Meter
nachträglich dazukommen, muss der Eintrag nicht gelöscht werden. Unter *Settings → Devices & services →
Fronius Modbus TCP* das Drei-Punkte-Menü des Eintrags öffnen und **Reconfigure** wählen. Das Gerät muss
dasselbe bleiben (gleiche Seriennummer); Entitäten und Historie bleiben erhalten.

Antwortet der Smart Meter beim Start nicht, wird der Wechselrichter trotzdem eingerichtet. Die Integration
sucht den Zähler dann alle 5 Minuten erneut und lädt den Eintrag neu, sobald er gefunden wird.

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

### Speichersteuerung (Geräte mit Batterie)

Hat der Wechselrichter einen Speicher (SunSpec-Modell 124), kommen diese Entitäten dazu. Sie ersetzen
die Anzeige-Sensoren „Batterie-Ladegrenze“, „-Entladegrenze“, „-Mindestreserve“ und „-Ladequelle“.

| Entität | Typ | Wirkung |
|---|---|---|
| Batterie-Ladegrenze | Zahl −100…100 % | Maximale Ladeleistung in % der Speicher-Nennleistung (`WChaMax`) |
| Batterie-Ladegrenze aktiv | Schalter | Ladegrenze anwenden |
| Batterie-Entladegrenze | Zahl −100…100 % | Maximale Entladeleistung in % von `WChaMax` |
| Batterie-Entladegrenze aktiv | Schalter | Entladegrenze anwenden |
| Batterie-Mindestreserve | Zahl 0–100 % | Ladezustand, der nicht unterschritten werden soll (bleibt dauerhaft gesetzt) |
| Batterie aus dem Netz laden | Schalter | Laden aus dem Netz erlauben. Muss zusätzlich in der Fronius-Weboberfläche erlaubt sein („Batterieladung aus EVU Netz erlauben“). |

Eine Grenze wirkt nur, solange ihr Schalter eingeschaltet ist. Typische Vorgaben (aus dem Fronius-Handbuch):

| Ziel | Einstellung |
|---|---|
| Nur laden, nicht entladen | Entladegrenze 0 %, „Entladegrenze aktiv“ ein |
| Nur entladen, nicht laden | Ladegrenze 0 %, „Ladegrenze aktiv“ ein |
| Speicher halten (weder laden noch entladen) | beide Grenzen 0 %, beide Schalter ein |
| Laden erzwingen mit mindestens 50 % | Entladegrenze −50 %, „Entladegrenze aktiv“ ein |
| Entladen erzwingen mit 50 % | Ladegrenze −50 %, Entladegrenze 50 %, beide Schalter ein |

Negative Werte erzwingen also die Gegenrichtung. Sind beide Grenzen aktiv, darf die negierte Ladegrenze
nicht größer sein als die Entladegrenze; ein solches Fenster lehnt die Integration mit einer Fehlermeldung
ab, bevor sie schreibt. Lade- und Entladegrenze werden mit der Rückfallzeit geschrieben (siehe unten),
Mindestreserve und Netzladung bleiben dauerhaft gesetzt. Alle Vorgaben sind laut Fronius Empfehlungen:
Der Wechselrichter kann aus Sicherheitsgründen davon abweichen.

**Nicht an einem echten Speicher getestet** – bisher nur gegen simulierte Geräte.

**Abfrageintervall:** Im selben Dialog („Konfigurieren“) lässt sich einstellen, wie oft das Gerät abgefragt
wird: 5–60 s, Standard 10 s. Datamanager-Geräte antworten langsam; ein längeres Intervall entlastet sie.
Die Rückfallzeit beträgt immer mindestens das Dreifache des Abfrageintervalls.

**Rückfallzeit:** Jede Vorgabe wird mit einer Rückfallzeit geschrieben. Da jede Modbus-Abfrage den Timer
im Wechselrichter neu startet, bleibt eine Vorgabe aktiv, solange Home Assistant läuft. Fällt Home Assistant
aus, kehrt der Wechselrichter nach dieser Zeit von selbst in den Normalbetrieb zurück – eine Drosselung
oder ein Standby kann also nicht „hängen bleiben“. Wird die Rückfallzeit geändert, überträgt die
Integration den neuen Wert sofort an alle gerade aktiven Vorgaben (Leistungsbegrenzung, Standby,
Lade-/Entladegrenze des Speichers).

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

## Verhalten, wenn das Gerät nicht antwortet

Die Integration merkt sich die zuletzt erkannte Gerätestruktur (Modelle, Strings, Speicher, Smart Meter).
Antwortet der Wechselrichter beim Start von Home Assistant nicht – etwa nachts, wenn ein Gerät am
Datamanager abgeschaltet ist –, wird der Eintrag trotzdem eingerichtet. Die Entitäten sind dann
„nicht verfügbar“ und liefern wieder Werte, sobald das Gerät antwortet; dabei lädt der Eintrag einmal neu
und erkennt die Struktur frisch. Nur bei der allerersten Einrichtung muss das Gerät erreichbar sein.

## Diagnose und Fehlermeldungen

Unter *Settings → Devices & services → Fronius Modbus TCP* lässt sich über das Drei-Punkte-Menü des Eintrags
**Download diagnostics** eine Datei herunterladen. Sie enthält die erkannte Gerätestruktur, die Optionen,
die zuletzt gelesenen Werte und die **rohen Register aller SunSpec-Modelle** von Wechselrichter und
Smart Metern (bei Datamanager-Geräten zusätzlich die Fronius-Register 212–216 und 500–513). Host und
Seriennummern sind entfernt. Bei einem Problem mit einem nicht getesteten Gerät diese Datei bitte dem
Issue anhängen – damit lässt sich das Verhalten ohne Zugriff auf das Gerät nachvollziehen.

Für Meldungen gibt es unter [Issues](https://github.com/alexanderwendel8/Fronius-Modbus-TCP-HA/issues/new/choose)
drei Vorlagen: Fehler, Rückmeldung zu einem getesteten Gerät und Wunsch.

## Struktur

| Datei | Zweck |
|---|---|
| `api.py` | Modbus-Client, Erkennung der Modellkette, Registerzugriff |
| `client_pool.py` | Gemeinsame Verbindung für alle Einträge am selben Host und Port |
| `sunspec.py` | SunSpec-Modelldefinitionen und Dekodierung (ohne HA-Abhängigkeit) |
| `coordinator.py` | Zyklische Abfrage (`DataUpdateCoordinator`) |
| `config_flow.py` | Einrichtung über die UI inkl. Verbindungstest |
| `entity.py` | Basisentität mit Gerätezuordnung |
| `sensor.py` | Sensor-Definitionen |
| `binary_sensor.py` | Binärsensoren (Fehler, Warnung, Vorgaben aus Modell 123) |
| `number.py`, `switch.py`, `button.py` | Steuerung (nur mit Option „Steuerung erlauben“) |
| `state_codes.py` | Fronius State Codes im Klartext (erzeugt mit `scripts/generate_state_codes.py`) |
| `diagnostics.py` | Diagnosedaten-Export inkl. roher Register aller SunSpec-Modelle |
| `strings.json`, `translations/` | Texte (EN/DE) |
| `icons.json` | Symbole der Entitäten ohne Geräteklasse |

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

Die Prüfungen (`validate.yml`) laufen bei jedem Pull Request, auf `main`, vor jedem Release und zusätzlich
jede Nacht – so fallen Brüche durch neue Versionen von Home Assistant oder pymodbus auch dann auf, wenn am
Repository nichts geändert wird.

Vor einem Commit außerdem `ruff check .` (Regeln in `pyproject.toml`) und `mypy` (Typprüfung des
Integrationscodes) ausführen; beide laufen auch in der CI.

Die Tests starten simulierte Fronius-Geräte (`tests/simulator.py`) als echten Modbus-TCP-Server und
richten die Integration in einer Home-Assistant-Testinstanz ein.

Zusätzlich prüft der Workflow [`update-check.yml`](.github/workflows/update-check.yml)
jeden Montag die externen Komponenten und legt für jede veraltete Komponente ein Issue mit
dem Label `aktualisierung` an:
- **GitHub Actions** in `.github/workflows` mit Versionsangabe (neues Release; Verweise auf einen
  Branch wie `@main` werden übersprungen)
- **Python-Pakete**, die in `requirements_test.txt` oder den Workflows fest gepinnt sind; Pins mit
  dem Kommentar `# update-check: ignore` (z. B. die Mindestversion von pymodbus) nicht
- **Home Assistant:** neues Monatsrelease gegenüber der neuesten Version in der Spalte
  „Home Assistant“ der Tabelle [Getestete Geräte](#getestete-geräte) und eine höhere
  Python-Mindestversion als in den Workflows

Ist die Komponente wieder aktuell, schließt der Workflow das Issue selbst. Die Prüfungen stehen
in [`.github/scripts/check_updates.py`](.github/scripts/check_updates.py); lokal zeigt
`python .github/scripts/check_updates.py --dry-run` das Ergebnis, ohne Issues zu ändern.

## Releases

Änderungen stehen in [`CHANGELOG.md`](CHANGELOG.md) (englisch: [`CHANGELOG.en.md`](CHANGELOG.en.md)). Releases erstellt der Workflow `release.yml`
mit den Notizen aus dem Changelog – entweder per Tag `vX.Y.Z` oder manuell unter
*Actions → Release → Run workflow* (auf `main`, Eingabe z. B. `0.1.0`; der Tag wird dann gesetzt).
Die Version muss zu `manifest.json` passen. Vor dem Release laufen dieselben Prüfungen wie bei jedem
Pull Request (Hassfest, HACS, Lint, Tests); schlägt eine fehl, entsteht kein Release. Marketplace bzw. HACS zeigen danach die Versionsnummer statt des Commit-Hashs.

### Vorabversionen

Der Marketplace meldet nur Releases als Update, keine einzelnen Commits auf `main`
([Quellcode](https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/marketplace/repositories/base.py)).
Zum Testen vor einem Release erstellt der Workflow `prerelease.yml` eine Vorabversion vom
aktuellen Stand von `main`: *Actions → Pre-release → Run workflow*, Eingabe ist die geplante
nächste Version, z. B. `0.3.0`. Daraus entsteht `v0.3.0b1`, beim nächsten Lauf `v0.3.0b2` usw.,
mit den Notizen aus „Unveröffentlicht“. Vorher laufen dieselben Prüfungen wie beim Release. Ein Pull
Request ist dafür nicht nötig; `main` bleibt unverändert (die Version `0.3.0b1` steht nur im Commit
des Tags).

Der Marketplace bietet Vorabversionen nur an, wenn beim Repository der Schalter **Pre-release**
eingeschaltet ist: **Settings** > **Devices & services** > **Marketplace** → Gerät *Fronius Modbus TCP*,
dort die standardmäßig deaktivierte Entität **Pre-release** aktivieren und einschalten
([Doku](https://www.home-assistant.io/integrations/marketplace/)). Alle anderen bekommen weiter
nur stabile Releases.

## Herstellerdokumentation

Die Fronius-Registerkarten und State-Code-Tabellen liegen in [`docs/fronius/`](docs/fronius/README.md) –
mit Dateiindex und Zusammenfassung der für diese Integration relevanten Punkte.
