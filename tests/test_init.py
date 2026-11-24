"""End-to-End-Tests: Einrichtungsdialog und Setup in Home Assistant."""

from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.fronius_modbus_tcp.const import (
    CONF_ALLOW_CONTROL,
    CONF_EXTRA_METER_UNIT_IDS,
    CONF_METER_UNIT_ID,
    CONF_SCAN_INTERVAL,
    CONF_SITE_REGISTERS,
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
    assert entry.data[CONF_SITE_REGISTERS] is False  # GEN24, dauerhaft gemerkt

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

    # Modell 122: genaue Gesamtenergie (kWh) und Isolationswiderstand
    assert float(s("33333333_ac_energy_lifetime").state) == pytest.approx(12345.679)
    assert float(s("33333333_isolation_resistance").state) == 1_500_000

    # Evt1 im Klartext
    assert s("33333333_event_message").state == "Over temperature; AC voltage above limit"

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


async def test_meter_found_later(hass: HomeAssistant, gen24, caplog) -> None:
    """Zähler antwortet beim Start nicht → spätere Suche findet ihn, Entitäten erscheinen."""
    from unittest.mock import patch

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.fronius_modbus_tcp.api import (
        FroniusModbusClient,
        FroniusModbusError,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="33333333",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: gen24.port,
            CONF_UNIT_ID: 1,
            CONF_METER_UNIT_ID: 200,
        },
    )
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    uid = "meter_M0000001_meter_power"

    with patch.object(
        FroniusModbusClient,
        "read_meter_info",
        side_effect=FroniusModbusError("keine Antwort"),
    ) as probe:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert "Die Suche wird alle 5 Minuten wiederholt" in caplog.text
        assert not ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
        coordinator = entry.runtime_data

        # Vor Ablauf des Intervalls wird nicht erneut gesucht
        await coordinator.async_refresh()
        assert probe.call_count == 1

        # Intervall abgelaufen: erste Wiederholung erfolglos
        coordinator._meter_next_retry = dt_util.utcnow()
        await coordinator.async_refresh()
        assert probe.call_count == 2
        assert not ent_reg.async_get_entity_id("sensor", DOMAIN, uid)

    # Zähler antwortet wieder → Eintrag lädt neu, Zähler-Entitäten erscheinen
    coordinator._meter_next_retry = dt_util.utcnow()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert "Eintrag wird neu geladen" in caplog.text
    state = _state(hass, ent_reg, uid)
    assert state is not None and state.state not in ("unknown", "unavailable")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


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


async def test_known_sensor_survives_missing_value(
    hass: HomeAssistant, gen24, socket_enabled
) -> None:
    """Früher gelieferter Wert fehlt beim Neustart → Sensor und Einstellungen bleiben."""
    import struct

    ent_reg = er.async_get(hass)
    entry = await _setup(hass, gen24.port)
    uid = "33333333_temperature_cabinet"
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
    assert entity_id
    ent_reg.async_update_entity(entity_id, name="Schaltschrank")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Gleiches Gerät, TmpCab jetzt NaN (z. B. nachts)
    regs = sim.gen24_plus_float()
    hi, lo = struct.unpack(">HH", struct.pack(">f", 41.0))
    nan = list(struct.unpack(">HH", struct.pack(">f", sim.NAN)))
    (pos,) = [i for i in range(len(regs) - 1) if regs[i : i + 2] == [hi, lo]]
    regs[pos : pos + 2] = nan
    server = sim.FroniusSimulator({1: regs, 200: sim.meter_213()})
    await server.start()
    try:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_PORT: server.port}
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert ent_reg.async_get_entity_id("sensor", DOMAIN, uid) == entity_id
        assert ent_reg.async_get(entity_id).name == "Schaltschrank"
        # Nie gelieferte Werte werden weiterhin nicht angelegt
        assert not ent_reg.async_get_entity_id(
            "sensor", DOMAIN, "33333333_temperature_heatsink"
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


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
        # Modell 122 nicht unterstützt → keine Sensoren
        assert "44444444_ac_energy_lifetime" not in uids
        assert "44444444_isolation_resistance" not in uids
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


# --- Steuerung (Option "Steuerung erlauben") -----------------------------------


async def _enable_control(hass: HomeAssistant, entry) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALLOW_CONTROL: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_control_disabled_by_default(hass: HomeAssistant, gen24) -> None:
    entry = await _setup(hass, gen24.port, **{CONF_METER_UNIT_ID: 0})
    ent_reg = er.async_get(hass)
    domains = {e.domain for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)}
    assert domains == {"sensor", "binary_sensor"}
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_control_entities(hass: HomeAssistant, gen24) -> None:
    entry = await _setup(hass, gen24.port, **{CONF_METER_UNIT_ID: 0})
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "33333333_power_limit")

    await _enable_control(hass, entry)
    eid = lambda domain, key: ent_reg.async_get_entity_id(domain, DOMAIN, f"33333333_{key}")  # noqa: E731

    # Anzeige-Entitäten durch schaltbare ersetzt
    assert eid("sensor", "power_limit") is None
    assert eid("binary_sensor", "power_limit_active") is None
    assert eid("binary_sensor", "feed_in_enabled") is None
    number, revert = eid("number", "power_limit"), eid("number", "revert_time")
    limit_switch, feed_in = eid("switch", "power_limit_active"), eid("switch", "feed_in_enabled")
    assert hass.states.get(number).state == "70.0"
    assert hass.states.get(limit_switch).state == "on"
    assert hass.states.get(feed_in).state == "on"
    assert hass.states.get(revert).state == "300"
    # GEN24: kein Button "Ereignisse zurücksetzen"
    assert eid("button", "reset_events") is None

    # Rückfallzeit ändern, dann Leistungsbegrenzung auf 40 %
    await hass.services.async_call(
        "number", "set_value", {"entity_id": revert, "value": 900}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": 40}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(number).state == "40.0"
    coordinator = entry.runtime_data
    start = coordinator.inverter.models[123][0]
    assert await coordinator.client.read(1, start + 3, 5) == [4000, 0, 900, 0, 1]

    # Begrenzung aus, Standby ein
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": limit_switch}, blocking=True
    )
    await hass.services.async_call("switch", "turn_off", {"entity_id": feed_in}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(limit_switch).state == "off"
    assert hass.states.get(feed_in).state == "off"
    assert await coordinator.client.read(1, start, 3) == [0, 900, 0]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reset_events_button(hass: HomeAssistant, socket_enabled) -> None:
    server = sim.FroniusSimulator(
        {1: (sim.datamanager_hybrid_int(), sim.fronius_registers(state_code=306))}
    )
    await server.start()
    try:
        entry = await _setup(hass, server.port, **{CONF_METER_UNIT_ID: 0})
        await _enable_control(hass, entry)
        ent_reg = er.async_get(hass)
        button = ent_reg.async_get_entity_id("button", DOMAIN, "44444444_reset_events")
        assert button
        await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
        assert await entry.runtime_data.client.read(1, 214, 1) == [0xFFFF]
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_power_low_is_no_error(hass: HomeAssistant, socket_enabled) -> None:
    """Datamanager am Abend: State Code 306 "Power Low" löst keinen Fehler aus."""
    server = sim.FroniusSimulator(
        {
            1: (
                sim.datamanager_hybrid_int(evt_vnd=(0x20, 0, 0, 0)),
                sim.fronius_registers(state_code=306),
            )
        }
    )
    await server.start()
    try:
        entry = await _setup(hass, server.port, **{CONF_METER_UNIT_ID: 0})
        ent_reg = er.async_get(hass)
        s = lambda uid: _state(hass, ent_reg, uid)  # noqa: E731
        assert s("44444444_state_message").state == "Power Low"
        assert s("44444444_vendor_events").state == "Power low"
        error = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, "44444444_error_active")
        assert hass.states.get(error).state == "off"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_site_registers_stored_for_old_entry(
    hass: HomeAssistant, socket_enabled
) -> None:
    """Eintrag ohne gespeicherten Gerätetyp: Ergebnis wird nachgetragen und danach nicht mehr geprüft."""
    from unittest.mock import patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.fronius_modbus_tcp.api import (
        FroniusModbusClient,
        FroniusModbusError,
    )

    server = sim.FroniusSimulator(
        {1: (sim.datamanager_hybrid_int(), sim.fronius_registers())}
    )
    await server.start()
    try:
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="44444444",
            data={
                CONF_HOST: "127.0.0.1",
                CONF_PORT: server.port,
                CONF_UNIT_ID: 1,
                CONF_METER_UNIT_ID: None,
            },
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.data[CONF_SITE_REGISTERS] is True
        ent_reg = er.async_get(hass)
        assert ent_reg.async_get_entity_id("sensor", DOMAIN, "44444444_site_power")

        # Neustart: Probe würde fehlschlagen, wird aber nicht mehr ausgeführt
        with patch.object(
            FroniusModbusClient,
            "_probe_site_registers",
            side_effect=FroniusModbusError("darf nicht aufgerufen werden"),
        ) as probe:
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert probe.call_count == 0
        assert entry.runtime_data.inverter.has_site_registers
        assert _state(hass, ent_reg, "44444444_site_power") is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_entries_on_same_host_share_connection(
    hass: HomeAssistant, socket_enabled
) -> None:
    """Zwei Wechselrichter am selben Datamanager teilen sich Client und Verbindung."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.fronius_modbus_tcp.client_pool import _pool

    def _device(serial: str) -> tuple[list[int], dict[int, int]]:
        regs = sim.datamanager_hybrid_int()
        old = sim.s("44444444", 16)
        (pos,) = [i for i in range(len(regs) - 15) if regs[i : i + 16] == old]
        regs[pos : pos + 16] = sim.s(serial, 16)
        return regs, sim.fronius_registers()

    server = sim.FroniusSimulator({1: _device("44444444"), 2: _device("55555555")})
    other = sim.FroniusSimulator({1: sim.gen24_float_no_battery()})
    await server.start()
    await other.start()
    try:
        entries = []
        for unit, serial, port in (
            (1, "44444444", server.port),
            (2, "55555555", server.port),
            (1, "other", other.port),
        ):
            entry = MockConfigEntry(
                domain=DOMAIN,
                unique_id=serial,
                data={
                    CONF_HOST: "127.0.0.1",
                    CONF_PORT: port,
                    CONF_UNIT_ID: unit,
                    CONF_METER_UNIT_ID: None,
                },
            )
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
            entries.append(entry)
        await hass.async_block_till_done()
        first, second, third = entries

        client = first.runtime_data.client
        assert second.runtime_data.client is client
        assert third.runtime_data.client is not client  # anderes Gerät
        assert len(_pool(hass)) == 2

        # Ein Eintrag wird entladen: Verbindung bleibt für den anderen bestehen
        assert await hass.config_entries.async_unload(first.entry_id)
        await hass.async_block_till_done()
        assert client._client.connected
        await second.runtime_data.async_refresh()
        assert second.runtime_data.last_update_success

        # Letzter Nutzer weg → Verbindung geschlossen, Pool leer
        assert await hass.config_entries.async_unload(second.entry_id)
        assert await hass.config_entries.async_unload(third.entry_id)
        await hass.async_block_till_done()
        assert not client._client.connected
        assert _pool(hass) == {}
    finally:
        await server.stop()
        await other.stop()


async def test_reconfigure(hass: HomeAssistant, gen24, gen24_plain) -> None:
    """Verbindungsdaten ändern: gleiches Gerät an neuer Adresse, falsches Gerät, kein Gerät."""
    entry = await _setup(hass, gen24.port)
    assert entry.data[CONF_METER_UNIT_ID] == 200
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, "33333333_ac_power")

    async def _reconfigure(port: int, **extra):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "127.0.0.1", CONF_PORT: port, CONF_UNIT_ID: 1, **extra},
        )
        await hass.async_block_till_done()
        return result

    # Anderes Gerät (andere Seriennummer) unter der neuen Adresse → abgelehnt
    result = await _reconfigure(gen24_plain.port, **{CONF_METER_UNIT_ID: 0})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data[CONF_PORT] == gen24.port

    # Nichts erreichbar → Formular mit Fehler, Eintrag unverändert
    result = await _reconfigure(1, **{CONF_METER_UNIT_ID: 0})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_PORT] == gen24.port

    # Gleiches Gerät an neuer Adresse, Zähler abgewählt
    moved = sim.FroniusSimulator({1: sim.gen24_plus_float(), 200: sim.meter_213()})
    await moved.start()
    try:
        result = await _reconfigure(moved.port, **{CONF_METER_UNIT_ID: 0})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_PORT] == moved.port
        assert entry.data[CONF_METER_UNIT_ID] is None
        assert entry.data[CONF_SITE_REGISTERS] is False
        assert entry.unique_id == "33333333"
        # Entität bleibt dieselbe und liefert wieder Werte
        assert ent_reg.async_get_entity_id("sensor", DOMAIN, "33333333_ac_power") == entity_id
        assert hass.states.get(entity_id).state not in ("unknown", "unavailable")
        assert entry.runtime_data.meter is None

        # Zählerfeld leer → automatische Suche findet ihn wieder
        result = await _reconfigure(moved.port)
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_METER_UNIT_ID] == 200
        assert entry.runtime_data.meter is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await moved.stop()


async def test_storage_control_entities(hass: HomeAssistant, gen24, gen24_plain) -> None:
    """Speichersteuerung: Entitäten ersetzen die Anzeige-Sensoren und schreiben ins Gerät."""
    from homeassistant.exceptions import HomeAssistantError

    entry = await _setup(hass, gen24.port, **{CONF_METER_UNIT_ID: 0})
    ent_reg = er.async_get(hass)
    eid = lambda domain, key: ent_reg.async_get_entity_id(domain, DOMAIN, f"33333333_{key}")  # noqa: E731
    assert eid("sensor", "battery_min_reserve")
    assert eid("number", "battery_min_reserve") is None

    await _enable_control(hass, entry)
    for key in (
        "battery_charge_limit",
        "battery_discharge_limit",
        "battery_min_reserve",
        "battery_grid_charging",
    ):
        assert eid("sensor", key) is None, key
    # Status und Steuermodus bleiben als Sensoren
    assert eid("sensor", "battery_soc")
    charge, discharge = eid("number", "battery_charge_limit"), eid("number", "battery_discharge_limit")
    reserve = eid("number", "battery_min_reserve")
    discharge_on = eid("switch", "battery_discharge_limit_active")
    charge_on = eid("switch", "battery_charge_limit_active")
    grid = eid("switch", "battery_grid_charging_allowed")
    assert hass.states.get(charge).state == "100.0"
    assert hass.states.get(reserve).state == "10.0"
    assert hass.states.get(discharge_on).state == "off"
    assert hass.states.get(grid).state == "on"

    async def call(domain: str, service: str, entity_id: str, **data) -> None:
        await hass.services.async_call(
            domain, service, {"entity_id": entity_id, **data}, blocking=True
        )
        await hass.async_block_till_done()

    await call("number", "set_value", discharge, value=-50)
    await call("switch", "turn_on", discharge_on)
    await call("number", "set_value", reserve, value=30)
    await call("switch", "turn_off", grid)
    assert hass.states.get(discharge).state == "-50.0"
    assert hass.states.get(discharge_on).state == "on"
    assert hass.states.get(reserve).state == "30.0"
    assert hass.states.get(grid).state == "off"

    coordinator = entry.runtime_data
    start = coordinator.inverter.models[124][0]
    regs = await coordinator.client.read(1, start, 24)
    assert regs[3] == 2 and regs[5] == 3000 and regs[10] == 0x10000 - 5000
    assert regs[13] == 300 and regs[15] == 0

    # Ungültiges Fenster → verständlicher Fehler, Gerät unverändert
    await call("number", "set_value", charge, value=20)
    with pytest.raises(HomeAssistantError):
        await call("switch", "turn_on", charge_on)
    assert (await coordinator.client.read(1, start + 3, 1)) == [2]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Ohne Speicher keine Speicher-Entitäten
    plain = await _setup(hass, gen24_plain.port)
    await _enable_control(hass, plain)
    assert not [
        e
        for e in er.async_entries_for_config_entry(ent_reg, plain.entry_id)
        if "battery" in e.unique_id
    ]
    assert await hass.config_entries.async_unload(plain.entry_id)
    await hass.async_block_till_done()


async def test_scan_interval_option(hass: HomeAssistant, gen24) -> None:
    """Abfrageintervall einstellbar; die Rückfallzeit überdauert mindestens drei Abfragen."""
    from datetime import timedelta

    entry = await _setup(hass, gen24.port, **{CONF_METER_UNIT_ID: 0})
    assert entry.runtime_data.update_interval == timedelta(seconds=10)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # außerhalb 5–60 s wird abgelehnt
    with pytest.raises(Exception):  # noqa: B017, PT011 - InvalidData aus dem Schema
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_ALLOW_CONTROL: True, CONF_SCAN_INTERVAL: 2}
        )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALLOW_CONTROL: True, CONF_SCAN_INTERVAL: 45}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_SCAN_INTERVAL] == 45

    coordinator = entry.runtime_data
    assert coordinator.update_interval == timedelta(seconds=45)
    # 3 × 45 s = 135 s Mindestwert; Standard 300 s bleibt
    assert coordinator.min_revert_seconds == 135
    assert coordinator.revert_seconds == 300
    ent_reg = er.async_get(hass)
    revert = ent_reg.async_get_entity_id("number", DOMAIN, "33333333_revert_time")
    assert hass.states.get(revert).attributes["min"] == 135
    with pytest.raises(Exception):  # noqa: B017, PT011 - ServiceValidationError
        await hass.services.async_call(
            "number", "set_value", {"entity_id": revert, "value": 60}, blocking=True
        )
    assert coordinator.revert_seconds == 300

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_multiple_meters(hass: HomeAssistant, socket_enabled) -> None:
    """Weitere Smart Meter: eigenes Gerät je Zähler, eigene Werte, Fehler im Formular."""
    server = sim.FroniusSimulator(
        {
            1: sim.gen24_plus_float(),
            200: sim.meter_213(),
            201: sim.meter_213(serial="M0000002", power=750.0),
        }
    )
    await server.start()
    try:
        async def _try(extra: str):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            return await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "127.0.0.1",
                    CONF_PORT: server.port,
                    CONF_UNIT_ID: 1,
                    CONF_EXTRA_METER_UNIT_IDS: extra,
                },
            )

        result = await _try("201, abc")
        assert result["errors"] == {CONF_EXTRA_METER_UNIT_IDS: "invalid_meter_list"}
        result = await _try("201, 300")
        assert result["errors"] == {CONF_EXTRA_METER_UNIT_IDS: "invalid_meter_list"}
        result = await _try("201, 202")
        assert result["errors"] == {CONF_EXTRA_METER_UNIT_IDS: "meter_not_found"}

        # Hauptzähler (200, automatisch gefunden) und Wechselrichter fallen aus der Liste
        result = await _try("200; 201, 201, 1")
        assert result["type"] is FlowResultType.CREATE_ENTRY, result
        await hass.async_block_till_done()
        entry = result["result"]
        assert entry.data[CONF_METER_UNIT_ID] == 200
        assert entry.data[CONF_EXTRA_METER_UNIT_IDS] == [201]

        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)
        assert _state(hass, ent_reg, "meter_M0000001_meter_power").state == "-1500.0"
        assert _state(hass, ent_reg, "meter_M0000002_meter_power").state == "750.0"
        primary = dev_reg.async_get_device(identifiers={(DOMAIN, "meter_M0000001")})
        second = dev_reg.async_get_device(identifiers={(DOMAIN, "meter_M0000002")})
        assert primary.name == "Smart Meter TS 65A-3"
        assert second.name == "Smart Meter TS 65A-3 (201)"
        assert second.via_device_id == primary.via_device_id

        coordinator = entry.runtime_data
        assert coordinator.meter.unit_id == 200
        assert sorted(coordinator.meters) == [200, 201]
        assert coordinator.data.values["201:meter_power"] == 750.0

        # Zweiter Zähler fällt aus: nur seine Entitäten werden unavailable
        del server.units[201]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert _state(hass, ent_reg, "meter_M0000002_meter_power").state == "unavailable"
        assert _state(hass, ent_reg, "meter_M0000001_meter_power").state == "-1500.0"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()
