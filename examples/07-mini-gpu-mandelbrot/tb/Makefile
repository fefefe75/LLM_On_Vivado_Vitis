# =============================================================================
# Banc de test du mini-GPU Mandelbrot (cocotb 2.x + GHDL).
#
#   make                    # petite image 96x64, 8 lanes, 64 iterations
#   make COCOTB_TESTCASE=test_petite_image_egale_le_modele
#   make clean
#
# Les parametres du design sont des GENERIQUES VHDL : ils se passent a l'elaboration.
# Sous GHDL, c'est l'etape `ghdl -r` qui les accepte, d'ou GHDL_RUN_ARGS (et non
# GHDL_ARGS, qui alimente aussi `ghdl -i`/`-m` et refuserait -g sur l'analyse).
#
# !!! Ces valeurs doivent rester identiques a `mandelbrot_config.generiques()` :
#     verifier avec `python3 mandelbrot_config.py`. Le banc de test relit la
#     configuration effective sur les ports o_cfg_* du design, donc une divergence
#     ferait echouer la comparaison (c'est voulu : c'est un garde-fou).
# =============================================================================

SIM ?= ghdl
TOPLEVEL_LANG = vhdl

COCOTB_TOPLEVEL := mandelbrot_gpu
COCOTB_TEST_MODULES := test_mandelbrot

VHDL_SOURCES := $(PWD)/../rtl/mandelbrot_pkg.vhd \
                $(PWD)/../rtl/mandelbrot_lane.vhd \
                $(PWD)/../rtl/mandelbrot_gpu.vhd

GHDL_ARGS += --std=08

# Generiques : 96x64, 8 lanes, 64 iterations, fenetre (-2.1..0.7) x (-1.2..1.2) en Q26.
GHDL_RUN_ARGS += -gC_IMG_W=96 -gC_IMG_H=64 -gC_LANES=8 -gC_MAX_ITER=64 \
                 -gC_XW=7 -gC_YW=7 -gC_FRAC=26 \
                 -gC_X0=-140928614 -gC_Y0=-80530637 \
                 -gC_DX=1957342 -gC_DY=2516582

# Reproductibilite : aucune graine aleatoire dans ce banc, mais on fige la variable
# par coherence avec les autres exemples du depot.
export COCOTB_RANDOM_SEED ?= 1234

# Les images produites par le test (.ppm + .png) atterrissent ici.
export MANDEL_IMG_DIR ?= $(PWD)/images

include $(shell cocotb-config --makefiles)/Makefile.sim

# ---------------------------------------------------------------------------
# Cibles complementaires (au-dela du test principal)
# ---------------------------------------------------------------------------

# Mesure l'acceleration par nombre de lanes : chaque configuration est elaboree et
# simulee, puis les compteurs materiels (o_cycles) sont lus.
bench:
	python3 bench_lanes.py --lanes 1 2 4 8 16

# Meme banc avec la configuration du Makefile, en une passe rapide
mesure:
	python3 bench_lanes.py --lanes 8 -w 128 -H 96 -i 64
