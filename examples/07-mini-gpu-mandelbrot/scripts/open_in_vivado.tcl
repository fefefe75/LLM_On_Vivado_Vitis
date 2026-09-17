# =============================================================================
# open_in_vivado.tcl - ouvre le mini-GPU dans l'IHM Vivado (mode graphique)
#
# Cree (ou rouvre) un projet Vivado contenant :
#   * les 4 sources VHDL            -> Sources, RTL Analysis, schematic
#   * les contraintes               -> constraints/timing.xdc (horloge 100 MHz)
#   * le banc de test cocotb et la reference C, ajoutes comme fichiers non-module
#     pour pouvoir les LIRE dans l'editeur de Vivado (c'est le but : voir le code)
# puis lance la synthese pour que le schema synthetise soit disponible.
#
# Usage (depuis le terminal, avec un affichage disponible) :
#   source ~/vivado/2025.2/Vivado/settings64.sh
#   vivado -mode gui -source scripts/open_in_vivado.tcl
#
# Options : --lanes N (defaut 8 : la configuration qui tient 100 MHz)
# =============================================================================

set script_dir [file dirname [file normalize [info script]]]
set racine     [file dirname $script_dir]

proc get_arg {args nom defaut} {
    set idx [lsearch -exact $args $nom]
    if {$idx < 0} { return $defaut }
    return [lindex $args [expr {$idx + 1}]]
}

set part   "xc7z020clg400-1"
set lanes  [get_arg $argv --lanes "8"]
set prj_dir [file join $racine "vivado_gui"]
set prj_file [file join $prj_dir "mini_gpu.xpr"]
set rtl [file join $racine "rtl"]

# ------------------------------------------------------------------- projet
if {[file exists $prj_file]} {
    puts "== reouverture du projet $prj_file"
    open_project $prj_file
} else {
    puts "== creation du projet $prj_file (part $part)"
    create_project mini_gpu $prj_dir -part $part -force

    add_files -fileset sources_1 -norecurse [list \
        [file join $rtl "mandelbrot_pkg.vhd"] \
        [file join $rtl "mandelbrot_lane.vhd"] \
        [file join $rtl "mandelbrot_gpu.vhd"] \
        [file join $rtl "top_mandelbrot.vhd"]]

    add_files -fileset constrs_1 -norecurse [file join $racine "constraints" "timing.xdc"]

    # Fichiers "non-module" : ils n'entrent pas dans la synthese, mais Vivado les
    # affiche dans l'arborescence du projet et les ouvre dans son editeur de texte.
    set docs [list]
    foreach f [glob -nocomplain [file join $racine "tb" "*.py"] \
                          [file join $racine "software" "*.c"] \
                          [file join $racine "README.md"] \
                          [file join $racine "scripts" "synth_vivado.tcl"]] {
        lappend docs $f
    }
    if {[llength $docs] > 0} {
        add_files -fileset sources_1 -norecurse $docs
        foreach f $docs { set_property IS_ENABLED 0 [get_files $f] }
    }

    set_property top top_mandelbrot [get_filesets sources_1]
    update_compile_order -fileset sources_1
}

# Generiques du top (l'equivalent des -g... de GHDL et des C_... du Makefile).
set_property generic "C_LANES=$lanes C_IMG_W=640 C_IMG_H=480 C_MAX_ITER=128" [get_filesets sources_1]
puts "== generiques du top : [get_property generic [get_filesets sources_1]]"

# ------------------------------------------------------------- synthese
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    puts "== lancement de la synthese (1 a 3 minutes, la barre de progression est en bas)"
    launch_runs synth_1 -jobs 8
    wait_on_run synth_1
} else {
    puts "== synthese deja terminee (PROGRESS=100%)"
}
puts "== statut synth_1 : [get_property STATUS [get_runs synth_1]]"

# Ouvre le design synthetise : le schema, la hierarchie et le timing sont alors
# accessibles depuis la fenetre (onglet Schematic, rapport d'utilisation, etc.).
open_run synth_1 -name synth_1
report_utilization -name rapport_gui
puts "== design synthetise ouvert dans l'IHM"

# ------------------------------------------------------------------- guide
puts "================= A REGARDER DANS LA FENETRE ================="
puts "  Sources (volet de gauche)  : les 4 fichiers VHDL, doubles-clic = editeur"
puts "                               le banc de test cocotb (*.py) et baseline_c.c"
puts "                               sont dans 'Non-module Files'"
puts "  RTL Analysis > Open Elaborated Design > Schematic : le schema porte"
puts "                               (voies, repartiteur, file de resultats)"
puts "  SYNTHESIS > Open Synthesized Design > Schematic    : ce que Vivado a"
puts "                               reellement infere (multiplicateurs -> DSP48)"
puts "  Reports > Report Utilization / Timing Summary      : les chiffres du README"
puts "  Tcl Console : 'report_dsp48' ou 'get_cells -hier -filter {REF_NAME =~ DSP48*}'"
puts "=============================================================="
puts "Rappel : pour voir le design PLACE ET ROUTE :"
puts "  open_checkpoint /tmp/mgpu_synth8/top_mandelbrot_routed.dcp"
