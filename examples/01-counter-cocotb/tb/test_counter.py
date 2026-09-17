"""Exemple 01 - testbench cocotb 2.x d'un compteur synchrone.

Trois lecons encodees ici (elles sont verifiees a l'execution) :

 1. Positionner les ENTREES avant de relacher le reset : sinon le compteur est
    decale d'un cycle et le test echoue pour une raison qui n'a rien a voir avec
    le design.

 2. Lire une sortie juste apres `await RisingEdge()` renvoie l'ANCIENNE valeur
    (le DUT met a jour ses sorties apres le front). Deux idiomes corrects :
     A. echantillonner sur front descendant ;
     B. `await RisingEdge()` puis `await ReadOnly()`.

 3. Apres un `await ReadOnly()`, avancer d'un evenement avant toute ecriture de
    signal, sinon cocotb leve :
       RuntimeError: Attempting settings a value during the ReadOnly phase.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge


async def start_clock_and_reset(dut, cycles: int = 3):
    """Horloge 10 ns (100 MHz) + reset synchrone. Les entrees doivent deja
    avoir ete positionnees par l'appelant."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    dut.i_rst.value = 1
    for _ in range(cycles):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0


@cocotb.test()
async def test_comptage_et_gel(dut):
    """Idiome A : pilotage sur front montant, echantillonnage sur front descendant."""
    dut.i_en.value = 1
    await start_clock_and_reset(dut)

    for expected in range(1, 6):
        await RisingEdge(dut.i_clk)
        await FallingEdge(dut.i_clk)          # sortie stabilisee
        got = int(dut.o_count.value)
        assert got == expected, f"cycle {expected}: attendu {expected}, recu {got}"

    dut.i_en.value = 0
    for _ in range(3):
        await RisingEdge(dut.i_clk)
    await FallingEdge(dut.i_clk)
    assert int(dut.o_count.value) == 5, "le compteur doit geler quand i_en = 0"
    dut._log.info("comptage et gel OK")


@cocotb.test()
async def test_reset_synchrone(dut):
    """Idiome B : echantillonnage ReadOnly, remise a zero pendant le reset."""
    dut.i_en.value = 1
    await start_clock_and_reset(dut)

    for expected in range(1, 6):
        await RisingEdge(dut.i_clk)
        await ReadOnly()                      # sortie du DUT mise a jour
        got = int(dut.o_count.value)
        assert got == expected, f"cycle {expected}: attendu {expected}, recu {got}"
        await FallingEdge(dut.i_clk)          # retour en phase d'ecriture

    # Remise a zero : le reset doit etre MAINTENU pendant le front echantillonne,
    # sinon le compteur repart des le cycle suivant (i_en est toujours a 1).
    dut.i_rst.value = 1
    await RisingEdge(dut.i_clk)
    await ReadOnly()
    assert int(dut.o_count.value) == 0, "le reset synchrone doit remettre le compteur a 0"
    await FallingEdge(dut.i_clk)
    dut.i_rst.value = 0
    dut._log.info("reset synchrone OK")


@cocotb.test()
async def test_debordement(dut):
    """Le compteur 8 bits doit reboucler naturellement apres 256 impulsions."""
    dut.i_en.value = 1
    await start_clock_and_reset(dut)

    for expected in range(1, 256):
        await RisingEdge(dut.i_clk)
        await FallingEdge(dut.i_clk)
        assert int(dut.o_count.value) == expected, f"attendu {expected}"

    await RisingEdge(dut.i_clk)          # 256e impulsion : debordement
    await FallingEdge(dut.i_clk)
    assert int(dut.o_count.value) == 0, "le compteur doit reboucler a 0 apres 255"
    dut._log.info("debordement OK (rebouclage 255 -> 0)")
