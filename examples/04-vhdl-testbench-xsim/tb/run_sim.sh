#!/usr/bin/env bash
# =============================================================================
# run_sim.sh — simulation XSim (Vivado Simulator) en ligne de commande
#
# Objectif : rejouer, hors de l'IDE Vivado, exactement les etapes que
# `launch_simulation` genere dans un projet (analyse -> elaboration ->
# execution), avec des variables pour tous les chemins.
#
# Usage :
#   ./run_sim.sh              # flux explicite : 4 commandes XSim
#   ./run_sim.sh --prj        # flux par fichier de projet : 3 commandes XSim
#   ./run_sim.sh --dry-run    # n'execute rien, affiche les commandes
#   ./run_sim.sh clean        # supprime les artefacts (XSim et GHDL)
#   ./run_sim.sh --help
#
# Prerequis : XSim (xvhdl, xelab, xsim) dans le PATH, ou XVHDL/XELAB/XSIM
# pointant vers l'installation Vivado, par exemple :
#   XVHDL=/tools/Xilinx/Vivado/2023.2/bin/xvhdl ./run_sim.sh
#
# Le testbench est auto-verifiant : il coupe lui-meme son horloge en fin de
# test, donc `xsim -R` (run all) se termine sans temps d'arret.
# =============================================================================

set -o errexit
set -o nounset
set -o pipefail

# -----------------------------------------------------------------------------
# 1. Outils (surchargeables par variables d'environnement)
# -----------------------------------------------------------------------------
XVHDL="${XVHDL:-xvhdl}"    # analyseur VHDL (ex. xvlog pour du Verilog)
XELAB="${XELAB:-xelab}"    # elaboration : construit le snapshot de simulation
XSIM="${XSIM:-xsim}"       # executant : charge le snapshot et simule

# -----------------------------------------------------------------------------
# 2. Chemins (a adapter si l'arborescence du projet change)
# -----------------------------------------------------------------------------
TB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RTL_DIR="$(cd "${TB_DIR}/../rtl" && pwd)"

RTL_FILE="${RTL_DIR}/word_parity_counter.vhd"
TB_FILE="${TB_DIR}/tb_word_parity_counter.vhd"
PRJ_FILE="${TB_DIR}/xsim_sources.prj"     # liste de sources (xvhdl/xelab -prj)
WAVE_TCL="${TB_DIR}/xsim_wave.tcl"        # trace d'ondes facultative

# -----------------------------------------------------------------------------
# 3. Parametres de simulation
# -----------------------------------------------------------------------------
LIB="work"                                # bibliotheque de travail
TOP="tb_word_parity_counter"              # entite testbench (top)
SNAPSHOT="tb_sim"                         # nom du snapshot elabore
VHDL_STD="-2008"                          # analyse VHDL-2008 (cf. xvhdl -2008)
RUN_LOG="${TB_DIR}/xsim_run.log"          # sortie brute de xsim (pour le grep)
PASS_TOKEN="ALL TESTS PASSED"             # marqueur emis par le testbench

# -----------------------------------------------------------------------------
# 4. Analyse des arguments
# -----------------------------------------------------------------------------
MODE="explicit"
DRY_RUN=0

usage () {
  awk 'NR>1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
}

for arg in "$@"; do
  case "${arg}" in
    --prj|-p)    MODE="prj" ;;
    --dry-run|-n) DRY_RUN=1 ;;
    clean)       MODE="clean" ;;
    --help|-h)   usage; exit 0 ;;
    *) printf "Argument inconnu : %s (--help pour l'aide)\n" "${arg}" >&2; exit 2 ;;
  esac
done

# -----------------------------------------------------------------------------
# 5. Utilitaires
# -----------------------------------------------------------------------------
#! Affiche puis execute une commande (ou l'affiche seulement en --dry-run).
run_cmd () {
  printf '  $ %s\n' "$*"
  if [ "${DRY_RUN}" -eq 1 ]; then
    return 0
  fi
  "$@"
}

#! Verifie la presence des outils demandes.
check_tools () {
  local tool
  for tool in "${XVHDL}" "${XELAB}" "${XSIM}"; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      printf 'ERREUR : %s introuvable.\n' "${tool}" >&2
      printf '         XSim fait partie de Vivado : ajoutez le repertoire\n' >&2
      printf '         <Vivado>/bin au PATH, ou passez XVHDL/XELAB/XSIM=...\n' >&2
      printf '         (alternative libre : voir les commandes GHDL du README).\n' >&2
      exit 127
    fi
  done
}

#! Supprime les artefacts de simulation du repertoire tb/.
do_clean () {
  cd "${TB_DIR}"
  printf 'Nettoyage de %s\n' "${TB_DIR}"
  # XSim
  rm -rf xsim.dir .Xil
  rm -f xsim.log xelab.log xvhdl.log xvlog.log xsim_run.log ./*.jou ./*.wdb
  # GHDL / autres simulateurs
  rm -f ./*.cf work-obj*.cf ./*.o ./*.vcd ./*.fst ./*.ghw
  printf 'OK\n'
}

# -----------------------------------------------------------------------------
# 6. Flux "explicite" : 4 commandes XSim lancees a la main
#    1) analyse VHDL du RTL
#    2) analyse VHDL du testbench
#    3) elaboration avec debug (xelab -debug typical -s tb_sim)
#    4) execution (xsim tb_sim -R  <=> run all puis quit)
# -----------------------------------------------------------------------------
run_explicit () {
  cd "${TB_DIR}"
  printf '=== XSim, flux explicite (4 commandes) ===\n'

  printf '\n--- [1/4] analyse VHDL du RTL ---\n'
  run_cmd "${XVHDL}" "${VHDL_STD}" -work "${LIB}" "${RTL_FILE}"

  printf '\n--- [2/4] analyse VHDL du testbench ---\n'
  run_cmd "${XVHDL}" "${VHDL_STD}" -work "${LIB}" "${TB_FILE}"

  printf '\n--- [3/4] elaboration : snapshot %s ---\n' "${SNAPSHOT}"
  run_cmd "${XELAB}" -debug typical -s "${SNAPSHOT}" "${LIB}.${TOP}"

  printf '\n--- [4/4] execution : run all (-R) ---\n'
  if [ "${DRY_RUN}" -eq 1 ]; then
    printf '  $ %s | tee %s\n' "${XSIM} ${SNAPSHOT} -R" "${RUN_LOG}"
    return 0
  fi
  set +o errexit
  "${XSIM}" "${SNAPSHOT}" -R 2>&1 | tee "${RUN_LOG}"
  local rc="${PIPESTATUS[0]}"
  set -o errexit
  final_check "${rc}"
}

# -----------------------------------------------------------------------------
# 7. Flux "prj" : 3 commandes, sources decrites dans xsim_sources.prj
# -----------------------------------------------------------------------------
run_prj () {
  cd "${TB_DIR}"
  printf '=== XSim, flux fichier de projet (3 commandes) ===\n'

  printf '\n--- [1/3] analyse des sources listees dans %s ---\n' "$(basename "${PRJ_FILE}")"
  run_cmd "${XVHDL}" -prj "${PRJ_FILE}"

  printf '\n--- [2/3] elaboration depuis le fichier de projet ---\n'
  run_cmd "${XELAB}" -prj "${PRJ_FILE}" -debug typical -s "${SNAPSHOT}" "${LIB}.${TOP}"

  printf '\n--- [3/3] execution : run all (-R) ---\n'
  if [ "${DRY_RUN}" -eq 1 ]; then
    printf '  $ %s | tee %s\n' "${XSIM} ${SNAPSHOT} -R" "${RUN_LOG}"
    return 0
  fi
  set +o errexit
  "${XSIM}" "${SNAPSHOT}" -R 2>&1 | tee "${RUN_LOG}"
  local rc="${PIPESTATUS[0]}"
  set -o errexit
  final_check "${rc}"
}

#! Verifie le code de retour de xsim et la presence de "ALL TESTS PASSED".
final_check () {
  local rc="$1"
  printf '\n=== Resultat ===\n'
  if [ "${rc}" -ne 0 ]; then
    printf "ECHEC : xsim s'est arrete avec le code %s (voir %s)\n" "${rc}" "${RUN_LOG}" >&2
    exit 1
  fi
  if grep -q "${PASS_TOKEN}" "${RUN_LOG}"; then
    printf 'OK : "%s" trouve dans %s\n' "${PASS_TOKEN}" "${RUN_LOG}"
    printf "Trace d'ondes facultative : xsim %s -gui -t %s\n" \
           "${SNAPSHOT}" "$(basename "${WAVE_TCL}")"
    exit 0
  fi
  printf 'ECHEC : "%s" absent de %s\n' "${PASS_TOKEN}" "${RUN_LOG}" >&2
  exit 1
}

# -----------------------------------------------------------------------------
# 8. Programme principal
# -----------------------------------------------------------------------------
case "${MODE}" in
  clean)    do_clean ;;
  explicit) if [ "${DRY_RUN}" -eq 0 ]; then check_tools; fi; run_explicit ;;
  prj)      if [ "${DRY_RUN}" -eq 0 ]; then check_tools; fi; run_prj ;;
esac
