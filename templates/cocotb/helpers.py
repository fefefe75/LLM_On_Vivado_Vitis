"""Helpers cocotb 2.x reutilisables - ecrits pour des agents LLM.

Copier ce fichier a cote du testbench, puis :

    from helpers import ClockReset, cycles, Scoreboard

Regles encodees ici (verifiees a l'execution avec cocotb 2.0.1 + GHDL 6.0.0) :
  1. Poser les entrees AVANT de relacher le reset, sinon tout est decale d'un cycle.
  2. Echantillonner une sortie sur front descendant, ou sur front montant puis
     `await ReadOnly()`. Jamais juste apres RisingEdge sans ReadOnly.
  3. Apres un `await ReadOnly()`, il faut AVANCER d'un evenement avant toute
     ecriture de signal, sinon :
     RuntimeError: Attempting settings a value during the ReadOnly phase.
  4. `Clock(clk, 10, unit="ns")` : le parametre s'appelle `unit` au singulier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer

# --------------------------------------------------------------------------- #
# Horloge + reset
# --------------------------------------------------------------------------- #


async def start_clock(clk, period_ns: float = 10.0) -> None:
    """Demarre une horloge en tache de fond. Front montant au milieu de periode."""
    cocotb.start_soon(Clock(clk, period_ns, unit="ns").start())


async def reset(dut, cycles_in_reset: int = 3, active_level: int = 1,
                rst_name: str = "i_rst") -> None:
    """Maintient le reset `cycles_in_reset` fronts, puis le relache.

    A appeler APRES avoir positionne toutes les autres entrees du DUT.
    """
    rst = getattr(dut, rst_name)
    rst.value = active_level
    for _ in range(cycles_in_reset):
        await RisingEdge(dut.i_clk)
    rst.value = 1 - active_level


async def cycles(dut, n: int = 1, sample_on_falling: bool = True) -> None:
    """Avance de `n` fronts d'horloge et laisse le DUT se stabiliser."""
    for _ in range(n):
        await RisingEdge(dut.i_clk)
        if sample_on_falling:
            await FallingEdge(dut.i_clk)


@dataclass
class ClockReset:
    """Horloge + reset en un seul appel : await ClockReset(dut).start()"""

    dut: Any
    period_ns: float = 10.0
    cycles_in_reset: int = 3
    rst_name: str = "i_rst"
    active_level: int = 1

    async def start(self) -> None:
        await start_clock(getattr(self.dut, "i_clk"), self.period_ns)
        await reset(self.dut, self.cycles_in_reset, self.active_level, self.rst_name)


# --------------------------------------------------------------------------- #
# Echantillonnage sur
# --------------------------------------------------------------------------- #


async def sample_now(dut) -> None:
    """Passe en phase read-only du pas de temps courant (lecture fiable).

    ATTENTION : apres cet appel, avancer d'un evenement avant toute ecriture.
    """
    await ReadOnly()


async def read_after_edge(dut, signal_name: str) -> int:
    """Lit un signal juste apres un front, en respectant les phases cocotb."""
    await RisingEdge(dut.i_clk)
    await ReadOnly()
    value = int(getattr(dut, signal_name).value)
    await FallingEdge(dut.i_clk)      # retour en phase d'ecriture
    return value


# --------------------------------------------------------------------------- #
# Bus : driver + monitor
# --------------------------------------------------------------------------- #


class BusDriver:
    """Pilote un bus synchrone simple (valide + donnee) et echantillonne les sorties.

    Exemple d'utilisation :
        drv = BusDriver(dut, valid="i_valid", data="i_data",
                        ready="o_ready", out="o_data")
        await drv.send(0xDEADBEEF)
        await drv.wait_ready()
    """

    def __init__(self, dut: Any, valid: str, data: str, ready: str | None = None,
                 out: str | None = None) -> None:
        self.dut = dut
        self.valid = getattr(dut, valid)
        self.data = getattr(dut, data)
        self.ready = getattr(dut, ready) if ready else None
        self.out = getattr(dut, out) if out else None
        self.sent: list[int] = []
        self.received: list[int] = []

    async def send(self, value: int, timeout_cycles: int = 100) -> None:
        """Positionne valide+donnee et attend un front ou le DUT les prend."""
        self.valid.value = 1
        self.data.value = value
        self.sent.append(int(value))
        for _ in range(timeout_cycles):
            await RisingEdge(self.dut.i_clk)
            if self.ready is None or int(self.ready.value) == 1:
                self.valid.value = 0
                self.data.value = 0
                return
        raise TimeoutError(f"bus jamais pret apres {timeout_cycles} cycles")

    async def wait_ready(self, timeout_cycles: int = 100) -> None:
        for _ in range(timeout_cycles):
            await RisingEdge(self.dut.i_clk)
            if int(self.ready.value) == 1:
                return
        raise TimeoutError("ready absent")


# --------------------------------------------------------------------------- #
# Scoreboard : modele de reference en Python
# --------------------------------------------------------------------------- #


@dataclass
class Scoreboard:
    """Compare les valeurs observees a un modele de reference Python.

    Utilisation :
        sb = Scoreboard("alu")
        sb.check(got=alu_out, expected=ref_model(a, b, op), ctx=f"op={op}")
        sb.report()   # leve une AssertionError si des erreurs ont ete vues
    """

    name: str = "dut"
    checks: int = 0
    errors: list[str] = field(default_factory=list)

    def check(self, got: int, expected: int, ctx: str = "") -> None:
        self.checks += 1
        if int(got) != int(expected):
            msg = f"[{self.name}] {ctx} attendu {expected} (0x{expected:x}), recu {got} (0x{got:x})"
            self.errors.append(msg)

    def check_equal(self, got: Any, expected: Any, ctx: str = "") -> None:
        self.checks += 1
        if got != expected:
            self.errors.append(f"[{self.name}] {ctx} attendu {expected!r}, recu {got!r}")

    def report(self, max_shown: int = 10) -> None:
        if self.errors:
            shown = "\n".join(self.errors[:max_shown])
            extra = "" if len(self.errors) <= max_shown else f"\n... +{len(self.errors) - max_shown} autres"
            raise AssertionError(
                f"{len(self.errors)} erreur(s) sur {self.checks} verifications :\n{shown}{extra}"
            )
        cocotb.log.info(f"[{self.name}] {self.checks} verifications OK")


# --------------------------------------------------------------------------- #
# Utilitaires divers
# --------------------------------------------------------------------------- #


def bits(value: int, width: int) -> int:
    """Tronque une valeur au nombre de bits du signal HDL."""
    return int(value) & ((1 << width) - 1)


def signed(value: int, width: int) -> int:
    """Interpretation signee (complement a deux) d'un entier de `width` bits."""
    value = bits(value, width)
    return value - (1 << width) if value & (1 << (width - 1)) else value


async def wait_ns(ns: float) -> None:
    """Attente temporelle (a preferer aux cycles quand le design est asynchrone)."""
    await Timer(ns, unit="ns")


def parametrize(values: Iterable[Any]) -> list[Any]:
    """Marqueur de lisibilite : les tests parametres se font avec une boucle
    et un sous-test, ou avec plusieurs @cocotb.test() generes dynamiquement."""
    return list(values)
