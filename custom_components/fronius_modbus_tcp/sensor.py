"""Sensor-Plattform für Fronius Modbus TCP."""

from __future__ import annotations

from dataclasses import dataclass

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
from .entity import FroniusEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FroniusSensorEntityDescription(SensorEntityDescription):
    """Sensorbeschreibung mit Mindestanzahl an Phasen."""

    min_phases: int = 1


def _current(key: str, min_phases: int = 1, **kw) -> FroniusSensorEntityDescription:
    return FroniusSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        min_phases=min_phases,
        **kw,
    )


def _voltage(key: str, min_phases: int = 1, **kw) -> FroniusSensorEntityDescription:
    return FroniusSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        min_phases=min_phases,
        **kw,
    )


def _temperature(key: str) -> FroniusSensorEntityDescription:
    return FroniusSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )


INVERTER_SENSORS: tuple[FroniusSensorEntityDescription, ...] = (
    FroniusSensorEntityDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    FroniusSensorEntityDescription(
        key="ac_energy",
        translation_key="ac_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    _current("ac_current"),
    _current("ac_current_a", entity_registry_enabled_default=False),
    _current("ac_current_b", 2, entity_registry_enabled_default=False),
    _current("ac_current_c", 3, entity_registry_enabled_default=False),
    _voltage("ac_voltage_an"),
    _voltage("ac_voltage_bn", 2),
    _voltage("ac_voltage_cn", 3),
    _voltage("ac_voltage_ab", 2, entity_registry_enabled_default=False),
    _voltage("ac_voltage_bc", 3, entity_registry_enabled_default=False),
    _voltage("ac_voltage_ca", 3, entity_registry_enabled_default=False),
    FroniusSensorEntityDescription(
        key="ac_frequency",
        translation_key="ac_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
    ),
    FroniusSensorEntityDescription(
        key="ac_apparent_power",
        translation_key="ac_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="ac_reactive_power",
        translation_key="ac_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="ac_power_factor",
        translation_key="ac_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    FroniusSensorEntityDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    _current("dc_current"),
    _voltage("dc_voltage"),
    _temperature("temperature_cabinet"),
    _temperature("temperature_heatsink"),
    _temperature("temperature_transformer"),
    _temperature("temperature_other"),
    FroniusSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(sunspec.STATUS.values()),
    ),
    FroniusSensorEntityDescription(
        key="status_vendor",
        translation_key="status_vendor",
        device_class=SensorDeviceClass.ENUM,
        options=list(sunspec.STATUS_VENDOR.values()),
    ),
    FroniusSensorEntityDescription(
        key="events",
        translation_key="events",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


def _mppt_sensors(index: int) -> tuple[SensorEntityDescription, ...]:
    prefix = f"mppt_{index}"
    return (
        SensorEntityDescription(
            key=f"{prefix}_dc_power",
            translation_key="mppt_dc_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        ),
        SensorEntityDescription(
            key=f"{prefix}_dc_current",
            translation_key="mppt_dc_current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        ),
        SensorEntityDescription(
            key=f"{prefix}_dc_voltage",
            translation_key="mppt_dc_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        ),
        SensorEntityDescription(
            key=f"{prefix}_dc_energy",
            translation_key="mppt_dc_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    device = coordinator.device_info
    entities: list[FroniusSensor] = []

    if device.inverter_model is not None:
        entities += [
            FroniusSensor(coordinator, desc)
            for desc in INVERTER_SENSORS
            if desc.min_phases <= device.phases
        ]

    for index, name in enumerate(device.mppt_names, start=1):
        entities += [
            FroniusSensor(coordinator, desc, {"module": name})
            for desc in _mppt_sensors(index)
        ]

    async_add_entities(entities)


class FroniusSensor(FroniusEntity, SensorEntity):
    """Ein Messwert des Wechselrichters."""

    def __init__(
        self,
        coordinator: FroniusCoordinator,
        description: SensorEntityDescription,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if placeholders:
            self._attr_translation_placeholders = placeholders

    @property
    def native_value(self) -> float | int | str | None:
        return self.coordinator.data.values.get(self.entity_description.key)
