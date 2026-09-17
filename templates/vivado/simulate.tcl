# =============================================================================
# simulate.tcl — simulation avec le simulateur Vivado (XSim) depuis un projet
#
# Enchaine, de facon scriptee et reproductible :
#   1. ouverture (optionnelle) du projet .xpr ;
#   2. configuration du fileset de simulation (runtime, simulateur cible) ;
#   3. launch_simulation  -> compile + elabore + charge la simulation ;
#   4. run all            -> execute jusqu'a la fin de la simulation ;
#   5. close_simulation   -> fermeture propre ;
#   6. verification du journal de simulation (marqueur "ALL TESTS PASSED").
#
# Usage (mode batch, depuis la racine du projet) :
#   vivado -mode batch -source templates/vivado/simulate.tcl
#   vivado -mode batch -source templates/vivado/simulate.tcl -tclargs mon_projet.xpr
#
# Usage depuis la console Tcl d'un projet deja ouvert :
#   source templates/vivado/simulate.tcl
#
# Reference des commandes utilisees : UG835 (launch_simulation, run, close_simulation)
# et UG900 (proprietes xsim.simulate.runtime, xsim.simulate.log_all_signals).
#
# Remarque : ce script est la version "projet". L'equivalent hors projet
# (sans .xpr) est examples/04-vhdl-testbench-xsim/tb/run_sim.sh, qui appelle
# directement xvhdl / xelab / xsim.
# =============================================================================

# -----------------------------------------------------------------------------
# 1. Parametres (a adapter : aucun chemin n'est code en dur ailleurs)
# -----------------------------------------------------------------------------
set sim_project  ""                        ;# .xpr a ouvrir ; "" = projet deja ouvert
set sim_set      "sim_1"                   ;# fileset de simulation
set sim_mode     "behavioral"              ;# behavioral | post-synthesis | post-implementation
set sim_runtime  "all"                     ;# "all" ou une duree, ex. "100us"
set sim_top      "tb_word_parity_counter"  ;# top de simulation attendu
set pass_token   "ALL TESTS PASSED"        ;# marqueur emis par le testbench auto-verifiant
set err_object   "/tb_word_parity_counter/s_errors" ;# compteur d'erreurs du testbench

# Le .xpr peut aussi etre passe en argument : vivado ... -source simulate.tcl -tclargs proj.xpr
if {[llength $argv] >= 1} {
    set sim_project [lindex $argv 0]
}

# -----------------------------------------------------------------------------
# 2. Ouverture du projet
# -----------------------------------------------------------------------------
if {$sim_project ne ""} {
    if {[catch {open_project $sim_project} err]} {
        puts "ERREUR : open_project $sim_project -> $err"
        exit 1
    }
}

set proj [current_project]
set proj_name [get_property NAME $proj]
puts "=== Projet : $proj_name ==="

# -----------------------------------------------------------------------------
# 3. Configuration du fileset de simulation
# -----------------------------------------------------------------------------
set_property target_simulator XSim $proj

if {[catch {set_property -name {xsim.simulate.runtime} -value $sim_runtime \
                -objects [get_filesets $sim_set]} err]} {
    puts "AVERTISSEMENT : xsim.simulate.runtime non applique -> $err"
}

# Trace d'ondes (facultatif) : decommenter pour forcer l'enregistrement de tous
# les signaux, puis utiliser xsim_wave.tcl / un .wcfg pour l'affichage.
# set_property -name {xsim.simulate.log_all_signals} -value true -objects [get_filesets $sim_set]

set top_actuel [get_property TOP [get_filesets $sim_set]]
if {$top_actuel ne $sim_top} {
    puts "AVERTISSEMENT : top du fileset $sim_set = '$top_actuel' (attendu '$sim_top')"
}

# -----------------------------------------------------------------------------
# 4. Lancement de la simulation (compile + elaborate + simulate)
# -----------------------------------------------------------------------------
puts "=== launch_simulation -mode $sim_mode -simset $sim_set ==="
if {[catch {launch_simulation -mode $sim_mode -simset $sim_set} err]} {
    puts "ERREUR : launch_simulation -> $err"
    exit 1
}

# -----------------------------------------------------------------------------
# 5. Conduite de la simulation puis fermeture
#    `run all` termine naturellement : le testbench coupe son horloge en fin de
#    test, il n'y a donc plus aucun evenement a traiter.
# -----------------------------------------------------------------------------
puts "=== run all ==="
if {[catch {run all} err]} {
    puts "ERREUR : run all -> $err"
    catch {close_simulation}
    exit 1
}

set t_fin "?"
catch {set t_fin [current_time]}
puts "=== Simulation terminee a $t_fin ==="

# Lecture du compteur d'erreurs du testbench dans la base de simulation
set n_errors "?"
if {[catch {set n_errors [get_value -radix unsigned $err_object]} err]} {
    puts "NOTE : $err_object illisible ($err)"
} else {
    puts "=== Compteur d'erreurs du testbench : $n_errors ==="
}

if {[catch {close_simulation} err]} {
    puts "ERREUR : close_simulation -> $err"
    exit 1
}

# -----------------------------------------------------------------------------
# 6. Verification du journal de simulation
#    Le journal est ecrit par xsim dans :
#      <projet>.sim/<fileset>/<mode>/xsim/simulate.log
#    (behav = behavioral, synth = post-synthesis, impl = post-implementation)
# -----------------------------------------------------------------------------
set proj_dir [pwd]
catch {set proj_dir [get_property DIRECTORY $proj]}

set mode_dir [string map {behavioral behav post-synthesis synth post-implementation impl} $sim_mode]
set sim_log [file join $proj_dir "${proj_name}.sim" $sim_set $mode_dir "xsim" "simulate.log"]

if {![file exists $sim_log]} {
    puts "AVERTISSEMENT : journal introuvable : $sim_log"
    puts "                verifiez manuellement la presence de \"$pass_token\"."
    exit 0
}

set fh [open $sim_log r]
set data [read $fh]
close $fh

if {[string first $pass_token $data] >= 0} {
    puts "OK : \"$pass_token\" trouve dans $sim_log"
    exit 0
}

puts "ECHEC : \"$pass_token\" ABSENT de $sim_log"
exit 1

# -----------------------------------------------------------------------------
# Alternative : Vivado peut sourcer un Tcl de simulation automatiquement.
#   - propriete xsim.simulate.custom_tcl : Tcl source a la place du fichier
#     genere par Vivado pour l'etape de simulation ;
#   - propriete xsim.simulate.tcl.post   : Tcl execute apres la simulation.
# Exemple :
#   set_property -name {xsim.simulate.tcl.post} -value {/chemin/post.tcl} \
#                -objects [get_filesets sim_1]
# -----------------------------------------------------------------------------
