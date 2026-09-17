# =============================================================================
# Exemple 03 : FIFO synchrone generique (VHDL) + testbench cocotb 2.x, GHDL.
#
#   cd examples/03-fifo/tb
#   make                                             analyse + simulation
#   make COCOTB_TESTCASE=test_vidage_et_ordre_fifo   un seul test
#   make clean                                       sim_build/ + results.xml
#
# Pour un DUT Verilog, voir les modeles reutilisables
# templates/cocotb/Makefile.icarus et templates/cocotb/Makefile.verilator.
#
# Variables cocotb 2.x (les anciennes MODULE / TOPLEVEL sont depreciees) :
#   COCOTB_TEST_MODULES : module Python contenant les tests
#   COCOTB_TOPLEVEL     : entite VHDL elaboree comme top-level
#   COCOTB_RESULTS_FILE : rapport JUnit XML ecrit par cocotb
#   SIM_BUILD           : repertoire de travail du simulateur
# =============================================================================

SIM           ?= ghdl
TOPLEVEL_LANG ?= vhdl

# Source VHDL : chemin relatif au dossier du Makefile (tb/ -> ../rtl/).
VHDL_SOURCES += $(PWD)/../rtl/fifo_sync.vhd

COCOTB_TOPLEVEL     = fifo_sync
COCOTB_TEST_MODULES = test_fifo

# VHDL-2008 est necessaire pour les fonctions locales et les assertions
# d'elaboration ; l'option doit s'appliquer a l'analyse ET a l'execution
# (Makefile.ghdl reutilise GHDL_ARGS dans les deux phases).
GHDL_ARGS += --std=08

# Horloge de simulation : 10 ns de periode par defaut cote Python.
COCOTB_HDL_TIMEUNIT      ?= 1ns
COCOTB_HDL_TIMEPRECISION ?= 1ps

# Reproductibilite (convention du depot) : graine cocotb fixe. Le test
# aleatoire utilise en plus son propre random.Random(RANDOM_SEED), ses vecteurs
# ne dependent donc pas de cette graine.
export COCOTB_RANDOM_SEED ?= 1234

include $(shell cocotb-config --makefiles)/Makefile.sim
