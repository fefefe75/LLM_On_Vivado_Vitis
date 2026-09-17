# =============================================================================
# Testbench cocotb 2.x de l'ALU combinatoire (examples/02-alu).
# Verifie avec : cocotb 2.0.1 + GHDL 6.0.0 (backend mcode), VHDL-2008.
#
#   make                                       compilation + tests
#   make SIM=ghdl                              VHDL libre, sans licence
#   make COCOTB_TESTCASE=test_golden_vectors   un seul test
#   make ALU_RANDOM_VECTORS=20000              campagne aleatoire plus longue
#   make COCOTB_RANDOM_SEED=999                autre graine
#   make clean                                 supprime sim_build/ et results.xml
#
# Traces : le backend GHDL de cocotb ne gere pas WAVES=1, et le binaire mcode
# 6.0.0 refuse --wave=FILE. Voir la section "Autres simulateurs" du README.
# =============================================================================

SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl

# --- sources VHDL, dans l'ORDRE de compilation (dependances d'abord) ---------
VHDL_SOURCES += $(PWD)/../rtl/alu_pkg.vhd
VHDL_SOURCES += $(PWD)/../rtl/alu.vhd

# --- top et module(s) de test ------------------------------------------------
# cocotb 2.x : COCOTB_TOPLEVEL remplace TOPLEVEL et COCOTB_TEST_MODULES
# remplace MODULE. Les anciens noms declenchent un avertissement de
# depreciation, et MODULE est ignore.
COCOTB_TOPLEVEL = alu
COCOTB_TEST_MODULES = test_alu

# --- VHDL-2008 : obligatoire a l'analyse ET a l'execution --------------------
# GHDL_ARGS est passe aux deux phases (analyse et run). Sans --std=08 :
# "cannot find entity or configuration alu".
GHDL_ARGS += --std=08

# --- reproductibilite --------------------------------------------------------
# Graine fixe : les vecteurs aleatoires de test_random_vectors sont rejouables.
export COCOTB_RANDOM_SEED ?= 1234

# --- taille de la campagne aleatoire (lue par tb/test_alu.py) ----------------
export ALU_RANDOM_VECTORS ?= 2000

# --- simulateurs sans support VHDL ------------------------------------------
# Icarus et Verilator ne compilent que Verilog et SystemVerilog. Voir la
# section "Autres simulateurs" du README pour porter l'ALU en Verilog.
ifneq ($(filter $(SIM),icarus verilator),)
$(warning SIM=$(SIM) ne compile pas le VHDL : il faut un portage Verilog de l'ALU, voir README.md)
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
