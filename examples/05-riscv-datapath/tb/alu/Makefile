# =============================================================================
# Testbench cocotb 2.x de l'ALU 32 bits (examples/05-riscv-datapath).
# Verifie avec : cocotb 2.0.1 + GHDL 6.0.0 (backend mcode), VHDL-2008.
#
#   make                    compilation + test
#   make SIM=ghdl           simulateur libre par defaut, sans licence
#   make clean              supprime sim_build/ et results.xml
#
# Autres simulateurs :
#   make SIM=questa         (Questa/ModelSim : GUI=1 + tb/*/waveform.do, non
#   make SIM=modelsim        testes sur cette machine, voir README.md)
#
# Ordre de compilation impose : les sous-modules avant alu.vhd, car l'entite
# "alu" les instancie directement (entity work.et_logique, ...).
# =============================================================================

SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl

# --- sources VHDL, dans l'ORDRE de compilation (dependances d'abord) ---------
VHDL_SOURCES += $(PWD)/../../rtl/alu/et_logique.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/ou_logique.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/somme.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/soustraction.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/alu.vhd

# --- top et module(s) de test ------------------------------------------------
# cocotb 2.x : COCOTB_TOPLEVEL remplace TOPLEVEL, COCOTB_TEST_MODULES remplace
# MODULE. Les anciens noms declenchent un avertissement de depreciation.
COCOTB_TOPLEVEL = alu
COCOTB_TEST_MODULES = testbench_alu

# --- VHDL-2008 : obligatoire a l'analyse ET a l'execution --------------------
# GHDL_ARGS est passe aux deux phases. Sans --std=08 :
# "cannot find entity or configuration alu".
GHDL_ARGS += --std=08

# --- reproductibilite --------------------------------------------------------
export COCOTB_RANDOM_SEED ?= 1234

# --- simulateurs sans support VHDL ------------------------------------------
ifneq ($(filter $(SIM),icarus verilator),)
$(warning SIM=$(SIM) ne compile pas le VHDL : utiliser SIM=ghdl (libre) ou SIM=questa)
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
