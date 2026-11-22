"""Tests für Modbus-Client und Dekodierung gegen simulierte Fronius-Geräte."""

from __future__ import annotations

import pytest

from custom_components.fronius_modbus_tcp import sunspec
from custom_components.fronius_modbus_tcp.api import (
    FroniusModbusClient,
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
