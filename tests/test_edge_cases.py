"""Fehlerpfade und Sonderfälle, die die übrigen Tests nicht berühren."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from custom_components.fronius_modbus_tcp import state_codes, sunspec
from custom_components.fronius_modbus_tcp.api import (
    FroniusConnectionError,
    FroniusModbusClient,
    FroniusModbusError,
    async_detect_meter,
)
from custom_components.fronius_modbus_tcp.client_pool import (
    _pool,
    async_release_client,
)
from custom_components.fronius_modbus_tcp.const import (
    CONF_ALLOW_CONTROL,
    CONF_EXTRA_METER_UNIT_IDS,
    CONF_METER_UNIT_ID,
    CONF_SITE_REGISTERS,
    CONF_UNIT_ID,
    DOMAIN,
)
from custom_components.fronius_modbus_tcp.diagnostics import (
    _package_version,
    async_get_config_entry_diagnostics,
)

from . import simulator as sim


def _entry(port: int, serial: str = "33333333", options=None, **data) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=serial,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: port,
            CONF_UNIT_ID: 1,
            CONF_METER_UNIT_ID: None,
            **data,
        },
        options=options or {},
    )


async def _serve(devices: dict) -> sim.FroniusSimulator:
    server = sim.FroniusSimulator(devices)
    await server.start()
    return server


# --- Modbus-Client ------------------------------------------------------------


async def test_write_to_unknown_address_reports_exception_code(socket_enabled) -> None:
    server = await _serve({1: sim.gen24_float_no_battery()})
    client = FroniusModbusClient("127.0.0.1", server.port)
    try:
        with pytest.raises(FroniusModbusError) as err:
            await client.write(1, 100, [1])
        assert err.value.exception_code == 2
        assert "Schreiben von 100" in str(err.value)
    finally:
        await client.close()
        await server.stop()


async def test_lost_connection_is_a_connection_error(socket_enabled) -> None:
    """Bricht die Verbindung mitten im Betrieb ab, ist das kein Gerätefehler."""
    server = await _serve({1: sim.gen24_float_no_battery()})
    client = FroniusModbusClient("127.0.0.1", server.port, timeout=1, retries=0)
    try:
        await client.read(1, 40000, 2)
        await server.stop()
        with pytest.raises(FroniusConnectionError):
            await client.read(1, 40000, 2)
        with pytest.raises(FroniusConnectionError):
            await client.write(1, 40000, [1])
    finally:
        await client.close()


async def test_modbus_exception_while_writing(socket_enabled) -> None:
    """Fehler der Modbus-Bibliothek beim Schreiben werden zu Verbindungsfehlern."""
    from pymodbus.exceptions import ModbusIOException

    server = await _serve({1: sim.gen24_float_no_battery()})
    client = FroniusModbusClient("127.0.0.1", server.port)
    try:
        await client.connect()
        with (
            patch.object(
                client._client, "write_registers", side_effect=ModbusIOException("weg")
            ),
            pytest.raises(FroniusConnectionError, match="weg"),
        ):
            await client.write(1, 40000, [1])
    finally:
        await client.close()
        await server.stop()


async def test_incomplete_response_is_rejected(socket_enabled) -> None:
    """Gerät liefert weniger Register als angefordert."""

    class Truncating(sim.FroniusSimulator):
        def _respond(self, unit: int, pdu: bytes) -> bytes:
            response = super()._respond(unit, pdu)
            if response[0] == 0x03 and response[1] > 2:
                return bytes([0x03, response[1] - 2]) + response[2:-2]
            return response

    server = Truncating({1: sim.gen24_float_no_battery()})
    await server.start()
    client = FroniusModbusClient("127.0.0.1", server.port)
    try:
        with pytest.raises(FroniusModbusError, match="Unvollständige Antwort"):
            await client.read(1, 40000, 4)
    finally:
        await client.close()
        await server.stop()


async def test_detection_errors(socket_enabled) -> None:
    """Kein SunSpec, kein Common Model, kein Zähler-Modell, kein Modell 123."""
    common = sim.common("Fronius", "Symo", "1.0", "77777777")
    server = await _serve(
        {
            1: [0, 0, 1, 0],  # keine "SunS"-Kennung
            2: sim.s("SunS", 2) + sim.inverter_113() + [0xFFFF, 0],  # ohne Common
            3: sim.device(common, sim.inverter_113()),  # Wechselrichter ohne 123
        }
    )
    client = FroniusModbusClient("127.0.0.1", server.port)
    try:
        with pytest.raises(FroniusModbusError, match="Keine SunSpec-Kennung"):
            await client.scan_models(1)
        with pytest.raises(FroniusModbusError, match="Common Model fehlt"):
            await client.scan_models(2)
        with pytest.raises(FroniusModbusError, match="Kein Zähler-Modell"):
            await client.read_meter_info(3)

        info = await client.read_inverter_info(3)
        assert not info.has_battery
        with pytest.raises(FroniusModbusError, match="kein Modell 123"):
            await client.set_power_limit(info, 50, enabled=True, revert_seconds=60)
        with pytest.raises(FroniusModbusError, match="kein Modell 123"):
            await client.set_feed_in(info, False, revert_seconds=60)
    finally:
        await client.close()
        await server.stop()


async def test_detect_meter_without_device(socket_enabled) -> None:
    """Niemand lauscht: jede Kandidaten-Adresse scheitert an der Verbindung."""
    assert await async_detect_meter("127.0.0.1", sim.free_port(), [200, 240]) is None


# --- Dekodierung ----------------------------------------------------------------


def test_decoding_edge_cases() -> None:
    # Symo Hybrid, Speicher ruht: Leistung 0 → weder Laden noch Entladen
    values = sunspec.combine_mppt(
        [
            {"dc_power": 1500.0, "dc_current": 4.0, "dc_voltage": 400.0, "dc_energy": None},
            {"dc_power": 0, "dc_current": 0.0, "dc_voltage": 380.0, "dc_energy": None},
        ],
        [sunspec.ROLE_PV, sunspec.ROLE_BATTERY_HYBRID],
        1500.0,
    )
    assert values["battery_power"] == 0.0
    assert values["battery_charge_power"] == 0.0
    assert values["battery_discharge_power"] == 0.0

    with pytest.raises(ValueError, match="Skalierungsfaktor"):
        sunspec.encode_percent(10, None, minimum=0, maximum=100, name="Test")
    # unbekannte Grenze: Fenster nicht prüfbar, kein Fehler
    sunspec.check_storage_window(3, None, 50)

    # unbekannte Gerätefamilie → Gesamtliste der Fehlerklassen
    assert state_codes.events_for_model("Unbekannt 5.0") is state_codes.EVENTS_ALL
    assert state_codes.events_for_model("Fronius Symo 3.0-3-M") is state_codes.EVENTS_SYMO


# --- Einrichtung -----------------------------------------------------------------


async def test_config_flow_unexpected_error(hass: HomeAssistant, socket_enabled, caplog) -> None:
    server = await _serve({1: sim.gen24_float_no_battery()})
    try:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        with patch.object(
            FroniusModbusClient, "read_inverter_info", side_effect=RuntimeError("boom")
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "127.0.0.1", CONF_PORT: server.port, CONF_UNIT_ID: 1},
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
        assert "unerwarteter Fehler" in caplog.text
        assert _pool(hass) == {}  # Verbindung trotz Fehler freigegeben
    finally:
        await server.stop()


async def test_setup_unexpected_error_releases_connection(
    hass: HomeAssistant, socket_enabled
) -> None:
    server = await _serve({1: sim.gen24_float_no_battery()})
    try:
        entry = _entry(server.port, "22222222")
        entry.add_to_hass(hass)
        with patch.object(
            FroniusModbusClient, "read_inverter_info", side_effect=RuntimeError("boom")
        ):
            assert not await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        assert _pool(hass) == {}

        # Fehler außerhalb der Abfrage (z. B. ungültige Konfiguration)
        from custom_components.fronius_modbus_tcp.coordinator import FroniusCoordinator

        with patch.object(
            FroniusCoordinator,
            "async_config_entry_first_refresh",
            side_effect=RuntimeError("boom"),
        ):
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
        assert _pool(hass) == {}
        # Freigeben ohne vorheriges Holen ist harmlos
        await async_release_client(hass, "127.0.0.1", server.port)
    finally:
        await server.stop()


async def test_reconfigure_keeps_site_registers_when_unsure(
    hass: HomeAssistant, socket_enabled
) -> None:
    """Probe ohne eindeutiges Ergebnis überschreibt den gespeicherten Gerätetyp nicht."""
    server = await _serve(
        {1: (sim.datamanager_hybrid_int(), sim.fronius_registers())}
    )
    try:
        entry = _entry(server.port, "44444444", **{CONF_SITE_REGISTERS: True})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        with patch.object(
            FroniusModbusClient, "_probe_site_registers", return_value=(False, False)
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "127.0.0.1",
                    CONF_PORT: server.port,
                    CONF_UNIT_ID: 1,
                    CONF_METER_UNIT_ID: 0,
                },
            )
            await hass.async_block_till_done()
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_SITE_REGISTERS] is True
        assert entry.runtime_data.inverter.has_site_registers

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


# --- Zähler ------------------------------------------------------------------------


async def test_meter_outage_and_recovery_are_logged_once(
    hass: HomeAssistant, socket_enabled, caplog
) -> None:
    meter = sim.meter_213()
    server = await _serve({1: sim.gen24_float_no_battery(), 200: meter})
    try:
        entry = _entry(server.port, **{CONF_METER_UNIT_ID: 200})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        registers = server.units.pop(200)

        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert caplog.text.count("Smart Meter (Unit-ID 200) antwortet nicht") == 1
        assert coordinator.last_update_success  # Wechselrichter bleibt verfügbar
        assert "meter_power" not in coordinator.data.values

        server.units[200] = registers
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert caplog.text.count("Smart Meter (Unit-ID 200) antwortet wieder") == 1
        assert coordinator.data.values["meter_power"] == -1500.0

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_retry_only_searches_missing_meters(
    hass: HomeAssistant, socket_enabled
) -> None:
    """Ein Zähler da, einer fehlt: gesucht wird nur der fehlende."""
    from homeassistant.util import dt as dt_util

    server = await _serve({1: sim.gen24_float_no_battery(), 200: sim.meter_213()})
    try:
        entry = _entry(
            server.port,
            **{CONF_METER_UNIT_ID: 200, CONF_EXTRA_METER_UNIT_IDS: [201]},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        assert sorted(coordinator.meters) == [200]

        coordinator._meter_next_retry = dt_util.utcnow()
        with patch.object(
            FroniusModbusClient,
            "read_meter_info",
            side_effect=FroniusModbusError("fehlt"),
        ) as probe:
            await coordinator.async_refresh()
        assert [call.args[0] for call in probe.call_args_list] == [201]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_meter_without_serial_number(hass: HomeAssistant, socket_enabled) -> None:
    """Ohne Seriennummer hängen die eindeutigen IDs am Eintrag (und an der Unit-ID)."""
    server = await _serve(
        {
            1: sim.gen24_float_no_battery(),
            200: sim.meter_213(serial=""),
            201: sim.meter_213(serial=""),
        }
    )
    try:
        entry = _entry(
            server.port,
            **{CONF_METER_UNIT_ID: 200, CONF_EXTRA_METER_UNIT_IDS: [201]},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ent_reg = er.async_get(hass)
        for unique_id in (
            f"{entry.entry_id}_meter_meter_power",
            f"{entry.entry_id}_meter_201_meter_power",
        ):
            assert ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id), unique_id

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


# --- Steuerung ---------------------------------------------------------------------


async def test_remaining_switch_directions(hass: HomeAssistant, socket_enabled) -> None:
    """Leistungsbegrenzung einschalten und Netzladung erlauben (Gegenrichtungen)."""
    device = sim.device(
        sim.common("Fronius", "Symo GEN24 10.0 Plus", "1.36.5-1", "33333333"),
        sim.inverter_113(),
        sim.controls_123(limit_pct=60, limit_ena=0),
        sim.storage_124(grid=0),
    )
    server = await _serve({1: device})
    try:
        entry = _entry(server.port, options={CONF_ALLOW_CONTROL: True})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ent_reg = er.async_get(hass)
        limit = ent_reg.async_get_entity_id("switch", DOMAIN, "33333333_power_limit_active")
        grid = ent_reg.async_get_entity_id(
            "switch", DOMAIN, "33333333_battery_grid_charging_allowed"
        )
        assert hass.states.get(limit).state == "off"
        assert hass.states.get(grid).state == "off"

        for entity_id in (limit, grid):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": entity_id}, blocking=True
            )
        await hass.async_block_till_done()
        assert hass.states.get(limit).state == "on"
        assert hass.states.get(grid).state == "on"

        coordinator = entry.runtime_data
        controls = coordinator.inverter.models[123][0]
        storage = coordinator.inverter.models[124][0]
        # hinterlegter Wert 60 % wird beim Einschalten verwendet
        assert await coordinator.client.read(1, controls + 3, 5) == [6000, 0, 300, 0, 1]
        assert await coordinator.client.read(1, storage + 15, 1) == [1]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_storage_control_without_model_123(hass: HomeAssistant, socket_enabled) -> None:
    """Speicher ohne Immediate Controls: Rückfallzeit gibt es trotzdem."""
    device = sim.device(
        sim.common("Fronius", "Symo GEN24 10.0 Plus", "1.36.5-1", "33333333"),
        sim.inverter_113(),
        sim.storage_124(),
    )
    server = await _serve({1: device})
    try:
        entry = _entry(server.port, options={CONF_ALLOW_CONTROL: True})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ent_reg = er.async_get(hass)
        assert not entry.runtime_data.control_allowed
        assert ent_reg.async_get_entity_id("number", DOMAIN, "33333333_revert_time")
        assert ent_reg.async_get_entity_id("number", DOMAIN, "33333333_battery_min_reserve")
        assert not ent_reg.async_get_entity_id("number", DOMAIN, "33333333_power_limit")

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


async def test_revert_time_is_restored(hass: HomeAssistant, socket_enabled) -> None:
    """Die Rückfallzeit übersteht einen Neustart; zu kleine Werte werden angehoben."""
    server = await _serve({1: sim.gen24_plus_float()})
    try:
        entry = _entry(server.port, options={CONF_ALLOW_CONTROL: True})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ent_reg = er.async_get(hass)
        revert = ent_reg.async_get_entity_id("number", DOMAIN, "33333333_revert_time")
        assert entry.runtime_data.revert_seconds == 300
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        def _stored(value: float) -> tuple[State, dict]:
            return (
                State(revert, str(value)),
                {
                    "native_value": value,
                    "native_min_value": 60,
                    "native_max_value": 28800,
                    "native_step": 1,
                    "native_unit_of_measurement": "s",
                },
            )

        mock_restore_cache_with_extra_data(hass, (_stored(1800),))
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.revert_seconds == 1800
        assert hass.states.get(revert).state == "1800"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # gespeicherter Wert unter dem Mindestwert (60 s)
        mock_restore_cache_with_extra_data(hass, (_stored(10),))
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.revert_seconds == 60

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


# --- Diagnose -----------------------------------------------------------------------


async def test_diagnostics_unreadable_fronius_registers(
    hass: HomeAssistant, socket_enabled
) -> None:
    extra = sim.fronius_registers()
    server = await _serve({1: (sim.datamanager_hybrid_int(), extra)})
    try:
        entry = _entry(server.port, "44444444")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        del server.units[1][211]  # Register 212 fehlt jetzt
        diag = await async_get_config_entry_diagnostics(hass, entry)
        fronius = diag["raw_registers"]["fronius_registers"]
        assert "error" in fronius["212-216"]
        assert isinstance(fronius["500-513"], str)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await server.stop()


def test_package_version_of_missing_package() -> None:
    assert _package_version("gibt-es-sicher-nicht-xyz") is None
    assert _package_version("pymodbus")
