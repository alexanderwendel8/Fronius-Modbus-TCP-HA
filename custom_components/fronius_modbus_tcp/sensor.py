"""Sensor-Plattform für Fronius Modbus TCP."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FroniusConfigEntry, FroniusCoordinator
from .entity import FroniusEntity

PARALLEL_UPDATES = 0

# Neue Sensoren: hier eintragen und in api.FroniusModbusClient.read_data() befüllen.
SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(FroniusSensor(coordinator, desc) for desc in SENSORS)


class FroniusSensor(FroniusEntity, SensorEntity):
    """Ein Messwert des Wechselrichters."""

    def __init__(
        self, coordinator: FroniusCoordinator, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        return self.coordinator.data.values.get(self.entity_description.key)
