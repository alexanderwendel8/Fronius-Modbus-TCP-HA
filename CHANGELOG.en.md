[Deutsch](CHANGELOG.md) | **English**

# Changelog

## Unreleased

- Prepared for newer Home Assistant versions: Smart Meters are linked to the inverter via `via_device_id` instead of the deprecated `via_device` (Home Assistant removes it in 2027.8; from 2026.10 a warning appears in the log otherwise). Form schemas use `probatio` where Home Assistant ships it, otherwise `voluptuous` as before. Home Assistant 2026.2 remains supported; lint and type check now run against both versions.
- Documentation: English versions of the README (`README.en.md`) and the changelog (`CHANGELOG.en.md`). Both language versions are maintained in parallel; a test checks that they have the same structure.
- Development: New workflow `prerelease.yml` manually creates a pre-release (`vX.Y.Zb1`, `b2` …) from the current state of `main`, with the notes from "Unreleased". This allows changes to be tested via the Marketplace (switch **Pre-release** for the repository) without making a release.
- Fixed: The diagnostics download failed with an internal error while the entry was not loaded (e.g. device not reachable at startup). It now returns the state, the error message, the entry data and the most recently stored device structure.

## 0.2.0

More robust detection and polling, new settings and control options and much broader test coverage.
On the real device (Symo 3.0-3-M behind a Datamanager 2.0), only version 0.1.0 including control has been
tested so far; everything new in this release has been checked against simulated devices.

### Important when updating
- **Minimum version: Home Assistant 2026.2** (previously stated incorrectly as 2025.2; the code only ran from 2025.3).
  pymodbus from 3.11.2, which ships with Home Assistant 2026.2.
- With "Allow control" and a battery present, new number and switch entities replace the previous
  sensors Battery charge limit, discharge limit, minimum reserve and charging source.

### New
- **Change connection settings** (**Reconfigure** in the entry menu): adjust host, port and Modbus addresses
  without deleting the entry. A device with a different serial number is rejected.
- **Battery control** for devices with battery (model 124, only with "Allow control"): charge and
  discharge limit with switches, minimum reserve and charging from the grid. Invalid power windows are
  rejected before writing.
- **Several Smart Meters** per entry: enter additional meters (GEN24: 201–204, Datamanager: 241–244) with their
  Modbus addresses; each appears as a separate device.
- **Configurable polling interval** (options, 5–60 s, default 10 s). The fallback time for settings is at
  least three times the interval.
- **Network discovery** via DHCP (MAC prefix 00:03:AC): if the device answers via Modbus TCP with the
  default settings, the setup is suggested; a new IP address of a device that is already set up is
  taken over automatically.
- **Start without a reachable device:** The most recently detected device structure is stored. If the
  inverter does not respond when Home Assistant starts (e.g. at night), the entry is set up anyway;
  the entities are "unavailable" until the first response instead of missing entirely.
- **Extended diagnostics download:** options, pymodbus version, polling interval and the raw registers of all
  SunSpec models of the inverter and Smart Meters (Datamanager: also the Fronius registers). Host and
  serial numbers are removed.
- Icons for entities without a device class, e.g. status, power limit, feed-in, battery limits.
- A changed fallback time takes effect immediately on currently active settings (power limit, standby,
  battery limits) instead of only on the next write.

### More robust
- Optional sensors that have delivered a value before are no longer deleted when the value is temporarily
  missing at a later start. Name, entity ID and settings are kept.
- A Smart Meter that does not respond at startup is searched for again every 5 minutes; its sensors
  then appear without a manual reload. Outage and recovery during operation are logged once.
- Detection "Datamanager or GEN24": a temporary Modbus error no longer permanently misclassifies the device.
  The definite result is stored in the entry. If a device does not respond to the Fronius registers
  at all, the setup no longer fails.
- SunSpec models that are too short are skipped with a warning instead of aborting the whole poll.
  Incomplete Modbus responses count as read errors.
- Several inverters behind the same Datamanager share one Modbus connection; they are polled
  one after the other instead of in parallel (Fronius requirement).
- Power limit: reading the scale factor and writing the setting run as one atomic sequence.

### Fixed
- After **Reconfigure** or an address change, the Modbus connection to the old address stayed open.
- Error responses when writing now carry the Modbus exception code, as when reading.

### Tested
- Control on the real Symo 3.0-3-M (Datamanager 2.0) with version 0.1.0: power limitation and feed-in
  off/on.
- Simulated only: GEN24, battery control, several Smart Meters, DHCP discovery, start without a reachable device.

### Development
- Tests run with Python 3.13 (Home Assistant 2026.2, pymodbus 3.11.2) and Python 3.14 (current Home
  Assistant, pymodbus 3.13.1 and latest version); coverage of the integration code 100 %. The test simulator
  is a dedicated Modbus TCP server.
- CI: lint (`ruff`) and type check (`mypy`), checks also every night and before every release, faster
  runs, GitHub Actions updated to current versions and pinned to commit SHAs.
- Workflow `update-check.yml`: checks GitHub Actions, pinned Python packages and new Home Assistant
  releases weekly and opens issues labelled `aktualisierung` for outdated components.
- Issue templates for bug reports, device reports and feature requests; no `assert` and `type: ignore`
  left in the integration code.

## 0.1.0

First release of the Home Assistant integration for Fronius inverters via Modbus TCP (SunSpec).

### Devices
- **GEN24 / Tauro / Verto** (unit ID 1) and **Datamanager devices** (Symo, Primo, Galvo, Eco, Symo Hybrid …;
  unit ID = inverter number, 00 → 100)
- SunSpec models are detected at runtime (no fixed register addresses), float and int+SF
- Fronius Smart Meter (201–204 / 211–214) as a separate device, automatic search (unit ID 200 or 240)

### Measurements
- AC: power, energy, currents, voltages, frequency, apparent/reactive power, power factor
- PV: total power and current, power/current/voltage/energy per string
- Battery (GEN24 Plus, Verto Plus, Symo Hybrid): power, voltage, energy counters, state of charge,
  state, minimum reserve, charging source, capacity
- Datamanager: site power, energy today / this year / total
- Ratings (rated power, rated current …), precise total energy (64-bit), isolation resistance (GEN24)

### Status and errors
- Operating state, Fronius state, state code and state message in plain text (Datamanager)
- Binary sensor Error (GEN24 also Warning), active error classes and SunSpec events in plain text
- "Power low" / "DC low" during shutdown and start-up do not count as errors

### Control (optional, option "Allow control")
- Power limit (0–100 %) and on/off, feed-in (standby), fallback time
- Reset events (Datamanager)
- Every setting with a fallback time: if Home Assistant fails, the inverter returns to normal operation
  by itself

### Other
- Sensors only for values the device actually provides
- Detailed logging of setup errors, diagnostics export
- Texts in German and English
- Manufacturer documentation with summary under `docs/fronius/`

**Tested** with a Symo 3.0-3-M behind a Datamanager 2.0 and with simulated GEN24, Symo Hybrid and
Smart Meter devices. Control has not yet been tried on the real device.
