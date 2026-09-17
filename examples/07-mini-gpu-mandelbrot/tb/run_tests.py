#!/usr/bin/env python3
"""Lance le banc du mini-GPU avec la configuration de son choix.

Pourquoi un lanceur Python en plus du Makefile : la taille de l'image, le nombre de
lanes et la fenetre du plan complexe sont des GENERIQUES VHDL. Les passer depuis un
script Python evite de recopier des constantes dans un Makefile et permet d'enchainer
plusieurs configurations (c'est ce que fait tb/bench_lanes.py).

    python3 run_tests.py                              # 96x64, 8 lanes, 64 iterations
    python3 run_tests.py --lanes 16 -w 320 -h 240 --max-iter 128
    python3 run_tests.py --testcase test_petite_image_egale_le_modele
    python3 run_tests.py --waves                      # traces .ghw

Verifie : cocotb 2.0.1 + GHDL 6.0.0 (sorties reelles dans le README).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

import mandelbrot_config as cfg

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SOURCES = [
    RTL / "mandelbrot_pkg.vhd",
    RTL / "mandelbrot_lane.vhd",
    RTL / "mandelbrot_gpu.vhd",
]


def main() -> int:
    p = argparse.ArgumentParser(description="Banc de test du mini-GPU Mandelbrot")
    p.add_argument("--lanes", type=int, default=8, help="nombre de lanes SIMT")
    p.add_argument("-w", "--largeur", type=int, default=96, help="largeur image (pixels)")
    p.add_argument("-H", "--hauteur", type=int, default=64, help="hauteur image (pixels)")
    p.add_argument("--max-iter", type=int, default=64, help="iterations maximum par point")
    p.add_argument("--testcase", default=None, help="ne lancer qu'un test (nom de fonction)")
    p.add_argument("--images", default=str(HERE / "images"), help="dossier des images produites")
    p.add_argument("--waves", action="store_true", help="enregistrer les traces (GHDL : .ghw)")
    p.add_argument("--sim", default="ghdl", help="simulateur cocotb (defaut : ghdl)")
    args = p.parse_args()

    gen = cfg.generiques(args.largeur, args.hauteur, args.lanes, args.max_iter)
    print(f"[banc] configuration : {args.largeur}x{args.hauteur}, {args.lanes} lanes, "
          f"max_iter={args.max_iter}, Q{cfg.FRAC}")
    print(f"[banc] generiques : {gen}")

    build_dir = HERE / "sim_build"
    runner = get_runner(args.sim)
    runner.build(
        sources=SOURCES,
        hdl_toplevel="mandelbrot_gpu",
        parameters=gen,
        build_args=["--std=08"],       # analyse VHDL-2008
        build_dir=build_dir,
        always=True,
    )
    runner.test(
        hdl_toplevel="mandelbrot_gpu",
        test_module="test_mandelbrot",
        parameters=gen,
        # PIEGE GHDL (mesure, cf. docs/03-simulation.md) : le runner execute la
        # simulation dans `test_dir`, alors que l'elaboration a eu lieu dans
        # `build_dir`. Sans ces deux options, GHDL repond
        # "cannot find entity or configuration mandelbrot_gpu".
        #   --std=08    : indispensable aussi a l'execution (et pas seulement a l'analyse)
        #   --workdir/-P: dire ou se trouve la bibliotheque elaboree
        test_args=["--std=08", f"--workdir={build_dir}", f"-P{build_dir}"],
        testcase=args.testcase,
        waves=args.waves,
        extra_env={"MANDEL_IMG_DIR": str(args.images)},
        build_dir=build_dir,
        test_dir=HERE,
    )
    print(f"[banc] images dans {args.images}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
