# =============================================================================
# Exemple 01 : compteur VHDL + testbench cocotb 2.x, simulateur GHDL (libre)
# Lancement :  make            (tous les tests)
#              make WAVES=1    (genere counter.ghw, ouvrable dans GTKWave/Surfer)
# =============================================================================

SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl

VHDL_SOURCES += $(PWD)/../rtl/counter.vhd

# cocotb 2.x : COCOTB_TOPLEVEL / COCOTB_TEST_MODULES (TOPLEVEL / MODULE = obsoletes)
COCOTB_TOPLEVEL = counter
COCOTB_TEST_MODULES = test_counter

# VHDL-2008 a l'analyse ET a l'execution (sinon : cannot find entity or configuration)
GHDL_ARGS += --std=08

# Tests reproductibles
export COCOTB_RANDOM_SEED ?= 1234

include $(shell cocotb-config --makefiles)/Makefile.sim
