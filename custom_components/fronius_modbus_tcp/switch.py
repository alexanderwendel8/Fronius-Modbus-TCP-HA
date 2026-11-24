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


BATTERY_CHARGE_LIMIT_ACTIVE = SwitchEntityDescription(
    key="battery_charge_limit_active", translation_key="battery_charge_limit_active"
)
BATTERY_DISCHARGE_LIMIT_ACTIVE = SwitchEntityDescription(
    key="battery_discharge_limit_active",
    translation_key="battery_discharge_limit_active",
)
BATTERY_GRID_CHARGING = SwitchEntityDescription(
    key="battery_grid_charging_allowed", translation_key="battery_grid_charging_allowed"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[_FroniusSwitch] = []
    if coordinator.control_allowed:
        entities += [
            FroniusPowerLimitSwitch(coordinator, POWER_LIMIT_ACTIVE),
            FroniusFeedInSwitch(coordinator, FEED_IN),
        ]
    if coordinator.storage_control_allowed:
        entities += [
            FroniusStorageLimitSwitch(coordinator, BATTERY_CHARGE_LIMIT_ACTIVE),
            FroniusStorageLimitSwitch(coordinator, BATTERY_DISCHARGE_LIMIT_ACTIVE),
            FroniusGridChargingSwitch(coordinator, BATTERY_GRID_CHARGING),
        ]
    async_add_entities(entities)


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


class FroniusStorageLimitSwitch(_FroniusSwitch):
    """Lade- bzw. Entladegrenze des Speichers aktivieren (Bits in StorCtl_Mod)."""

    async def _async_set(self, active: bool) -> None:
        coordinator = self.coordinator
        key = self.entity_description.key
        flag = (
            "charge_active"
            if key == "battery_charge_limit_active"
            else "discharge_active"
        )
        await async_write(
            coordinator,
            coordinator.client.set_storage_limits(
                coordinator.inverter,
                revert_seconds=coordinator.revert_seconds,
                **{flag: active},
            ),
            {key: active},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class FroniusGridChargingSwitch(_FroniusSwitch):
    """Laden des Speichers aus dem Netz erlauben (ChaGriSet)."""

    async def _async_set(self, allowed: bool) -> None:
        coordinator = self.coordinator
        await async_write(
            coordinator,
            coordinator.client.set_grid_charging(coordinator.inverter, allowed),
            {self.entity_description.key: allowed},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
