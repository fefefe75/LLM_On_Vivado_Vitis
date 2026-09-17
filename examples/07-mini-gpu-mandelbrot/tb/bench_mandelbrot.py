"""Module de mesure du mini-GPU (et non de correction : voir test_mandelbrot.py).

Astuce de performance : le banc n'attend PAS chaque front d'horloge (cela couterait
~0,6 ms de Python par cycle, mesure faite). Il se reveille uniquement quand `o_done`
change de valeur, grace aux declencheurs `value_change` de cocotb 2.x. Le rendu complet
est ainsi mesure en quelques centaines de millisecondes au lieu de plusieurs minutes.

Le travail total en "cycles-lane" est calcule avec le modele de reference Python. C'est
legitime : test_mandelbrot.py prouve que le materiel produit exactement les memes
iterations, pixel par pixel. Le banc compare donc des configurations entre elles.

Resultats ecrits en JSON dans $MANDEL_BENCH_OUT pour que bench_lanes.py les agrege.
"""

import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from test_mandelbrot import (
    mandelbrot_reference,
    point_de_depart,
)


async def attendre_fin(dut):
    """Attend le pulse o_done sans poller l'horloge."""
    while True:
        await dut.o_done.value_change
        if int(dut.o_done.value) == 1:
            return int(dut.o_cycles.value)


@cocotb.test(timeout_time=600, timeout_unit="ms")
async def bench_mesure(dut):
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    dut.i_rst.value = 1
    dut.i_start.value = 0
    dut.i_px_ready.value = 1
    for _ in range(5):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0
    await RisingEdge(dut.i_clk)

    largeur = int(dut.o_cfg_w.value)
    hauteur = int(dut.o_cfg_h.value)
    lanes = int(dut.o_cfg_lanes.value)
    max_iter = int(dut.o_cfg_iter.value)
    frac = int(dut.o_cfg_frac.value)
    x0 = int(dut.o_cfg_x0.value.to_signed())
    y0 = int(dut.o_cfg_y0.value.to_signed())
    dx = int(dut.o_cfg_dx.value.to_signed())
    dy = int(dut.o_cfg_dy.value.to_signed())

    dut.i_start.value = 1
    await RisingEdge(dut.i_clk)
    dut.i_start.value = 0
    cycles = await attendre_fin(dut)

    # travail total, calcule par le modele de reference (identique au materiel, prouve
    # par test_mandelbrot.py)
    travail = 0
    iterations = 0
    for y in range(hauteur):
        for x in range(largeur):
            cr, ci = point_de_depart(x, y, x0, dx, y0, dy)
            n, _e = mandelbrot_reference(cr, ci, max_iter, frac)
            travail += 3 * n + 2
            iterations += n

    mesures = {
        "lanes": lanes,
        "largeur": largeur,
        "hauteur": hauteur,
        "max_iter": max_iter,
        "pixels": largeur * hauteur,
        "cycles": cycles,
        "cycles_par_pixel": cycles / (largeur * hauteur),
        "iterations_totales": iterations,
        "travail_cycles_lane": travail,
        "efficacite_parallele": travail / (lanes * cycles),
    }
    dut._log.info(
        f"BENCH lanes={lanes} pixels={largeur * hauteur} cycles={cycles} "
        f"cycles_par_pixel={cycles / (largeur * hauteur):.3f} "
        f"efficacite={100 * travail / (lanes * cycles):.1f}%"
    )

    sortie = os.environ.get("MANDEL_BENCH_OUT")
    if sortie:
        Path(sortie).write_text(json.dumps(mesures, indent=2))
        dut._log.info(f"BENCH mesures -> {sortie}")
