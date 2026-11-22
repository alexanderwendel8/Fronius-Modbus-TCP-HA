"""Number-Plattform: Leistungsbegrenzung und Rückfallzeit (nur mit "Steuerung erlauben")."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_REVERT_SECONDS, MAX_REVERT_SECONDS, MIN_REVERT_SECONDS
from .coordinator import FroniusConfigEntry, FroniusCoordinator
from .entity import FroniusEntity, async_write

PARALLEL_UPDATES = 1

POWER_LIMIT = NumberEntityDescription(
    key="power_limit",
    translation_key="power_limit",
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    mode=NumberMode.BOX,
)
REVERT_TIME = NumberEntityDescription(
    key="revert_time",
    translation_key="revert_time",
    device_class=NumberDeviceClass.DURATION,
    native_min_value=MIN_REVERT_SECONDS,
    native_max_value=MAX_REVERT_SECONDS,
    native_step=1,
    native_unit_of_measurement=UnitOfTime.SECONDS,
    mode=NumberMode.BOX,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.control_allowed:
        async_add_entities(
            [
                FroniusPowerLimitNumber(coordinator, POWER_LIMIT),
                FroniusRevertTimeNumber(coordinator, REVERT_TIME),
            ]
        )


class FroniusPowerLimitNumber(FroniusEntity, NumberEntity):
    """Leistungsbegrenzung in % der Nennleistung (WMaxLimPct).

    Ist die Begrenzung aktiv (Schalter), wirkt ein neuer Wert sofort; sonst wird
    er nur hinterlegt und beim Einschalten verwendet.
    """

    def __init__(
        self, coordinator: FroniusCoordinator, description: NumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.values.get("power_limit")

    async def async_set_native_value(self, value: float) -> None:
        coordinator = self.coordinator
        await async_write(
            coordinator,
            coordinator.client.set_power_limit(
                coordinator.inverter,
                value,
                enabled=coordinator.data.values.get("power_limit_active") is True,
                revert_seconds=coordinator.revert_seconds,
            ),
            {"power_limit": value},
        )


class FroniusRevertTimeNumber(FroniusEntity, RestoreNumber):
    """Rückfallzeit für Vorgaben (RvrtTms). Wird nur lokal gespeichert.

    Solange die Integration das Gerät abfragt, startet jede Abfrage den Timer
    neu; fällt Home Assistant aus, endet die Vorgabe nach dieser Zeit.
    """

    def __init__(
        self, coordinator: FroniusCoordinator, description: NumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) is not None and (
            last.native_value is not None
        ):
            self.coordinator.revert_seconds = int(last.native_value)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.revert_seconds

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.revert_seconds = int(value) or DEFAULT_REVERT_SECONDS
        self.async_write_ha_state()
