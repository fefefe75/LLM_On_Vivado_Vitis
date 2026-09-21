#!/usr/bin/env python3
"""Zoom de Mandelbrot CALCULE PAR LE RTL (mini-GPU SIMT, exemple 07).

Chaque image de l'animation est produite par le design VHDL lui-meme : le script
reelabore le mini-GPU avec la vue (region du plan complexe) de l'image voulue, lance
simulation, et laisse `test_mandelbrot.test_image_complete_et_image_png` ecrire le PNG.
Ce test compare AUSSI chaque pixel au modele de reference Python : une image fausse
ferait echouer le run au lieu de produire une jolie animation trompeuse.

Les images sont INDEPENDANTES : `--jobs N` en calcule N en parallele. C'est le seul
parallelisme disponible ici — GHDL (backend mcode) est mono-thread, une simulation
n'occupe qu'un coeur quel que soit C_LANES (les voies sont simulees cycle par cycle,
pas en parallele). Chaque tache a son propre dossier de travail (copie du banc,
sim_build, results.xml), donc aucun fichier partage.

Usage :
    python3 render_zoom.py --frames 12 --out /tmp/zoom --width 128 --height 96 \
        --lanes 16 --max-iter 96 --jobs 6
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mandelbrot_config as cfg  # noqa: E402
from cocotb_tools.runner import get_runner  # noqa: E402

# Centre du zoom : "seahorse valley", point classique des zooms profonds de Mandelbrot.
CENTRE = (-0.743643887037151, 0.131825904205330)

RTL = (HERE.parent / "rtl").resolve()
SOURCES = sorted(RTL.glob("*.vhd"))
MODULES = ("test_mandelbrot.py", "mandelbrot_config.py")


def region(frame: int, frames: int, largeur_init: float | None = None, centre=CENTRE,
           facteur: float = 0.78, recadrage: int = 3) -> tuple[float, float, float, float]:
    """Vue de la frame `frame`.

    Frame 0 = exactement la vue "classique" du depot (cfg.REGION), pour que la premiere
    image de l'animation soit celle du README. Ensuite : recadrage progressif sur
    `centre` (en `recadrage` images) et reduction de la fenetre par `facteur`.
    """
    xmin, xmax, ymin, ymax = cfg.REGION
    ratio = (ymax - ymin) / (xmax - xmin)
    w0 = largeur_init if largeur_init else (xmax - xmin)
    h0 = w0 * ratio
    cx0, cy0 = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
    t = min(1.0, frame / float(max(1, recadrage)))
    cx = cx0 + (centre[0] - cx0) * t
    cy = cy0 + (centre[1] - cy0) * t
    w = w0 * (facteur ** frame)
    h = h0 * (facteur ** frame)
    return (cx - w / 2.0, cx + w / 2.0, cy - h / 2.0, cy + h / 2.0)


def rendre_une_image(numero: int, cadre: dict) -> tuple[int, float, str]:
    """Elabore et simule UNE image, dans son propre dossier. Renvoie (n, duree, note)."""
    t0 = time.time()
    reg = region(numero, cadre["frames"], cadre["largeur_init"], facteur=cadre["facteur"])
    gen = cfg.generiques(cadre["width"], cadre["height"], cadre["lanes"],
                         cadre["max_iter"], reg)
    dossier = cadre["out"] / f"frame_{numero:02d}"
    tb = dossier / "tb"
    tb.mkdir(parents=True, exist_ok=True)
    for module in MODULES:                  # banc copie par tache : rien de partage
        shutil.copy(HERE / module, tb / module)
    build_dir = dossier / "sim_build"

    runner = get_runner("ghdl")
    runner.build(
        sources=SOURCES,
        hdl_toplevel="mandelbrot_gpu",
        parameters=gen,
        build_args=["--std=08"],
        build_dir=build_dir,
        always=True,
    )
    runner.test(
        hdl_toplevel="mandelbrot_gpu",
        test_module="test_mandelbrot",
        parameters=gen,
        test_args=["--std=08", f"--workdir={build_dir}", f"-P{build_dir}"],
        testcase=cadre["testcase"],
        extra_env={"MANDEL_IMG_DIR": str(dossier)},
        build_dir=build_dir,
        test_dir=tb,
    )
    if not (dossier / "mandelbrot.png").exists():
        return numero, time.time() - t0, "ECHEC (aucun PNG)"
    return numero, time.time() - t0, f"largeur={reg[1] - reg[0]:.3e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--width", type=int, default=96)
    ap.add_argument("--height", type=int, default=64)
    ap.add_argument("--lanes", type=int, default=8)
    ap.add_argument("--max-iter", type=int, default=64)
    ap.add_argument("--largeur-init", type=float, default=None,
                    help="largeur de la fenetre a la premiere image (defaut : vue du depot)")
    ap.add_argument("--facteur", type=float, default=0.78, help="facteur de zoom par image")
    ap.add_argument("--out", default="/tmp/mandel_zoom")
    ap.add_argument("--testcase", default="test_image_complete_et_image_png")
    ap.add_argument("--jobs", type=int, default=1,
                    help="images en parallele (1 = sequentiel ; GHDL est mono-thread)")
    ap.add_argument("--force", action="store_true", help="recalculer les images deja la")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cadre = {
        "out": out, "frames": args.frames, "width": args.width, "height": args.height,
        "lanes": args.lanes, "max_iter": args.max_iter, "facteur": args.facteur,
        "largeur_init": args.largeur_init, "testcase": args.testcase,
    }
    a_faire = [n for n in range(args.frames)
               if args.force or not (out / f"frame_{n:02d}" / "mandelbrot.png").exists()]
    print(f"[zoom] {len(a_faire)}/{args.frames} image(s) a calculer : {args.width}x{args.height}, "
          f"{args.lanes} lanes, max_iter={args.max_iter}, facteur {args.facteur}, "
          f"jobs={args.jobs} -> {out}", flush=True)
    if not a_faire:
        return 0

    t0 = time.time()
    if args.jobs <= 1:
        for numero in a_faire:
            n, duree, note = rendre_une_image(numero, cadre)
            print(f"[zoom] image {n + 1}/{args.frames} en {duree:.1f} s ({note})", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futurs = [pool.submit(rendre_une_image, n, cadre) for n in a_faire]
            for futur in as_completed(futurs):
                n, duree, note = futur.result()
                print(f"[zoom] image {n + 1}/{args.frames} en {duree:.1f} s ({note})", flush=True)

    total = time.time() - t0
    print(f"[zoom] {len(a_faire)} image(s) en {total:.1f} s avec {args.jobs} job(s) "
          f"({total / len(a_faire):.1f} s/image en moyenne)")
    print(f"[zoom] images dans {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
