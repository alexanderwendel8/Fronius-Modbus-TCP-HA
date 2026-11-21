"""Basisklasse für alle Entitäten der Integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FroniusCoordinator


class FroniusEntity(CoordinatorEntity[FroniusCoordinator]):
    """Gemeinsame Geräte-Zuordnung und Namensgebung."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FroniusCoordinator, key: str) -> None:
        super().__init__(coordinator)
        info = coordinator.device_info
        device_id = info.serial_number or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=info.manufacturer or MANUFACTURER,
            model=info.model or None,
            sw_version=info.version or None,
            serial_number=info.serial_number or None,
        )
