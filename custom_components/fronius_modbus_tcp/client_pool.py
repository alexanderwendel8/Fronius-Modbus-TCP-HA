"""Gemeinsame Modbus-Verbindung je Gerät (Host und Port).

Mehrere Wechselrichter an einem Datamanager werden als eigene Config-Einträge
eingerichtet, hängen aber am selben Modbus-TCP-Server. Fronius verlangt, dass
Abfragen nacheinander laufen. Alle Einträge desselben Geräts teilen sich deshalb
einen Client – und damit eine TCP-Verbindung und einen Lock.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant, callback

from .api import FroniusModbusClient
from .const import DOMAIN

_DATA_KEY = f"{DOMAIN}_clients"


@dataclass
class _SharedClient:
    client: FroniusModbusClient
    users: int = 0


def _key(host: str, port: int) -> tuple[str, int]:
    return (host.strip().lower(), port)


def _pool(hass: HomeAssistant) -> dict[tuple[str, int], _SharedClient]:
    return hass.data.setdefault(_DATA_KEY, {})


@callback
def async_acquire_client(hass: HomeAssistant, host: str, port: int) -> FroniusModbusClient:
    """Client für Host/Port holen; jeder Aufruf braucht ein async_release_client."""
    pool = _pool(hass)
    shared = pool.get(_key(host, port))
    if shared is None:
        shared = pool[_key(host, port)] = _SharedClient(FroniusModbusClient(host, port))
    shared.users += 1
    return shared.client


async def async_release_client(hass: HomeAssistant, host: str, port: int) -> None:
    """Client freigeben; die Verbindung schließt, wenn ihn niemand mehr nutzt."""
    pool = _pool(hass)
    shared = pool.get(_key(host, port))
    if shared is None:
        return
    shared.users -= 1
    if shared.users <= 0:
        del pool[_key(host, port)]
        await shared.client.close()
