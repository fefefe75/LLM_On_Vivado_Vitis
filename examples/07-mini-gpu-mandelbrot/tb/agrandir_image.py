#!/usr/bin/env python3
"""Agrandit une image .ppm produite par le banc de test (plus proche voisin) en .png.

Utile parce que les petites configurations (48x32, 96x64) donnent des images exactes
mais minuscules a l'ecran : ce script les rend lisibles sans rien interpoler (aucun
pixel invente, chacun est simplement duplique).

    python3 agrandir_image.py images_48/mandelbrot_petite.ppm grand.png --facteur 8

Aucune dependance : l'ecriture PNG utilise zlib et struct de la bibliotheque standard
(meme code que dans test_mandelbrot.py).
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path


def lire_ppm(chemin: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Lit un PPM binaire (P6) et retourne (largeur, hauteur, pixels)."""
    data = chemin.read_bytes()
    if not data.startswith(b"P6"):
        raise ValueError(f"{chemin} n'est pas un PPM binaire P6")
    champs: list[int] = []
    i = 2
    while len(champs) < 3:
        while i < len(data) and data[i : i + 1].isspace():
            i += 1
        if data[i : i + 1] == b"#":                      # commentaire
            while i < len(data) and data[i : i + 1] != b"\n":
                i += 1
            continue
        debut = i
        while i < len(data) and not data[i : i + 1].isspace():
            i += 1
        champs.append(int(data[debut:i]))
    i += 1                                                # un seul blanc apres l'entete
    largeur, hauteur, _max = champs
    brut = data[i : i + largeur * hauteur * 3]
    if len(brut) != largeur * hauteur * 3:
        raise ValueError(f"{chemin} est tronque : {len(brut)} octets de pixels au lieu de {largeur * hauteur * 3}")
    return largeur, hauteur, [(brut[k], brut[k + 1], brut[k + 2]) for k in range(0, len(brut), 3)]


def ecrire_png(chemin: Path, largeur: int, hauteur: int, pixels: list[tuple[int, int, int]]) -> None:
    """PNG RGB 8 bits minimal, ecrit a la main."""
    brut = bytearray()
    for ligne in range(hauteur):
        brut.append(0)                                    # filtre 0
        debut = ligne * largeur
        for (r, g, b) in pixels[debut : debut + largeur]:
            brut += bytes((r, g, b))

    def bloc(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    with chemin.open("wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0)))
        f.write(bloc(b"IDAT", zlib.compress(bytes(brut), 9)))
        f.write(bloc(b"IEND", b""))


def main() -> int:
    p = argparse.ArgumentParser(description="Agrandit un PPM (plus proche voisin) vers un PNG")
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("--facteur", type=int, default=8, help="facteur d'agrandissement entier")
    args = p.parse_args()

    largeur, hauteur, pixels = lire_ppm(args.source)
    f = max(1, args.facteur)
    sortie: list[tuple[int, int, int]] = []
    for y in range(hauteur):
        ligne = pixels[y * largeur : (y + 1) * largeur]
        agrandie = [px for px in ligne for _ in range(f)]
        for _ in range(f):
            sortie.extend(agrandie)
    ecrire_png(args.destination, largeur * f, hauteur * f, sortie)
    print(f"{args.source} ({largeur}x{hauteur}) -> {args.destination} ({largeur * f}x{hauteur * f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
