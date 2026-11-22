"""Tests für Modbus-Client und Dekodierung gegen simulierte Fronius-Geräte."""

from __future__ import annotations

import pytest

from custom_components.fronius_modbus_tcp import sunspec
from custom_components.fronius_modbus_tcp.api import (
    FroniusModbusClient,
    FroniusModbusError,
    async_detect_meter,
)

from . import simulator as sim


@pytest.fixture
async def gen24(socket_enabled):
    server = sim.FroniusSimulator({1: sim.gen24_plus_float(), 200: sim.meter_213()})
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def datamanager(socket_enabled):
    server = sim.FroniusSimulator(
        {
            1: (sim.datamanager_hybrid_int(), sim.fronius_registers(day=0)),
            240: sim.meter_203(),
        }
    )
    await server.start()
    yield server
    await server.stop()


async def test_gen24_plus(gen24) -> None:
    client = FroniusModbusClient("127.0.0.1", gen24.port)
    try:
        info = await client.read_inverter_info(1)
        assert info.model == "Symo GEN24 10.0 Plus"
        assert info.inverter_model == 113 and info.phases == 3
        assert info.has_storage and not info.hybrid_storage
        assert not info.has_site_registers  # GEN24: keine Fronius-Register
        assert info.mppt_roles == [
            sunspec.ROLE_PV,
            sunspec.ROLE_PV,
            sunspec.ROLE_BATTERY_CHARGE,
            sunspec.ROLE_BATTERY_DISCHARGE,
        ]

        v = await client.read_inverter_data(info)
        assert v["ac_power"] == 3333.3
        assert v["dc_current"] is None  # mehrere DC-Eingänge → nicht unterstützt
        assert v["mppt_1_dc_power"] == 1680 and v["mppt_2_dc_power"] == 1590
        assert "mppt_3_dc_power" not in v  # Batteriemodul ist kein PV-String
        assert v["pv_power"] == 3270
        assert v["pv_current"] == 8.1  # 4,12 A + 3,98 A
        assert v["battery_discharge_power"] == 1440
        assert v["battery_charge_power"] == 0
        assert v["battery_power"] == 1440  # positiv = Entladen
        assert v["battery_voltage"] == 480.0
        assert v["battery_charge_energy"] == 111111
        assert v["battery_discharge_energy"] == 222222
        assert v["battery_soc"] == 54.2
        assert v["battery_state"] == "charging"
        assert v["battery_min_reserve"] == 10.0
        assert v["battery_grid_charging"] == "grid"
        assert v["battery_max_power"] == 10000

        # Modell 120: Nennwerte, einmal beim Start gelesen
        assert info.nameplate["rated_power"] == 10000
        assert v["rated_power"] == 10000
        assert v["rated_current"] == 14.5
        assert v["battery_capacity"] == 10240
        assert v["battery_max_charge_power"] == 10000

        # Modell 122: genauer Energiezähler und Isolationswiderstand (1500 × 10³ Ω)
        assert v["ac_energy_lifetime"] == 12_345_679
        assert v["isolation_resistance"] == 1_500_000

        # Evt1 (SunSpec): Übertemperatur + AC-Überspannung
        assert v["events"] == 0x0480
        assert v["event_message"] == "Over temperature; AC voltage above limit"

        # EvtVnd1 (Sicht "Customer"): Bit 1 = Warnung, kein Fehler
        assert v["warning_active"] is True
        assert v["error_active"] is False
        assert "vendor_events" not in v

        # Modell 123 (nur lesend): Drosselung auf 70 % aktiv
        assert v["power_limit"] == 70.0
        assert v["power_limit_active"] is True
        assert v["feed_in_enabled"] is True
        assert v["pf_setpoint"] == -0.95
        assert v["pf_control_active"] is False
        assert v["var_limit"] == 0

        meter = await client.read_meter_info(200)
        assert meter.meter_model == 213 and meter.options == "<primary>"
        m = await client.read_meter_data(meter)
        assert m["meter_power"] == -1500.0
        assert m["meter_energy_import"] == 3_000_000
        assert m["meter_energy_export"] == 5_000_000
        assert m["meter_voltage_an"] == 230.0
        assert m["meter_power_factor"] == -0.95
        assert m["meter_apparent_power"] == 1600.0
    finally:
        await client.close()


async def test_datamanager_symo_hybrid(datamanager) -> None:
    client = FroniusModbusClient("127.0.0.1", datamanager.port)
    try:
        info = await client.read_inverter_info(1)
        assert info.inverter_model == 103
        assert info.hybrid_storage
        assert info.mppt_roles == [sunspec.ROLE_PV, sunspec.ROLE_BATTERY_HYBRID]

        # DCW = 1000 = PV 2000 − Bat 1000 → Laden
        v = await client.read_inverter_data(info)
        assert v["pv_power"] == 2000
        assert v["battery_power"] == -1000
        assert v["battery_charge_power"] == 1000
        assert v["battery_discharge_power"] == 0
        assert v["battery_soc"] == 80.0
        assert v["battery_grid_charging"] == "pv"
        assert "battery_charge_energy" not in v

        # Fronius-Register (Datamanager): Anlagensummen, Tagesenergie 0 ist gültig
        assert info.has_site_registers
        assert v["site_power"] == 2000
        assert v["site_energy_day"] == 0
        assert v["site_energy_year"] == 1_234_567
        assert v["site_energy_total"] == 9_330_290
        assert v["state_code"] == 0
        assert v["state_message"] == "OK"
        # Modell 122 beim Datamanager nicht unterstützt
        assert v["ac_energy_lifetime"] is None
        assert v["isolation_resistance"] is None

        # Keine Fehlerklassen aktiv
        assert v["error_active"] is False
        assert v["vendor_events"] == "OK"
        assert "warning_active" not in v

        meter = await client.read_meter_info(240)
        m = await client.read_meter_data(meter)
        assert m["meter_power"] == 1500
        assert m["meter_current"] == 12.0
        assert m["meter_voltage_an"] == 230.0
        assert m["meter_frequency"] == 50.0
        assert m["meter_power_factor"] == 0.95
        assert m["meter_energy_import"] == 3_000_000
    finally:
        await client.close()


def test_hybrid_discharge_direction() -> None:
    modules = [
        {"dc_current": 5.0, "dc_voltage": 400.0, "dc_power": 2000.0, "dc_energy": None},
        {"dc_current": 2.0, "dc_voltage": 490.0, "dc_power": 1000.0, "dc_energy": None},
    ]
    roles = [sunspec.ROLE_PV, sunspec.ROLE_BATTERY_HYBRID]
    v = sunspec.combine_mppt(modules, roles, inverter_dc_power=3000.0)
    assert v["battery_power"] == 1000.0
    assert v["battery_discharge_power"] == 1000.0
    assert v["battery_charge_power"] == 0.0
    # Ohne DC-Gesamtleistung ist die Richtung unbekannt
    v = sunspec.combine_mppt(modules, roles, inverter_dc_power=None)
    assert v["battery_power"] is None


def test_storage_without_battery() -> None:
    regs = [0] + [0xFFFF] * 23  # US-Gerät ohne Batterie: WChaMax = 0
    assert not sunspec.storage_available(regs)
    assert not sunspec.storage_available([0xFFFF] * 24)


async def test_detect_meter(gen24, datamanager) -> None:
    meter = await async_detect_meter("127.0.0.1", gen24.port, [200, 240])
    assert meter is not None and meter.unit_id == 200
    meter = await async_detect_meter("127.0.0.1", datamanager.port, [200, 240])
    assert meter is not None and meter.unit_id == 240
    assert await async_detect_meter("127.0.0.1", gen24.port, [201]) is None


def test_state_code_text() -> None:
    from custom_components.fronius_modbus_tcp import state_codes

    symo = state_codes.table_for_model("Symo 3.0-3-M")
    assert sunspec.parse_fronius_state_code(306, symo) == {
        "state_code": 306,
        "state_message": "Power Low",
    }
    # IG Plus hat eigene Texte
    igplus = state_codes.table_for_model("IG Plus 50 V-1")
    assert sunspec.parse_fronius_state_code(307, igplus)["state_message"] == "DC Low"
    # Unbekannte Familie → alle Tabellen; unbekannter Code → Nummer
    other = state_codes.table_for_model("Eco 25.0-3-S")
    assert sunspec.parse_fronius_state_code(306, other)["state_message"] == "Power Low"
    assert sunspec.parse_fronius_state_code(9999, other)["state_message"] == "State code 9999"
    # Nicht unterstützt
    assert sunspec.parse_fronius_state_code(0xFFFF, other)["state_code"] is None


def test_vendor_event_classes() -> None:
    from custom_components.fronius_modbus_tcp import state_codes

    symo = state_codes.events_for_model("Symo 3.0-3-M")
    v = sunspec.parse_vendor_event_classes([0x20, 0x4, 0, 0], symo)
    assert v == {"error_active": True, "vendor_events": "Power low; 24h no feed in"}
    # Familienspezifisch: EvtVnd2 0x8 heißt beim Primo anders als beim Symo
    primo = state_codes.events_for_model("Primo 5.0-1")
    assert sunspec.parse_vendor_event_classes([0, 0x8, 0, 0], primo)["vendor_events"] == (
        "No communication with filter"
    )
    assert sunspec.parse_vendor_event_classes([0, 0x8, 0, 0], symo)["vendor_events"] == (
        "Faulty plug connections"
    )
    # Unbekanntes Bit, nicht unterstützt
    assert sunspec.parse_vendor_event_classes([0, 0, 0, 0x10], symo)["vendor_events"] == (
        "EvtVnd4 0x10"
    )
    assert sunspec.parse_vendor_event_classes([None] * 4, symo)["error_active"] is None


def test_severity_events() -> None:
    assert sunspec.parse_severity_events([0b001, 0, 0, 0]) == {
        "error_active": True,
        "warning_active": False,
    }
    assert sunspec.parse_severity_events([None, 0, 0, 0])["error_active"] is None


def test_event_message() -> None:
    assert sunspec.parse_event_message(0) == {"event_message": "OK"}
    assert sunspec.parse_event_message(0x0001) == {"event_message": "Ground fault"}
    assert sunspec.parse_event_message(0x10000)["event_message"] == "Evt1 0x10000"
    assert sunspec.parse_event_message(None) == {"event_message": None}


# --- Schreiben (Steuerung) -----------------------------------------------------


def test_encode_power_limit() -> None:
    # Handbuch-Beispiel: 80 % bei SF −2, ohne Zeitvorgaben → 8000, 0, 0, 0, 1
    assert sunspec.encode_power_limit(80, -2, 0, True) == [8000, 0, 0, 0, 1]
    assert sunspec.encode_power_limit(55.5, -2, 300, False) == [5550, 0, 300, 0, 0]
    with pytest.raises(ValueError):
        sunspec.encode_power_limit(101, -2, 300, True)
    with pytest.raises(ValueError):
        sunspec.encode_power_limit(50, None, 300, True)
    assert sunspec.encode_feed_in(False, 300) == [0, 300, 0]
    assert sunspec.encode_feed_in(True, 300) == [0, 0, 1]


async def test_write_controls(gen24) -> None:
    client = FroniusModbusClient("127.0.0.1", gen24.port)
    try:
        info = await client.read_inverter_info(1)
        start = info.models[sunspec.CONTROLS_MODEL][0]

        await client.set_power_limit(info, 55, enabled=True, revert_seconds=600)
        v = await client.read_inverter_data(info)
        assert v["power_limit"] == 55.0 and v["power_limit_active"] is True
        # WMaxLimPct_RvrtTms gesetzt
        assert (await client.read(1, start + 5, 1)) == [600]

        await client.disable_power_limit(info)
        v = await client.read_inverter_data(info)
        assert v["power_limit_active"] is False and v["power_limit"] == 55.0

        await client.set_feed_in(info, False, revert_seconds=300)
        v = await client.read_inverter_data(info)
        assert v["feed_in_enabled"] is False
        assert (await client.read(1, start, 3)) == [0, 300, 0]
        await client.set_feed_in(info, True, revert_seconds=300)
        assert (await client.read_inverter_data(info))["feed_in_enabled"] is True

        # GEN24 hat keine Fronius-Register
        with pytest.raises(FroniusModbusError):
            await client.reset_events(info)
    finally:
        await client.close()


async def test_reset_events_datamanager(datamanager) -> None:
    client = FroniusModbusClient("127.0.0.1", datamanager.port)
    try:
        info = await client.read_inverter_info(1)
        await client.reset_events(info)
        assert (await client.read(1, sunspec.FRONIUS_RESET_EVENTS_ADDRESS, 1)) == [0xFFFF]
    finally:
        await client.close()
