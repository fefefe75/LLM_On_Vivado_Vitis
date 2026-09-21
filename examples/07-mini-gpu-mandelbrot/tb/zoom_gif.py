#!/usr/bin/env python3
"""Assemble en GIF les images produites par `render_zoom.py` (RTL mini-GPU).

Les images font `--width x --height` pixels (128x96 par defaut) : elles sont agrandies
par un facteur entier, sans interpolation (le pixel RTL reste visible, rien n'est
invente entre deux pixels), puis encodees en GIF anime.

Usage :
    python3 zoom_gif.py /tmp/zoom_rtl /tmp/mandelbrot_zoom.gif --scale 8
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

PREMIERE_S, COURANTE_S, DERNIERE_S = 1.2, 0.35, 1.6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier", help="dossier contenant frame_00/mandelbrot.png, frame_01/...")
    ap.add_argument("sortie")
    ap.add_argument("--scale", type=int, default=8, help="facteur d'agrandissement entier")
    ap.add_argument("--colors", type=int, default=160)
    args = ap.parse_args()

    racine = Path(args.dossier)
    images = sorted(racine.glob("frame_*/mandelbrot.png"))
    if len(images) < 2:
        raise SystemExit(f"moins de 2 images trouvees dans {racine}")

    frames, durees = [], []
    for i, chemin in enumerate(images):
        img = Image.open(chemin).convert("RGB")
        img = img.resize((img.width * args.scale, img.height * args.scale), Image.NEAREST)
        frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=args.colors))
        duree = PREMIERE_S if i == 0 else (DERNIERE_S if i == len(images) - 1 else COURANTE_S)
        durees.append(int(duree * 1000))

    sortie = Path(args.sortie)
    frames[0].save(
        sortie, save_all=True, append_images=frames[1:], duration=durees, loop=0,
        optimize=True, disposal=1,
    )
    total = sum(durees) / 1000.0
    print(f"{len(frames)} images {frames[0].width}x{frames[0].height} -> {sortie} "
          f"({sortie.stat().st_size / 1e6:.2f} Mo, {total:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
