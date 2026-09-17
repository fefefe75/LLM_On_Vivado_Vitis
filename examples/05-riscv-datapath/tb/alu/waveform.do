# =============================================================================
# Script de visualisation Questa / ModelSim pour l'ALU 32 bits
# (examples/05-riscv-datapath/tb/alu).
#
# Non teste sur cette machine : Questa/ModelSim n'y est pas installe. Le flux
# verifie est SIM=ghdl (voir README.md).
#
# Utilisation :
#   make SIM=questa GUI=1                 (cocotb compile puis ouvre la GUI)
#   vsim -do waveform.do work.alu         (a la main, apres vcom/vlib)
#
# Les chemins sont relatifs au dossier tb/alu/.
# =============================================================================

# --- Compilation des sources VHDL (dependances d'abord) ----------------------
vlib work
vcom -2008 ../../rtl/alu/et_logique.vhd
vcom -2008 ../../rtl/alu/ou_logique.vhd
vcom -2008 ../../rtl/alu/somme.vhd
vcom -2008 ../../rtl/alu/soustraction.vhd
vcom -2008 ../../rtl/alu/alu.vhd

# --- Chargement du design ----------------------------------------------------
vsim -gui work.alu

# --- Configuration des waveforms ---------------------------------------------
add wave -r /*
add wave -divider "Entrees"
add wave -hex /alu/i_val_1
add wave -hex /alu/i_val_2
add wave -hex /alu/i_opcode
add wave -divider "Sorties"
add wave -hex /alu/o_data
add wave /alu/o_flag
view wave
run -all
