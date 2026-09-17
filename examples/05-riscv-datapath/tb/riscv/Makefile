# =============================================================================
# Testbench cocotb 2.x du datapath RV32I (examples/05-riscv-datapath).
# Verifie avec : cocotb 2.0.1 + GHDL 6.0.0 (backend mcode), VHDL-2008.
#
#   make                    compilation du design + test
#   make clean              supprime sim_build/ et results.xml
#
# ATTENTION : ce test a besoin du programme RISC-V compile
#             (software/main.bin). Ce binaire n'est PAS committe : voir la
#             section "Programme RISC-V" du README.md pour le generer.
#             Sans lui, le test echoue avec un message explicite.
#
#   make RISCV_BIN=/chemin/vers/main.bin      choisir un autre binaire
#
# Autres simulateurs :
#   make SIM=questa   /  make SIM=modelsim   (non testes ici, voir README.md)
# =============================================================================

SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl

# --- sources VHDL, dans l'ORDRE de compilation (dependances d'abord) ---------
VHDL_SOURCES += $(PWD)/../../rtl/alu/et_logique.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/ou_logique.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/somme.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/soustraction.vhd
VHDL_SOURCES += $(PWD)/../../rtl/alu/alu.vhd
VHDL_SOURCES += $(PWD)/../../rtl/decoder/decoder.vhd
VHDL_SOURCES += $(PWD)/../../rtl/registre/banc_registre.vhd
VHDL_SOURCES += $(PWD)/../../rtl/datapath.vhd

# --- top et module(s) de test ------------------------------------------------
# cocotb 2.x : COCOTB_TOPLEVEL / COCOTB_TEST_MODULES (TOPLEVEL / MODULE sont
# obsoletes). Le prefixe "work." n'est plus necessaire pour GHDL.
COCOTB_TOPLEVEL = datapath
COCOTB_TEST_MODULES = testbench_datapath

# --- VHDL-2008 : obligatoire a l'analyse ET a l'execution --------------------
GHDL_ARGS += --std=08

# --- programme RISC-V a charger ---------------------------------------------
# Chemin RELATIF a ce Makefile ; cocotb execute le test depuis sim_build/,
# donc on exporte un chemin ABSOLU vers le testbench.
RISCV_BIN ?= $(PWD)/../../software/main.bin
export RISCV_BIN := $(abspath $(RISCV_BIN))

# --- reproductibilite --------------------------------------------------------
export COCOTB_RANDOM_SEED ?= 1234

include $(shell cocotb-config --makefiles)/Makefile.sim
