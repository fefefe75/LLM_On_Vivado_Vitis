# =============================================================================
# open_project_gui.tcl - ouvre le mini-GPU dans l'IHM Vivado, SANS synthese.
#
# But : pouvoir LIRE et parcourir le code (VHDL, banc cocotb, reference C) dans
# Vivado, et consulter la hierarchie. Aucune compilation n'est lancee.
#
# Usage :
#   source ~/vivado/2025.2/Vivado/settings64.sh
#   vivado -mode gui -source scripts/open_project_gui.tcl
#
# Pour lancer la synthese ensuite : bouton "Run Synthesis" de la fenetre, ou
#   launch_runs synth_1 -jobs 8 ; wait_on_run synth_1 ; open_run synth_1
# Pour synthetiser automatiquement a l'ouverture : scripts/open_in_vivado.tcl
# =============================================================================

set script_dir [file dirname [file normalize [info script]]]
set racine     [file dirname $script_dir]

proc get_arg {args nom defaut} {
    set idx [lsearch -exact $args $nom]
    if {$idx < 0} { return $defaut }
    return [lindex $args [expr {$idx + 1}]]
}

set part  "xc7z020clg400-1"
set lanes [get_arg $argv --lanes "8"]
set prj_dir  [file join $racine "vivado_gui"]
set prj_file [file join $prj_dir "mini_gpu.xpr"]
set rtl      [file join $racine "rtl"]

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

    # Fichiers non-module : ils apparaissent dans l'arborescence et s'ouvrent dans
    # l'editeur de texte de Vivado (banc cocotb, reference C, scripts, README).
    set docs [list]
    foreach f [glob -nocomplain [file join $racine "tb" "*.py"] \
                          [file join $racine "software" "*.c"] \
                          [file join $racine "scripts" "*.tcl"] \
                          [file join $racine "README.md"]] {
        lappend docs $f
    }
    if {[llength $docs] > 0} {
        add_files -fileset sources_1 -norecurse $docs
        foreach f $docs { set_property IS_ENABLED 0 [get_files $f] }
    }

    set_property top top_mandelbrot [get_filesets sources_1]
    update_compile_order -fileset sources_1
}

set_property generic "C_LANES=$lanes C_IMG_W=640 C_IMG_H=480 C_MAX_ITER=128" [get_filesets sources_1]

# La hierarchie s'affiche immediatement dans le volet Sources. Pour le schema RTL
# (sans synthese, quelques secondes) : menu Flow > Open Elaborated Design.
puts "================= LE PROJET EST OUVERT, RIEN N'EST COMPILE ==================="
puts "  Volet Sources (gauche) : 4 fichiers VHDL + 'Non-module Files' (banc cocotb"
puts "      test_mandelbrot.py, mandelbrot_config.py, bench_lanes.py, baseline_c.c,"
puts "      scripts et README) -- double-clic = editeur de texte"
puts "  Double-clic sur mandelbrot_gpu.vhd : le coeur (repartiteur, file de resultats)"
puts "  Flow > Open Elaborated Design  : schema RTL, sans synthese (quelques secondes)"
puts "  Flow > Run Synthesis           : a lancer si tu veux le netlist et les chiffres"
puts "  Tcl Console : report_utilization / report_timing_summary apres synthese"
puts "============================================================================="
puts "Rappel des chiffres deja mesures (Vivado 2025.2, xc7z020clg400-1) :"
puts "  8 voies  : 99 DSP (45 %), WNS +0,244 ns -> 102,5 MHz (tient 100 MHz)"
puts "  16 voies : 195 DSP (88,6 %), WNS -1,583 ns -> 86,3 MHz"
