#!/usr/bin/env python3
"""Rend un fichier .cast (asciinema v2) en GIF 1280x720.

- l'ecran est reconstruit avec pyte (vrai terminal : couleurs, effacements) ;
- les temps morts sont compresses (sinon un run de synthese fait un GIF de 5 min) ;
- les frames identiques consecutives sont fusionnees.

Usage : python3 cast2gif.py entree.cast sortie.gif [--fps 10] [--idle-max 1.2]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (30, 30, 46)
FG = (205, 214, 244)
PALETTE = {
    "black": (69, 71, 90), "red": (243, 139, 168), "green": (166, 227, 161),
    "brown": (249, 226, 175), "blue": (137, 180, 250), "magenta": (203, 166, 247),
    "cyan": (148, 226, 213), "white": (186, 194, 222),
    "brightblack": (88, 91, 112), "brightred": (243, 139, 168),
    "brightgreen": (166, 227, 161), "brightbrown": (249, 226, 175),
    "brightblue": (137, 180, 250), "brightmagenta": (203, 166, 247),
    "brightcyan": (148, 226, 213), "brightwhite": (205, 214, 244),
    "default": FG,
}
FONT_R = Path.home() / ".fonts/JetBrainsMono-2.304/fonts/ttf/JetBrainsMono-Regular.ttf"
FONT_B = Path.home() / ".fonts/JetBrainsMono-2.304/fonts/ttf/JetBrainsMono-Bold.ttf"


def load_cast(path: Path):
    events = []
    header = {}
    with path.open() as fh:
        for i, raw in enumerate(fh):
            raw = raw.strip()
            if not raw:
                continue
            obj = json.loads(raw)
            if i == 0 and "version" in obj:
                header = obj
                continue
            events.append(obj)
    return header, events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cast")
    ap.add_argument("gif")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--idle-max", type=float, default=1.2, help="secondes max d'inactivite conservees")
    ap.add_argument("--font-size", type=int, default=21)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    header, events = load_cast(Path(args.cast))
    cols = header.get("width", 100)
    rows = header.get("height", 30)
    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)

    font = ImageFont.truetype(str(FONT_R), args.font_size)
    font_b = ImageFont.truetype(str(FONT_B), args.font_size)
    cell_w = font.getlength("M")
    line_h = H / rows
    x0 = (W - cell_w * cols) / 2

    frames = []          # (image, duree)
    last_key = None
    sim_time = 0.0
    prev_ev_time = 0.0
    for ev in events:
        if len(ev) < 3 or ev[1] != "o":
            continue
        t = float(ev[0])
        # temps mort compresse
        sim_time += min(max(t - prev_ev_time, 0.0), args.idle_max)
        prev_ev_time = t
        stream.feed(ev[2])
        rows_data = screen.buffer
        key = tuple(rows_data[y][x].data for y in range(rows) for x in range(cols)) + tuple(
            (rows_data[y][x].fg, rows_data[y][x].bg, rows_data[y][x].bold) for y in range(rows) for x in range(cols))
        if key == last_key:
            continue
        last_key = key

        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        for y in range(rows):
            for x in range(cols):
                ch = rows_data[y][x]
                if ch.data.strip() == "" and ch.bg == "default":
                    continue
                fg = PALETTE.get(ch.fg, FG)
                bg = PALETTE.get(ch.bg, None) if ch.bg != "default" else None
                px, py = x0 + x * cell_w, y * line_h
                if bg:
                    d.rectangle([px, py, px + cell_w, py + line_h], fill=bg)
                if ch.data != " ":
                    d.text((px, py), ch.data, font=font_b if ch.bold else font, fill=fg)
        frames.append((img, sim_time))

    # durees : ecart entre snapshots, borne
    if not frames:
        print("aucune frame", file=sys.stderr)
        return 1
    tmp = Path("/tmp/cast2gif_frames")
    if tmp.exists():
        for old in tmp.glob("*.png"):
            old.unlink()
    tmp.mkdir(exist_ok=True)
    # duree de chaque snapshot -> nombre de copies a 1/fps
    idx = 0
    for i, (img, _) in enumerate(frames):
        dur = (frames[i + 1][1] - frames[i][1]) if i + 1 < len(frames) else 2.5
        for _ in range(max(1, round(dur * args.fps))):
            img.save(tmp / f"f{idx:05d}.png")
            idx += 1
    print(f"  {len(frames)} snapshots -> {idx} frames a {args.fps} fps "
          f"({idx/args.fps:.1f} s de lecture)")

    out = Path(args.gif)
    pal = tmp / "palette.png"
    scale = f"fps={args.fps},scale={W}:{H}:flags=lanczos"
    seq = str(tmp / "f%05d.png")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(args.fps), "-i", seq,
        "-vf", f"{scale},palettegen=stats_mode=diff", "-update", "1", str(pal),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(args.fps), "-i", seq,
        "-i", str(pal),
        "-lavfi", f"{scale}[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=3",
        "-loop", "0", str(out),
    ], check=True)
    seconds = sum((frames[i + 1][1] - frames[i][1]) if i + 1 < len(frames) else 2.5 for i in range(len(frames)))
    print(f"{len(frames)} frames -> {out} ({out.stat().st_size/1e6:.2f} Mo, duree ~{seconds:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
