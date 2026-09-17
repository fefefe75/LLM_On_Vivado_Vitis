# =============================================================================
# xsim_wave.tcl — trace d'ondes XSim (script de commandes batch)
#
# Usage interactif / graphique :
#     xsim tb_sim -gui -t xsim_wave.tcl
# Usage batch (sans GUI, genere le .wdb puis quitte) :
#     xsim tb_sim -t xsim_wave.tcl
#
# Prerequis : l'elaboration doit avoir ete faite avec -debug typical
# (`xelab -debug typical -s tb_sim ...`), sinon les signaux internes du
# testbench et du DUT ne sont pas visibles.
#
# Ce script est OPTIONNEL : le testbench est auto-verifiant et ne produit
# aucun fichier de trace. Les ondes servent uniquement au debogage manuel.
#
# Radix valides pour add_wave (UG900) : bin, oct, hex, dec, unsigned, ascii.
# =============================================================================

# --- Signaux du testbench -----------------------------------------------------
add_wave -radix bin      /tb_word_parity_counter/s_clk
add_wave -radix bin      /tb_word_parity_counter/s_rst
add_wave -radix bin      /tb_word_parity_counter/s_valid
add_wave -radix hex      /tb_word_parity_counter/s_data
add_wave -radix unsigned /tb_word_parity_counter/s_errors
add_wave -radix unsigned /tb_word_parity_counter/s_checks
add_wave                 /tb_word_parity_counter/s_done

# --- Sorties du DUT (parite paire) -------------------------------------------
add_wave -radix bin      /tb_word_parity_counter/dut_even/o_valid
add_wave -radix bin      /tb_word_parity_counter/dut_even/o_parity
add_wave -radix unsigned /tb_word_parity_counter/dut_even/o_words

# --- Sorties du DUT (parite impaire) -----------------------------------------
add_wave -radix bin      /tb_word_parity_counter/dut_odd/o_valid
add_wave -radix bin      /tb_word_parity_counter/dut_odd/o_parity
add_wave -radix unsigned /tb_word_parity_counter/dut_odd/o_words

# --- Etat interne du DUT pair (visible grace a -debug typical) ----------------
add_wave -radix hex      /tb_word_parity_counter/dut_even/s_data_r
add_wave -radix bin      /tb_word_parity_counter/dut_even/s_valid_r

# --- Execution ----------------------------------------------------------------
run all
quit
