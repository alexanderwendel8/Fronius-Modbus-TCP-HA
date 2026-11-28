**Deutsch** | [English](CHANGELOG.en.md)

# Changelog

## Unveröffentlicht

- Behoben: Der Diagnose-Download las die pymodbus-Version über eine Dateioperation in der Event-Loop; Home Assistant meldete das als „Detected blocking call“. Die Version kommt jetzt direkt aus dem Modul.
- Vorbereitet auf neuere Home-Assistant-Versionen: Smart Meter werden über `via_device_id` dem Wechselrichter zugeordnet statt über das veraltete `via_device` (laut Home Assistant entfällt es mit 2027.8; ab 2026.10 erscheint sonst eine Warnung im Log). Formular-Schemas verwenden `probatio`, wo Home Assistant es mitbringt, sonst wie bisher `voluptuous`. Home Assistant 2026.2 bleibt unterstützt; Lint und Typprüfung laufen jetzt gegen beide Versionen.
- Dokumentation: Englische Fassungen von README (`README.en.md`) und Changelog (`CHANGELOG.en.md`). Beide Sprachfassungen werden gleichlaufend gepflegt; ein Test prüft, dass sie dieselbe Struktur haben.
- Entwicklung: Neuer Workflow `prerelease.yml` erstellt manuell eine Vorabversion (`vX.Y.Zb1`, `b2` …) vom aktuellen Stand von `main`, mit den Notizen aus „Unveröffentlicht“. So lassen sich Änderungen über den Marketplace testen (Schalter **Pre-release** beim Repository), ohne ein Release zu machen.
- Behoben: Der Diagnose-Download brach mit einem internen Fehler ab, solange der Eintrag nicht geladen war (z. B. Gerät beim Start nicht erreichbar). Er liefert jetzt Zustand, Fehlermeldung, Eintragsdaten und die zuletzt gespeicherte Gerätestruktur.

## 0.2.0

Robustere Erkennung und Abfrage, neue Einstell- und Steuermöglichkeiten sowie eine deutlich breitere
Testabdeckung. Am echten Gerät (Symo 3.0-3-M am Datamanager 2.0) getestet ist weiterhin nur der Stand 0.1.0
einschließlich der Steuerung; alles Neue in diesem Release ist gegen simulierte Geräte geprüft.

### Wichtig beim Update
- **Mindestversion: Home Assistant 2026.2** (bisher fälschlich 2025.2 angegeben; der Code lief erst ab 2025.3).
  pymodbus ab 3.11.2, das Home Assistant 2026.2 mitbringt.
- Mit „Steuerung erlauben“ und vorhandenem Speicher ersetzen neue Zahl- und Schalter-Entitäten die bisherigen
  Sensoren Batterie-Ladegrenze, -Entladegrenze, -Mindestreserve und -Ladequelle.

### Neu
- **Verbindungsdaten ändern** (**Reconfigure** im Menü des Eintrags): Host, Port und Modbus-Adressen anpassen,
  ohne den Eintrag zu löschen. Ein Gerät mit anderer Seriennummer wird abgelehnt.
- **Speichersteuerung** für Geräte mit Batterie (Modell 124, nur mit „Steuerung erlauben“): Lade- und
  Entladegrenze samt Schaltern, Mindestreserve und Laden aus dem Netz. Ungültige Leistungsfenster werden vor
  dem Schreiben abgelehnt.
- **Mehrere Smart Meter** je Eintrag: weitere Zähler (GEN24: 201–204, Datamanager: 241–244) mit ihren
  Modbus-Adressen eintragen; jeder erscheint als eigenes Gerät.
- **Abfrageintervall einstellbar** (Optionen, 5–60 s, Standard 10 s). Die Rückfallzeit für Vorgaben beträgt
  mindestens das Dreifache des Intervalls.
- **Erkennung im Netzwerk** per DHCP (MAC-Präfix 00:03:AC): Antwortet das Gerät per Modbus TCP unter den
  Standardwerten, wird die Einrichtung vorgeschlagen; eine neue IP-Adresse eines eingerichteten Geräts wird
  automatisch übernommen.
- **Start ohne erreichbares Gerät:** Die zuletzt erkannte Gerätestruktur wird gespeichert. Antwortet der
  Wechselrichter beim Start von Home Assistant nicht (z. B. nachts), wird der Eintrag trotzdem eingerichtet;
  die Entitäten sind bis zur ersten Antwort „nicht verfügbar“, statt ganz zu fehlen.
- **Diagnose-Download erweitert:** Optionen, pymodbus-Version, Abfrageintervall und die rohen Register aller
  SunSpec-Modelle von Wechselrichter und Smart Metern (Datamanager: zusätzlich Fronius-Register). Host und
  Seriennummern werden entfernt.
- Symbole für Entitäten ohne Geräteklasse, z. B. Status, Leistungsbegrenzung, Einspeisung, Speichergrenzen.
- Eine geänderte Rückfallzeit wirkt sofort auf gerade aktive Vorgaben (Leistungsbegrenzung, Standby,
  Speichergrenzen) und nicht erst beim nächsten Schreiben.

### Robuster
- Optionale Sensoren, die schon einmal einen Wert geliefert haben, werden nicht mehr gelöscht, wenn der Wert
  bei einem späteren Start vorübergehend fehlt. Name, Entitäts-ID und Einstellungen bleiben erhalten.
- Ein Smart Meter, der beim Start nicht antwortet, wird alle 5 Minuten erneut gesucht; seine Sensoren
  erscheinen dann ohne manuelles Neuladen. Ausfall und Rückkehr im laufenden Betrieb stehen einmalig im Log.
- Erkennung „Datamanager oder GEN24“: Ein vorübergehender Modbus-Fehler stuft das Gerät nicht mehr dauerhaft
  falsch ein. Das eindeutige Ergebnis wird im Eintrag gespeichert. Antwortet ein Gerät auf die Fronius-Register
  gar nicht, scheitert die Einrichtung nicht mehr.
- Zu kurze SunSpec-Modelle werden mit einer Warnung übersprungen, statt die ganze Abfrage abzubrechen.
  Unvollständige Modbus-Antworten gelten als Lesefehler.
- Mehrere Wechselrichter am selben Datamanager teilen sich eine Modbus-Verbindung; ihre Abfragen laufen
  nacheinander statt parallel (Vorgabe von Fronius).
- Leistungsbegrenzung: Skalierungsfaktor lesen und Vorgabe schreiben laufen als ein unteilbarer Ablauf.

### Behoben
- Nach **Reconfigure** oder einem Adresswechsel blieb die Modbus-Verbindung zur alten Adresse offen.
- Fehlerantworten beim Schreiben tragen jetzt wie beim Lesen den Modbus-Exception-Code.

### Getestet
- Steuerung am echten Symo 3.0-3-M (Datamanager 2.0) mit Version 0.1.0: Leistungsbegrenzung und Einspeisung
  aus/ein.
- Nur simuliert: GEN24, Speichersteuerung, mehrere Smart Meter, DHCP-Erkennung, Start ohne erreichbares Gerät.

### Entwicklung
- Tests laufen mit Python 3.13 (Home Assistant 2026.2, pymodbus 3.11.2) und Python 3.14 (aktuelles Home
  Assistant, pymodbus 3.13.1 und neueste Version); Abdeckung des Integrationscodes 100 %. Der Testsimulator ist
  ein eigener Modbus-TCP-Server.
- CI: Lint (`ruff`) und Typprüfung (`mypy`), Prüfungen zusätzlich jede Nacht und vor jedem Release, schnellere
  Läufe, GitHub Actions auf aktuelle Versionen und Commit-SHAs festgelegt.
- Workflow `update-check.yml`: prüft wöchentlich GitHub Actions, gepinnte Python-Pakete und neue
  Home-Assistant-Releases und legt für veraltete Komponenten Issues mit dem Label `aktualisierung` an.
- Issue-Vorlagen für Fehler, Geräte-Rückmeldungen und Wünsche; keine `assert`- und `type: ignore`-Stellen
  mehr im Integrationscode.

## 0.1.0

Erstes Release der Home-Assistant-Integration für Fronius-Wechselrichter per Modbus TCP (SunSpec).

### Geräte
- **GEN24 / Tauro / Verto** (Unit-ID 1) und **Datamanager-Geräte** (Symo, Primo, Galvo, Eco, Symo Hybrid …;
  Unit-ID = Wechselrichter-Nummer, 00 → 100)
- SunSpec-Modelle werden zur Laufzeit erkannt (keine festen Registeradressen), float und int+SF
- Fronius Smart Meter (201–204 / 211–214) als eigenes Gerät, automatische Suche (Unit-ID 200 bzw. 240)

### Messwerte
- AC: Leistung, Energie, Ströme, Spannungen, Frequenz, Schein-/Blindleistung, Leistungsfaktor
- PV: Leistung und Strom gesamt, Leistung/Strom/Spannung/Energie je String
- Batterie (GEN24 Plus, Verto Plus, Symo Hybrid): Leistung, Spannung, Energiezähler, Ladezustand,
  Status, Mindestreserve, Ladequelle, Kapazität
- Datamanager: Anlagenleistung, Energie heute / dieses Jahr / gesamt
- Nennwerte (Nennleistung, Nennstrom …), genaue Gesamtenergie (64-bit), Isolationswiderstand (GEN24)

### Status und Fehler
- Betriebszustand, Fronius-Zustand, Statuscode und Statusmeldung im Klartext (Datamanager)
- Binärsensor Fehler (GEN24 zusätzlich Warnung), aktive Fehlerklassen und SunSpec-Ereignisse im Klartext
- „Power low“ / „DC low“ beim Ab- und Anschalten zählen nicht als Fehler

### Steuerung (optional, Option „Steuerung erlauben“)
- Leistungsbegrenzung (0–100 %) und Ein/Aus, Einspeisung (Standby), Rückfallzeit
- Ereignisse zurücksetzen (Datamanager)
- Jede Vorgabe mit Rückfallzeit: fällt Home Assistant aus, kehrt der Wechselrichter von selbst in den
  Normalbetrieb zurück

### Sonstiges
- Nur Sensoren für Werte, die das Gerät tatsächlich liefert
- Ausführliche Protokollierung von Einrichtungsfehlern, Diagnose-Export
- Texte auf Deutsch und Englisch
- Herstellerdokumentation mit Zusammenfassung unter `docs/fronius/`

**Getestet** mit einem Symo 3.0-3-M am Datamanager 2.0 sowie mit simulierten GEN24-, Symo-Hybrid- und
Smart-Meter-Geräten. Die Steuerung ist noch nicht am echten Gerät erprobt.
