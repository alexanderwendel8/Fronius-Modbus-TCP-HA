"""Binärsensor-Plattform für Fronius Modbus TCP."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
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
    entities: list[FroniusBinarySensor] = []
    if sunspec.CONTROLS_MODEL in coordinator.inverter.models:
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
