# Changelog

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
