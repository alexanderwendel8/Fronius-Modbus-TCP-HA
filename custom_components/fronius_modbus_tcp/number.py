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

from .const import MAX_REVERT_SECONDS, MIN_REVERT_SECONDS
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


def _storage_limit(key: str) -> NumberEntityDescription:
    return NumberEntityDescription(
        key=key,
        translation_key=key,
        native_min_value=-100,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
    )


BATTERY_CHARGE_LIMIT = _storage_limit("battery_charge_limit")
BATTERY_DISCHARGE_LIMIT = _storage_limit("battery_discharge_limit")
BATTERY_MIN_RESERVE = NumberEntityDescription(
    key="battery_min_reserve",
    translation_key="battery_min_reserve",
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    if coordinator.control_allowed:
        entities += [
            FroniusPowerLimitNumber(coordinator, POWER_LIMIT),
            FroniusRevertTimeNumber(coordinator, REVERT_TIME),
        ]
    if coordinator.storage_control_allowed:
        entities += [
            FroniusStorageLimitNumber(coordinator, BATTERY_CHARGE_LIMIT),
            FroniusStorageLimitNumber(coordinator, BATTERY_DISCHARGE_LIMIT),
            FroniusMinReserveNumber(coordinator, BATTERY_MIN_RESERVE),
        ]
        if not coordinator.control_allowed:
            # Rückfallzeit gilt auch für das Leistungsfenster des Speichers
            entities.append(FroniusRevertTimeNumber(coordinator, REVERT_TIME))
    async_add_entities(entities)


class _FroniusValueNumber(FroniusEntity, NumberEntity):
    """Number, deren Wert unter ihrem Schlüssel in den gelesenen Daten steht."""

    def __init__(
        self, coordinator: FroniusCoordinator, description: NumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.values.get(self.entity_description.key)


class FroniusStorageLimitNumber(_FroniusValueNumber):
    """Lade- bzw. Entladegrenze des Speichers in % von WChaMax (InWRte / OutWRte).

    Wirkt nur, solange der zugehörige Schalter "Grenze aktiv" eingeschaltet ist.
    Negative Werte erzwingen die Gegenrichtung: Entladegrenze −50 % heißt
    "mit mindestens 50 % laden" (Handbuch, Beispiele Leistungsfenster).
    """

    async def async_set_native_value(self, value: float) -> None:
        coordinator = self.coordinator
        key = self.entity_description.key
        limits = {
            "charge_limit" if key == "battery_charge_limit" else "discharge_limit": value
        }
        await async_write(
            coordinator,
            coordinator.client.set_storage_limits(
                coordinator.inverter,
                revert_seconds=coordinator.revert_seconds,
                **limits,
            ),
            {key: value},
        )


class FroniusMinReserveNumber(_FroniusValueNumber):
    """Mindestreserve des Speichers in % (MinRsvPct)."""

    async def async_set_native_value(self, value: float) -> None:
        coordinator = self.coordinator
        await async_write(
            coordinator,
            coordinator.client.set_min_reserve(coordinator.inverter, value),
            {self.entity_description.key: value},
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
    """Rückfallzeit für Vorgaben (RvrtTms). Wird lokal gespeichert und bei einer
    Änderung an gerade aktive Vorgaben übertragen.

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
            # ein längeres Abfrageintervall kann den Mindestwert angehoben haben
            self.coordinator.revert_seconds = max(
                int(last.native_value), self.coordinator.min_revert_seconds
            )

    @property
    def available(self) -> bool:
        return True

    @property
    def native_min_value(self) -> float:
        return self.coordinator.min_revert_seconds

    @property
    def native_value(self) -> float:
        return self.coordinator.revert_seconds

    async def async_set_native_value(self, value: float) -> None:
        coordinator = self.coordinator
        coordinator.revert_seconds = max(int(value), coordinator.min_revert_seconds)
        self.async_write_ha_state()
        # laufende Vorgaben sofort mit der neuen Rückfallzeit versehen
        await async_write(coordinator, coordinator.async_apply_revert_time())
