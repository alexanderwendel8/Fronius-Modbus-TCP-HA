"""Basisklasse für alle Entitäten der Integration."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, TypeVar

from collections.abc import Awaitable

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import FroniusModbusError
from .const import DOMAIN, MANUFACTURER
from .coordinator import FroniusCoordinator

_LOGGER = logging.getLogger(__name__)

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


_EntityT = TypeVar("_EntityT", bound=FroniusEntity)


def drop_unsupported(
    hass: HomeAssistant,
    coordinator: FroniusCoordinator,
    platform: str,
    entities: Sequence[_EntityT],
) -> list[_EntityT]:
    """Entitäten weglassen, deren Wert das Gerät als "nicht unterstützt" meldet.

    Betrifft nur Beschreibungen mit skip_if_unsupported=True, und nur wenn der
    Wert gelesen wurde (Schlüssel vorhanden) und None ist – fehlt der Schlüssel,
    ist das Lesen fehlgeschlagen (z. B. Smart Meter antwortet nicht) und die
    Entität bleibt erhalten.

    Eine Entität, die für diesen Eintrag schon einmal angelegt wurde, hat früher
    einen Wert geliefert. Fehlt er jetzt, ist das vorübergehend (Nacht, Neustart
    des Geräts): Sie wird weiter angelegt und zeigt "unbekannt", damit Name,
    Entitäts-ID und Einstellungen des Nutzers nicht verloren gehen. Verwaiste
    Registry-Einträge ohne Bezug zu diesem Eintrag werden entfernt.
    """
    values = coordinator.data.values if coordinator.data else {}
    registry = er.async_get(hass)
    kept: list[_EntityT] = []
    for entity in entities:
        desc = entity.entity_description
        key = desc.key
        if getattr(desc, "skip_if_unsupported", False) and key in values and values[key] is None:
            entity_id = registry.async_get_entity_id(
                platform, DOMAIN, entity.unique_id or ""
            )
            known = entity_id is not None and (
                (reg_entry := registry.async_get(entity_id)) is not None
                and reg_entry.config_entry_id == coordinator.config_entry.entry_id
            )
            if not known:
                _LOGGER.debug(
                    "%s %s nicht unterstützt, wird nicht angelegt", platform, key
                )
                if entity_id:
                    registry.async_remove(entity_id)
                continue
            _LOGGER.debug(
                "%s %s liefert gerade keinen Wert, bleibt erhalten", platform, key
            )
        kept.append(entity)
    return kept


# Anzeige-Entitäten, die bei erlaubter Steuerung durch schaltbare ersetzt werden
REPLACED_BY_CONTROLS: dict[str, set[str]] = {
    "sensor": {"power_limit"},
    "binary_sensor": {"power_limit_active", "feed_in_enabled"},
}


def remove_replaced(
    hass: HomeAssistant, coordinator: FroniusCoordinator, platform: str
) -> set[str]:
    """Registry-Einträge der ersetzten Anzeige-Entitäten entfernen.

    Gibt die Schlüssel zurück, die die Plattform nicht anlegen soll.
    """
    if not coordinator.control_allowed:
        return set()
    keys = REPLACED_BY_CONTROLS.get(platform, set())
    registry = er.async_get(hass)
    for key in keys:
        unique_id = f"{inverter_device_id(coordinator)}_{key}"
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, unique_id):
            registry.async_remove(entity_id)
    return keys


async def async_write(
    coordinator: FroniusCoordinator,
    action: Awaitable[None],
    written: dict[str, Any] | None = None,
) -> None:
    """Schreibvorgang ausführen, Fehler verständlich melden, Werte neu lesen.

    `written`: geschriebene Werte, die sofort angezeigt werden – sonst springt
    ein Schalter bis zur nächsten (gebündelten) Abfrage auf den alten Zustand.
    """
    try:
        await action
    except (FroniusModbusError, ValueError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="write_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    if written and coordinator.data is not None:
        coordinator.data.values.update(written)
        coordinator.async_update_listeners()
    await coordinator.async_request_refresh()
