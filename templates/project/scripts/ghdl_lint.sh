#!/usr/bin/env bash
# =============================================================================
#  Analyse VHDL-2008 de tout un dossier RTL avec GHDL.
#
#  Appele par : make lint   (voir le Makefile racine du projet)
#  Usage      : scripts/ghdl_lint.sh [RTL_DIR] [LIB_DIR] [GHDL_BIN]
#  Defauts    : rtl  build/lint  ghdl
#
#  POURQUOI DEUX ETAPES
#    1) ghdl -i  : importe les fichiers, construit la bibliotheque de travail
#                  (work-obj08.cf) et valide au passage la liste des fichiers.
#    2) ghdl -a  : analyse reellement les fichiers. GHDL exige que les
#                  dependances soient deja analysees : on fait donc des passes
#                  successives et on n'analyse un fichier que lorsque ses
#                  dependances sont presentes dans la bibliotheque.
#                  L'ordre du `find` (alphabetique) est ainsi indifferent.
#
#  Toute erreur d'analyse est affichee telle quelle par GHDL et le script sort
#  en code 1. Aucun resultat n'est invente : s'il n'y a pas d'erreur, c'est que
#  GHDL n'en a pas rapporte.
# =============================================================================

set -u

RTL_DIR="${1:-rtl}"
LIB_DIR="${2:-build/lint}"
GHDL_BIN="${3:-${GHDL:-ghdl}}"

if ! command -v "$GHDL_BIN" >/dev/null 2>&1; then
    echo "[lint] binaire ghdl introuvable : $GHDL_BIN" >&2
    echo "[lint] installez GHDL ou passez le chemin : make lint GHDL=/opt/ghdl/bin/ghdl" >&2
    exit 1
fi

if [ ! -d "$RTL_DIR" ]; then
    echo "[lint] dossier $RTL_DIR/ absent : rien a analyser."
    exit 0
fi

# --- liste des sources, ordre alphabetique (l'ordre reel est calcule plus bas)
mapfile -t FILES < <(find "$RTL_DIR" -type f \( -name '*.vhd' -o -name '*.vhdl' \) | sort)

if [ "${#FILES[@]}" -eq 0 ]; then
    echo "[lint] aucun fichier VHDL dans $RTL_DIR/ : rien a analyser."
    echo "[lint] (placez vos modules dans $RTL_DIR/<nom_du_module>.vhd)"
    exit 0
fi

echo "[lint] outils   : $($GHDL_BIN --version 2>/dev/null | head -1)"
echo "[lint] sources  : ${#FILES[@]} fichier(s) sous $RTL_DIR/ (VHDL-2008)"
echo "[lint] biblio   : $LIB_DIR"
mkdir -p "$LIB_DIR"

# --- etape 1 : import --------------------------------------------------------
echo "[lint] --- ghdl -i --std=08 (import) ---"
if ! "$GHDL_BIN" -i --std=08 --workdir="$LIB_DIR" "${FILES[@]}"; then
    echo "[lint] ECHEC : ghdl -i n'a pas pu importer les fichiers ci-dessus." >&2
    exit 1
fi

# --- etape 2 : analyse, passes successives jusqu'a stabilisation -------------
declare -A PENDING=() DONE=()
for f in "${FILES[@]}"; do PENDING["$f"]=1; done

ORDER=()
pass=0
while [ "${#PENDING[@]}" -gt 0 ]; do
    pass=$((pass + 1))
    progress=0
    errors=""
    for f in "${!PENDING[@]}"; do
        out="$("$GHDL_BIN" -a --std=08 --workdir="$LIB_DIR" "$f" 2>&1)"
        rc=$?
        if [ $rc -eq 0 ]; then
            ORDER+=("$f")
            unset 'PENDING[$f]'
            progress=1
        else
            # "unite introuvable" = dependance pas encore analysee : on reessaiera
            # a la passe suivante. Toute autre erreur est une vraie erreur.
            case "$out" in
                *"not found in library"*|*"was not analysed"*|*"not yet analyzed"*) : ;;
                *) errors="${errors}${out}"$'\n' ;;
            esac
        fi
    done
    if [ $progress -eq 0 ]; then
        # Plus rien ne progresse : ce qui reste est en erreur (ou depend d'un
        # fichier absent). On affiche les diagnostics reels collectes.
        echo "" >&2
        echo "[lint] ECHEC : ${#PENDING[@]} fichier(s) non analyse(s) :" >&2
        for f in "${!PENDING[@]}"; do echo "        - $f" >&2; done
        if [ -n "$errors" ]; then
            echo "[lint] erreurs rapportees par ghdl :" >&2
            printf '%s' "$errors" >&2
        else
            echo "[lint] aucune erreur directe : verifiez qu'un fichier definissant" >&2
            echo "       l'unite manquante existe bien dans $RTL_DIR/." >&2
            echo "[lint] relance detaille : $GHDL_BIN -a --std=08 --workdir=$LIB_DIR <fichier>" >&2
        fi
        exit 1
    fi
done

# --- resultat ----------------------------------------------------------------
echo "[lint] --- ordre d'analyse retenu (${#ORDER[@]} fichiers) ---"
i=0
for f in "${ORDER[@]}"; do
    i=$((i + 1))
    printf '[lint]   %2d. %s\n' "$i" "$f"
done
echo "[lint] OK : ${#ORDER[@]} fichier(s) analyse(s) sans erreur (VHDL-2008)."
echo "[lint] rappel : une analyse sans erreur ne prouve PAS que le design fonctionne."
echo "[lint]          la preuve, c'est la simulation : make sim"
exit 0
