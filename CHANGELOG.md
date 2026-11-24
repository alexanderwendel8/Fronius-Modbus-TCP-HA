# Changelog

## Unveröffentlicht

- Steuerung am echten Symo 3.0-3-M (Datamanager 2.0) erfolgreich getestet: Leistungsbegrenzung und Einspeisung aus/ein.
- **Mindestversion angehoben: Home Assistant 2026.2** (bisher fälschlich 2025.2 angegeben; der Code lief erst ab 2025.3). Real getestet ist die Integration auf 2026.11.
- Optionale Sensoren, die schon einmal einen Wert geliefert haben, werden nicht mehr gelöscht, wenn der Wert bei einem späteren Start vorübergehend fehlt. Name, Entitäts-ID und Einstellungen bleiben erhalten.
- Smart Meter, der beim Start nicht antwortet, wird alle 5 Minuten erneut gesucht; sobald er gefunden wird, erscheinen seine Sensoren ohne manuelles Neuladen. Ausfall und Rückkehr des Zählers im laufenden Betrieb stehen jetzt einmalig im Log.
- Erkennung „Datamanager oder GEN24“ abgesichert: Ein vorübergehender Modbus-Fehler beim Prüfen der Fronius-Register 500–513 stuft das Gerät nicht mehr dauerhaft falsch ein. Nur die Fehlerantwort „unzulässige Adresse“ gilt als „nicht vorhanden“; das eindeutige Ergebnis wird im Eintrag gespeichert und bei späteren Starts nicht erneut geprüft. Antwortet ein Gerät auf diese Register gar nicht, scheitert die Einrichtung nicht mehr.
- CI beschleunigt: pip-Cache, keine doppelten Läufe mehr bei Pull Requests, überholte Läufe werden abgebrochen.
- Zu kurze SunSpec-Modelle bringen die Abfrage nicht mehr zum Absturz: Ein Modell, das kürzer ist als von der Auswertung benötigt, wird mit einer Warnung im Log übersprungen; die übrigen Werte bleiben verfügbar. Unvollständige Modbus-Antworten werden als Lesefehler gemeldet.
- Mehrere Wechselrichter am selben Datamanager teilen sich jetzt eine Modbus-Verbindung; ihre Abfragen laufen nacheinander statt parallel (Vorgabe von Fronius).
- pymodbus: Mindestversion 3.11.2 (die von Home Assistant 2026.2 vorgegebene). Die CI testet mit 3.11.2, 3.13.1 (Vorgabe von Home Assistant 2026.11) und der neuesten Version. Der Testsimulator ist ein eigener kleiner Modbus-TCP-Server und hängt nicht mehr vom Server aus pymodbus ab.
- Leistungsbegrenzung: Skalierungsfaktor lesen und Vorgabe schreiben laufen jetzt als ein unteilbarer Ablauf; eine gleichzeitige Abfrage kann sich nicht mehr dazwischenschieben. Gelesen wird dabei nur noch das eine Register statt des ganzen Modells 123.
- Neu: Verbindungsdaten nachträglich ändern (**Reconfigure** im Menü des Eintrags) – Host, Port und Modbus-Adressen lassen sich anpassen, ohne den Eintrag zu löschen. Ein Gerät mit anderer Seriennummer wird abgelehnt.
- Neuer Workflow `update-check.yml`: prüft jeden Montag GitHub Actions, gepinnte Python-Pakete und neue
  Home-Assistant-Releases (samt Python-Mindestversion) und legt für jede veraltete Komponente ein Issue mit
  dem Label `aktualisierung` an; ist sie wieder aktuell, wird das Issue geschlossen. Logik in
  `.github/scripts/check_updates.py`, mit Tests. Offene Issues werden zu Beginn jeder Claude-Sitzung geprüft
  und nur nach Rückfrage abgearbeitet (`CLAUDE.md`).
- Neu: Speichersteuerung für Geräte mit Batterie (Modell 124, nur mit „Steuerung erlauben“): Lade- und Entladegrenze samt Schaltern, Mindestreserve und Laden aus dem Netz. Ungültige Leistungsfenster werden vor dem Schreiben abgelehnt. Bisher nur gegen simulierte Geräte getestet.
- Neu: Abfrageintervall einstellbar (Optionen, 5–60 s, Standard 10 s). Die Rückfallzeit für Vorgaben beträgt mindestens das Dreifache des Intervalls, damit eine Vorgabe nicht zwischen zwei Abfragen endet.
- Neu: mehrere Smart Meter je Eintrag. Weitere Zähler (GEN24: 201–204, Datamanager: 241–244) werden bei der Einrichtung oder über **Reconfigure** mit ihren Modbus-Adressen eingetragen; jeder erscheint als eigenes Gerät. Bisher nur gegen simulierte Geräte getestet.
- Eine geänderte Rückfallzeit wirkt jetzt sofort auf gerade aktive Vorgaben (Leistungsbegrenzung, Standby, Speichergrenzen) und nicht erst beim nächsten Schreiben.
- Diagnose-Download erweitert: Optionen, pymodbus-Version, Abfrageintervall und die rohen Register aller SunSpec-Modelle von Wechselrichter und Smart Metern (Datamanager: zusätzlich Fronius-Register). Host und Seriennummern werden entfernt.

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
