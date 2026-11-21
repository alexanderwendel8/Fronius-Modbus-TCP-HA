"""Simulierte Fronius-Geräte (SunSpec-Registerkarten) für Tests.

Aufbau gemäß docs/fronius/archiv_1.2.7 (GEN24) bzw. archiv_1.1.7/handbuecher (Datamanager).
"""

from __future__ import annotations

import socket
import struct

NAN = float("nan")


def s(text: str, n: int) -> list[int]:
    raw = text.encode().ljust(n * 2, b"\0")
    return list(struct.unpack(f">{n}H", raw))


def f(value: float) -> list[int]:
    return list(struct.unpack(">HH", struct.pack(">f", value)))


def i16(value: int) -> int:
    return value & 0xFFFF


def acc32(value: int) -> list[int]:
    return [value >> 16, value & 0xFFFF]


def model(model_id: int, body: list[int]) -> list[int]:
    return [model_id, len(body), *body]


def common(mn: str, md: str, vr: str, sn: str, opt: str = "", length: int = 65) -> list[int]:
    body = s(mn, 16) + s(md, 16) + s(opt, 8) + s(vr, 8) + s(sn, 16) + [1]
    body += [0x8000] * (length - len(body))  # Argeno: Pad auf 66
    return model(1, body)


def device(*models: list[int]) -> list[int]:
    regs = s("SunS", 2)
    for m in models:
        regs += m
    return regs + [0xFFFF, 0]


# --- Wechselrichter ---------------------------------------------------------


def inverter_113(w: float = 3333.3, dcw: float = 3400.0, phases: int = 3) -> list[int]:
    body = (
        f(14.5) + f(4.8) + f(4.9) + f(4.8)
        + f(400.1) + f(401.2) + f(399.8)
        + f(231.0) + f(232.1) + f(230.5)
        + f(w) + f(50.01) + f(3340.0) + f(-120.0) + f(99.5) + f(12345678.0)
        + f(NAN) + f(NAN) + f(dcw)
        + f(41.0) + f(NAN) + f(NAN) + f(NAN)
        + [4, 4] + [0, 0] + [0] * 10
    )
    assert len(body) == 60
    return model(110 + phases, body)


def inverter_103(w: int = 3333, dcw: int = 3400) -> list[int]:
    body = [
        1450, 480, 490, 480, i16(-2),
        4001, 4012, 3998, 2310, 2321, 2305, i16(-1),
        i16(w), 0, 5001, i16(-2), 334, 1, i16(-12), 1, i16(-995), i16(-1),
        *acc32(12345), 1,
        0xFFFF, i16(-1), 0xFFFF, i16(-1), i16(dcw), 0,
        410, 0x8000, 0x8000, 0x8000, i16(-1),
        4, 7, 0, 0, 0, 0,
    ] + [0] * 8
    assert len(body) == 50
    return model(103, body)


def mppt_160(modules: list[tuple[str, int, int, int, int]], dcwh_sf: int = 0) -> list[int]:
    """modules: (IDStr, DCA, DCV, DCW, DCWH) – Rohwerte; SF: A −2, V −1, W 0."""
    body = [i16(-2), i16(-1), 0, i16(dcwh_sf), 0, 0, len(modules), 0xFFFF]
    for n, (name, a, v, w, wh) in enumerate(modules, 1):
        body += [n, *s(name, 8), a, v, w, *acc32(wh), 0, 0, 0x8000, 0xFFFF, 0xFFFF, 0xFFFF]
    return model(160, body)


def storage_124(wchamax: int = 10000, soc: int = 5420, chast: int = 4, grid: int = 1) -> list[int]:
    body = [
        wchamax, 100, 100, 0, 0xFFFF, 1000, soc, 0xFFFF, 0xFFFF, chast,
        10000, 10000, 0xFFFF, 0, 0xFFFF, grid,
        0, 0, 0x8000, i16(-2), i16(-2), 0x8000, 0x8000, i16(-2),
    ]
    assert len(body) == 24
    return model(124, body)


def filler(model_id: int, length: int) -> list[int]:
    return model(model_id, [0xFFFF] * length)


def gen24_plus_float() -> list[int]:
    """Symo GEN24 Plus, float, 2 PV-Strings + Batterie (StCha 3 / StDisCha 4)."""
    return device(
        common("Fronius", "Symo GEN24 10.0 Plus", "1.36.5-1", "33333333"),
        inverter_113(),
        filler(120, 26), filler(121, 30), filler(122, 44), filler(123, 24),
        mppt_160([
            ("MPPT 1", 412, 4050, 1680, 1234567),
            ("MPPT 2", 398, 3980, 1590, 7654321),
            ("StCha 3", 0, 4800, 0, 111111),
            ("StDisCha 4", 300, 4800, 1440, 222222),
        ]),
        storage_124(),
    )


def datamanager_hybrid_int(dcw: int = 1000) -> list[int]:
    """Symo Hybrid am Datamanager, int+SF: String 1 = PV, String 2 = Speicher (Betrag)."""
    return device(
        common("Fronius", "Symo Hybrid 5.0-3-S", "1.13.1-1", "44444444"),
        inverter_103(dcw=dcw),
        filler(120, 26), filler(121, 30), filler(122, 44), filler(123, 24),
        mppt_160([("String 1", 500, 4000, 2000, 0), ("String 2", 200, 4900, 1000, 0)]),
        storage_124(wchamax=5000, soc=8000, chast=4, grid=0),
    )


def gen24_float_no_battery() -> list[int]:
    return device(
        common("Fronius", "Primo GEN24 6.0", "1.36.5-1", "55555555"),
        inverter_113(phases=1),
        mppt_160([("MPPT 1", 412, 4050, 1680, 1), ("MPPT 2", 398, 3980, 1590, 1)]),
    )


# --- Smart Meter ------------------------------------------------------------


def meter_213() -> list[int]:
    body = (
        f(12.0) + f(4.0) + f(4.1) + f(3.9)              # A, AphA-C
        + f(230.5) + f(230.0) + f(231.0) + f(230.5)     # PhV, PhVphA-C
        + f(399.0) + f(398.5) + f(399.5) + f(399.0)     # PPV, AB, BC, CA
        + f(50.0)                                       # Hz
        + f(-1500.0) + f(-500.0) + f(-600.0) + f(-400.0)  # W, WphA-C
        + f(1600.0) + f(NAN) * 3                        # VA
        + f(200.0) + f(NAN) * 3                         # VAR
        + f(-0.95) + f(NAN) * 3                         # PF
        + f(5_000_000.0) + f(1.0) + f(2.0) + f(3.0)     # TotWhExp + Phasen
        + f(3_000_000.0) + f(4.0) + f(5.0) + f(6.0)     # TotWhImp + Phasen
        + f(NAN) * 8                                    # VAh (8 Werte)
        + f(NAN) * 16                                   # VArh (16 Werte)
        + [0, 0]                                        # Evt
    )
    assert len(body) == 124, len(body)
    return device(
        common("Fronius", "Smart Meter TS 65A-3", "1.3", "M0000001", opt="<primary>"),
        model(213, body),
    )


def meter_203() -> list[int]:
    body = [
        1200, 400, 410, 390, i16(-2),
        2305, 2300, 2310, 2305, 3990, 3985, 3995, 3990, i16(-1),
        5000, i16(-2),
        i16(1500), i16(500), i16(600), i16(400), 0,
        1600, 0x8000, 0x8000, 0x8000, 0,
        200, 0x8000, 0x8000, 0x8000, 0,
        i16(9500), 0x8000, 0x8000, 0x8000, i16(-2),
        *acc32(5_000_000), *acc32(1), *acc32(2), *acc32(3),
        *acc32(3_000_000), *acc32(4), *acc32(5), *acc32(6), 0,
    ] + [0] * 16 + [0x8000] + [0] * 32 + [0x8000] + [0, 0]  # VAh, VArh, Evt
    assert len(body) == 105, len(body)
    return device(
        common("Fronius", "Smart Meter 63A", "2.9", "M0000002"), model(203, body)
    )


# --- Server -----------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_context(devices: dict[int, list[int]]):
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext

    try:
        from pymodbus.datastore import ModbusDeviceContext as Dev

        kw = "devices"
    except ImportError:  # pymodbus < 3.10
        from pymodbus.datastore import ModbusSlaveContext as Dev

        kw = "slaves"
    # Legacy-Datastore adressiert intern +1 → Block bei 40001 beginnen
    ctx = {
        unit: Dev(hr=ModbusSequentialDataBlock(40001, regs))
        for unit, regs in devices.items()
    }
    return ModbusServerContext(**{kw: ctx}, single=False)


class FroniusSimulator:
    """Asynchroner Modbus-TCP-Server mit mehreren Unit-IDs."""

    def __init__(self, devices: dict[int, list[int]]) -> None:
        from pymodbus.server import ModbusTcpServer

        self.port = free_port()
        self._server = ModbusTcpServer(
            build_context(devices), address=("127.0.0.1", self.port)
        )
        self._task = None

    async def start(self) -> None:
        import asyncio

        self._task = asyncio.create_task(self._server.serve_forever())
        for _ in range(50):
            try:
                _, writer = await asyncio.open_connection("127.0.0.1", self.port)
                writer.close()
                await writer.wait_closed()
                return
            except OSError:
                await asyncio.sleep(0.05)
        raise RuntimeError("Simulator nicht gestartet")

    async def stop(self) -> None:
        await self._server.shutdown()
        if self._task:
            self._task.cancel()
