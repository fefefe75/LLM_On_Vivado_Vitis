"""Debug : ou en est le mini-GPU ? Accede aux signaux internes du design."""
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge

HERE = Path(__file__).parent
RTL = HERE.parent / "rtl"


def const(dut):
    """Lecture tolerante d'un interne (certains peuvent ne pas etre visibles)."""
    try:
        return int(dut.o_cfg_lanes.value)
    except Exception:
        return -1


@cocotb.test(timeout_time=60, timeout_unit="ms")
async def debug_progression(dut):
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    dut.i_rst.value = 1
    dut.i_start.value = 0
    dut.i_px_ready.value = 1
    for _ in range(5):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0
    await RisingEdge(dut.i_clk)

    dut.i_start.value = 1
    await RisingEdge(dut.i_clk)
    dut.i_start.value = 0

    lecture = lambda sig, nom: (int(getattr(dut, nom).value) if hasattr(dut, nom) else -1)
    for cycle in range(1, 200001):
        await RisingEdge(dut.i_clk)
        await ReadOnly()
        if cycle % 5000 == 0 or cycle < 12:
            try:
                s_issued = int(dut.s_issued.value)
            except Exception:
                s_issued = -999
            try:
                s_emitted = int(dut.s_emitted.value)
            except Exception:
                s_emitted = -999
            try:
                libres = str(dut.lane_free.value)
                finis = str(dut.lane_done.value)
                en_attente = str(dut.res_pending.value)
            except Exception as e:
                libres = finis = en_attente = f"<invisible: {e}>"
            dut._log.info(
                f"cycle {cycle:6d} | emis={s_issued} livres={s_emitted} "
                f"| valid={int(dut.o_px_valid.value)} done={int(dut.o_done.value)} "
                f"| lanes libres={libres} finis={finis} attente={en_attente}"
            )
        if int(dut.o_done.value) == 1:
            dut._log.info(f"RENDU TERMINE au cycle {cycle} (o_cycles={int(dut.o_cycles.value)})")
            return
    dut._log.error("PAS TERMINE apres 200000 cycles")
