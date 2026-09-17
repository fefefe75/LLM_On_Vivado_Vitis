"""Testbench cocotb 2.x de la FIFO synchrone générique (fifo_sync.vhd).

Vérifie :
  * l'état vide après reset (o_empty=1, o_full=0, o_level=0) ;
  * le remplissage complet jusqu'à o_full ;
  * le débordement ignoré (écriture quand plein) ;
  * l'ordre FIFO des lectures (mode standard, pas de first-word-fall-through) ;
  * le vidage complet jusqu'à o_empty ;
  * la lecture quand la FIFO est vide (ignorée, pointeur de lecture intact) ;
  * écriture et lecture simultanées ;
  * un test aléatoire à graine fixe, croisant écritures et lectures, comparé à
    un modèle de référence Python (collections.deque), valeur par valeur.

Protocole de pilotage (important en VHDL / VHPI) :
  les entrées sont appliquées juste après un front descendant ; les sorties sont
  échantillonnées au front descendant suivant. Le front montant situé entre les
  deux est celui qui a enregistré les entrées, et l'échantillonnage se fait une
  demi-période plus tard, quand tous les cycles delta sont terminés et que les
  sorties (registres + sorties combinatoires issues du compteur) sont stables.
  Cette méthode évite d'attendre ReadOnly, après lequel toute écriture exige
  d'avancer d'un événement.
"""

import random
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

# Période d'horloge en ns (100 MHz)
CLK_PERIOD_NS = 10

# Graine du test aléatoire : fixe, pour que la simulation soit reproductible
RANDOM_SEED = 20260917

# Nombre de cycles du test aléatoire
RANDOM_CYCLES = 2000


def dut_shape(dut):
    """Déduit (largeur de mot, profondeur) des ports de la FIFO.

    Largeurs lues sur les ports plutôt que codées en dur : le test suit
    automatiquement C_WDATA / C_DEPTH. L'invariant du RTL est
    C_DEPTH = 2**(largeur de o_level - 1) (vérifié par assertion à l'élaboration).
    """
    wdata = len(dut.i_data)
    level_w = len(dut.o_level)
    depth = 1 << (level_w - 1)
    return wdata, depth


class FifoDriver:
    """Pilote synchrone de la FIFO : applique les entrées, échantillonne les sorties."""

    def __init__(self, dut):
        self.dut = dut

    async def start_clock(self):
        """Démarre l'horloge sur i_clk."""
        cocotb.start_soon(Clock(self.dut.i_clk, CLK_PERIOD_NS, unit="ns").start())

    def _drive(self, wr_en, rd_en, data):
        self.dut.i_wr_en.value = wr_en
        self.dut.i_rd_en.value = rd_en
        self.dut.i_data.value = data

    def _sample(self):
        return {
            "data": int(self.dut.o_data.value),
            "full": int(self.dut.o_full.value),
            "empty": int(self.dut.o_empty.value),
            "level": int(self.dut.o_level.value),
        }

    async def reset(self):
        """Assertion puis relâchement du reset ; les entrées sont posées AVANT le relâchement.

        Retourne l'état échantillonné pendant que le reset est encore actif.
        """
        await FallingEdge(self.dut.i_clk)
        self.dut.i_rst.value = 1
        self._drive(0, 0, 0)
        await FallingEdge(self.dut.i_clk)   # le front montant a appliqué le reset
        state = self._sample()
        self.dut.i_rst.value = 0            # relâchement une demi-période avant le front suivant
        return state

    async def step(self, wr_en=0, rd_en=0, data=0):
        """Un cycle : applique les entrées, attend le front descendant, lit les sorties."""
        self._drive(wr_en, rd_en, data)
        await FallingEdge(self.dut.i_clk)
        return self._sample()


async def setup(dut):
    """Démarre l'horloge et sort du reset. Retourne (pilote, largeur, profondeur)."""
    wdata, depth = dut_shape(dut)
    drv = FifoDriver(dut)
    await drv.start_clock()
    state = await drv.reset()
    # état vide attendu juste après le reset
    assert state["empty"] == 1, f"o_empty doit valoir 1 après reset, lu {state['empty']}"
    assert state["full"] == 0, f"o_full doit valoir 0 après reset, lu {state['full']}"
    assert state["level"] == 0, f"o_level doit valoir 0 après reset, lu {state['level']}"
    return drv, wdata, depth


def pattern(value, wdata):
    """Mot de test déterministe."""
    return value & ((1 << wdata) - 1)


def valeur_absente(ecrits, wdata, depart=1):
    """Première valeur (>= depart) absente de l'ensemble `ecrits` (mot témoin)."""
    candidat = depart
    while pattern(candidat, wdata) in ecrits:
        candidat += 1
    return pattern(candidat, wdata)


@cocotb.test()
async def test_reset_etat_vide(dut):
    """Après reset : FIFO vide, non pleine, niveau nul."""
    drv, wdata, depth = await setup(dut)
    dut._log.info(f"FIFO vérifiée : {wdata} bits de données, profondeur {depth}")

    # la FIFO reste vide tant qu'aucune écriture n'est demandée
    state = await drv.step()
    assert state["empty"] == 1 and state["full"] == 0 and state["level"] == 0, state


@cocotb.test()
async def test_remplissage_jusqu_a_full(dut):
    """Remplissage complet : o_level suit le nombre d'écritures, o_full monte à la fin."""
    drv, wdata, depth = await setup(dut)

    for i in range(depth):
        state = await drv.step(wr_en=1, data=pattern(i, wdata))
        assert state["level"] == i + 1, f"niveau {state['level']} au lieu de {i + 1}"
        assert state["empty"] == 0, "la FIFO ne doit pas être vide pendant le remplissage"
        assert state["full"] == (1 if i + 1 == depth else 0), (
            f"o_full={state['full']} pour un niveau de {i + 1} sur {depth}"
        )

    # un cycle sans demande ne change rien
    state = await drv.step()
    assert state["full"] == 1 and state["level"] == depth, state


@cocotb.test()
async def test_debordement_ignore(dut):
    """Écriture sur FIFO pleine : ignorée (le mot n'entre pas, rien n'est écrasé)."""
    drv, wdata, depth = await setup(dut)

    for i in range(depth):
        await drv.step(wr_en=1, data=pattern(i + 1, wdata))

    # valeur absente du motif écrit (robuste quelle que soit la largeur de mot)
    sentinelle = valeur_absente({pattern(i + 1, wdata) for i in range(depth)}, wdata, depth + 1)

    # trois tentatives d'écriture sur FIFO pleine
    for _ in range(3):
        state = await drv.step(wr_en=1, data=sentinelle)
        assert state["full"] == 1, "la FIFO doit rester pleine"
        assert state["level"] == depth, f"niveau {state['level']} au lieu de {depth}"

    # la lecture doit rendre le motif d'origine, sans la valeur de débordement
    for i in range(depth):
        state = await drv.step(rd_en=1)
        attendu = pattern(i + 1, wdata)
        assert state["data"] == attendu, (
            f"lecture {i} : 0x{state['data']:X} au lieu de 0x{attendu:X} "
            "(le mot écrit sur FIFO pleine a été accepté ?)"
        )
    state = await drv.step()
    assert state["empty"] == 1 and state["level"] == 0, state


@cocotb.test()
async def test_vidage_et_ordre_fifo(dut):
    """Les mots ressortent dans l'ordre d'entrée (mode standard, lecture enregistrée)."""
    drv, wdata, depth = await setup(dut)

    valeurs = [pattern(0x10 + i, wdata) for i in range(depth)]
    for v in valeurs:
        await drv.step(wr_en=1, data=v)

    for i, attendu in enumerate(valeurs):
        state = await drv.step(rd_en=1)
        assert state["data"] == attendu, (
            f"lecture {i} : 0x{state['data']:X} au lieu de 0x{attendu:X} (ordre FIFO rompu)"
        )
        assert state["level"] == depth - (i + 1), (
            f"niveau {state['level']} au lieu de {depth - (i + 1)}"
        )
        assert state["empty"] == (1 if i + 1 == depth else 0), (
            "o_empty doit monter au dernier mot lu"
        )

    # vidée : o_data conserve le dernier mot lu (mode standard)
    state = await drv.step()
    assert state["empty"] == 1 and state["full"] == 0 and state["level"] == 0
    assert state["data"] == valeurs[-1], (
        "o_data doit conserver le dernier mot lu après vidage"
    )


@cocotb.test()
async def test_lecture_quand_vide(dut):
    """Lecture sur FIFO vide : ignorée, le pointeur de lecture reste sur le premier mot."""
    drv, wdata, depth = await setup(dut)

    for _ in range(4):
        state = await drv.step(rd_en=1)
        assert state["empty"] == 1, "la FIFO doit rester vide"
        assert state["level"] == 0, f"niveau {state['level']} au lieu de 0"
        assert state["full"] == 0, "la FIFO ne doit pas devenir pleine"

    # les lectures refusées n'ont pas déplacé le pointeur : l'ordre est intact
    valeurs = [pattern(0xA0 + i, wdata) for i in range(3)]
    for v in valeurs:
        await drv.step(wr_en=1, data=v)
    for i, attendu in enumerate(valeurs):
        state = await drv.step(rd_en=1)
        assert state["data"] == attendu, (
            f"lecture {i} : 0x{state['data']:X} au lieu de 0x{attendu:X} "
            "(pointeur de lecture déplacé par une lecture à vide ?)"
        )


@cocotb.test()
async def test_ecriture_et_lecture_simultanees(dut):
    """Écriture et lecture dans le même cycle.

    Cas 1 (FIFO partiellement remplie) : les deux demandes sont acceptées,
    o_level ne change pas, le mot écrit part en queue.
    Cas 2 (FIFO pleine) : o_full est un verrou dur, l'écriture est refusée même
    si une lecture a lieu dans le même cycle ; le mot refusé n'apparaît jamais.
    """
    drv, wdata, depth = await setup(dut)

    demi = max(1, depth // 2)
    valeurs = [pattern(0x30 + i, wdata) for i in range(demi)]
    for v in valeurs:
        await drv.step(wr_en=1, data=v)

    # --- cas 1 : une entrée, une sortie dans le même cycle ---
    nouveau = valeur_absente(set(valeurs), wdata, 0x80)
    state = await drv.step(wr_en=1, rd_en=1, data=nouveau)
    assert state["data"] == valeurs[0], (
        f"0x{state['data']:X} lu au lieu de 0x{valeurs[0]:X}"
    )
    assert state["level"] == demi, "le niveau ne doit pas changer (une entrée, une sortie)"
    assert state["full"] == 0 and state["empty"] == 0, state

    for i in range(1, demi):
        state = await drv.step(rd_en=1)
        assert state["data"] == valeurs[i], (
            f"lecture {i} : 0x{state['data']:X} au lieu de 0x{valeurs[i]:X}"
        )
    state = await drv.step(rd_en=1)
    assert state["data"] == nouveau, "le mot écrit pendant la lecture simultanée doit être en queue"
    state = await drv.step()
    assert state["empty"] == 1 and state["level"] == 0, state

    # --- cas 2 : pleine, écriture refusée même avec une lecture simultanée ---
    motif = [pattern(i + 1, wdata) for i in range(depth)]
    for v in motif:
        await drv.step(wr_en=1, data=v)
    refuse = valeur_absente(set(motif), wdata, depth + 1)

    state = await drv.step(wr_en=1, rd_en=1, data=refuse)
    assert state["data"] == motif[0], (
        f"0x{state['data']:X} lu au lieu de 0x{motif[0]:X}"
    )
    assert state["level"] == depth - 1, (
        f"niveau {state['level']} : seule la lecture doit être acceptée (plein, verrou dur)"
    )
    assert state["full"] == 0, "o_full doit retomber après la lecture"

    for i in range(1, depth):
        state = await drv.step(rd_en=1)
        assert state["data"] == motif[i], (
            f"lecture {i} : 0x{state['data']:X} au lieu de 0x{motif[i]:X}"
        )
        assert state["data"] != refuse, "le mot refusé (écriture sur FIFO pleine) a été stocké"
    state = await drv.step()
    assert state["empty"] == 1 and state["level"] == 0, state


@cocotb.test()
async def test_aleatoire_modele_deque(dut):
    """Test aléatoire à graine fixe, comparé à un modèle Python (collections.deque).

    À chaque cycle, les entrées sont tirées au hasard ; à chaque lecture acceptée
    par le modèle, la valeur lue sur o_data est comparée à la valeur prédite.
    Drapeaux o_full / o_empty / o_level sont aussi comparés au modèle.
    """
    drv, wdata, depth = await setup(dut)

    rng = random.Random(RANDOM_SEED)
    modele = deque()          # mots attendus, dans l'ordre FIFO
    prochain = 0              # compteur de mots écrits (motif unique)
    lectures = 0
    ecritures = 0
    debordements = 0
    lectures_a_vide = 0

    for cycle in range(RANDOM_CYCLES):
        wr_en = rng.random() < 0.5
        rd_en = rng.random() < 0.5
        mot = pattern(prochain, wdata)

        wr_ok = wr_en and len(modele) < depth
        rd_ok = rd_en and len(modele) > 0

        if wr_ok:
            modele.append(mot)
            prochain += 1
            ecritures += 1
        elif wr_en:
            debordements += 1

        attendu = None
        if rd_ok:
            attendu = modele.popleft()
            lectures += 1
        elif rd_en:
            lectures_a_vide += 1

        state = await drv.step(wr_en=1 if wr_en else 0, rd_en=1 if rd_en else 0, data=mot)

        # comparaison valeur par valeur de chaque lecture effectuée
        if attendu is not None:
            assert state["data"] == attendu, (
                f"cycle {cycle} : 0x{state['data']:X} lu au lieu de 0x{attendu:X}"
            )

        # comparaison des drapeaux et du niveau avec le modèle
        assert state["level"] == len(modele), (
            f"cycle {cycle} : o_level={state['level']} au lieu de {len(modele)}"
        )
        assert state["full"] == (1 if len(modele) == depth else 0), (
            f"cycle {cycle} : o_full={state['full']} pour un niveau de {len(modele)}"
        )
        assert state["empty"] == (1 if len(modele) == 0 else 0), (
            f"cycle {cycle} : o_empty={state['empty']} pour un niveau de {len(modele)}"
        )

    # vidage final : tout ce qui reste doit sortir dans l'ordre du modèle
    restant = len(modele)
    for i in range(restant):
        attendu = modele.popleft()
        state = await drv.step(rd_en=1)
        assert state["data"] == attendu, (
            f"vidage final {i} : 0x{state['data']:X} au lieu de 0x{attendu:X}"
        )
    state = await drv.step()
    assert state["empty"] == 1 and state["level"] == 0, state

    dut._log.info(
        f"graine={RANDOM_SEED} cycles={RANDOM_CYCLES} ecritures={ecritures} "
        f"lectures={lectures} debordements_ignores={debordements} "
        f"lectures_a_vide_ignorees={lectures_a_vide}"
    )
