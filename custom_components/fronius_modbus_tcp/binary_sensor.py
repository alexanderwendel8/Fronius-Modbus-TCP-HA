"""Binärsensor-Plattform für Fronius Modbus TCP."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import sunspec
from .coordinator import FroniusConfigEntry, FroniusCoordinator
from .entity import FroniusEntity, drop_unsupported

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FroniusBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binärsensor; nicht unterstützte Werte werden nicht angelegt."""

    skip_if_unsupported: bool = True


# Fehler/Warnungen aus EvtVnd1-4 (GEN24: Schweregrad, Datamanager: Fehlerklassen)
ERROR_BINARY_SENSOR = FroniusBinarySensorEntityDescription(
    key="error_active",
    translation_key="error_active",
    device_class=BinarySensorDeviceClass.PROBLEM,
)
WARNING_BINARY_SENSOR = FroniusBinarySensorEntityDescription(
    key="warning_active",
    translation_key="warning_active",
    device_class=BinarySensorDeviceClass.PROBLEM,
)

# Aktueller Zustand der Vorgaben aus Modell 123 (nur lesend)
CONTROLS_BINARY_SENSORS: tuple[FroniusBinarySensorEntityDescription, ...] = (
    FroniusBinarySensorEntityDescription(
        key="power_limit_active", translation_key="power_limit_active"
    ),
    FroniusBinarySensorEntityDescription(
        key="feed_in_enabled", translation_key="feed_in_enabled"
    ),
    FroniusBinarySensorEntityDescription(
        key="pf_control_active",
        translation_key="pf_control_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    FroniusBinarySensorEntityDescription(
        key="var_control_active",
        translation_key="var_control_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    inverter = coordinator.inverter
    entities: list[FroniusBinarySensor] = [
        FroniusBinarySensor(coordinator, ERROR_BINARY_SENSOR)
    ]
    if not inverter.has_site_registers:
        # Warnungen gibt es nur bei den Schweregrad-Bits (GEN24/Tauro/Verto)
        entities.append(FroniusBinarySensor(coordinator, WARNING_BINARY_SENSOR))
    if sunspec.CONTROLS_MODEL in inverter.models:
        entities += [
            FroniusBinarySensor(coordinator, desc) for desc in CONTROLS_BINARY_SENSORS
        ]
    async_add_entities(drop_unsupported(hass, coordinator, "binary_sensor", entities))


class FroniusBinarySensor(FroniusEntity, BinarySensorEntity):
    """Ein Ja/Nein-Zustand des Wechselrichters."""

    entity_description: FroniusBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FroniusCoordinator,
        description: FroniusBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.values.get(self.entity_description.key)
