"""End-to-End-Tests: Einrichtungsdialog und Setup in Home Assistant."""

from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.fronius_modbus_tcp.const import (
    CONF_METER_UNIT_ID,
    CONF_UNIT_ID,
    DOMAIN,
)

from . import simulator as sim


@pytest.fixture
async def gen24(socket_enabled):
    server = sim.FroniusSimulator({1: sim.gen24_plus_float(), 200: sim.meter_213()})
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def gen24_plain(socket_enabled):
    server = sim.FroniusSimulator({1: sim.gen24_float_no_battery()})
    await server.start()
    yield server
    await server.stop()


async def _setup(hass: HomeAssistant, port: int, **extra) -> config_entries.ConfigEntry:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: port, CONF_UNIT_ID: 1, **extra},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    await hass.async_block_till_done()
    return result["result"]


def _state(hass: HomeAssistant, entity_registry, unique_id: str):
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id, unique_id
    return hass.states.get(entity_id)


async def test_gen24_plus_with_meter(hass: HomeAssistant, gen24) -> None:
    entry = await _setup(hass, gen24.port)
    assert entry.title == "Fronius Symo GEN24 10.0 Plus"
    assert entry.unique_id == "33333333"
    assert entry.data[CONF_METER_UNIT_ID] == 200  # automatisch gefunden

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    s = lambda uid: _state(hass, ent_reg, uid)  # noqa: E731

    assert float(s("33333333_ac_power").state) == 3333.3
    assert float(s("33333333_pv_power").state) == 3270
    assert float(s("33333333_mppt_1_dc_power").state) == 1680
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "33333333_mppt_3_dc_power") is None
    assert float(s("33333333_battery_power").state) == 1440
    assert float(s("33333333_battery_soc").state) == 54.2
    assert s("33333333_battery_state").state == "charging"
    # Energie wird in kWh angezeigt
    assert float(s("33333333_battery_charge_energy").state) == pytest.approx(111.111)

    meter_power = s("meter_M0000001_meter_power")
    assert float(meter_power.state) == -1500.0
    assert float(s("meter_M0000001_meter_energy_import").state) == pytest.approx(3000.0)

    inverter_dev = dev_reg.async_get_device({(DOMAIN, "33333333")})
    meter_dev = dev_reg.async_get_device({(DOMAIN, "meter_M0000001")})
    assert inverter_dev and meter_dev
    assert meter_dev.via_device_id == inverter_dev.id
    assert meter_dev.name == "Smart Meter TS 65A-3"

    # Gerät darf nicht doppelt eingerichtet werden
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: gen24.port, CONF_UNIT_ID: 1}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_meter_disabled(hass: HomeAssistant, gen24) -> None:
    entry = await _setup(hass, gen24.port, **{CONF_METER_UNIT_ID: 0})
    assert entry.data[CONF_METER_UNIT_ID] is None
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "meter_M0000001_meter_power") is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_meter_not_found(hass: HomeAssistant, gen24) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: gen24.port, CONF_UNIT_ID: 1, CONF_METER_UNIT_ID: 201},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_METER_UNIT_ID: "meter_not_found"}


async def test_gen24_without_battery(hass: HomeAssistant, gen24_plain) -> None:
    entry = await _setup(hass, gen24_plain.port)
    assert entry.data[CONF_METER_UNIT_ID] is None
    ent_reg = er.async_get(hass)
    uids = {
        e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    assert "55555555_pv_power" in uids
    assert not any("battery" in uid for uid in uids)
    # Einphasig: keine Sensoren für L2/L3
    assert "55555555_ac_voltage_bn" not in uids
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_cannot_connect(hass: HomeAssistant, socket_enabled) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: sim.free_port(), CONF_UNIT_ID: 1},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_second_inverter_same_host_gets_no_meter(hass: HomeAssistant, socket_enabled) -> None:
    """Datamanager mit zwei Wechselrichtern: Zähler nur beim ersten Eintrag."""
    server = sim.FroniusSimulator(
        {1: sim.datamanager_hybrid_int(), 2: sim.gen24_float_no_battery(), 240: sim.meter_203()}
    )
    await server.start()
    try:
        first = await _setup(hass, server.port)
        assert first.data[CONF_METER_UNIT_ID] == 240
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "127.0.0.1", CONF_PORT: server.port, CONF_UNIT_ID: 2},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data[CONF_METER_UNIT_ID] is None
        await hass.async_block_till_done()
        for entry in hass.config_entries.async_entries(DOMAIN):
            assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()
