"""SunSpec-Modelldefinitionen und Dekodierung (ohne Home-Assistant-Abhängigkeiten).

Offsets beziehen sich jeweils auf den Modellrumpf, also auf das erste Register
nach der Modell-ID und der Längenangabe.
"""

from __future__ import annotations

import math
import struct
from typing import Any

# Wechselrichter-Modelle -> Anzahl Phasen
INVERTER_FLOAT_MODELS: dict[int, int] = {111: 1, 112: 2, 113: 3}
INVERTER_INT_SF_MODELS: dict[int, int] = {101: 1, 102: 2, 103: 3}
COMMON_MODEL = 1
MPPT_MODEL = 160
END_MODEL = 0xFFFF

MPPT_HEADER_LEN = 8
MPPT_MODULE_LEN = 20

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

# Fronius-spezifischer Status "StVnd"
STATUS_VENDOR: dict[int, str] = {
    **STATUS,
    9: "no_solarnet",
    10: "no_inverter_comm",
    11: "sn_overcurrent",
    12: "bootload",
    13: "afci",
}


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


# --- Wechselrichter (Modelle 111-113, float) -------------------------------


def parse_inverter_float(regs: list[int]) -> dict[str, Any]:
    def f(offset: int, digits: int = 2) -> float | None:
        return _round(to_float32(regs[offset : offset + 2]), digits)

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


def _positive(value: float | None) -> float | None:
    """Zählerstände von 0 als "nicht verfügbar" behandeln (verhindert Resets)."""
    return value if value else None


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


def mppt_module_count(header: list[int]) -> int:
    return to_uint16(header[6]) or 0


def mppt_module_names(regs: list[int]) -> list[str]:
    names = []
    for i in range(mppt_module_count(regs)):
        base = MPPT_HEADER_LEN + i * MPPT_MODULE_LEN
        names.append(to_str(regs[base + 1 : base + 9]) or f"MPPT {i + 1}")
    return names


def parse_mppt(regs: list[int]) -> dict[str, Any]:
    dca_sf = to_int16(regs[0])
    dcv_sf = to_int16(regs[1])
    dcw_sf = to_int16(regs[2])
    dcwh_sf = to_int16(regs[3])
    values: dict[str, Any] = {}
    for i in range(mppt_module_count(regs)):
        base = MPPT_HEADER_LEN + i * MPPT_MODULE_LEN
        n = i + 1
        values[f"mppt_{n}_dc_current"] = scale(to_uint16(regs[base + 9]), dca_sf)
        values[f"mppt_{n}_dc_voltage"] = scale(to_uint16(regs[base + 10]), dcv_sf)
        values[f"mppt_{n}_dc_power"] = scale(to_uint16(regs[base + 11]), dcw_sf)
        values[f"mppt_{n}_dc_energy"] = scale(
            to_acc32(regs[base + 12 : base + 14]), dcwh_sf, 0
        )
    return values
