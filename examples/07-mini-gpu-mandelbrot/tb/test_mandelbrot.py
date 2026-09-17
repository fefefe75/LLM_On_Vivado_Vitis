"""Banc de test cocotb du mini-GPU SIMT (exemple 07).

Ce que ce test prouve, et comment :

1. CORRECTION : chaque pixel calcule par le materiel est compare a un modele de
   reference Python qui refait le MEME calcul virgule fixe, operation par operation
   (y compris les debordements 32 bits). Ce n'est pas une approximation : c'est une
   comparaison d'egalite exacte sur les 6144/76800 pixels.
2. PARALLELISME : le test mesure les cycles reels du rendu et calcule le travail
   total en "cycles-lane" a partir des resultats (3 cycles par iteration + 2). Le
   rapport des deux donne l'efficacite parallele REELLE, et donc la perte due a la
   divergence -- exactement la metrique qui fait mal a un GPU.
3. SORTIE VISUELLE : l'image calculee par le RTL est ecrite en .ppm et .png (oracle
   visuel immediat : si le materiel se trompait, l'image serait fausse).

Conventions de lecture (voir docs/04-cocotb-recipes.md) : on echantillonne apres
`ReadOnly()` pour ne pas lire une sortie enregistree avant la fin des cycles delta ;
les entrees sont posees avant le front.

Reproductible : aucun aleatoire, tout est deterministe.
"""

import os
import struct
import zlib
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

# ----------------------------------------------------------------------------- 
# Modele de reference : meme arithmetique que le VHDL, en Python
# -----------------------------------------------------------------------------

# Le format Q n'est PAS fige dans ce test : le design l'annonce sur son port
# `o_cfg_frac`, et tous les calculs de reference s'y adaptent. Un test qui suppose
# le format au lieu de le lire est un test qui se trompe silencieusement le jour ou
# le RTL change de format.
MOD32 = 1 << 32


def i32(valeur: int) -> int:
    """Reproduit `resize(..., C_WIDTH)` + addition : debordement modulo 2**32."""
    valeur &= MOD32 - 1
    return valeur - MOD32 if valeur >= (1 << 31) else valeur


def mandelbrot_reference(cr: int, ci: int, max_iter: int, frac: int) -> tuple[int, bool]:
    """Nombre d'iterations avant fuite, et fuite, pour un point donne.

    Reproduction exacte de l'automate de `mandelbrot_lane.vhd` :
      PROD   : p_rr = zr*zr ; p_ii = zi*zi ; p_ri = 2*zr*zi      (domaine Q(2*frac))
      DECIDE : m2 = p_rr + p_ii ; fuite si m2 > 4.0
      UPDATE : zr = ((p_rr - p_ii) >> frac) + cr ; zi = (p_ri >> frac) + ci
    Le decalage a droite en VHDL sur un `signed` est arithmetique (arrondi vers
    -infini) : c'est exactement le comportement de `>>` en Python.
    """
    one = 1 << frac
    zr = 0
    zi = 0
    n = 0
    seuil = 4 * one * one  # 4.0 dans le domaine des produits (Q(2*frac))
    while True:
        p_rr = zr * zr
        p_ii = zi * zi
        p_ri = 2 * zr * zi
        if (p_rr + p_ii) > seuil:
            return n, True
        if n >= max_iter:
            return n, False
        zr = i32(((p_rr - p_ii) >> frac) + cr)
        zi = i32((p_ri >> frac) + ci)
        n += 1


def point_de_depart(x: int, y: int, x0: int, dx: int, y0: int, dy: int) -> tuple[int, int]:
    """c = (x0 + x*dx) + i*(y0 + y*dy) — meme calcul entier que le RTL."""
    return x0 + dx * x, y0 + dy * y


def config_fenetre(dut) -> tuple[int, int]:
    """Fenetre du plan complexe telle que le DESIGN la declare (Q28 signe).

    Lire la configuration sur le design plutot que de la recopier dans le test evite
    une classe entiere de faux echecs : le test verifie l'arithmetique du RTL, ce qui
    est son vrai role, et il verifie du meme coup que les generiques ont bien ete pris
    en compte a l'elaboration.
    """
    return int(dut.o_cfg_x0.value.to_signed()), int(dut.o_cfg_y0.value.to_signed())


# -----------------------------------------------------------------------------
# Ecriture d'image (sans aucune dependance : zlib + struct sont dans la stdlib)
# -----------------------------------------------------------------------------

def palette(iterations: int, escaped: bool, max_iter: int) -> tuple[int, int, int]:
    """Coloration : noir dans l'ensemble, degrade bleu/vert/orange a l'exterieur."""
    if not escaped:
        return (0, 0, 0)
    t = iterations / max(1, max_iter)
    r = int(255 * min(1.0, 3.0 * t))
    g = int(180 * min(1.0, 2.0 * t))
    b = int(255 * (1.0 - min(1.0, 1.5 * t)) + 60)
    return (r, g, min(255, b))


def ecrire_ppm(chemin: Path, largeur: int, hauteur: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    with chemin.open("wb") as f:
        f.write(f"P6\n{largeur} {hauteur}\n255\n".encode("ascii"))
        for ligne in pixels:
            for (r, g, b) in ligne:
                f.write(bytes((r, g, b)))


def ecrire_png(chemin: Path, largeur: int, hauteur: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    """PNG minimal (RGB 8 bits), ecrit a la main : zlib pour les donnees, struct pour les blocs."""
    brut = bytearray()
    for ligne in pixels:
        brut.append(0)                                    # filtre 0 (aucun)
        for (r, g, b) in ligne:
            brut += bytes((r, g, b))

    def bloc(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    entete = struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0)
    with chemin.open("wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(bloc(b"IHDR", entete))
        f.write(bloc(b"IDAT", zlib.compress(bytes(brut), 9)))
        f.write(bloc(b"IEND", b""))


# -----------------------------------------------------------------------------
# Pilotage du DUT
# -----------------------------------------------------------------------------

CLK_PERIODE_NS = 10          # 100 MHz : la meme frequence que la cible Vivado


async def demarrer(dut):
    """Horloge + reset + etat initial des entrees.

    Termine volontairement sur un FRONT, pas sur un ReadOnly() : ecrire un signal
    juste apres ReadOnly() leve "Attempting settings a value during the ReadOnly
    phase." (erreur reellement rencontree ici, cf. docs/04-cocotb-recipes.md).
    """
    cocotb.start_soon(Clock(dut.i_clk, CLK_PERIODE_NS, unit="ns").start())
    dut.i_rst.value = 1
    dut.i_start.value = 0
    dut.i_px_ready.value = 1          # consommateur toujours pret : debit maximal
    for _ in range(5):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0
    await RisingEdge(dut.i_clk)


async def rendre_image(dut, total_pixels: int, timeout_cycles: int = 5_000_000):
    """Lance un rendu et collecte les pixels.

    Retourne (resultats, cycles) ou resultats[(x, y)] = (iterations, escaped).
    L'echantillonnage se fait apres ReadOnly(), quand tout est stable.
    """
    dut.i_start.value = 1
    await RisingEdge(dut.i_clk)
    dut.i_start.value = 0
    await ReadOnly()

    resultats: dict[tuple[int, int], tuple[int, bool]] = {}
    doublons = []
    cycles_vus = None
    cycles = 0
    while cycles < timeout_cycles:
        # Echantillonnage sur le FRONT DESCENDANT : un seul declencheur par cycle (au
        # lieu de RisingEdge + ReadOnly, deux fois plus lent) et les valeurs sont
        # stabilisees au milieu de la periode. `o_px_valid` reste actif une periode
        # entiere, donc chaque pixel est vu exactement une fois.
        await FallingEdge(dut.i_clk)
        cycles += 1

        if int(dut.o_px_valid.value) == 1:
            cle = (int(dut.o_px_x.value), int(dut.o_px_y.value))
            if cle in resultats:
                doublons.append(cle)
            resultats[cle] = (int(dut.o_px_iter.value), bool(int(dut.o_px_escaped.value)))
        if int(dut.o_done.value) == 1:
            cycles_vus = int(dut.o_cycles.value)
            break
    else:
        raise AssertionError(
            f"Le rendu n'a pas fini apres {timeout_cycles} cycles "
            f"({len(resultats)}/{total_pixels} pixels collectes) : le design est bloque."
        )

    if doublons:
        raise AssertionError(f"{len(doublons)} pixel(s) emis plusieurs fois, ex. {doublons[:5]}")
    if len(resultats) != total_pixels:
        manquants = total_pixels - len(resultats)
        raise AssertionError(f"{manquants} pixel(s) jamais emis (sur {total_pixels})")
    return resultats, (cycles_vus if cycles_vus else cycles)


def verifier_contre_le_modele(dut, resultats, x0, dx, y0, dy, max_iter, frac, nom=""):
    """Compare chaque pixel au modele Python et retourne la liste des ecarts."""
    ecarts = []
    for (x, y), (iter_hw, escaped_hw) in sorted(resultats.items()):
        cr, ci = point_de_depart(x, y, x0, dx, y0, dy)
        iter_ref, escaped_ref = mandelbrot_reference(cr, ci, max_iter, frac)
        if (iter_hw, bool(escaped_hw)) != (iter_ref, escaped_ref):
            ecarts.append((x, y, iter_hw, escaped_hw, iter_ref, escaped_ref))
    return ecarts


def rendre_image_png(chemin: Path, largeur: int, hauteur: int, resultats, max_iter: int) -> None:
    grille = [[(0, 0, 0) for _ in range(largeur)] for _ in range(hauteur)]
    for (x, y), (n, escaped) in resultats.items():
        grille[y][x] = palette(n, bool(escaped), max_iter)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ecrire_ppm(chemin.with_suffix(".ppm"), largeur, hauteur, grille)
    ecrire_png(chemin.with_suffix(".png"), largeur, hauteur, grille)


def rapport_debit(dut, resultats, cycles, largeur, hauteur):
    """Metriques de parallelisme, calculees UNIQUEMENT depuis la sortie du design.

    travail = somme des cycles qu'un seul lane aurait passes (3 par iteration, + 2)
    efficacite = travail / (lanes * cycles) -> mesure directe de la divergence.
    """
    travail = sum(3 * n + 2 for (n, _e) in resultats.values())
    lanes = int(dut.o_cfg_lanes.value)
    efficacite = travail / (lanes * cycles)
    dut._log.info(
        f"--- debit : {largeur}x{hauteur}, {lanes} lanes, {cycles} cycles, "
        f"{cycles / (largeur * hauteur):.2f} cycles/pixel"
    )
    dut._log.info(
        f"--- travail total {travail} cycles-lane, efficacite parallele "
        f"{100 * efficacite:.1f} % (perte par divergence : {100 * (1 - efficacite):.1f} %)"
    )
    return travail, efficacite


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

# La fenetre du plan complexe n'est PAS definie ici : elle est passee en generiques
# au moment du build (voir mandelbrot_config.py, source unique de verite) et le test
# la relit sur les ports o_cfg_* du design.


@cocotb.test(timeout_time=10, timeout_unit="ms")
async def test_petite_image_egale_le_modele(dut):
    """96x64 : chaque pixel doit etre EXACTEMENT celui du modele de reference."""
    await demarrer(dut)
    # Toutes les lectures APRES le reset : avant la propagation des deltas, les sorties
    # valent 'U' (erreur reelle : "Can't convert LogicArray to int: it contains non-0/1 values").
    largeur = int(dut.o_cfg_w.value)
    hauteur = int(dut.o_cfg_h.value)
    max_iter = int(dut.o_cfg_iter.value)
    x0, y0 = config_fenetre(dut)
    dx = int(dut.o_cfg_dx.value.to_signed())
    dy = int(dut.o_cfg_dy.value.to_signed())
    frac = int(dut.o_cfg_frac.value)
    dut._log.info(
        f"configuration lue sur le design : {largeur}x{hauteur}, {int(dut.o_cfg_lanes.value)} lanes, "
        f"max_iter={max_iter}, Q{frac}, x0={x0} dx={dx} y0={y0} dy={dy}"
    )

    resultats, cycles = await rendre_image(dut, largeur * hauteur)
    ecarts = verifier_contre_le_modele(dut, resultats, x0, dx, y0, dy, max_iter, frac)
    for (x, y, ih, eh, ir, er) in ecarts[:10]:
        dut._log.error(
            f"pixel ({x},{y}) : materiel iter={ih} escaped={eh} / modele iter={ir} escaped={er}"
        )
    assert not ecarts, f"{len(ecarts)} / {largeur * hauteur} pixels differents du modele"

    travail, eff = rapport_debit(dut, resultats, cycles, largeur, hauteur)
    assert eff > 0.50, f"efficacite parallele trop faible ({eff:.2%}) : divergence excessive"

    images = Path(os.environ.get("MANDEL_IMG_DIR", "."))
    rendre_image_png(images / "mandelbrot_petite", largeur, hauteur, resultats, max_iter)
    dut._log.info(f"image ecrite : {images / 'mandelbrot_petite.png'}")
    dut._log.info(f"cycle(s) de travail total : {travail}")


@cocotb.test(timeout_time=30, timeout_unit="ms")
async def test_image_complete_et_image_png(dut):
    """Image pleine resolution du build courant : comparaison totale + rendu PNG."""
    await demarrer(dut)
    largeur = int(dut.o_cfg_w.value)
    hauteur = int(dut.o_cfg_h.value)
    max_iter = int(dut.o_cfg_iter.value)
    x0, y0 = config_fenetre(dut)
    dx = int(dut.o_cfg_dx.value.to_signed())
    dy = int(dut.o_cfg_dy.value.to_signed())
    frac = int(dut.o_cfg_frac.value)

    resultats, cycles = await rendre_image(dut, largeur * hauteur)
    ecarts = verifier_contre_le_modele(dut, resultats, x0, dx, y0, dy, max_iter, frac)
    assert not ecarts, f"{len(ecarts)} pixels differents du modele (ex. {ecarts[:5]})"

    rapport_debit(dut, resultats, cycles, largeur, hauteur)
    images = Path(os.environ.get("MANDEL_IMG_DIR", "."))
    rendre_image_png(images / "mandelbrot", largeur, hauteur, resultats, max_iter)
    n_dedans = sum(1 for (_n, e) in resultats.values() if not e)
    dut._log.info(
        f"image {largeur}x{hauteur} ecrite dans {images / 'mandelbrot.png'} "
        f"({n_dedans} pixels dans l'ensemble, {len(resultats) - n_dedans} hors)"
    )
