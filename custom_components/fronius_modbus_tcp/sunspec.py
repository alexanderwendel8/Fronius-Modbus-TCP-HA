"""SunSpec-Modelldefinitionen und Dekodierung (ohne Home-Assistant-Abhängigkeiten).

Offsets beziehen sich jeweils auf den Modellrumpf, also auf das erste Register
nach der Modell-ID und der Längenangabe. Quellen: docs/fronius/ (siehe CLAUDE.md).
"""

from __future__ import annotations

import math
import struct
from typing import Any

# Wechselrichter-Modelle -> Anzahl Phasen
INVERTER_FLOAT_MODELS: dict[int, int] = {111: 1, 112: 2, 113: 3}
INVERTER_INT_SF_MODELS: dict[int, int] = {101: 1, 102: 2, 103: 3}
# Zähler-Modelle -> Anzahl Phasen (214/204 = Dreieck, ohne Neutralleiter)
METER_FLOAT_MODELS: dict[int, int] = {211: 1, 212: 2, 213: 3, 214: 3}
METER_INT_SF_MODELS: dict[int, int] = {201: 1, 202: 2, 203: 3, 204: 3}
COMMON_MODEL = 1
STORAGE_MODEL = 124
MPPT_MODEL = 160
END_MODEL = 0xFFFF

MPPT_HEADER_LEN = 8
MPPT_MODULE_LEN = 20

# Rollen der Module in Modell 160
ROLE_PV = "pv"
ROLE_BATTERY_CHARGE = "battery_charge"  # GEN24/Verto: "StCha n"
ROLE_BATTERY_DISCHARGE = "battery_discharge"  # GEN24/Verto: "StDisCha n"
ROLE_BATTERY_HYBRID = "battery_hybrid"  # Symo Hybrid: String 2, nur Betrag

# SunSpec "St" (Operating State)
STATUS: dict[int, str] = {
    1: "off",
    2: "sleeping",
    3: "starting",
    4: "mppt",
    5: "throttled",
    6: "shutting_down",
    7: "fault",
    8: "standby",
}

# Fronius-spezifischer Status "StVnd" (Datamanager; beim GEN24 identisch mit St)
STATUS_VENDOR: dict[int, str] = {
    **STATUS,
    9: "no_solarnet",
    10: "no_inverter_comm",
    11: "sn_overcurrent",
    12: "bootload",
    13: "afci",
}

# Modell 124 "ChaSt"
STORAGE_STATE: dict[int, str] = {
    1: "off",
    2: "empty",
    3: "discharging",
    4: "charging",
    5: "full",
    6: "holding",
    7: "testing",
}

# Modell 124 "StorCtl_Mod" (Bit 0 = Ladegrenze aktiv, Bit 1 = Entladegrenze aktiv)
STORAGE_CONTROL_MODE: dict[int, str] = {
    0: "none",
    1: "charge_limit",
    2: "discharge_limit",
    3: "charge_and_discharge_limit",
}

# Modell 124 "ChaGriSet"
STORAGE_GRID_CHARGING: dict[int, str] = {0: "pv", 1: "grid"}


# --- Basis-Dekoder (liefern None für "nicht implementiert") -----------------


def to_str(regs: list[int]) -> str:
    raw = b"".join(struct.pack(">H", r) for r in regs)
    return raw.decode("ascii", errors="ignore").replace("\x00", "").strip()


def to_uint16(reg: int) -> int | None:
    return None if reg == 0xFFFF else reg


def to_int16(reg: int) -> int | None:
    if reg == 0x8000:
        return None
    return reg - 0x10000 if reg & 0x8000 else reg


def to_uint32(regs: list[int]) -> int | None:
    value = (regs[0] << 16) | regs[1]
    return None if value == 0xFFFFFFFF else value


def to_acc32(regs: list[int]) -> int | None:
    value = (regs[0] << 16) | regs[1]
    return None if value == 0 else value


def to_float32(regs: list[int]) -> float | None:
    value = struct.unpack(">f", struct.pack(">HH", regs[0], regs[1]))[0]
    return None if math.isnan(value) or math.isinf(value) else value


def scale(value: int | None, sf: int | None, digits: int = 3) -> float | None:
    if value is None or sf is None:
        return None
    return round(value * 10**sf, digits)


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _enum(value: int | None, mapping: dict[int, str]) -> str | None:
    return None if value is None else mapping.get(value)


def _positive(value: float | None) -> float | None:
    """Zählerstände von 0 als "nicht verfügbar" behandeln (verhindert Resets)."""
    return value if value else None


def _float_reader(regs: list[int]):
    def f(offset: int, digits: int = 2) -> float | None:
        return _round(to_float32(regs[offset : offset + 2]), digits)

    return f


# --- Wechselrichter (Modelle 111-113, float) -------------------------------


def parse_inverter_float(regs: list[int]) -> dict[str, Any]:
    f = _float_reader(regs)
    status = to_uint16(regs[46])
    status_vendor = to_uint16(regs[47])
    return {
        "ac_current": f(0),
        "ac_current_a": f(2),
        "ac_current_b": f(4),
        "ac_current_c": f(6),
        "ac_voltage_ab": f(8, 1),
        "ac_voltage_bc": f(10, 1),
        "ac_voltage_ca": f(12, 1),
        "ac_voltage_an": f(14, 1),
        "ac_voltage_bn": f(16, 1),
        "ac_voltage_cn": f(18, 1),
        "ac_power": f(20, 1),
        "ac_frequency": f(22),
        "ac_apparent_power": f(24, 1),
        "ac_reactive_power": f(26, 1),
        "ac_power_factor": f(28),
        "ac_energy": _positive(f(30, 0)),
        "dc_current": f(32),
        "dc_voltage": f(34, 1),
        "dc_power": f(36, 1),
        "temperature_cabinet": f(38, 1),
        "temperature_heatsink": f(40, 1),
        "temperature_transformer": f(42, 1),
        "temperature_other": f(44, 1),
        "status": _enum(status, STATUS),
        "status_vendor": _enum(status_vendor, STATUS_VENDOR),
        "events": to_uint32(regs[48:50]),
    }


# --- Wechselrichter (Modelle 101-103, Integer + Scale Factor) --------------


def parse_inverter_int_sf(regs: list[int]) -> dict[str, Any]:
    a_sf = to_int16(regs[4])
    v_sf = to_int16(regs[11])
    w_sf = to_int16(regs[13])
    hz_sf = to_int16(regs[15])
    va_sf = to_int16(regs[17])
    var_sf = to_int16(regs[19])
    pf_sf = to_int16(regs[21])
    wh_sf = to_int16(regs[24])
    dca_sf = to_int16(regs[26])
    dcv_sf = to_int16(regs[28])
    dcw_sf = to_int16(regs[30])
    tmp_sf = to_int16(regs[35])

    status = to_uint16(regs[36])
    status_vendor = to_uint16(regs[37])
    return {
        "ac_current": scale(to_uint16(regs[0]), a_sf),
        "ac_current_a": scale(to_uint16(regs[1]), a_sf),
        "ac_current_b": scale(to_uint16(regs[2]), a_sf),
        "ac_current_c": scale(to_uint16(regs[3]), a_sf),
        "ac_voltage_ab": scale(to_uint16(regs[5]), v_sf),
        "ac_voltage_bc": scale(to_uint16(regs[6]), v_sf),
        "ac_voltage_ca": scale(to_uint16(regs[7]), v_sf),
        "ac_voltage_an": scale(to_uint16(regs[8]), v_sf),
        "ac_voltage_bn": scale(to_uint16(regs[9]), v_sf),
        "ac_voltage_cn": scale(to_uint16(regs[10]), v_sf),
        "ac_power": scale(to_int16(regs[12]), w_sf),
        "ac_frequency": scale(to_uint16(regs[14]), hz_sf),
        "ac_apparent_power": scale(to_int16(regs[16]), va_sf),
        "ac_reactive_power": scale(to_int16(regs[18]), var_sf),
        "ac_power_factor": scale(to_int16(regs[20]), pf_sf),
        "ac_energy": scale(to_acc32(regs[22:24]), wh_sf, 0),
        "dc_current": scale(to_uint16(regs[25]), dca_sf),
        "dc_voltage": scale(to_uint16(regs[27]), dcv_sf),
        "dc_power": scale(to_int16(regs[29]), dcw_sf),
        "temperature_cabinet": scale(to_int16(regs[31]), tmp_sf),
        "temperature_heatsink": scale(to_int16(regs[32]), tmp_sf),
        "temperature_transformer": scale(to_int16(regs[33]), tmp_sf),
        "temperature_other": scale(to_int16(regs[34]), tmp_sf),
        "status": _enum(status, STATUS),
        "status_vendor": _enum(status_vendor, STATUS_VENDOR),
        "events": to_uint32(regs[38:40]),
    }


# --- MPPT (Modell 160, Multiple MPPT Inverter Extension) --------------------


def mppt_module_count(regs: list[int]) -> int:
    return to_uint16(regs[6]) or 0


def mppt_module_names(regs: list[int]) -> list[str]:
    """Rohe Modulnamen (IDStr); leer, wenn nicht unterstützt."""
    names = []
    for i in range(mppt_module_count(regs)):
        base = MPPT_HEADER_LEN + i * MPPT_MODULE_LEN
        names.append(to_str(regs[base + 1 : base + 9]))
    return names


def mppt_roles(names: list[str], hybrid_storage: bool) -> list[str]:
    """Rolle jedes Moduls bestimmen.

    GEN24 Plus / Verto Plus kennzeichnen den Batterieanschluss über die Namen
    "StCha n" (Laden) und "StDisCha n" (Entladen). Beim Symo Hybrid
    (Datamanager) ist String 2 der Speicher – erkennbar nur am Modell 124.
    """
    roles = []
    for name in names:
        lower = name.lower()
        if lower.startswith("stdischa"):
            roles.append(ROLE_BATTERY_DISCHARGE)
        elif lower.startswith("stcha"):
            roles.append(ROLE_BATTERY_CHARGE)
        else:
            roles.append(ROLE_PV)
    if hybrid_storage and len(roles) == 2 and roles == [ROLE_PV, ROLE_PV]:
        roles[1] = ROLE_BATTERY_HYBRID
    return roles


def parse_mppt(regs: list[int]) -> list[dict[str, float | None]]:
    """Messwerte je Modul (Reihenfolge wie im Gerät)."""
    dca_sf = to_int16(regs[0])
    dcv_sf = to_int16(regs[1])
    dcw_sf = to_int16(regs[2])
    dcwh_sf = to_int16(regs[3])
    modules = []
    for i in range(mppt_module_count(regs)):
        base = MPPT_HEADER_LEN + i * MPPT_MODULE_LEN
        modules.append(
            {
                "dc_current": scale(to_uint16(regs[base + 9]), dca_sf),
                "dc_voltage": scale(to_uint16(regs[base + 10]), dcv_sf),
                "dc_power": scale(to_uint16(regs[base + 11]), dcw_sf),
                "dc_energy": scale(
                    to_acc32(regs[base + 12 : base + 14]), dcwh_sf, 0
                ),
            }
        )
    return modules


def combine_mppt(
    modules: list[dict[str, float | None]],
    roles: list[str],
    inverter_dc_power: float | None,
) -> dict[str, Any]:
    """PV-Strings und Batterieanschluss aus Modell 160 in Sensorwerte umsetzen.

    Vorzeichen der Batterieleistung: positiv = Entladen, negativ = Laden.
    """
    values: dict[str, Any] = {}
    pv_powers: list[float | None] = []
    pv_currents: list[float | None] = []
    charge = discharge = hybrid = None

    for index, (module, role) in enumerate(zip(modules, roles, strict=False), 1):
        if role == ROLE_PV:
            for field, value in module.items():
                values[f"mppt_{index}_{field}"] = value
            pv_powers.append(module["dc_power"])
            pv_currents.append(module["dc_current"])
        elif role == ROLE_BATTERY_CHARGE:
            charge = module
        elif role == ROLE_BATTERY_DISCHARGE:
            discharge = module
        elif role == ROLE_BATTERY_HYBRID:
            hybrid = module

    if pv_powers:
        values["pv_power"] = (
            None if None in pv_powers else round(sum(pv_powers), 1)  # type: ignore[arg-type]
        )
        # Summe der String-Ströme (eine Gesamtspannung gibt es bei mehreren
        # Strings nicht – die Spannung bleibt nur je String verfügbar)
        values["pv_current"] = (
            None if None in pv_currents else round(sum(pv_currents), 2)  # type: ignore[arg-type]
        )

    if charge is not None or discharge is not None:
        charge_power = charge["dc_power"] if charge else None
        discharge_power = discharge["dc_power"] if discharge else None
        values["battery_charge_power"] = charge_power
        values["battery_discharge_power"] = discharge_power
        values["battery_power"] = (
            None
            if charge_power is None or discharge_power is None
            else round(discharge_power - charge_power, 1)
        )
        # Bis FW 1.30 ist das gerade inaktive Modul 0 → größten Wert nehmen
        voltages = [
            m["dc_voltage"] for m in (charge, discharge) if m and m["dc_voltage"]
        ]
        values["battery_voltage"] = max(voltages) if voltages else None
        values["battery_charge_energy"] = charge["dc_energy"] if charge else None
        values["battery_discharge_energy"] = (
            discharge["dc_energy"] if discharge else None
        )

    if hybrid is not None:
        # Symo Hybrid: nur Betrag; Richtung aus DCW des Inverter-Modells ableiten
        # (Entladen: DCW = PV + Bat, Laden: DCW = PV − Bat)
        power = hybrid["dc_power"]
        pv = pv_powers[0] if pv_powers else None
        battery_power = None
        if power == 0:
            battery_power = 0.0
        elif None not in (power, pv, inverter_dc_power):
            discharging = abs(inverter_dc_power - (pv + power)) <= abs(  # type: ignore[operator]
                inverter_dc_power - (pv - power)  # type: ignore[operator]
            )
            battery_power = power if discharging else -power  # type: ignore[operator]
        values["battery_power"] = battery_power
        values["battery_charge_power"] = (
            None if battery_power is None else max(-battery_power, 0.0)
        )
        values["battery_discharge_power"] = (
            None if battery_power is None else max(battery_power, 0.0)
        )
        values["battery_voltage"] = hybrid["dc_voltage"]

    return values


# --- Speicher (Modell 124, Basic Storage Controls) -------------------------


def storage_available(regs: list[int]) -> bool:
    """WChaMax = 0 bzw. nicht unterstützt bedeutet: kein Speicher vorhanden."""
    return bool(to_uint16(regs[0]))


def parse_storage(regs: list[int]) -> dict[str, Any]:
    in_out_sf = to_int16(regs[23])
    return {
        "battery_max_power": scale(to_uint16(regs[0]), to_int16(regs[16]), 0),
        "battery_control_mode": _enum(to_uint16(regs[3]), STORAGE_CONTROL_MODE),
        "battery_min_reserve": scale(to_uint16(regs[5]), to_int16(regs[19]), 2),
        "battery_soc": scale(to_uint16(regs[6]), to_int16(regs[20]), 2),
        "battery_state": _enum(to_uint16(regs[9]), STORAGE_STATE),
        "battery_discharge_limit": scale(to_int16(regs[10]), in_out_sf, 2),
        "battery_charge_limit": scale(to_int16(regs[11]), in_out_sf, 2),
        "battery_grid_charging": _enum(to_uint16(regs[15]), STORAGE_GRID_CHARGING),
    }


# --- Smart Meter (Modelle 211-214 float, 201-204 int+SF) --------------------


def parse_meter_float(regs: list[int]) -> dict[str, Any]:
    f = _float_reader(regs)
    return {
        "meter_current": f(0),
        "meter_current_a": f(2),
        "meter_current_b": f(4),
        "meter_current_c": f(6),
        "meter_voltage_an": f(10, 1),
        "meter_voltage_bn": f(12, 1),
        "meter_voltage_cn": f(14, 1),
        "meter_voltage_ab": f(18, 1),
        "meter_voltage_bc": f(20, 1),
        "meter_voltage_ca": f(22, 1),
        "meter_frequency": f(24),
        "meter_power": f(26, 1),
        "meter_power_a": f(28, 1),
        "meter_power_b": f(30, 1),
        "meter_power_c": f(32, 1),
        "meter_apparent_power": f(34, 1),
        "meter_reactive_power": f(42, 1),
        "meter_power_factor": f(50, 3),
        "meter_energy_export": _positive(f(58, 0)),
        "meter_energy_export_a": _positive(f(60, 0)),
        "meter_energy_export_b": _positive(f(62, 0)),
        "meter_energy_export_c": _positive(f(64, 0)),
        "meter_energy_import": _positive(f(66, 0)),
        "meter_energy_import_a": _positive(f(68, 0)),
        "meter_energy_import_b": _positive(f(70, 0)),
        "meter_energy_import_c": _positive(f(72, 0)),
    }


def parse_meter_int_sf(regs: list[int]) -> dict[str, Any]:
    a_sf = to_int16(regs[4])
    v_sf = to_int16(regs[13])
    hz_sf = to_int16(regs[15])
    w_sf = to_int16(regs[20])
    va_sf = to_int16(regs[25])
    var_sf = to_int16(regs[30])
    pf_sf = to_int16(regs[35])
    wh_sf = to_int16(regs[52])

    def i16(offset: int, sf: int | None, digits: int = 3) -> float | None:
        return scale(to_int16(regs[offset]), sf, digits)

    def wh(offset: int) -> float | None:
        return scale(to_acc32(regs[offset : offset + 2]), wh_sf, 0)

    # PF ist hier in Prozent → wie beim float-Modell als Faktor (−1…1) ausgeben
    pf = i16(31, pf_sf)
    return {
        "meter_current": i16(0, a_sf),
        "meter_current_a": i16(1, a_sf),
        "meter_current_b": i16(2, a_sf),
        "meter_current_c": i16(3, a_sf),
        "meter_voltage_an": i16(6, v_sf),
        "meter_voltage_bn": i16(7, v_sf),
        "meter_voltage_cn": i16(8, v_sf),
        "meter_voltage_ab": i16(10, v_sf),
        "meter_voltage_bc": i16(11, v_sf),
        "meter_voltage_ca": i16(12, v_sf),
        "meter_frequency": i16(14, hz_sf),
        "meter_power": i16(16, w_sf),
        "meter_power_a": i16(17, w_sf),
        "meter_power_b": i16(18, w_sf),
        "meter_power_c": i16(19, w_sf),
        "meter_apparent_power": i16(21, va_sf),
        "meter_reactive_power": i16(26, var_sf),
        "meter_power_factor": None if pf is None else round(pf / 100, 3),
        "meter_energy_export": wh(36),
        "meter_energy_export_a": wh(38),
        "meter_energy_export_b": wh(40),
        "meter_energy_export_c": wh(42),
        "meter_energy_import": wh(44),
        "meter_energy_import_a": wh(46),
        "meter_energy_import_b": wh(48),
        "meter_energy_import_c": wh(50),
    }
