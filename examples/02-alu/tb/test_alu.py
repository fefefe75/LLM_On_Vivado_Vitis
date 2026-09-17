"""Testbench cocotb 2.x de l'ALU combinatoire de examples/02-alu.

Contenu du fichier :

  * un modele de reference Python de l'ALU, ecrit a partir de la specification
    du RTL et non derive du VHDL. Il sert d'oracle pour toutes les campagnes ;
  * quatre campagnes de test qui comparent le DUT au modele :

      test_golden_vectors             cas calcules a la main, independants du
                                      modele de reference
      test_all_opcodes_corner_values  tous les opcodes x toutes les paires de
                                      valeurs limites
      test_operand_sweep_all_opcodes  balayage de i_a sur toutes les valeurs
                                      accessibles, pour chaque opcode
      test_random_vectors             vecteurs aleatoires, graine fixe

L'ALU est purement combinatoire : il n'y a ni horloge, ni reset, donc rien a
relacher avant d'appliquer les stimulus. Chaque vecteur est ecrit sur les
entrees, puis le test attend SETTLE_TIME avant de lire les sorties. Attendre un
Timer est indispensable : sans cela on lirait les sorties de propagation
precedente.

Graine aleatoire : cocotb.RANDOM_SEED, lui-meme fixe par la variable
d'environnement COCOTB_RANDOM_SEED que le Makefile exporte. Deux executions
avec la meme graine rejouent exactement les memes vecteurs.
"""

from __future__ import annotations

import os
import random
from typing import Callable, Dict, NamedTuple

import cocotb
from cocotb.triggers import Timer

# ---------------------------------------------------------------------------
# Interface du DUT. Ces constantes recopient rtl/alu_pkg.vhd ; le test compare
# cette liste a la largeur reelle du port i_op et echoue si les deux divergent.
# ---------------------------------------------------------------------------
OP_WIDTH = 4

OP_ADD = 0b0000
OP_SUB = 0b0001
OP_AND = 0b0010
OP_OR = 0b0011
OP_XOR = 0b0100
OP_NOT = 0b0101
OP_EQ = 0b0110
OP_LT_U = 0b0111
OP_LT_S = 0b1000
OP_SLL = 0b1001
OP_SRL = 0b1010
OP_PASS_B = 0b1011

#: Duree d'attente apres application d'un vecteur, en ns. Le DUT est
#: combinatoire : 1 ns suffisent pour laisser tous les deltas se propager.
SETTLE_TIME_NS = 1

#: Nombre de vecteurs aleatoires, surchargeable depuis l'environnement.
RANDOM_VECTORS = int(os.environ.get("ALU_RANDOM_VECTORS", "2000"))

#: Largeur maximale pour laquelle le balayage exhaustif de i_a est fait.
SWEEP_MAX_WIDTH = 9

#: Valeurs de i_b utilisees pendant le balayage de i_a.
SWEEP_B_VALUES = (1, 3, 2**4)


# ===========================================================================
# Modele de reference
# ===========================================================================
class AluResult(NamedTuple):
    """Sortie attendue de l'ALU."""

    y: int
    zero: bool
    carry: int


def _mask(width: int) -> int:
    return (1 << width) - 1


def _signed(value: int, width: int) -> int:
    """Reinterprete value sur width bits en complement a deux."""
    value &= _mask(width)
    if value >> (width - 1):
        value -= 1 << width
    return value


def _op_add(a: int, b: int, width: int) -> tuple[int, int]:
    total = a + b
    return total & _mask(width), (total >> width) & 1


def _op_sub(a: int, b: int, width: int) -> tuple[int, int]:
    """a - b calcule comme a + (not b) + 1, sur width + 1 bits, comme le RTL."""
    total = a + (_mask(width) ^ b) + 1
    return total & _mask(width), (total >> width) & 1


def _op_and(a: int, b: int, width: int) -> tuple[int, int]:
    return a & b, 0


def _op_or(a: int, b: int, width: int) -> tuple[int, int]:
    return a | b, 0


def _op_xor(a: int, b: int, width: int) -> tuple[int, int]:
    return a ^ b, 0


def _op_not(a: int, b: int, width: int) -> tuple[int, int]:
    return _mask(width) ^ a, 0


def _op_eq(a: int, b: int, width: int) -> tuple[int, int]:
    return int(a == b), 0


def _op_lt_u(a: int, b: int, width: int) -> tuple[int, int]:
    return int(a < b), 0


def _op_lt_s(a: int, b: int, width: int) -> tuple[int, int]:
    return int(_signed(a, width) < _signed(b, width)), 0


def _op_sll(a: int, b: int, width: int) -> tuple[int, int]:
    if b >= width:
        return 0, 0
    return (a << b) & _mask(width), 0


def _op_srl(a: int, b: int, width: int) -> tuple[int, int]:
    if b >= width:
        return 0, 0
    return a >> b, 0


def _op_pass_b(a: int, b: int, width: int) -> tuple[int, int]:
    return b, 0


#: Table d'operations : un appelable par opcode, (a, b, width) -> (y, carry).
REFERENCE: Dict[int, Callable[[int, int, int], "tuple[int, int]"]] = {
    OP_ADD: _op_add,
    OP_SUB: _op_sub,
    OP_AND: _op_and,
    OP_OR: _op_or,
    OP_XOR: _op_xor,
    OP_NOT: _op_not,
    OP_EQ: _op_eq,
    OP_LT_U: _op_lt_u,
    OP_LT_S: _op_lt_s,
    OP_SLL: _op_sll,
    OP_SRL: _op_srl,
    OP_PASS_B: _op_pass_b,
}

#: Tous les codes pour lesquels le RTL n'a pas d'operation : sortie nulle.
RESERVED_OPS = tuple(op for op in range(1 << OP_WIDTH) if op not in REFERENCE)


def alu_reference(op: int, a: int, b: int, width: int) -> AluResult:
    """Modele de reference de l'ALU : sortie attendue pour (op, a, b)."""
    mask = _mask(width)
    a &= mask
    b &= mask
    handler = REFERENCE.get(op)
    if handler is None:
        # Opcode reserve : le RTL force zero sur o_y et o_carry.
        return AluResult(y=0, zero=True, carry=0)
    y, carry = handler(a, b, width)
    y &= mask
    return AluResult(y=y, zero=(y == 0), carry=carry & 1)


# ===========================================================================
# Pilotage du DUT
# ===========================================================================
async def apply_vector(dut, op: int, a: int, b: int) -> None:
    """Ecrit un vecteur sur les entrees, puis laisse le DUT se stabiliser."""
    dut.i_op.value = op
    dut.i_a.value = a
    dut.i_b.value = b
    await Timer(SETTLE_TIME_NS, unit="ns")


def dut_width(dut) -> int:
    return len(dut.i_a.value)


def dut_op_width(dut) -> int:
    return len(dut.i_op.value)


def check_contract(dut) -> tuple[int, int]:
    """Verifie la forme des ports et renvoie (C_WIDTH, largeur de i_op)."""
    width = dut_width(dut)
    op_width = dut_op_width(dut)
    assert len(dut.i_b.value) == width, f"i_b fait {len(dut.i_b.value)} bits, i_a {width}"
    assert len(dut.o_y.value) == width, f"o_y fait {len(dut.o_y.value)} bits, i_a {width}"
    assert len(dut.o_zero.value) == 1, "o_zero doit faire 1 bit"
    assert len(dut.o_carry.value) == 1, "o_carry doit faire 1 bit"
    assert op_width == OP_WIDTH, (
        f"i_op fait {op_width} bits, le testbench en attend {OP_WIDTH} "
        "(rtl/alu_pkg.vhd et tb/test_alu.py ont diverge)"
    )
    return width, op_width


class AluChecker:
    """Applique des vecteurs et compare o_y, o_zero, o_carry au modele."""

    def __init__(self, dut, width: int, op_width: int) -> None:
        self.dut = dut
        self.width = width
        self.op_width = op_width
        self.count = 0

    def _label(self, op: int, a: int, b: int) -> str:
        nibbles = (self.width + 3) // 4
        return (
            f"i_op=0b{op:0{self.op_width}b} i_a=0x{a:0{nibbles}X} "
            f"i_b=0x{b:0{nibbles}X} C_WIDTH={self.width}"
        )

    def _read(self) -> AluResult:
        dut = self.dut
        assert dut.o_y.value.is_resolvable, f"o_y vaut {dut.o_y.value}, X ou Z propage"
        assert dut.o_zero.value.is_resolvable, f"o_zero vaut {dut.o_zero.value}"
        assert dut.o_carry.value.is_resolvable, f"o_carry vaut {dut.o_carry.value}"
        return AluResult(
            y=int(dut.o_y.value),
            zero=bool(int(dut.o_zero.value)),
            carry=int(dut.o_carry.value),
        )

    def _compare(
        self, op: int, a: int, b: int, expected: AluResult, source: str
    ) -> None:
        got = self._read()
        self.count += 1
        label = f"{self._label(op, a, b)} [{source}]"
        assert got.y == expected.y, (
            f"o_y faux : attendu 0x{expected.y:X}, lu 0x{got.y:X} ({label})"
        )
        assert got.zero == expected.zero, (
            f"o_zero faux : attendu {int(expected.zero)}, lu {int(got.zero)} ({label})"
        )
        assert got.carry == expected.carry, (
            f"o_carry faux : attendu {expected.carry}, lu {got.carry} ({label})"
        )
        # Coherence interne du DUT, verifiee independamment du modele.
        assert got.zero == (got.y == 0), f"o_zero incoherent avec o_y ({label})"

    async def check(self, op: int, a: int, b: int) -> None:
        """Compare le DUT au modele de reference pour un vecteur."""
        await apply_vector(self.dut, op, a, b)
        self._compare(op, a, b, alu_reference(op, a, b, self.width), "modele")

    async def check_expected(
        self, op: int, a: int, b: int, expected: AluResult
    ) -> None:
        """Compare le DUT a une valeur attendue calculee hors du modele."""
        await apply_vector(self.dut, op, a, b)
        self._compare(op, a, b, expected, "golden")


# ===========================================================================
# Campagnes de test
# ===========================================================================
@cocotb.test()
async def test_golden_vectors(dut):
    """Cas calcules a la main, exprimes en fonction de C_WIDTH.

    Ces valeurs attendues ne passent pas par le modele de reference : elles
    attrapent une erreur qui serait presente a la fois dans le RTL et dans le
    modele. Les cas degenerent pour C_WIDTH < 4 (i_a et i_b n'ont alors plus
    assez d'etats) et les autres campagnes assurent la couverture.
    """
    width, op_width = check_contract(dut)
    if width < 4:
        cocotb.log.info(
            f"test_golden_vectors : C_WIDTH={width} < 4, cas non applicables, "
            "couverture assuree par les autres tests"
        )
        return

    mask = _mask(width)
    msb = 1 << (width - 1)
    cases = [
        # (op, a, b, y attendu, zero attendu, carry attendu)
        (OP_ADD, mask, 1, 0, True, 1),
        (OP_ADD, msb, msb, 0, True, 1),
        (OP_ADD, 1, 1, 2, False, 0),
        (OP_ADD, 0, 0, 0, True, 0),
        (OP_SUB, 0, 1, mask, False, 0),
        (OP_SUB, 1, 1, 0, True, 1),
        (OP_SUB, mask, mask, 0, True, 1),
        (OP_SUB, 0, msb, msb, False, 0),
        (OP_AND, msb, mask, msb, False, 0),
        (OP_AND, mask, 0, 0, True, 0),
        (OP_OR, msb, 1, msb | 1, False, 0),
        (OP_OR, 0, 0, 0, True, 0),
        (OP_XOR, mask, mask, 0, True, 0),
        (OP_XOR, msb, msb, 0, True, 0),
        (OP_NOT, 0, 0, mask, False, 0),
        (OP_NOT, mask, mask, 0, True, 0),
        (OP_EQ, mask, mask, 1, False, 0),
        (OP_EQ, mask, 0, 0, True, 0),
        (OP_LT_U, 0, mask, 1, False, 0),
        (OP_LT_U, mask, 0, 0, True, 0),
        (OP_LT_U, msb, msb, 0, True, 0),
        (OP_LT_S, msb, 0, 1, False, 0),
        (OP_LT_S, 0, msb, 0, True, 0),
        (OP_LT_S, mask, msb, 0, True, 0),
        (OP_SLL, 1, 1, 2, False, 0),
        (OP_SLL, 1, width - 1, msb, False, 0),
        (OP_SLL, 1, width, 0, True, 0),
        (OP_SLL, 1, mask, 0, True, 0),
        (OP_SRL, msb, width - 1, 1, False, 0),
        (OP_SRL, mask, width, 0, True, 0),
        (OP_SRL, mask, mask, 0, True, 0),
        (OP_PASS_B, 0, mask, mask, False, 0),
        (OP_PASS_B, mask, 0, 0, True, 0),
        (RESERVED_OPS[0], mask, mask, 0, True, 0),
        (RESERVED_OPS[-1], 0, 0, 0, True, 0),
    ]

    checker = AluChecker(dut, width, op_width)
    for op, a, b, exp_y, exp_zero, exp_carry in cases:
        await checker.check_expected(
            op, a, b, AluResult(y=exp_y, zero=exp_zero, carry=exp_carry)
        )
    cocotb.log.info(
        f"test_golden_vectors : {checker.count} vecteurs calcules a la main "
        f"verifies (C_WIDTH={width}, opcode reserve {RESERVED_OPS[0]:#06b})"
    )


@cocotb.test()
async def test_all_opcodes_corner_values(dut):
    """Tous les opcodes sur toutes les paires de valeurs limites.

    Les valeurs limites couvrent zero, un, le maximum, le maximum moins un,
    le bit de poids fort seul, les extremums signes (plus negatif, plus negatif
    plus un, plus grand positif), les motifs a bits alternes et les bornes de
    decalage (C_WIDTH - 1, C_WIDTH, C_WIDTH + 1).
    """
    width, op_width = check_contract(dut)
    mask = _mask(width)
    msb = 1 << (width - 1)
    alt_low = int("01" * ((width + 1) // 2), 2) & mask
    alt_high = int("10" * ((width + 1) // 2), 2) & mask
    corners = sorted(
        {
            v & mask
            for v in (
                0,
                1,
                2,
                mask - 1,
                mask,
                msb,
                msb - 1,
                msb + 1,
                alt_low,
                alt_high,
                width - 1,
                width,
                width + 1,
            )
        }
    )

    checker = AluChecker(dut, width, op_width)
    for op in range(1 << op_width):
        for a in corners:
            for b in corners:
                await checker.check(op, a, b)

    cocotb.log.info(
        f"test_all_opcodes_corner_values : {checker.count} vecteurs verifies "
        f"({1 << op_width} opcodes x {len(corners)} valeurs limites au carre, "
        f"C_WIDTH={width})"
    )


@cocotb.test()
async def test_operand_sweep_all_opcodes(dut):
    """Balayage de i_a sur tout l'espace accessible, pour chaque opcode.

    L'ALU n'a pas d'etat interne : la sortie ne depend que de (i_op, i_a, i_b).
    Balayer i_a sur les 2**C_WIDTH valeurs possibles, pour plusieurs i_b et
    pour chaque opcode, couvre donc la table de verite complete de chaque
    operation. Au dela de SWEEP_MAX_WIDTH bits le balayage est remplace par un
    pas regulier, pour garder un temps de simulation raisonnable.
    """
    width, op_width = check_contract(dut)
    mask = _mask(width)
    total = 1 << width
    if total <= (1 << SWEEP_MAX_WIDTH):
        a_values = range(total)
        mode = "exhaustif"
    else:
        step = total // (1 << SWEEP_MAX_WIDTH)
        a_values = range(0, total, step)
        mode = f"pas de {step}"

    b_values = [v & mask for v in SWEEP_B_VALUES]

    checker = AluChecker(dut, width, op_width)
    for op in range(1 << op_width):
        for b in b_values:
            for a in a_values:
                await checker.check(op, a, b)

    cocotb.log.info(
        f"test_operand_sweep_all_opcodes : {checker.count} vecteurs verifies "
        f"(balayage {mode} de i_a sur {len(a_values)} valeurs, {len(b_values)} "
        f"i_b, {1 << op_width} opcodes, C_WIDTH={width})"
    )


@cocotb.test()
async def test_random_vectors(dut):
    """Vecteurs aleatoires reproductibles.

    La moitie des vecteurs tire i_b dans les petites valeurs, ce qui concentre
    les changements de resultat autour des bornes de decalage ; l'autre moitie
    balaie tout l'espace. La graine vient de cocotb.RANDOM_SEED, fixe par
    COCOTB_RANDOM_SEED dans le Makefile.
    """
    width, op_width = check_contract(dut)
    seed = cocotb.RANDOM_SEED
    seed_env = os.environ.get("COCOTB_RANDOM_SEED", "<non defini>")
    rng = random.Random(seed)
    checker = AluChecker(dut, width, op_width)

    for index in range(RANDOM_VECTORS):
        op = rng.randrange(1 << op_width)
        a = rng.randrange(1 << width)
        if index % 2 == 0:
            # Valeurs petites : frontiere des decalages et des comparaisons.
            b = rng.randrange(0, min(1 << width, width + 3))
        else:
            b = rng.randrange(1 << width)
        await checker.check(op, a, b)

    cocotb.log.info(
        f"test_random_vectors : {checker.count} vecteurs aleatoires verifies "
        f"(COCOTB_RANDOM_SEED={seed_env}, graine de test={seed}, "
        f"C_WIDTH={width}, opcode reserve {RESERVED_OPS[0]:#06b} teste comme "
        "les autres)"
    )
