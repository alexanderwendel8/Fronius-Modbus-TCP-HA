"""Switch-Plattform: Leistungsbegrenzung und Einspeisung (nur mit "Steuerung erlauben")."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FroniusConfigEntry, FroniusCoordinator
from .entity import FroniusEntity, async_write

PARALLEL_UPDATES = 1

POWER_LIMIT_ACTIVE = SwitchEntityDescription(
    key="power_limit_active", translation_key="power_limit_active"
)
FEED_IN = SwitchEntityDescription(key="feed_in_enabled", translation_key="feed_in_enabled")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.control_allowed:
        async_add_entities(
            [
                FroniusPowerLimitSwitch(coordinator, POWER_LIMIT_ACTIVE),
                FroniusFeedInSwitch(coordinator, FEED_IN),
            ]
        )


class _FroniusSwitch(FroniusEntity, SwitchEntity):
    def __init__(
        self, coordinator: FroniusCoordinator, description: SwitchEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.values.get(self.entity_description.key)


class FroniusPowerLimitSwitch(_FroniusSwitch):
    """Leistungsbegrenzung ein/aus (WMaxLim_Ena) mit dem Wert der Number-Entität."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        coordinator = self.coordinator
        percent = coordinator.data.values.get("power_limit")
        await async_write(
            coordinator,
            coordinator.client.set_power_limit(
                coordinator.inverter,
                100.0 if percent is None else percent,
                enabled=True,
                revert_seconds=coordinator.revert_seconds,
            ),
            {"power_limit_active": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        coordinator = self.coordinator
        await async_write(
            coordinator,
            coordinator.client.disable_power_limit(coordinator.inverter),
            {"power_limit_active": False},
        )


class FroniusFeedInSwitch(_FroniusSwitch):
    """Einspeisung (Conn): aus = Standby, nach der Rückfallzeit wieder Einspeisung."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        coordinator = self.coordinator
        await async_write(
            coordinator,
            coordinator.client.set_feed_in(
                coordinator.inverter, True, revert_seconds=coordinator.revert_seconds
            ),
            {"feed_in_enabled": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        coordinator = self.coordinator
        await async_write(
            coordinator,
            coordinator.client.set_feed_in(
                coordinator.inverter, False, revert_seconds=coordinator.revert_seconds
            ),
            {"feed_in_enabled": False},
        )
