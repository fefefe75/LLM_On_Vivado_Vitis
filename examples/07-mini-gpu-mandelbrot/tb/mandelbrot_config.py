"""Source unique de verite des parametres du mini-GPU (exemple 07).

Le MEME dictionnaire de generiques sert a construire le design ; le banc de test, lui,
relit la configuration effective sur les ports `o_cfg_*` du design. Il n'y a donc
jamais deux copies d'une constante a garder synchronisees.

Verifie : GHDL 6.0.0 + cocotb 2.0.1 (voir README pour les sorties reelles).
"""

from __future__ import annotations

FRAC = 26                       # bits fractionnaires (doit correspondre a C_FRAC du RTL)
ONE = 1 << FRAC                 # 1.0 dans ce format

# Fenetre du plan complexe : (xmin, xmax, ymin, ymax). C'est la vue "classique".
REGION = (-2.1, 0.7, -1.2, 1.2)


def quantifier(valeur: float) -> int:
    """Convertit un reel dans le format Q(FRAC) du design (arrondi au plus proche).

    Pourquoi 26 bits fractionnaires et pas 28 : avec C_WIDTH=32, un format Q28 a une
    plage de +/-8.0, or l'intermediaire 2*zr*zi du lane atteint exactement 8.0 au bord
    de la fuite -> "bound check failure" sous GHDL (mesure). Q26 porte +/-32 et reste
    largement plus precis que le pas d'un pixel (erreur ~2e-9 contre un pas de ~0.03).
    """
    return int(round(valeur * ONE))


def largeur_bits(valeur: int) -> int:
    """Nombre de bits necessaires : doit satisfaire valeur <= 2**bits (assertion du RTL)."""
    bits = 1
    while valeur > 1:
        valeur //= 2
        bits += 1
    return bits


def generiques(largeur: int = 96, hauteur: int = 64, lanes: int = 8,
               max_iter: int = 64, region: tuple[float, float, float, float] = REGION) -> dict:
    """Generiques VHDL a passer a l'elaboration (cocotb `parameters=`, ou -g sous GHDL)."""
    xmin, xmax, ymin, ymax = region
    return {
        "C_IMG_W": largeur,
        "C_IMG_H": hauteur,
        "C_LANES": lanes,
        "C_MAX_ITER": max_iter,
        "C_FRAC": FRAC,
        "C_XW": largeur_bits(largeur),
        "C_YW": largeur_bits(hauteur),
        "C_X0": quantifier(xmin),
        "C_Y0": quantifier(ymin),
        "C_DX": quantifier((xmax - xmin) / largeur),
        "C_DY": quantifier((ymax - ymin) / hauteur),
    }


def ligne_ghdl(gen: dict) -> str:
    """Meme chose au format GHDL : '-gNAME=valeur', pour GHDL_RUN_ARGS du Makefile."""
    return " ".join(f"-g{nom}={valeur}" for nom, valeur in gen.items())


if __name__ == "__main__":
    import sys

    # Verification croisee utile : les constantes figees dans le Makefile doivent
    # correspondre exactement a ce que calcule ce module.
    gen = generiques()
    print("generiques par defaut (Makefile, simulation) :")
    for nom, valeur in gen.items():
        print(f"  {nom:11s} = {valeur}")
    print("\nGHDL_RUN_ARGS +=", ligne_ghdl(gen))
    print("\nimage pleine 320x240, 16 lanes :")
    print(ligne_ghdl(generiques(320, 240, 16, 128)))
    sys.exit(0)
