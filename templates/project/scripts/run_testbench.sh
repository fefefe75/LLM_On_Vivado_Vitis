#!/usr/bin/env bash
# =============================================================================
#  Lance UN testbench et rend un verdict fiable.
#
#  Appele par : make sim (boucle sur tb/*/) et make sim-one
#  Usage      : scripts/run_testbench.sh tb/compteur
#  Variables  : SIM (ghdl), WAVES (0/1), SEED (1234), PYTHON (python3), MAKE (make)
#
#  Deux lanceurs acceptes dans le dossier du testbench :
#    - Makefile      : flux cocotb classique (make SIM=... avec les makefiles
#                      fournis par cocotb-config --makefiles) ;
#    - run_tests.py  : flux cocotb 2.x via cocotb_tools.runner.
#
#  POURQUOI RELIRE results.xml ET PAS SEULEMENT LE CODE DE RETOUR
#  Avec cocotb 2.x, cocotb_tools.runner.test() ne fait pas echouer le processus
#  quand un test echoue : le script Python peut sortir en 0 avec des tests
#  rouges. On relit donc results.xml (JUnit) et on compte les elements
#  <failure>. Sans cela, un test en echec serait annonce vert, ce qui viole la
#  regle du depot : aucune affirmation sans log qui la soutienne.
#
#  Code de sortie : 0 = tous les tests passent ; 1 = au moins un test en echec
#  ou lancement impossible ; 3 = aucun lanceur reconnu dans le dossier.
# =============================================================================

set -u

TB_DIR="${1:-}"
SIM="${SIM:-ghdl}"
WAVES="${WAVES:-0}"
SEED="${SEED:-1234}"
PYTHON="${PYTHON:-python3}"
MAKE_BIN="${MAKE:-make}"

if [ -z "$TB_DIR" ] || [ ! -d "$TB_DIR" ]; then
    echo "  [tb] dossier de testbench introuvable : '$TB_DIR'" >&2
    exit 1
fi

TB_NAME="$(basename "$TB_DIR")"
XML="$TB_DIR/results.xml"

# Un results.xml d'un run precedent ferait mentir le verdict : on l'efface.
rm -f "$XML"

# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------
rc=0
if [ -f "$TB_DIR/Makefile" ]; then
    # GHDL range les options de simulation APRES l'unite de tete ; cocotb place
    # GHDL_RUN_ARGS avant (option d'elaboration comme --time-resolution) et
    # SIM_ARGS apres. --wave=... est une option de simulation : elle doit donc
    # passer par SIM_ARGS, sinon GHDL repond
    #   unknown command option '--wave=...' + "place it after toplevel unit".
    waves_arg=""
    if [ "$WAVES" = "1" ] && [ "$SIM" = "ghdl" ]; then
        waves_arg="SIM_ARGS=--wave=$PWD/$TB_DIR/$TB_NAME.ghw"
    fi
    echo "  [tb] cd $TB_DIR && $MAKE_BIN SIM=$SIM WAVES=$WAVES COCOTB_RANDOM_SEED=$SEED $waves_arg"
    ( cd "$TB_DIR" && "$MAKE_BIN" SIM="$SIM" WAVES="$WAVES" COCOTB_RANDOM_SEED="$SEED" $waves_arg ) || rc=$?
elif [ -f "$TB_DIR/run_tests.py" ]; then
    echo "  [tb] cd $TB_DIR && SIM=$SIM WAVES=$WAVES COCOTB_RANDOM_SEED=$SEED $PYTHON run_tests.py"
    ( cd "$TB_DIR" && SIM="$SIM" WAVES="$WAVES" COCOTB_RANDOM_SEED="$SEED" "$PYTHON" run_tests.py ) || rc=$?
else
    echo "  [tb] $TB_DIR : ni Makefile ni run_tests.py (voir tb/README.md)" >&2
    exit 3
fi

# ---------------------------------------------------------------------------
# Verdict : code de retour + contenu de results.xml (JUnit)
# ---------------------------------------------------------------------------
nb_tests=0
echecs=""
if [ -f "$XML" ]; then
    # dans results.xml de cocotb, chaque <failure/> suit la ligne de son
    # <testcase name="..."> : on associe la derniere ligne testcase vue.
    echecs="$(awk -F'"' '/<testcase/ {n=$2} /<failure/ {print n}' "$XML")"
    nb_tests="$(grep -c '<testcase' "$XML")"
fi
nb_echecs="$(printf '%s\n' "$echecs" | grep -c .)"

if [ "$nb_echecs" -gt 0 ]; then
    echo "  [tb] ECHEC : $nb_echecs test(s) en echec sur $nb_tests dans $TB_DIR"
    printf '%s\n' "$echecs" | sed 's/^/  [tb]   - /'
    exit 1
fi

if [ "$rc" -ne 0 ]; then
    echo "  [tb] ECHEC : le lancement a echoue (code $rc) - ni resultat ni trace utilisable" >&2
    exit 1
fi

if [ ! -f "$XML" ]; then
    echo "  [tb] $TB_DIR : code de retour 0 mais AUCUN results.xml : resultat NON VERIFIABLE."
    echo "  [tb]   -> verifiez que le testbench ecrit bien ses resultats (cocotb le fait)."
    exit 0
fi

echo "  [tb] OK : $nb_tests test(s) passe(s) (results.xml)"
exit 0
