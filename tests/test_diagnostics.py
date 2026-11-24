"""Tests für den Diagnose-Download."""

from __future__ import annotations

import json

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fronius_modbus_tcp.const import (
    CONF_ALLOW_CONTROL,
    CONF_EXTRA_METER_UNIT_IDS,
    CONF_METER_UNIT_ID,
    CONF_UNIT_ID,
    DOMAIN,
)
from custom_components.fronius_modbus_tcp.diagnostics import (
    async_get_config_entry_diagnostics,
)

from . import simulator as sim


def _entry(port: int, serial: str, **data) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=serial,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: port, CONF_UNIT_ID: 1, **data},
        options={CONF_ALLOW_CONTROL: True},
    )


async def test_diagnostics_gen24(hass: HomeAssistant, socket_enabled) -> None:
    """Rohregister aller Modelle, Optionen und Zähler; Seriennummern und Host fehlen."""
    server = sim.FroniusSimulator(
        {
            1: sim.gen24_plus_float(),
            200: sim.meter_213(),
            201: sim.meter_213(serial="M0000002"),
        }
    )
    await server.start()
    try:
        entry = _entry(
            server.port,
            "33333333",
            **{CONF_METER_UNIT_ID: 200, CONF_EXTRA_METER_UNIT_IDS: [201]},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diag = await async_get_config_entry_diagnostics(hass, entry)
        text = json.dumps(diag)  # muss serialisierbar sein
        for secret in ("33333333", "M0000001", "M0000002", "127.0.0.1"):
            assert secret not in text, secret
        # Seriennummer steckt auch nicht hex-kodiert in den Rohregistern
        assert "33333333".encode().hex().upper() not in text

        assert diag["options"] == {CONF_ALLOW_CONTROL: True}
        assert diag["scan_interval"] == 10
        assert diag["pymodbus"]
        assert len(diag["extra_meters"]) == 1

        raw = diag["raw_registers"]
        inverter = entry.runtime_data.inverter
        assert set(raw["inverter"]) == {str(m) for m in inverter.models}
        for model_id, (start, length) in inverter.models.items():
            dump = raw["inverter"][str(model_id)]
            assert dump["start"] == start and dump["length"] == length
            assert len(dump["registers"]) == 4 * length
        assert "fronius_registers" not in raw  # GEN24
        assert set(raw["meters"]) == {"200", "201"}
        assert "213" in raw["meters"]["201"]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_diagnostics_datamanager(hass: HomeAssistant, socket_enabled) -> None:
    """Datamanager: zusätzlich die Fronius-Register 212–216 und 500–513."""
    server = sim.FroniusSimulator(
        {1: (sim.datamanager_hybrid_int(), sim.fronius_registers(state_code=306))}
    )
    await server.start()
    try:
        entry = _entry(server.port, "44444444", **{CONF_METER_UNIT_ID: None})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diag = await async_get_config_entry_diagnostics(hass, entry)
        fronius = diag["raw_registers"]["fronius_registers"]
        # Register 212–216: F_Delete_Data, F_Store_Data, State Code 306, Reset, ModelType
        assert fronius["212-216"] == "00000000013200000001"
        assert len(fronius["500-513"]) == 4 * 14
        assert diag["raw_registers"]["meters"] == {}
        assert diag["meter"] is None

        # Ein nicht lesbares Modell wird vermerkt, der Rest bleibt
        inverter = entry.runtime_data.inverter
        inverter.models[999] = (30000, 4)
        diag = await async_get_config_entry_diagnostics(hass, entry)
        assert "error" in diag["raw_registers"]["inverter"]["999"]
        assert "registers" in diag["raw_registers"]["inverter"]["103"]
        del inverter.models[999]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()
