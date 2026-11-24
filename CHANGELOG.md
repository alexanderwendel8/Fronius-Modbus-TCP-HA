# Changelog

## Unveröffentlicht

- Steuerung am echten Symo 3.0-3-M (Datamanager 2.0) erfolgreich getestet: Leistungsbegrenzung und Einspeisung aus/ein.
- Mindestversion korrigiert: Home Assistant 2025.3 (statt 2025.2) – der Code nutzt `AddConfigEntryEntitiesCallback`, das es erst ab 2025.3 gibt.
- Optionale Sensoren, die schon einmal einen Wert geliefert haben, werden nicht mehr gelöscht, wenn der Wert bei einem späteren Start vorübergehend fehlt. Name, Entitäts-ID und Einstellungen bleiben erhalten.
- Smart Meter, der beim Start nicht antwortet, wird alle 5 Minuten erneut gesucht; sobald er gefunden wird, erscheinen seine Sensoren ohne manuelles Neuladen. Ausfall und Rückkehr des Zählers im laufenden Betrieb stehen jetzt einmalig im Log.
- Erkennung „Datamanager oder GEN24“ abgesichert: Ein vorübergehender Modbus-Fehler beim Prüfen der Fronius-Register 500–513 stuft das Gerät nicht mehr dauerhaft falsch ein. Nur die Fehlerantwort „unzulässige Adresse“ gilt als „nicht vorhanden“; das eindeutige Ergebnis wird im Eintrag gespeichert und bei späteren Starts nicht erneut geprüft. Antwortet ein Gerät auf diese Register gar nicht, scheitert die Einrichtung nicht mehr.
- CI beschleunigt: pip-Cache, keine doppelten Läufe mehr bei Pull Requests, überholte Läufe werden abgebrochen.
- Zu kurze SunSpec-Modelle bringen die Abfrage nicht mehr zum Absturz: Ein Modell, das kürzer ist als von der Auswertung benötigt, wird mit einer Warnung im Log übersprungen; die übrigen Werte bleiben verfügbar. Unvollständige Modbus-Antworten werden als Lesefehler gemeldet.
- Mehrere Wechselrichter am selben Datamanager teilen sich jetzt eine Modbus-Verbindung; ihre Abfragen laufen nacheinander statt parallel (Vorgabe von Fronius).
- pymodbus: Mindestversion 3.8.3 (die von Home Assistant 2025.3 vorgegebene). Der Name des Unit-ID-Parameters wird einmalig an der Signatur abgelesen statt über einen abgefangenen `TypeError`; die CI testet mit pymodbus 3.8.3, 3.11.2 und der neuesten Version. Der Testsimulator ist ein eigener kleiner Modbus-TCP-Server und hängt nicht mehr vom Server aus pymodbus ab.

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
