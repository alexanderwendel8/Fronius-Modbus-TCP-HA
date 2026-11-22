"""Sensor-Plattform für Fronius Modbus TCP."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import sunspec
from .coordinator import FroniusConfigEntry, FroniusCoordinator
from .entity import DEVICE_INVERTER, DEVICE_METER, FroniusEntity, drop_unsupported

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FroniusSensorEntityDescription(SensorEntityDescription):
    """Sensorbeschreibung mit Mindestanzahl an Phasen."""

    min_phases: int = 1
    # Wert hängt vom Gerätetyp ab: meldet das Gerät ihn beim Start als
    # "nicht unterstützt", wird der Sensor nicht angelegt. Nicht für
    # Messwerte, die nachts vorübergehend NaN sein können (Leistung, Spannung …).
    skip_if_unsupported: bool = False


# --- Fabriken für wiederkehrende Sensortypen --------------------------------


def _desc(key: str, **kw) -> FroniusSensorEntityDescription:
    kw.setdefault("translation_key", key)
    return FroniusSensorEntityDescription(key=key, **kw)


def _power(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        **kw,
    )


def _current(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        **kw,
    )


def _voltage(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        **kw,
    )


def _energy(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        **kw,
    )


def _frequency(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        **kw,
    )


def _apparent_power(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_registry_enabled_default=False,
        **kw,
    )


def _reactive_power(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        **kw,
    )


def _temperature(key: str) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        skip_if_unsupported=True,
    )


def _enum(key: str, options: dict[int, str], **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        device_class=SensorDeviceClass.ENUM,
        options=list(options.values()),
        **kw,
    )


def _percent(key: str, **kw) -> FroniusSensorEntityDescription:
    return _desc(
        key,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        **kw,
    )


_OFF = {"entity_registry_enabled_default": False}
_DIAG = {"entity_category": EntityCategory.DIAGNOSTIC}

# --- Wechselrichter ---------------------------------------------------------

INVERTER_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _power("ac_power"),
    _energy("ac_energy"),
    _current("ac_current"),
    _current("ac_current_a", **_OFF),
    _current("ac_current_b", min_phases=2, **_OFF),
    _current("ac_current_c", min_phases=3, **_OFF),
    _voltage("ac_voltage_an"),
    _voltage("ac_voltage_bn", min_phases=2),
    _voltage("ac_voltage_cn", min_phases=3),
    _voltage("ac_voltage_ab", min_phases=2, **_OFF),
    _voltage("ac_voltage_bc", min_phases=3, **_OFF),
    _voltage("ac_voltage_ca", min_phases=3, **_OFF),
    _frequency("ac_frequency"),
    _apparent_power("ac_apparent_power"),
    _reactive_power("ac_reactive_power"),
    _desc(
        "ac_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        **_OFF,
    ),
    _power("dc_power"),
    _current("dc_current"),
    _voltage("dc_voltage"),
    _temperature("temperature_cabinet"),
    _temperature("temperature_heatsink"),
    _temperature("temperature_transformer"),
    _temperature("temperature_other"),
    _enum("status", sunspec.STATUS),
    _enum("status_vendor", sunspec.STATUS_VENDOR),
    _desc("events", skip_if_unsupported=True, **_DIAG, **_OFF),
)

PV_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _power("pv_power"),
    _current("pv_current"),
)

# Bei mehreren DC-Eingängen liefert das Inverter-Model nur DCW; DCA und DCV sind
# laut Fronius "not implemented" (Werte stehen je Eingang in Modell 160).
SINGLE_DC_INPUT_ONLY = {"dc_current", "dc_voltage"}

# Aktuelle Vorgaben aus Modell 123 (nur lesend)
CONTROLS_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _percent("power_limit", suggested_display_precision=0, skip_if_unsupported=True),
    _desc(
        "pf_setpoint",
        device_class=SensorDeviceClass.POWER_FACTOR,
        skip_if_unsupported=True,
        **_DIAG,
        **_OFF,
    ),
    _percent("var_limit", skip_if_unsupported=True, **_DIAG, **_OFF),
)

# Nennwerte aus Modell 120 (statisch)
NAMEPLATE_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _desc(
        "rated_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        skip_if_unsupported=True,
        **_DIAG,
    ),
    _desc(
        "rated_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        skip_if_unsupported=True,
        **_DIAG,
        **_OFF,
    ),
    _desc(
        "rated_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        skip_if_unsupported=True,
        **_DIAG,
        **_OFF,
    ),
)
BATTERY_NAMEPLATE_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _desc(
        "battery_capacity",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        skip_if_unsupported=True,
    ),
    _desc(
        "battery_max_charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        skip_if_unsupported=True,
        **_DIAG,
    ),
    _desc(
        "battery_max_discharge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        skip_if_unsupported=True,
        **_DIAG,
    ),
)

# Anlagensummen aus den Fronius-Registern 500-513 (nur Datamanager)
SITE_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _power("site_power"),
    _energy("site_energy_day"),
    _energy("site_energy_year"),
    _energy("site_energy_total"),
    # Aktueller Fronius State Code (Register 214) mit Klartext aus der Fronius-Liste
    _desc("state_code", skip_if_unsupported=True),
    _desc("state_message", skip_if_unsupported=True),
)

# Batterie über Modell 160 (Leistung, Spannung, Energie)
BATTERY_MPPT_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _power("battery_power"),
    _power("battery_charge_power"),
    _power("battery_discharge_power"),
    _voltage("battery_voltage"),
)
BATTERY_ENERGY_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _energy("battery_charge_energy"),
    _energy("battery_discharge_energy"),
)

# Batterie über Modell 124 (Ladezustand, Status, Vorgaben)
BATTERY_STORAGE_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _desc(
        "battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    _enum("battery_state", sunspec.STORAGE_STATE),
    _percent("battery_min_reserve", suggested_display_precision=0),
    _enum("battery_grid_charging", sunspec.STORAGE_GRID_CHARGING, **_DIAG),
    _enum("battery_control_mode", sunspec.STORAGE_CONTROL_MODE, **_DIAG, **_OFF),
    _percent("battery_charge_limit", **_DIAG, **_OFF),
    _percent("battery_discharge_limit", **_DIAG, **_OFF),
    _desc(
        "battery_max_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        **_DIAG,
    ),
)

# --- Smart Meter ------------------------------------------------------------

METER_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    _power("meter_power"),
    _power("meter_power_a", **_OFF),
    _power("meter_power_b", min_phases=2, **_OFF),
    _power("meter_power_c", min_phases=3, **_OFF),
    _energy("meter_energy_import"),
    _energy("meter_energy_export"),
    _energy("meter_energy_import_a", **_OFF),
    _energy("meter_energy_import_b", min_phases=2, **_OFF),
    _energy("meter_energy_import_c", min_phases=3, **_OFF),
    _energy("meter_energy_export_a", **_OFF),
    _energy("meter_energy_export_b", min_phases=2, **_OFF),
    _energy("meter_energy_export_c", min_phases=3, **_OFF),
    _current("meter_current"),
    _current("meter_current_a", **_OFF),
    _current("meter_current_b", min_phases=2, **_OFF),
    _current("meter_current_c", min_phases=3, **_OFF),
    _voltage("meter_voltage_an"),
    _voltage("meter_voltage_bn", min_phases=2),
    _voltage("meter_voltage_cn", min_phases=3),
    _voltage("meter_voltage_ab", min_phases=2, **_OFF),
    _voltage("meter_voltage_bc", min_phases=3, **_OFF),
    _voltage("meter_voltage_ca", min_phases=3, **_OFF),
    _frequency("meter_frequency"),
    _apparent_power("meter_apparent_power"),
    _reactive_power("meter_reactive_power"),
    _desc(
        "meter_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        **_OFF,
    ),
)

# Welche Zählerwerte geliefert werden, hängt von Zählertyp und Netzanschluss ab
METER_SENSORS = tuple(
    desc if desc.key == "meter_power" else replace(desc, skip_if_unsupported=True)
    for desc in METER_SENSORS
)


def _mppt_sensors(index: int) -> tuple[FroniusSensorEntityDescription, ...]:
    prefix = f"mppt_{index}"
    return (
        _power(f"{prefix}_dc_power", translation_key="mppt_dc_power"),
        _current(f"{prefix}_dc_current", translation_key="mppt_dc_current"),
        _voltage(f"{prefix}_dc_voltage", translation_key="mppt_dc_voltage"),
        _energy(
            f"{prefix}_dc_energy",
            translation_key="mppt_dc_energy",
            skip_if_unsupported=True,
            **_OFF,
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    inverter = coordinator.inverter
    entities: list[FroniusSensor] = [
        FroniusSensor(coordinator, desc)
        for desc in INVERTER_SENSORS
        if desc.min_phases <= inverter.phases
        and not (
            len(inverter.mppt_roles) > 1 and desc.key in SINGLE_DC_INPUT_ONLY
        )
    ]

    roles = inverter.mppt_roles
    for index, (name, role) in enumerate(zip(inverter.mppt_names, roles, strict=True), start=1):
        if role == sunspec.ROLE_PV:
            entities += [
                FroniusSensor(coordinator, desc, {"module": name})
                for desc in _mppt_sensors(index)
            ]

    if sunspec.ROLE_PV in roles:
        entities += [FroniusSensor(coordinator, desc) for desc in PV_SENSORS]
    if any(role != sunspec.ROLE_PV for role in roles):
        entities += [FroniusSensor(coordinator, desc) for desc in BATTERY_MPPT_SENSORS]
    if sunspec.ROLE_BATTERY_CHARGE in roles or sunspec.ROLE_BATTERY_DISCHARGE in roles:
        # Symo Hybrid liefert keine DC-Energiezähler
        entities += [
            FroniusSensor(coordinator, desc) for desc in BATTERY_ENERGY_SENSORS
        ]
    if inverter.has_storage:
        entities += [
            FroniusSensor(coordinator, desc) for desc in BATTERY_STORAGE_SENSORS
        ]
    if inverter.has_site_registers:
        entities += [FroniusSensor(coordinator, desc) for desc in SITE_SENSORS]
    if sunspec.CONTROLS_MODEL in inverter.models:
        entities += [FroniusSensor(coordinator, desc) for desc in CONTROLS_SENSORS]
    if inverter.nameplate:
        entities += [FroniusSensor(coordinator, desc) for desc in NAMEPLATE_SENSORS]
        if inverter.has_storage:
            entities += [
                FroniusSensor(coordinator, desc) for desc in BATTERY_NAMEPLATE_SENSORS
            ]

    if (meter := coordinator.meter) is not None:
        entities += [
            FroniusSensor(coordinator, desc, device=DEVICE_METER)
            for desc in METER_SENSORS
            if desc.min_phases <= meter.phases
        ]

    async_add_entities(drop_unsupported(hass, coordinator, "sensor", entities))


class FroniusSensor(FroniusEntity, SensorEntity):
    """Ein Messwert von Wechselrichter, Batterie oder Smart Meter."""

    entity_description: FroniusSensorEntityDescription

    def __init__(
        self,
        coordinator: FroniusCoordinator,
        description: FroniusSensorEntityDescription,
        placeholders: dict[str, str] | None = None,
        device: str = DEVICE_INVERTER,
    ) -> None:
        super().__init__(coordinator, description.key, device)
        self.entity_description = description
        if placeholders:
            self._attr_translation_placeholders = placeholders

    @property
    def native_value(self) -> float | int | str | None:
        return self.coordinator.data.values.get(self.entity_description.key)
