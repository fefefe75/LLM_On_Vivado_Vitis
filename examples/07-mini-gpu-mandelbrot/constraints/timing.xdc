# Contraintes minimales du mini-GPU pour la synthese et le placement-routage.
#
# Sans ce fichier, Vivado n'a AUCUNE horloge : `report_timing_summary` affiche alors
# « There are no user specified timing constraints » et aucun WNS n'est disponible.
# C'est le piege classique documente dans docs/07-timing-closure.md -- il a ete
# rencontre pour de vrai en ecrivant cet exemple (le script de synthese echouait sur
# `get_timing_paths` qui ne renvoyait aucun chemin).
#
# Les entrees/sorties ne sont volontairement PAS contraintes : le but ici est de
# mesurer ce que le moteur de calcul permet comme frequence, pas de construire un
# bitstream pour une carte (voir README, section "ce qui n'est PAS verifie").

# Horloge d'entree : 100 MHz (10 ns), soit la frequence de reference du banc de test.
create_clock -period 10.000 -name i_clk -waveform {0.000 5.000} [get_ports i_clk]

# Chemins asynchrones a ne pas analyser : reset et commandes externes.
set_false_path -from [get_ports {i_rst i_start i_px_ready}]
set_false_path -to   [get_ports {o_px_valid o_px_x o_px_y o_px_iter o_px_escaped o_busy o_done}]
