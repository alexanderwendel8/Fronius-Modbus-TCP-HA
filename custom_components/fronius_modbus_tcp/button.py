"""Button-Plattform: Ereignisse zurücksetzen (Datamanager, nur mit "Steuerung erlauben")."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FroniusConfigEntry, FroniusCoordinator
from .entity import FroniusEntity, async_write

PARALLEL_UPDATES = 1

RESET_EVENTS = ButtonEntityDescription(
    key="reset_events",
    translation_key="reset_events",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.control_allowed and coordinator.inverter.has_site_registers:
        async_add_entities([FroniusResetEventsButton(coordinator, RESET_EVENTS)])


class FroniusResetEventsButton(FroniusEntity, ButtonEntity):
    """Event Flags und State Code löschen (F_Reset_All_Event_Flags = 0xFFFF).

    Laut Handbuch bleiben einzelne Event Flags teils stehen, obwohl der Zustand
    am Wechselrichter nicht mehr anliegt.
    """

    def __init__(
        self, coordinator: FroniusCoordinator, description: ButtonEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        coordinator = self.coordinator
        await async_write(coordinator, coordinator.client.reset_events(coordinator.inverter))
