[Deutsch](README.md) | **English**

# Fronius Modbus TCP for Home Assistant

Custom integration that reads Fronius inverters locally via **Modbus TCP (SunSpec)** – no cloud and no
Solar.web. It supports GEN24/Tauro/Verto as well as older devices behind a Datamanager
(Symo, Primo, Galvo, Eco, Symo Hybrid …), each with PV strings, battery and Fronius Smart Meter.
Optionally, power limitation and feed-in can be controlled from Home Assistant.

> **Status:** Version 0.2 – in use on a real Symo 3.0-3-M behind a Datamanager 2.0
> (see [Tested devices](#tested-devices)); GEN24, battery and Smart Meter only tested against
> simulated devices so far. Reports about further devices are welcome.

## Features

- Automatic detection of the SunSpec models (register addresses are not hard-coded)
- Both Fronius settings: **float** (111–113 / 211–214) and **int+SF** (101–103 / 201–204)
- GEN24 / Tauro / Verto **and** Datamanager devices (Symo, Primo, Galvo, Eco, Symo Hybrid …)
- Single-, two- and three-phase devices; per-phase sensors are created to match
- **PV strings** (model 160) individually and as a total
- **Battery** (GEN24 Plus, Verto Plus, Symo Hybrid): charge/discharge power, voltage, energy counters,
  state of charge, state, minimum reserve, charging source (model 124)
- **Fronius Smart Meter** as a separate device: power, import/export, currents, voltages, frequency
- Diagnostics (host and serial numbers redacted) for bug reports

### Sensors

| Device | Area | Sensors | Enabled by default |
|---|---|---|---|
| Inverter | AC | Power, total energy, current, voltage L-N per phase, grid frequency | yes |
| | AC | Current per phase, voltage L-L, apparent/reactive power, power factor | no |
| | DC | Power; current and voltage only on devices with a single DC input* | yes |
| | PV | Total PV power and PV current; power, current, voltage per string | yes |
| | PV | Energy per string | no |
| | Battery | Power (+ discharging / − charging), charge and discharge power, voltage, charged/discharged energy**, state of charge, state, minimum reserve | yes |
| | Battery | Charging source, maximum power (diagnostic); control mode, charge/discharge limit | partly |
| | Status | Operating state (SunSpec), Fronius state | yes |
| | Status (Datamanager) | State code and state message in plain text (e.g. "306 Power Low") | yes |
| | Errors | Binary sensor Error; GEN24/Tauro/Verto also Warning; Datamanager: active error classes in plain text ("Power low"/"DC low" during shutdown and start-up do not count as errors) | yes |
| | Events | SunSpec events in plain text (e.g. "Over temperature") | yes |
| | Model 122 | Total energy (precise, 64-bit counter; GEN24 and Datamanager); isolation resistance (diagnostic, GEN24) | yes |
| | Site (Datamanager) | Site power, energy today, energy this year, site total energy | yes |
| | Settings (model 123, read-only) | Power limit in %, power limit active, feed-in enabled | yes |
| | Settings (diagnostic) | Power factor and reactive power setting and whether they are active | no |
| | Ratings (model 120) | Rated power; battery capacity; max. charge/discharge power | yes (diagnostic) |
| | Ratings (diagnostic) | Rated apparent power, rated current | no |
| | Diagnostic | Temperatures, event flags (raw value) | no |
| Smart Meter | | Power, energy imported, energy exported, current, voltage L-N per phase, frequency | yes |
| | | Power/current/energy per phase, voltage L-L, apparent/reactive power, power factor | no |

\* With several DC inputs, Fronius provides DC current and DC voltage only per string (model 160);
the totals in the inverter model are then "not supported" and are not created.

\*\* Battery energy counters only on GEN24/Verto (Symo Hybrid does not provide them).

Optional values that the device reports as "not supported" at startup (temperatures, event flags,
energy per string, individual Smart Meter values) are not created at all. If a new firmware supports the
value later, the sensor appears after the next restart. A sensor that has delivered a value before is kept,
even if the value is missing at a later start – it then shows "unknown". Core values such as power, current
and voltage are always created, even if they are temporarily "unknown" (e.g. at night).

**Signs:** battery power positive = discharging. Smart Meter as delivered by the device – when installed at
the grid connection point, positive = grid import, negative = feed-in.

## Tested devices

| Device | Connection | Inverter firmware | Integration | Home Assistant | Result |
|---|---|---|---|---|---|
| **Symo 3.0-3-M** (real device) | Datamanager 2.0, Modbus TCP, unit ID 1 | 0.3.30.2 | 0.1.0 | 2026.11.2 (HA OS 18.4) | ✅ measurements, site values, state code, error classes, models 120/122/123 read-only · ✅ control: power limitation and feed-in off/on (2026-11-23) |
| GEN24 Plus with battery and Smart Meter | simulated (tests) | – | 0.2.1 | test environment | ✅ automated tests |
| Symo Hybrid with battery (Datamanager) | simulated (tests) | – | 0.2.1 | test environment | ✅ automated tests |
| GEN24 without battery, device with a single DC input | simulated (tests) | – | 0.2.1 | test environment | ✅ automated tests |
| Smart Meter 203 (int+SF) / 213 (float) | simulated (tests) | – | 0.2.1 | test environment | ✅ automated tests |

Observations on the real Symo: it provides `ActWh` (model 122), but no isolation resistance and no
temperatures – these sensors are therefore not created.

Control test on the Symo (with only about 40 W of PV power):
- **Power limit 1 % (= 30 W):** after about 7 s operating state *throttled*, AC power 33 → 29 W.
- **Feed-in off:** after about 15 s 0 W, operating state *standby*, no error.
- **Feed-in back on, limit off:** the inverter restarts; in very low light this can take several minutes
  (repeated start attempts with state code *306 Power Low*, about 9 minutes in the test).
  The binary sensor *Error* stays off.
- The switches show the state read back from the device. Please report further devices via an issue
(model, firmware, connection, Home Assistant version, diagnostics export).

## Requirements

- Modbus TCP enabled:
  - **GEN24 / Tauro / Verto:** user interface → Communication → Modbus → *TCP Server*
  - **Datamanager:** web interface → Settings → Modbus → *Data output via Modbus* **tcp** (Datamanager 2.0 is set to rtu at the factory)
- SunSpec Model Type: **float** or **int+SF**
- Home Assistant 2026.2 or newer

## Installation

**Marketplace (Home Assistant 2026.11 and later):** Since 2026.11 the built-in *Marketplace* replaces HACS
([official documentation](https://www.home-assistant.io/integrations/marketplace/)). It is found under
*Settings → Marketplace* (administrators only); a separate HACS installation is not needed.
The integration is not (yet) listed in the catalog and is added as a custom repository:

1. Open *Settings → Marketplace*; when opening it for the first time, accept the warning
   (without consent the Marketplace cannot install anything).
2. In the top right, select **Add from link**, enter `alexanderwendel8/Fronius-Modbus-TCP-HA` under
   **GitHub link**, then **Add**. If not done yet, the Marketplace now asks for a GitHub connection
   (sign-in with a code on github.com; read access to public data only) – it is required for custom
   repositories.
3. Open the repository in the list, select **Install**, check the version (latest release, e.g. `v0.2.1`),
   **Install**. If a restart is needed, a repair issue under *Settings → System → Repairs* reminds you.

Updates appear under *Settings → Updates* (with release notes); with a GitHub connection the Marketplace
checks custom repositories every 48 hours. Restart Home Assistant after an update – again a repair issue
reminds you. An existing HACS installation is taken over automatically on the first start of 2026.11,
including this repository and its update entity.

**HACS (Home Assistant before 2026.11):** Add this repository as a custom repository (type *Integration*),
install it, restart Home Assistant.

**Manually:** Copy `custom_components/fronius_modbus_tcp` to `<config>/custom_components/` and restart.

Then search for "Fronius Modbus TCP" under *Settings → Devices & services → Add integration*:
(If a Fronius device shows up in the network via DHCP and answers via Modbus TCP on port 502 at
address 1, Home Assistant suggests the setup on its own. If a device that is already set up gets a new
IP address this way, it is taken over automatically.)


| Field | GEN24 / Tauro / Verto | Datamanager (Symo, Primo, Galvo …) |
|---|---|---|
| Host | IP of the inverter | IP of the Datamanager |
| Port | 502 (or 1502) | 502 |
| Inverter Modbus address | **1** | **inverter number** (00 → 100) |
| Smart Meter Modbus address | empty = automatic (200) | empty = automatic (240) |
| Additional Smart Meters | e.g. `201, 202` | e.g. `241, 242` |

`0` as the Smart Meter address disables the meter. With several inverters behind one Datamanager,
create a separate entry for each inverter; the Smart Meter is assigned automatically only to the
first entry. All entries on the same Datamanager share one Modbus connection and are polled
one after the other.

**Several Smart Meters:** Additional meters (e.g. consumption or production meters) are entered in the
"Additional Smart Meters" field with their Modbus addresses, separated by commas. Each meter appears
as a separate device with the same sensors; with identical models the device name shows the address in
parentheses. The meter in the "Smart Meter Modbus address" field remains the main meter at the grid
connection point.

**Changing the connection settings:** If the inverter gets a new IP address or the Smart Meter is to be
added later, the entry does not have to be deleted. Under *Settings → Devices & services →
Fronius Modbus TCP*, open the three-dot menu of the entry and select **Reconfigure**. The device must
stay the same (same serial number); entities and history are kept.

If the Smart Meter does not respond at startup, the inverter is set up anyway. The integration then
searches for the meter again every 5 minutes and reloads the entry as soon as it is found.

## Control (optional)

By default, the integration only reads. Writing entities are only available after
*Settings → Devices & services → Fronius Modbus TCP → **Configure** → "Allow control"*.

**Requirement on the device:** In the Fronius web interface, "Inverter control via Modbus"
(Datamanager) or "Allow Control" (GEN24) must be enabled. Recommended: "Restrict Control"
to the IP address of Home Assistant. Settings of the grid operator (control priorities in the
UC Editor) take precedence.

| Entity | Type | Effect |
|---|---|---|
| Power limit | number 0–100 % | Maximum output power in % of the rated power. While the limit is active, a new value takes effect immediately; otherwise it is only stored. |
| Power limit active | switch | Limit on/off |
| Feed-in | switch | Off = standby (no feed-in) |
| Fallback time for settings | number (s), configuration | Default 300 s, see below |
| Reset events | button, Datamanager only | Clears stuck event flags and the state code |

When control is allowed, "Power limit", "Power limit active" and "Feed-in" replace the
display-only entities of the same name.

### Battery control (devices with battery)

If the inverter has a storage system (SunSpec model 124), these entities are added. They replace
the display sensors "Battery charge limit", "Battery discharge limit", "Battery minimum reserve" and
"Battery charging source".

| Entity | Type | Effect |
|---|---|---|
| Battery charge limit | number −100…100 % | Maximum charge power in % of the storage rating (`WChaMax`) |
| Battery charge limit active | switch | Apply the charge limit |
| Battery discharge limit | number −100…100 % | Maximum discharge power in % of `WChaMax` |
| Battery discharge limit active | switch | Apply the discharge limit |
| Battery minimum reserve | number 0–100 % | State of charge that should not be undercut (stays set permanently) |
| Battery charging from grid | switch | Allow charging from the grid. Must also be allowed in the Fronius web interface ("battery charging from DNO grid"). |

A limit only applies while its switch is on. Typical settings (from the Fronius manual):

| Goal | Setting |
|---|---|
| Charge only, do not discharge | discharge limit 0 %, "discharge limit active" on |
| Discharge only, do not charge | charge limit 0 %, "charge limit active" on |
| Hold the battery (neither charge nor discharge) | both limits 0 %, both switches on |
| Force charging with at least 50 % | discharge limit −50 %, "discharge limit active" on |
| Force discharging with 50 % | charge limit −50 %, discharge limit 50 %, both switches on |

Negative values therefore force the opposite direction. If both limits are active, the negated charge
limit must not be greater than the discharge limit; the integration rejects such a window with an error
message before writing. Charge and discharge limits are written with the fallback time (see below);
minimum reserve and grid charging stay set permanently. According to Fronius, all settings are
recommendations: the inverter may deviate from them for safety reasons.

**Symo Hybrid (Datamanager):** The device does not support a fallback time for the charge and
discharge limits (`InOutWRte_RvrtTms` is "Not supported" according to the Fronius register map). An
active limit stays in place there until its switch is turned off – even if Home Assistant fails. The
integration then does not write the fallback time and reports this once in the log.

On the Datamanager, the charge and discharge limit values show only the limits set via Modbus by default,
not system-wide restrictions (Fronius register 217 `F_Storage_Restrictions_View_Mode`, 0 = "local").

**Not tested with a real battery** – only against simulated devices so far.

**Polling interval:** In the same dialog (**Configure**) you can set how often the device is polled:
5–60 s, default 10 s. Datamanager devices respond slowly; a longer interval reduces their load.
The fallback time is always at least three times the polling interval.

**Fallback time:** Every setting is written with a fallback time. Since every Modbus request restarts the
timer in the inverter, a setting stays active as long as Home Assistant is running. If Home Assistant
fails, the inverter returns to normal operation by itself after this time – a power reduction or standby
therefore cannot "get stuck". When the fallback time is changed, the integration immediately transfers
the new value to all currently active settings (power limit, standby, battery charge/discharge limit).

Example automation: throttle to 0 % when the electricity price is negative:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.electricity_price
    below: 0
actions:
  - action: number.set_value
    target: {entity_id: number.symo_3_0_3_m_power_limit}
    data: {value: 0}
  - action: switch.turn_on
    target: {entity_id: switch.symo_3_0_3_m_power_limit_active}
```

## Behavior when the device does not respond

The integration remembers the most recently detected device structure (models, strings, battery, Smart
Meters). If the inverter does not respond when Home Assistant starts – for example at night, when a device
behind the Datamanager is switched off – the entry is set up anyway. The entities are then
"unavailable" and deliver values again as soon as the device responds; the entry then reloads once
and detects the structure afresh. Only for the very first setup does the device have to be reachable.

## Diagnostics and bug reports

Under *Settings → Devices & services → Fronius Modbus TCP*, the three-dot menu of the entry offers
**Download diagnostics**. The file contains the detected device structure, the options,
the most recently read values and the **raw registers of all SunSpec models** of the inverter and
Smart Meters (for Datamanager devices also the Fronius registers 212–216 and 500–513). Host and
serial numbers are removed. If there is a problem with a device that has not been tested, please attach
this file to the issue – it allows the behavior to be traced without access to the device.

Under [Issues](https://github.com/alexanderwendel8/Fronius-Modbus-TCP-HA/issues/new/choose) there are
three templates: bug report, report on a tested device, and feature request.

## Structure

| File | Purpose |
|---|---|
| `api.py` | Modbus client, detection of the model chain, register access |
| `client_pool.py` | Shared connection for all entries on the same host and port |
| `sunspec.py` | SunSpec model definitions and decoding (no Home Assistant dependency) |
| `coordinator.py` | Periodic polling (`DataUpdateCoordinator`) |
| `config_flow.py` | Setup via the UI including connection test |
| `entity.py` | Base entity with device assignment |
| `sensor.py` | Sensor definitions |
| `binary_sensor.py` | Binary sensors (error, warning, settings from model 123) |
| `number.py`, `switch.py`, `button.py` | Control (only with the "Allow control" option) |
| `state_codes.py` | Fronius state codes in plain text (generated with `scripts/generate_state_codes.py`) |
| `diagnostics.py` | Diagnostics export including raw registers of all SunSpec models |
| `strings.json`, `translations/` | Texts (EN/DE) |
| `icons.json` | Icons for entities without a device class |

## Adding new sensors

1. Decode the value in the matching `parse_*` function in `sunspec.py` and return it under `"<key>"`
   (for a new SunSpec model, also read it in `FroniusModbusClient.read_inverter_data()`).
2. Add a matching `SensorEntityDescription` with the same `key` in `sensor.py`.
3. Add the name under `entity.sensor.<key>` in `strings.json` and `translations/*.json`.

## Tests

```bash
pip install -r requirements_test.txt
pytest
```

The checks (`validate.yml`) run on every pull request, on `main`, before every release and additionally
every night – so breakage caused by new versions of Home Assistant or pymodbus shows up even when
nothing in the repository has changed.

Before a commit, also run `ruff check .` (rules in `pyproject.toml`) and `mypy` (type check of the
integration code); both also run in CI.

The tests start simulated Fronius devices (`tests/simulator.py`) as a real Modbus TCP server and
set up the integration in a Home Assistant test instance.

In addition, the workflow [`update-check.yml`](.github/workflows/update-check.yml) checks the
external components every Monday and opens an issue with the label `aktualisierung` for every
outdated component:
- **GitHub Actions** in `.github/workflows` with a version (new release; references to a
  branch such as `@main` are skipped)
- **Python packages** pinned in `requirements_test.txt` or the workflows; pins with
  the comment `# update-check: ignore` (e.g. the minimum version of pymodbus) are skipped
- **Home Assistant:** a new monthly release compared with the newest version in the column
  "Home Assistant" of the table [Tested devices](#tested-devices) in `README.md`, and a higher
  minimum Python version than in the workflows

Once the component is current again, the workflow closes the issue itself. The checks are in
[`.github/scripts/check_updates.py`](.github/scripts/check_updates.py); locally,
`python .github/scripts/check_updates.py --dry-run` shows the result without changing issues.

## Releases

Changes are listed in [`CHANGELOG.en.md`](CHANGELOG.en.md) (German: [`CHANGELOG.md`](CHANGELOG.md),
which is the source of the release notes). Releases are created by the workflow `release.yml`
with the notes from the changelog – either via a tag `vX.Y.Z` or manually under
*Actions → Release → Run workflow* (on `main`, input e.g. `0.1.0`; the tag is then created).
The version must match `manifest.json`. Before the release, the same checks run as for every
pull request (Hassfest, HACS, lint, tests); if one fails, no release is created. Marketplace and HACS then show the version number instead of the commit hash.

### Pre-releases

The Marketplace only reports releases as updates, not individual commits on `main`
([source code](https://github.com/home-assistant/core/blob/2026.11.2/homeassistant/components/marketplace/repositories/base.py)).
For testing before a release, the workflow `prerelease.yml` creates a pre-release from the
current state of `main`: *Actions → Pre-release → Run workflow*; the input is the planned
next version, e.g. `0.3.0`. This creates `v0.3.0b1`, on the next run `v0.3.0b2` and so on,
with the notes from the "Unveröffentlicht" (unreleased) section of `CHANGELOG.md`. The same checks run
beforehand as for a release. No pull request is needed; `main` stays unchanged (the version `0.3.0b1`
exists only in the commit of the tag).

The Marketplace only offers pre-releases if the **Pre-release** switch is turned on for the repository:
**Settings** > **Devices & services** > **Marketplace** → device *Fronius Modbus TCP*,
enable the **Pre-release** entity there (disabled by default) and turn it on
([documentation](https://www.home-assistant.io/integrations/marketplace/)). Everyone else keeps
receiving stable releases only.

## Manufacturer documentation

The Fronius register maps and state code tables are in [`docs/fronius/`](docs/fronius/README.md) –
with a file index and a summary (in German) of the points relevant to this integration.

These documents come from Fronius International GmbH and can be downloaded freely there
(links in [`docs/fronius/README.md`](docs/fronius/README.md)). They are kept here only as a reference
for development and are **not** covered by this project's licence; all rights remain with
Fronius. This also applies to the English state texts in
[`state_codes.py`](custom_components/fronius_modbus_tcp/state_codes.py), which are taken from
"Fronius State Codes & Event Flags 1.0".

## Licence

The code of this project is licensed under the [Apache License 2.0](LICENSE). Excluded are the
manufacturer documents in `docs/fronius/` and the state texts taken from them (see
[Manufacturer documentation](#manufacturer-documentation)). "Fronius", "GEN24", "Symo", "Primo",
"Tauro" and "Verto" are trademarks of Fronius International GmbH; this project is not affiliated
with Fronius.
