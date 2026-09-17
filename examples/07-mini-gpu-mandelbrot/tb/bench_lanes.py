#!/usr/bin/env python3
"""Mesure l'acceleration reelle du mini-GPU quand on ajoute des lanes.

    python3 bench_lanes.py                        # 1, 2, 4, 8, 16 voies sur 48x32
    python3 bench_lanes.py --lanes 1 2 4 -w 96 -H 64 -i 48
    python3 bench_lanes.py --lanes 8            # une seule configuration

Duree : chaque point est une elaboration + une simulation complete, et GHDL (mcode)
simule ce design a ~500 cycles/s (mesure). La configuration a 1 voie est la plus lente,
car il n'y a aucun parallelisme pour raccourcir la simulation elle-meme.

Pour chaque configuration : elaboration avec le bon nombre de lanes, simulation, puis
lecture des compteurs materiels (o_cycles). Le gain (speedup) et l'efficacite sont
calcules a partir des cycles MESURES -- jamais d'une formule theorique.

Verifie : GHDL 6.0.0 + cocotb 2.0.1 (chiffres reels dans le README).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import mandelbrot_config as cfg

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SOURCES = [RTL / "mandelbrot_pkg.vhd", RTL / "mandelbrot_lane.vhd", RTL / "mandelbrot_gpu.vhd"]


def executer(lanes: int, largeur: int, hauteur: int, max_iter: int) -> dict:
    """Elabore et simule une configuration, retourne les mesures lues sur le design."""
    from cocotb_tools.runner import get_runner

    gen = cfg.generiques(largeur, hauteur, lanes, max_iter)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        chemin_mesures = f.name
    try:
        env = dict(os.environ)
        env["MANDEL_BENCH_OUT"] = chemin_mesures
        os.environ["MANDEL_BENCH_OUT"] = chemin_mesures

        runner = get_runner("ghdl")
        runner.build(sources=SOURCES, hdl_toplevel="mandelbrot_gpu", parameters=gen,
                     build_args=["--std=08"], build_dir=HERE / "sim_build", always=True)
        runner.test(hdl_toplevel="mandelbrot_gpu", test_module="bench_mandelbrot",
                    parameters=gen,
                    test_args=["--std=08", f"--workdir={HERE / 'sim_build'}",
                               f"-P{HERE / 'sim_build'}"],
                    test_dir=HERE, build_dir=HERE / "sim_build")

        # Le module de mesure ecrit son JSON a la fin de la simulation. Si le fichier
        # est vide, c'est que la simulation a ete interrompue : le dire clairement
        # plutot que de laisser remonter un "JSONDecodeError" (erreur reellement
        # rencontree quand une simulation est tuee en cours de route).
        chemin = Path(chemin_mesures)
        texte = chemin.read_text() if chemin.exists() else ""
        if not texte.strip():
            raise RuntimeError(
                f"aucune mesure pour {lanes} lane(s) : la simulation s'est arretee "
                f"avant la fin (regarder la sortie du simulateur ci-dessus, ou relancer "
                f"cette configuration seule avec --lanes {lanes})"
            )
        return json.loads(texte)
    finally:
        os.environ.pop("MANDEL_BENCH_OUT", None)
        Path(chemin_mesures).unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Acceleration du mini-GPU par nombre de lanes")
    p.add_argument("--lanes", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    p.add_argument("-w", "--largeur", type=int, default=48)
    p.add_argument("-H", "--hauteur", type=int, default=32)
    p.add_argument("-i", "--max-iter", type=int, default=32)
    args = p.parse_args()

    print(f"Image {args.largeur}x{args.hauteur}, max_iter={args.max_iter}, Q{cfg.FRAC}")
    print(f"{'lanes':>6} {'cycles':>10} {'cycles/pixel':>13} {'gain':>8} {'efficacite':>11}")
    print("-" * 54)

    reference = None
    lignes = []
    for lanes in args.lanes:
        m = executer(lanes, args.largeur, args.hauteur, args.max_iter)
        if reference is None:
            reference = m["cycles"]
        gain = reference / m["cycles"]
        print(f"{lanes:>6} {m['cycles']:>10} {m['cycles_par_pixel']:>13.3f} "
              f"{gain:>7.2f}x {100 * m['efficacite_parallele']:>10.1f}%")
        lignes.append({**m, "gain": gain})
        sys.stdout.flush()

    print("\nLecture : 'gain' est le rapport des cycles MESURES sur celui d'un seul lane.")
    print("'efficacite' = travail utile / (lanes x cycles) : 100 % = aucun lane inactif.")
    print("La chute a partir d'un certain nombre de lanes est la divergence (des points")
    print("qui ont besoin de 64 iterations immobilisent leur lane) et non un bug.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
