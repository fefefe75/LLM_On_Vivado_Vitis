#!/usr/bin/env bash
# =============================================================================
# verify_all.sh - passe de verification complete du depot, sur une machine Linux.
#
# Ce script est la "preuve" du depot : il execute reellement chaque exemple, les
# templates et les tests du serveur MCP, et n'affiche un OK que sur un code
# retour nul. Il est concu pour etre lance avant un commit et par un agent qui
# veut savoir ce qui marche VRAIMENT ici.
#
# Prerequis :
#   - GHDL dans le PATH (voir docs/01-toolchain.md ; ex. /tmp/ghdl_tool/bin)
#   - cocotb 2.x installe (python -m pip install "cocotb>=2.0,<3")
#   - tclsh, make, python3
#   - facultatif : Vivado/Vitis sourcees (settings64.sh) pour les cibles EDA
#   - facultatif : pytest et fastmcp pour la section MCP (sinon elle est ignoree)
#
# Usage :
#   bash scripts/verify_all.sh            # tout ce qui est possible ici
#   SIM=ghdl bash scripts/verify_all.sh   # forcer le simulateur cocotb
#
# Sortie : une ligne par verification, puis un bilan et un code retour
# (0 = tout ce qui a pu etre execute est vert).
# =============================================================================
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GHDL_BIN="${GHDL:-ghdl}"
PY="${PYTHON:-python3}"
SIM="${SIM:-ghdl}"
LOGDIR="${TMPDIR:-/tmp}/verif_depot"
mkdir -p "$LOGDIR"

ok=0; ko=0; skipped=0

ligne () { printf '  %-34s %s\n' "$1" "$2"; }

verifie () {                       # $1 = libelle, $2 = code retour
    if [ "$2" -eq 0 ]; then ligne "$1" "OK"; ok=$((ok+1));
    else                    ligne "$1" "ECHEC (code $2)"; ko=$((ko+1)); fi
}

ignore () { ligne "$1" "IGNORE ($2)"; skipped=$((skipped+1)); }

section () { printf '\n=== %s ===\n' "$1"; }

# --- outils ----------------------------------------------------------------
section "outils disponibles"
have_ghdl=0; have_tclsh=0; have_vivado=0; have_pytest=0
command -v "$GHDL_BIN" >/dev/null 2>&1 && have_ghdl=1
command -v tclsh      >/dev/null 2>&1 && have_tclsh=1
command -v vivado     >/dev/null 2>&1 && have_vivado=1
"$PY" -c "import pytest" >/dev/null 2>&1 && have_pytest=1
ligne "ghdl"   "$([ $have_ghdl  -eq 1 ] && $GHDL_BIN --version | head -1 || echo 'absent')"
ligne "tclsh"  "$([ $have_tclsh -eq 1 ] && tclsh <<< 'puts [info patchlevel]' || echo 'absent')"
ligne "vivado" "$([ $have_vivado -eq 1 ] && echo 'present (cibles EDA possibles)' || echo 'absent (cibles EDA ignorees)')"
ligne "python" "$($PY --version 2>&1)"

# --- exemples cocotb -------------------------------------------------------
section "exemples cocotb (dossier tb/ de chaque exemple)"
for e in 01-counter-cocotb 02-alu 03-fifo; do
    d="$REPO/examples/$e/tb"
    [ -d "$d" ] || { ignore "$e" "dossier tb/ absent"; continue; }
    ( cd "$d" && make clean >/dev/null 2>&1; PATH="$(dirname "$(command -v "$GHDL_BIN")"):$PATH" make > "$LOGDIR/$e.log" 2>&1 )
    rc=$?
    resu="$(grep -a 'TESTS=' "$LOGDIR/$e.log" | tail -1 | sed 's/^ *//;s/  */ /g')"
    [ -n "$resu" ] && ligne "$e" "$resu"
    verifie "$e" "$rc"
done

# --- exemple 05 : RISC-V ---------------------------------------------------
section "exemple 05 - RISC-V (structure de reference)"
d="$REPO/examples/05-riscv-datapath/tb/alu"
if [ -d "$d" ]; then
    ( cd "$d" && make clean >/dev/null 2>&1; PATH="$(dirname "$(command -v "$GHDL_BIN")"):$PATH" make SIM="$SIM" > "$LOGDIR/05-alu.log" 2>&1 )
    rc=$?; [ -n "$(grep -a 'TESTS=' "$LOGDIR/05-alu.log")" ] && \
        ligne "05-riscv/tb/alu" "$(grep -a 'TESTS=' "$LOGDIR/05-alu.log" | tail -1 | sed 's/^ *//;s/  */ /g')"
    verifie "05-riscv/tb/alu" "$rc"
else
    ignore "05-riscv/tb/alu" "absent"
fi

# le testbench datapath EXIGE software/main.bin (non committe) : on verifie que
# l'absence produit un echec EXPLICITE, c'est le comportement voulu.
d="$REPO/examples/05-riscv-datapath/tb/riscv"
if [ -d "$d" ] && [ ! -f "$REPO/examples/05-riscv-datapath/software/main.bin" ]; then
    ( cd "$d" && make clean >/dev/null 2>&1; PATH="$(dirname "$(command -v "$GHDL_BIN")"):$PATH" make SIM="$SIM" > "$LOGDIR/05-riscv.log" 2>&1 )
    rc=$?
    if [ "$rc" -ne 0 ] && grep -qa "PROGRAMME RISC-V ABSENT" "$LOGDIR/05-riscv.log"; then
        ligne "05-riscv/tb/riscv (sans .bin)" "echec explicite, code $rc : OK"; ok=$((ok+1))
    else
        ligne "05-riscv/tb/riscv (sans .bin)" "attendu : echec + message clair"; ko=$((ko+1))
    fi
else
    ignore "05-riscv/tb/riscv" "main.bin present ou dossier absent"
fi

# --- exemple 04 : testbench VHDL pur (XSim ou GHDL) ------------------------
section "exemple 04 - testbench VHDL pur"
d="$REPO/examples/04-vhdl-testbench-xsim"
if [ $have_ghdl -eq 1 ]; then
    ( cd "$d" && rm -f work-obj08.cf
      "$GHDL_BIN" -a --std=08 rtl/word_parity_counter.vhd tb/tb_word_parity_counter.vhd > "$LOGDIR/04.log" 2>&1 &&
      "$GHDL_BIN" -m --std=08 tb_word_parity_counter >> "$LOGDIR/04.log" 2>&1 &&
      "$GHDL_BIN" -r --std=08 tb_word_parity_counter --assert-level=error >> "$LOGDIR/04.log" 2>&1 )
    rc=$?
    ligne "04 (GHDL)" "$(grep -a 'verifications' "$LOGDIR/04.log" | tail -1 | sed 's/^.*(report note): //')"
    verifie "04-vhdl-testbench-xsim" "$rc"
else
    ignore "04-vhdl-testbench-xsim" "ghdl absent"
fi
if [ -x "$d/tb/run_sim.sh" ] && command -v xvhdl >/dev/null 2>&1; then
    ( cd "$d/tb" && ./run_sim.sh > "$LOGDIR/04-xsim.log" 2>&1 )
    verifie "04 (XSim : run_sim.sh)" "$?"
else
    ignore "04 (XSim)" "xvhdl absent (sourcer Vivado)"
fi

# --- templates -------------------------------------------------------------
section "templates VHDL (compilation + testbench auto-verifiant)"
if [ $have_ghdl -eq 1 ]; then
    d="$REPO/templates/vhdl"
    ( cd "$d" && rm -f work-obj08.cf
      "$GHDL_BIN" -a --std=08 entity_combinatoire.vhd registre_synchrone.vhd compteur.vhd \
                    fsm_moore.vhd synchroniseur_2ff.vhd package_utils.vhd > "$LOGDIR/tpl.log" 2>&1 &&
      "$GHDL_BIN" -a --std=08 compteur.vhd tb_compteur.vhd >> "$LOGDIR/tpl.log" 2>&1 &&
      "$GHDL_BIN" -m --std=08 tb_compteur >> "$LOGDIR/tpl.log" 2>&1 &&
      "$GHDL_BIN" -r --std=08 tb_compteur --assert-level=error >> "$LOGDIR/tpl.log" 2>&1 )
    rc=$?
    ligne "templates/vhdl" "$(grep -a 'verifications' "$LOGDIR/tpl.log" | tail -1 | sed 's/^.*(report note): //')"
    verifie "templates/vhdl" "$rc"
else
    ignore "templates/vhdl" "ghdl absent"
fi

section "scripts Tcl (syntaxe + procedures executees)"
if [ $have_tclsh -eq 1 ]; then
    "$PY" "$REPO/scripts/check_tcl.py" > "$LOGDIR/tcl.log" 2>&1
    rc=$?; tail -2 "$LOGDIR/tcl.log" | sed 's/^/    /'
    verifie "scripts/check_tcl.py" "$rc"
else
    ignore "check_tcl.py" "tclsh absent"
fi

# --- serveur MCP -----------------------------------------------------------
section "serveur MCP (pytest)"
if "$PY" -c "import pytest" >/dev/null 2>&1; then
    ( cd "$REPO/mcp" && PYTHONPATH="$REPO/mcp" "$PY" -m pytest -q > "$LOGDIR/mcp.log" 2>&1 )
    rc=$?
    grep -aE "^[0-9]+ passed|failed" "$LOGDIR/mcp.log" | tail -1 | sed 's/^/    /'
    verifie "mcp/tests" "$rc"
else
    ignore "mcp/tests" "pytest absent"
fi

# --- cible EDA (facultative) ----------------------------------------------
section "cible EDA (Vivado) - facultative"
if [ $have_vivado -eq 1 ]; then
    "$PY" "$REPO/scripts/verify_vivado.py" > "$LOGDIR/vivado.log" 2>&1
    rc=$?
    tail -3 "$LOGDIR/vivado.log" | sed 's/^/    /'
    verifie "flux Vivado (synthese reelle)" "$rc"
else
    ignore "flux Vivado" "vivado absent du PATH (source settings64.sh)"
fi

# --- nettoyage (JAMAIS de fichiers versionnes : fixtures exclues) ----------
section "nettoyage des artefacts"
find "$REPO" -path "$REPO/.git" -prune -o -path "$REPO/mcp/tests/fixtures" -prune -o \
    \( -name "__pycache__" -o -name "sim_build" -o -name ".pytest_cache" -o -name "xsim.dir" \
       -o -name "*.cf" -o -name "*.pb" -o -name "results.xml" -o -name "*.ghw" \
       -o -name "*.wdb" -o -name "xsim*.log" -o -name "xelab.log" -o -name "xvlog.log" \) \
    -print -exec rm -rf {} + 2>/dev/null | sed 's/^/  supprime: /'
restants=$(find "$REPO" -path "$REPO/.git" -prune -o -path "$REPO/mcp/tests/fixtures" -prune -o -type f -print 2>/dev/null \
    | grep -cE "__pycache__|sim_build|\.cf$|results\.xml|\.pb$|\.ghw$")
ligne "artefacts restants" "$restants (0 attendu)"

printf '\n===== BILAN : %s OK, %s ECHEC, %s IGNORE =====\n' "$ok" "$ko" "$skipped"
if [ "$ko" -ne 0 ]; then
    printf 'Les logs sont dans %s\n' "$LOGDIR"
    exit 1
fi
printf 'Ce qui est IGNORE n a PAS ete verifie : ne pas le presenter comme valide.\n'
exit 0
