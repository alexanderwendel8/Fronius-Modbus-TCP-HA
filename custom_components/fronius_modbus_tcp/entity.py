"""Basisklasse für alle Entitäten der Integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FroniusCoordinator

DEVICE_INVERTER = "inverter"
DEVICE_METER = "meter"


def inverter_device_id(coordinator: FroniusCoordinator) -> str:
    return coordinator.inverter.serial_number or coordinator.config_entry.entry_id


def meter_device_id(coordinator: FroniusCoordinator) -> str:
    assert coordinator.meter is not None
    serial = coordinator.meter.serial_number
    return f"meter_{serial}" if serial else f"{coordinator.config_entry.entry_id}_meter"


class FroniusEntity(CoordinatorEntity[FroniusCoordinator]):
    """Gemeinsame Geräte-Zuordnung, Namensgebung und Verfügbarkeit."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FroniusCoordinator, key: str, device: str = DEVICE_INVERTER
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        inverter_id = inverter_device_id(coordinator)

        if device == DEVICE_METER:
            meter = coordinator.meter
            assert meter is not None
            device_id = meter_device_id(coordinator)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_id)},
                name=meter.model or "Smart Meter",
                manufacturer=meter.manufacturer or MANUFACTURER,
                model=meter.model or None,
                sw_version=meter.version or None,
                serial_number=meter.serial_number or None,
                via_device=(DOMAIN, inverter_id),
            )
        else:
            inverter = coordinator.inverter
            device_id = inverter_id
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_id)},
                name=inverter.model or "Fronius Wechselrichter",
                manufacturer=inverter.manufacturer or MANUFACTURER,
                model=inverter.model or None,
                sw_version=inverter.version or None,
                serial_number=inverter.serial_number or None,
            )
        self._attr_unique_id = f"{device_id}_{key}"

    @property
    def available(self) -> bool:
        # Fehlt der Schlüssel (z. B. Smart Meter antwortet nicht) → nicht verfügbar
        return (
            super().available
            and self.coordinator.data is not None
            and self._key in self.coordinator.data.values
        )
