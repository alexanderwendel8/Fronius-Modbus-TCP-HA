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
    assert float(s("33333333_pv_current").state) == 8.1
    # Mehrere DC-Eingänge: DCA/DCV vom Gerät nicht unterstützt → keine Sensoren
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "33333333_dc_current") is None
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "33333333_dc_voltage") is None
    assert float(s("33333333_dc_power").state) == 3400.0

    # Modell 120: Nennleistung und Batteriekapazität
    assert float(s("33333333_rated_power").state) == 10000
    assert float(s("33333333_battery_capacity").state) == pytest.approx(10.24)

    # Modell 123: aktive Drosselung als Sensor und Binärsensoren
    assert float(s("33333333_power_limit").state) == 70.0
    limit_active = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, "33333333_power_limit_active"
    )
    feed_in = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "33333333_feed_in_enabled")
    assert hass.states.get(limit_active).state == "on"

    # EvtVnd1 (GEN24): Warnung aktiv, kein Fehler
    warning = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "33333333_warning_active")
    error = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "33333333_error_active")
    assert hass.states.get(warning).state == "on"
    assert hass.states.get(error).state == "off"
    assert hass.states.get(feed_in).state == "on"
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


async def test_setup_errors_are_logged(hass: HomeAssistant, gen24, caplog) -> None:
    """Fehler beim Einrichten landen mit Host, Port, Unit-ID und Ursache im Log."""
    caplog.set_level("INFO", logger="custom_components.fronius_modbus_tcp")

    # Falsche Unit-ID: Gerät antwortet, liefert aber keine Wechselrichterdaten
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: gen24.port, CONF_UNIT_ID: 7, CONF_METER_UNIT_ID: 0},
    )
    assert result["errors"] == {"base": "not_sunspec"}
    assert f"127.0.0.1:{gen24.port} (Unit-ID 7)" in caplog.text
    assert "keine SunSpec-Wechselrichterdaten" in caplog.text

    # Smart Meter unter angegebener Adresse nicht vorhanden
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: gen24.port, CONF_UNIT_ID: 1, CONF_METER_UNIT_ID: 201},
    )
    assert result["errors"] == {CONF_METER_UNIT_ID: "meter_not_found"}
    assert "kein Smart Meter unter Unit-ID 201" in caplog.text
    assert "Symo GEN24 10.0 Plus erkannt" in caplog.text

    # Keine Verbindung
    port = sim.free_port()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: port, CONF_UNIT_ID: 1}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert f"127.0.0.1:{port} (Unit-ID 1): keine Verbindung" in caplog.text


async def test_single_dc_input_keeps_dc_sensors(hass: HomeAssistant, socket_enabled) -> None:
    """Nur ein DC-Eingang: DC-Strom und DC-Spannung kommen aus dem Inverter-Model."""
    server = sim.FroniusSimulator({1: sim.single_mppt_float()})
    await server.start()
    try:
        entry = await _setup(hass, server.port, **{CONF_METER_UNIT_ID: 0})
        ent_reg = er.async_get(hass)
        assert float(_state(hass, ent_reg, "66666666_dc_current").state) == 8.2
        assert float(_state(hass, ent_reg, "66666666_dc_voltage").state) == 410.0
        assert float(_state(hass, ent_reg, "66666666_pv_current").state) == 8.2
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_unsupported_sensors_not_created(hass: HomeAssistant, gen24) -> None:
    """Vom Gerät als "nicht unterstützt" gemeldete Werte → kein Sensor, alte Einträge weg."""
    ent_reg = er.async_get(hass)
    # Eintrag aus einer älteren Version vorhanden
    stale = ent_reg.async_get_or_create(
        "sensor", DOMAIN, "33333333_temperature_heatsink"
    )

    entry = await _setup(hass, gen24.port)
    uids = {
        e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    # Simulator: TmpCab = 41 °C, TmpSnk/TmpTrns/TmpOt = NaN
    assert "33333333_temperature_cabinet" in uids
    assert "33333333_temperature_heatsink" not in uids
    assert "33333333_temperature_transformer" not in uids
    assert "33333333_temperature_other" not in uids
    assert ent_reg.async_get(stale.entity_id) is None
    # Unterstützte optionale Werte bleiben
    assert "33333333_mppt_1_dc_energy" in uids
    assert "meter_M0000001_meter_energy_import_a" in uids
    # Kernwerte sind nie betroffen
    assert "33333333_ac_power" in uids

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_hybrid_unused_energy_not_created(hass: HomeAssistant, socket_enabled) -> None:
    """Symo Hybrid: DCWH nicht unterstützt (0) → kein Energiesensor für den String."""
    server = sim.FroniusSimulator({1: sim.datamanager_hybrid_int()})
    await server.start()
    try:
        entry = await _setup(hass, server.port, **{CONF_METER_UNIT_ID: 0})
        ent_reg = er.async_get(hass)
        uids = {
            e.unique_id
            for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        }
        assert "44444444_mppt_1_dc_power" in uids
        assert "44444444_mppt_1_dc_energy" not in uids
        # Ohne Fronius-Register keine Anlagensummen
        assert "44444444_site_energy_day" not in uids
        # Nennwerte: WRtg vorhanden, ARtg und Batteriekapazität nicht unterstützt
        assert "44444444_rated_power" in uids
        assert "44444444_rated_current" not in uids
        assert "44444444_battery_capacity" not in uids
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_datamanager_site_totals(hass: HomeAssistant, socket_enabled) -> None:
    """Datamanager: Anlagenleistung und Tages-/Jahres-/Gesamtenergie als Sensoren."""
    server = sim.FroniusSimulator(
        {
            1: (
                sim.datamanager_hybrid_int(evt_vnd=(0x20, 0x4, 0, 0)),
                sim.fronius_registers(day=12_345, state_code=306),
            )
        }
    )
    await server.start()
    try:
        entry = await _setup(hass, server.port, **{CONF_METER_UNIT_ID: 0})
        ent_reg = er.async_get(hass)
        s = lambda uid: _state(hass, ent_reg, uid)  # noqa: E731
        assert float(s("44444444_site_power").state) == 2000
        assert float(s("44444444_site_energy_day").state) == pytest.approx(12.345)
        assert float(s("44444444_site_energy_year").state) == pytest.approx(1234.567)
        assert float(s("44444444_site_energy_total").state) == pytest.approx(9330.29)
        # Symo Hybrid → Symo-Tabelle
        assert s("44444444_state_code").state == "306"
        assert s("44444444_state_message").state == "Power Low"
        # Fehlerklassen aus EvtVnd1-4 (Symo-Tabelle)
        assert s("44444444_vendor_events").state == "Power low; 24h no feed in"
        error = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "44444444_error_active")
        assert hass.states.get(error).state == "on"
        # Warnungen gibt es nur beim GEN24
        assert ent_reg.async_get_entity_id(
            "binary_sensor", DOMAIN, "44444444_warning_active"
        ) is None
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()
