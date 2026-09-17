# =============================================================================
# Script de visualisation Questa / ModelSim pour le datapath RV32I
# (examples/05-riscv-datapath/tb/riscv).
#
# Fichier repris du projet d'origine, corrige : il visait work.alu et ne
# compilait que les sources de l'ALU alors qu'il est place dans tb/riscv/.
#
# Non teste sur cette machine : Questa/ModelSim n'y est pas installe. Le flux
# verifie est SIM=ghdl (voir README.md).
#
# Utilisation :
#   make SIM=questa GUI=1                 (cocotb compile puis ouvre la GUI)
#   vsim -do waveform.do work.datapath    (a la main, apres vlib/vcom)
#
# Les chemins sont relatifs au dossier tb/riscv/.
# =============================================================================

# --- Compilation des sources VHDL (dependances d'abord) ----------------------
vlib work
vcom -2008 ../../rtl/alu/et_logique.vhd
vcom -2008 ../../rtl/alu/ou_logique.vhd
vcom -2008 ../../rtl/alu/somme.vhd
vcom -2008 ../../rtl/alu/soustraction.vhd
vcom -2008 ../../rtl/alu/alu.vhd
vcom -2008 ../../rtl/decoder/decoder.vhd
vcom -2008 ../../rtl/registre/banc_registre.vhd
vcom -2008 ../../rtl/datapath.vhd

# --- Chargement du design ----------------------------------------------------
vsim -gui work.datapath

# --- Configuration des waveforms ---------------------------------------------
add wave -r /*
add wave -divider "PC / Instructions"
add wave -hex /datapath/i_pc
add wave -hex /datapath/i_instruction
add wave -hex /datapath/o_next_pc
add wave -divider "RAM"
add wave -hex /datapath/o_ram_addr
add wave -hex /datapath/o_ram_data
add wave /datapath/o_mem_read
add wave /datapath/o_mem_write
add wave /datapath/o_branch
view wave
run -all
