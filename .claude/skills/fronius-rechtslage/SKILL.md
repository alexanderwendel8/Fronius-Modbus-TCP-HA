---
name: fronius-rechtslage
description: Prüfen, ob die im Repository veröffentlichten Fronius-Unterlagen (Registerkarten, Handbücher, State Codes unter docs/fronius/) wiederveröffentlicht werden dürfen – Inventar mit Rechtevermerken, Fronius-Bedingungen, Einordnung, Optionen und Anfragetext an Fronius. Verwenden bei "dürfen wir die Fronius-Doku veröffentlichen", "Lizenz der Fronius-Dateien", "Rechtslage Fronius-Dokumentation", "Fronius um Erlaubnis fragen".
---

# Rechtslage der Fronius-Unterlagen prüfen

Das Repository steht unter Apache 2.0, `docs/fronius/` enthält aber **fremdes Material** von Fronius
International GmbH (Originale, daraus erzeugte CSV-/Textfassungen) und eigene Zusammenfassungen.
Dieser Ablauf sammelt Fakten und bereitet eine Entscheidung vor. **Er ist keine Rechtsberatung** –
das im Bericht so sagen; die Entscheidung trifft der Nutzer, im Zweifel mit Fachberatung oder einer
Freigabe von Fronius.

## 1. Inventar und Vermerke in den Dateien

```bash
python3 -I .claude/skills/fronius-rechtslage/scripts/inventar.py . > <Scratchpad>/inventar.md
```
Listet Originale (Größe, SHA-256), abgeleitete Fassungen und eigene README-Dateien und sucht in den
Originalen nach Vermerken (Copyright, „alle Rechte vorbehalten“, vertraulich, Lizenz, Weitergabe):
PDF-Metadaten und -Text, xlsx-Dokumenteigenschaften und Zellentexte, Text-/CSV-/JSON-Inhalt.

Datenschutz: Die xlsx-Eigenschaften enthalten Namen von Fronius-Mitarbeitern (Ersteller). Im Bericht
nur „Fronius-Mitarbeiter“ bzw. die Firma nennen, Namen nicht in Commits, PRs oder Anfragen übernehmen.

Stand 28.11.2026: keine Copyright-, Lizenz- oder Vertraulichkeitsvermerke in den Dateien; die
GEN24-/Tauro-/Verto-Registerkarten nennen als Firma „Fronius International GmbH“.

## 2. Herkunft und Bedingungen bei Fronius

- Herkunft: Alle Originale sind öffentliche, frei zugängliche Downloads von `www.fronius.com`
  (QR-Links 0006/0024 aus den Handbüchern, Handbuch-PDFs; Liste im Skill `fronius-doku-aktualisierung`).
  Prüfen, ob sie weiterhin öffentlich sind – das stützt Option B unten.
- Bedingungen lesen (WebFetch bzw. `web-fetch`-Agent; Fronius' Sperre gegen automatisierte Abrufe
  nicht umgehen, bei Ablehnung den Nutzer bitten, die Seite im Browser zu öffnen):
  - Impressum / Offenlegung: `https://www.fronius.com/de-at/austria/impressum` – Inhalt wird per
    JavaScript nachgeladen; ggf. mit Playwright rendern (Chromium ist vorinstalliert) oder den Nutzer
    bitten, die Abschnitte zu Urheberrecht und Nutzung der Website zu kopieren.
  - AGB: `https://www.fronius.com/de-at/austria/agb` – Punkt 10 (geistiges Eigentum, u. a. an
    Handbüchern und technischen Unterlagen; Weitergabe an Dritte nur mit Freigabe) und 11
    (Vertraulichkeit). Die AGB regeln Lieferverträge mit Kunden; ob sie für öffentliche Downloads
    gelten, ist offen – so im Bericht darstellen.
  - Website-Nutzungsbedingungen, Datenschutz/Cookie-Seiten und Fußzeile auf weitere Hinweise prüfen.
- Jede Aussage mit URL und wörtlichem Zitat belegen; nichts aus dem Gedächtnis.

## 3. Einordnung (Fragen, keine Urteile)

- Österreichisches Recht (Sitz Fronius, Pettenbach) und deutsches Recht (Nutzer) sind ähnlich:
  - Handbücher sind Sprachwerke mit Abbildungen → urheberrechtlich geschützt; vollständige
    Wiederveröffentlichung braucht eine Erlaubnis.
  - Registerkarten sind überwiegend Fakten nach dem SunSpec-Standard; Fakten selbst sind nicht
    geschützt, eine systematische Sammlung kann aber Datenbankschutz genießen (§ 76c ff. öUrhG,
    §§ 87a ff. dt. UrhG).
  - Eigene Zusammenfassungen und daraus abgeleiteter Code (Registeroffsets, Statustexte in eigener
    Formulierung) sind in der Regel unproblematisch; kurze Zitate mit Quellenangabe sind zulässig.
- Die Apache-2.0-Lizenz des Repositorys erfasst das Fronius-Material **nicht**; klären, ob das in
  README/`docs/fronius/README.md` deutlich gesagt wird.
- Marken: „Fronius“, „GEN24“ usw. nur beschreibend verwenden (Nennung der kompatiblen Geräte).

## 4. Optionen für den Bericht

| Option | Inhalt | Aufwand / Risiko |
|---|---|---|
| A | Fronius um schriftliche Erlaubnis bitten (Text unten), bis dahin Stand lassen | gering; Ergebnis offen |
| B | Originale, CSV- und Textfassungen entfernen, nur eigene Zusammenfassungen + Links auf die Fronius-Downloads behalten; Abgleich-Skript lädt lokal | mittel; Git-Historie enthält die Dateien weiter |
| C | Nur Registerkarten (Fakten) behalten, Handbuch-PDFs und Volltexte entfernen | mittel; Datenbankfrage bleibt |
| D | Hinweis „Fremdmaterial, nicht unter Apache 2.0, © Fronius“ ergänzen | gering; ersetzt keine Erlaubnis |

Bei B/C: Folgen für `CLAUDE.md` (Verweise auf `csv/` und `text/`) und Tests nennen. Für das
Entfernen aus der Git-Historie wäre ein Umschreiben der Historie nötig – nur auf ausdrücklichen
Wunsch, nie selbst force-pushen.

## 5. Anfrage an Fronius (Entwurf, Nutzer versendet selbst)

Empfänger beim Nutzer erfragen bzw. aus dem Impressum entnehmen; keine persönlichen Daten des Nutzers
einsetzen, Platzhalter lassen. Den Text als Datei im Scratchpad ablegen.

```text
Betreff: Anfrage zur Veröffentlichung von Fronius-Modbus-Unterlagen in einem Open-Source-Projekt

Sehr geehrte Damen und Herren,

ich entwickle die freie Home-Assistant-Integration „Fronius Modbus TCP“
(https://github.com/alexanderwendel8/Fronius-Modbus-TCP-HA, Apache-2.0-Lizenz), die Fronius-
Wechselrichter und Smart Meter über Modbus TCP / SunSpec ausliest.

Als Referenz liegen im Repository folgende öffentlich auf www.fronius.com verfügbare Unterlagen,
unverändert sowie als durchsuchbare CSV-/Textfassung:
- Modbus SunSpec Maps, State Codes & Events (Version 1.1.7-0, QR-Link 0006)
- GEN24/Tauro/Verto Register Maps (Version 1.2.7-2, QR-Link 0024)
- Bedienungsanleitungen 42,0410,2649, 42,0410,2049 und 42,0426,0191

Darf ich diese Unterlagen in dieser Form im Repository bereitstellen, mit Quellenangabe und dem
Hinweis, dass sie nicht unter der Projektlizenz stehen? Falls nicht, wäre ein Verweis auf Ihre
Download-Seiten zusammen mit eigenen Zusammenfassungen für Sie in Ordnung?

Mit freundlichen Grüßen
<Name>
```
Englische Fassung auf Wunsch; Fronius-Bezeichnungen wie im englischen Teil der Handbücher.

## 6. Ergebnis

Bericht im Scratchpad (Inventar, belegte Bedingungen mit Zitaten, Einordnung, Optionen, Anfragetext),
dem Nutzer kurz zusammenfassen und fragen, welche Option er will. **Ohne Zustimmung nichts im
Repository ändern.**
