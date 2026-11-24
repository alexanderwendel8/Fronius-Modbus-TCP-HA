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


def inverter_113(
    w: float = 3333.3,
    dcw: float = 3400.0,
    phases: int = 3,
    evt1: int = 0,
    evt_vnd: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> list[int]:
    body = (
        f(14.5) + f(4.8) + f(4.9) + f(4.8)
        + f(400.1) + f(401.2) + f(399.8)
        + f(231.0) + f(232.1) + f(230.5)
        + f(w) + f(50.01) + f(3340.0) + f(-120.0) + f(99.5) + f(12345678.0)
        + f(NAN) + f(NAN) + f(dcw)
        + f(41.0) + f(NAN) + f(NAN) + f(NAN)
        + [4, 4] + acc32(evt1) + [0, 0]
        + [r for v in evt_vnd for r in acc32(v)]
    )
    assert len(body) == 60
    return model(110 + phases, body)


def inverter_103(
    w: int = 3333,
    dcw: int = 3400,
    evt1: int = 0,
    evt_vnd: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> list[int]:
    body = [
        1450, 480, 490, 480, i16(-2),
        4001, 4012, 3998, 2310, 2321, 2305, i16(-1),
        i16(w), 0, 5001, i16(-2), 334, 1, i16(-12), 1, i16(-995), i16(-1),
        *acc32(12345), 1,
        0xFFFF, i16(-1), 0xFFFF, i16(-1), i16(dcw), 0,
        410, 0x8000, 0x8000, 0x8000, i16(-1),
        4, 7, *acc32(evt1), 0, 0,
    ] + [r for v in evt_vnd for r in acc32(v)]
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


def nameplate_120(
    *, w_rtg: int = 1000, a_rtg: int = 1450, wh_rtg: int = 0xFFFF, cha: int = 0xFFFF
) -> list[int]:
    """Nameplate: WRtg/VARtg mit SF 1, ARtg mit SF −2, Batteriewerte mit SF 0."""
    body = [
        82,                              # DERTyp (PV_STOR)
        w_rtg, 1, w_rtg, 1,              # WRtg, WRtg_SF, VARtg, VARtg_SF
        500, 0, 0, i16(-500), 1,         # VArRtgQ1-Q4, VArRtg_SF
        a_rtg, i16(-2),                  # ARtg, ARtg_SF
        i16(-800), 1000, 1000, 800, i16(-3),  # PFRtgQ1-Q4, PFRtg_SF
        wh_rtg, 0,                       # WHRtg, WHRtg_SF
        0xFFFF, 0x8000,                  # AhrRtg, AhrRtg_SF (n. u.)
        cha, 0, cha, 0,                  # MaxChaRte, _SF, MaxDisChaRte, _SF
        0x8000,                          # Pad
    ]
    assert len(body) == 26
    return model(120, body)


def status_122(*, act_wh: int = 0, ris: int = 0xFFFF, ris_sf: int = 0x8000) -> list[int]:
    """Extended Measurements: ActWh (acc64) und Ris; Standard = nicht unterstützt."""
    body = [
        0b111, 0xFFFF, 0b1,                                 # PVConn, StorConn, ECPConn
        *[(act_wh >> s) & 0xFFFF for s in (48, 32, 16, 0)],  # ActWh
        *[0] * 4 * 5,                                       # ActVAh, ActVArhQ1-Q4
        0x8000, 0x8000, 0xFFFF, 0x8000,                     # VArAval(_SF), WAval(_SF)
        0xFFFF, 0xFFFF, 0, 0,                               # StSetLimMsk, StActCtl
        *s("RTC", 4), 0, 0,                                 # TmSrc, Tms
        0xFFFF, ris, i16(ris_sf) if ris_sf != 0x8000 else 0x8000,  # RtSt, Ris, Ris_SF
    ]
    assert len(body) == 44, len(body)
    return model(122, body)


def controls_123(
    *, conn: int = 1, limit_pct: float = 100.0, limit_ena: int = 0, pf_ena: int = 0
) -> list[int]:
    """Immediate Controls: WMaxLimPct mit SF −2, OutPFSet mit SF −3."""
    body = [
        0, 0, conn,                      # Conn_WinTms, Conn_RvrtTms, Conn
        round(limit_pct * 100), 0, 0, 0,  # WMaxLimPct, _WinTms, _RvrtTms, _RmpTms
        limit_ena,                       # WMaxLim_Ena
        i16(-950), 0, 0, 0, pf_ena,      # OutPFSet (−0,95), _WinTms, _RvrtTms, _RmpTms, _Ena
        0x8000, 0, 0x8000,               # VArWMaxPct (n. u.), VArMaxPct, VArAvalPct (n. u.)
        0, 0, 0, 2, 0,                   # VArPct_WinTms, _RvrtTms, _RmpTms, _Mod, _Ena
        i16(-2), i16(-3), 0,             # WMaxLimPct_SF, OutPFSet_SF, VArPct_SF
    ]
    assert len(body) == 24
    return model(123, body)


def filler(model_id: int, length: int) -> list[int]:
    return model(model_id, [0xFFFF] * length)


def gen24_plus_float() -> list[int]:
    """Symo GEN24 Plus, float, 2 PV-Strings + Batterie (StCha 3 / StDisCha 4)."""
    return device(
        common("Fronius", "Symo GEN24 10.0 Plus", "1.36.5-1", "33333333"),
        inverter_113(evt1=0x0080 | 0x0400, evt_vnd=(0b010, 0b011, 0, 0)),
        nameplate_120(wh_rtg=10240, cha=10000),
        filler(121, 30), status_122(act_wh=12_345_679, ris=1500, ris_sf=3),
        controls_123(limit_pct=70, limit_ena=1),
        mppt_160([
            ("MPPT 1", 412, 4050, 1680, 1234567),
            ("MPPT 2", 398, 3980, 1590, 7654321),
            ("StCha 3", 0, 4800, 0, 111111),
            ("StDisCha 4", 300, 4800, 1440, 222222),
        ]),
        storage_124(),
    )


def datamanager_hybrid_int(
    dcw: int = 1000, evt_vnd: tuple[int, int, int, int] = (0, 0, 0, 0)
) -> list[int]:
    """Symo Hybrid am Datamanager, int+SF: String 1 = PV, String 2 = Speicher (Betrag)."""
    return device(
        common("Fronius", "Symo Hybrid 5.0-3-S", "1.13.1-1", "44444444"),
        inverter_103(dcw=dcw, evt_vnd=evt_vnd),
        nameplate_120(w_rtg=500, a_rtg=0xFFFF),
        filler(121, 30), status_122(), controls_123(),
        mppt_160([("String 1", 500, 4000, 2000, 0), ("String 2", 200, 4900, 1000, 0)]),
        storage_124(wchamax=5000, soc=8000, chast=4, grid=0),
    )


def gen24_float_no_battery() -> list[int]:
    return device(
        common("Fronius", "Primo GEN24 6.0", "1.36.5-1", "55555555"),
        inverter_113(phases=1),
        mppt_160([("MPPT 1", 412, 4050, 1680, 1), ("MPPT 2", 398, 3980, 1590, 1)]),
    )


def single_mppt_float() -> list[int]:
    """Wechselrichter mit nur einem DC-Eingang: DCA/DCV im Inverter-Model vorhanden."""
    inverter = inverter_113(phases=3)
    body = inverter[2:]
    body[32:34] = f(8.2)   # DCA
    body[34:36] = f(410.0)  # DCV
    return device(
        common("Fronius", "Tauro ECO 50-3-D", "1.36.5-1", "66666666"),
        model(113, body),
        mppt_160([("MPPT 1", 820, 4100, 3362, 1)]),
    )


# --- Smart Meter ------------------------------------------------------------


def meter_213(serial: str = "M0000001", power: float = -1500.0) -> list[int]:
    body = (
        f(12.0) + f(4.0) + f(4.1) + f(3.9)              # A, AphA-C
        + f(230.5) + f(230.0) + f(231.0) + f(230.5)     # PhV, PhVphA-C
        + f(399.0) + f(398.5) + f(399.5) + f(399.0)     # PPV, AB, BC, CA
        + f(50.0)                                       # Hz
        + f(power) + f(-500.0) + f(-600.0) + f(-400.0)   # W, WphA-C
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
        common("Fronius", "Smart Meter TS 65A-3", "1.3", serial, opt="<primary>"),
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


def fronius_registers(
    *,
    state_code: int = 0,
    site_power: int = 2000,
    day: int = 12_345,
    year: int = 1_234_567,
    total: int = 9_330_290,
) -> dict[int, int]:
    """Fronius-Register des Datamanagers (0-basierte Adressen)."""
    regs: dict[int, int] = {}

    def put(address: int, values: list[int]) -> None:
        for i, value in enumerate(values):
            regs[address + i] = value

    def u64(value: int) -> list[int]:
        return [(value >> s) & 0xFFFF for s in (48, 32, 16, 0)]

    put(211, [0, 0, state_code, 0, 1])  # F_Delete_Data … F_ModelType
    put(499, [site_power >> 16, site_power & 0xFFFF, *u64(day), *u64(year), *u64(total)])
    return regs


def build_registers(
    devices: dict[int, list[int] | tuple[list[int], dict[int, int]]],
) -> dict[int, dict[int, int]]:
    """devices: Unit-ID -> SunSpec-Register ab 40001, optional mit Zusatzregistern.

    Zusatzregister als {0-basierte Adresse: Wert}. Ergebnis: Unit-ID ->
    {0-basierte Adresse: Wert}.
    """
    units: dict[int, dict[int, int]] = {}
    for unit, spec in devices.items():
        sunspec_regs, extra = spec if isinstance(spec, tuple) else (spec, {})
        values = {40000 + i: v for i, v in enumerate(sunspec_regs)}
        values.update(extra)
        units[unit] = values
    return units


EXC_ILLEGAL_FUNCTION = 1
EXC_ILLEGAL_ADDRESS = 2
EXC_GATEWAY_NO_RESPONSE = 11


class FroniusSimulator:
    """Kleiner Modbus-TCP-Server mit mehreren Unit-IDs.

    Bewusst ohne den Server aus pymodbus: dessen Datastore-API und Verhalten
    ändern sich zwischen den Versionen, die Tests sollen aber mit jeder von
    Home Assistant vorgegebenen pymodbus-Version laufen. Unterstützt werden
    Read Holding Registers (0x03) und Write Multiple Registers (0x10).

    Verhalten wie ein echtes Gerät: nicht belegte Adressen → Exception 2
    (unzulässige Adresse), unbekannte Unit-ID → Exception 11 (Gateway: Zielgerät
    antwortet nicht).
    """

    def __init__(
        self, devices: dict[int, list[int] | tuple[list[int], dict[int, int]]]
    ) -> None:
        self.port = free_port()
        self.units = build_registers(devices)
        self._server = None
        self._writers: set = set()

    async def start(self) -> None:
        import asyncio

        self._server = await asyncio.start_server(
            self._handle, "127.0.0.1", self.port
        )

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        for writer in list(self._writers):
            writer.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle(self, reader, writer) -> None:
        import asyncio

        self._writers.add(writer)
        try:
            while True:
                header = await reader.readexactly(7)
                transaction, _, length, unit = struct.unpack(">HHHB", header)
                pdu = await reader.readexactly(length - 1)
                response = self._respond(unit, pdu)
                writer.write(
                    struct.pack(">HHHB", transaction, 0, len(response) + 1, unit)
                    + response
                )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._writers.discard(writer)
            writer.close()

    def _respond(self, unit: int, pdu: bytes) -> bytes:
        function = pdu[0]

        def error(code: int) -> bytes:
            return bytes([function | 0x80, code])

        registers = self.units.get(unit)
        if registers is None:
            return error(EXC_GATEWAY_NO_RESPONSE)
        if function == 0x03:
            address, count = struct.unpack(">HH", pdu[1:5])
            wanted = range(address, address + count)
            if not all(a in registers for a in wanted):
                return error(EXC_ILLEGAL_ADDRESS)
            return bytes([function, count * 2]) + struct.pack(
                f">{count}H", *(registers[a] for a in wanted)
            )
        if function == 0x10:
            address, count, _ = struct.unpack(">HHB", pdu[1:6])
            values = struct.unpack(f">{count}H", pdu[6 : 6 + count * 2])
            wanted = range(address, address + count)
            if not all(a in registers for a in wanted):
                return error(EXC_ILLEGAL_ADDRESS)
            registers.update(zip(wanted, values, strict=True))
            return bytes([function]) + struct.pack(">HH", address, count)
        return error(EXC_ILLEGAL_FUNCTION)
