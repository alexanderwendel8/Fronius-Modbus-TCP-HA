# Hinweise für Claude

Home-Assistant-Custom-Integration `fronius_modbus_tcp` (Fronius-Wechselrichter per Modbus TCP / SunSpec).
Code: `custom_components/fronius_modbus_tcp/`. Sprache in Code-Kommentaren und Doku: Deutsch.

## Herstellerdokumentation – immer zuerst hier nachschlagen

**Einstieg: [`docs/fronius/README.md`](docs/fronius/README.md)** – Dateiindex, Zusammenfassung,
bekannte Fehler in den Quellen und Bezug zum Code.

- Registerbelegung eines SunSpec-Modells: `docs/fronius/csv/Argeno_Register_Map/<Modellnummer>.csv`
  (z. B. `113.csv`, `160.csv`, `123.csv`; Übersicht in `Index.csv`)
- Status-/Event-Dekodierung: `docs/fronius/csv/Fronius_State_Codes_Event_Flags_1_0/`
  (`St.csv`, `StVnd.csv`, `Evt1.csv`, `EvtVnd1_4_<Familie>.csv`, `<Familie>_State_Codes.csv`)
- Originaldateien (xlsx/json/csv) unverändert in `docs/fronius/original/`

Suchbeispiel: `grep -rn "WMaxLimPct" docs/fronius/csv/`

Regeln:
- Adressen in der Fronius-Doku sind **1-basiert**, im Code **0-basiert** (−1).
- Bei Widersprüchen gelten die xlsx/CSV-Tabellen, nicht `FroniusEventFlags.json`
  (dort fehlen Bits, siehe README Abschnitt 6).
- Keine festen Registeradressen einbauen – Modelle werden zur Laufzeit gescannt.
- „not supported“-Register liefern NaN / 0xFFFF / 0x8000 → werden zu `None`.

## Entwicklung

- SunSpec-Dekodierung ohne HA-Abhängigkeit in `sunspec.py`; Modbus-Zugriff in `api.py`.
- Neuer Sensor: Wert in `sunspec.py` dekodieren → Beschreibung in `sensor.py` →
  Namen in `strings.json`, `translations/en.json`, `translations/de.json`.
