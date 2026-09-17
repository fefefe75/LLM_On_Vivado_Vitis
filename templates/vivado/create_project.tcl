# =============================================================================
# create_project.tcl - creation d'un projet Vivado complet depuis les sources
#
# Usage :
#   vivado -mode batch -source scripts/create_project.tcl -nolog -nojournal \
#          -tclargs --name mon_projet --part xc7z020clg400-1 --top top
#
# Variables (par defaut) :
#   --name   nom du projet ET du dossier .xpr          (defaut : prj)
#   --dir    dossier ou creer le projet                (defaut : . )
#   --part   partie FPGA ciblee                        (defaut : xc7a35tcsg324-1)
#   --top    entite top-level                          (defaut : top)
#   --lang   VHDL | Verilog | SystemVerilog            (defaut : VHDL)
#
# Le projet est TOUJOURS recree (-force) : ne jamais editer un .xpr a la main.
# =============================================================================

proc get_arg {args key default} {
    set idx [lsearch -exact $args $key]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        return [lindex $args [expr {$idx + 1}]]
    }
    return $default
}

# Collecte recursive des fichiers d'une extension donnee (Tcl glob n'a pas de **).
proc collect_sources {root ext} {
    set files {}
    set stack [list $root]
    while {[llength $stack] > 0} {
        set dir [lindex $stack 0]
        set stack [lrange $stack 1 end]
        if {![file isdirectory $dir]} { continue }
        foreach f [lsort [glob -nocomplain -directory $dir -type f "*.$ext"]] {
            lappend files $f
        }
        foreach d [lsort [glob -nocomplain -directory $dir -type d *]] {
            lappend stack $d
        }
    }
    return $files
}

set project_name [get_arg $argv --name prj]
set project_dir  [get_arg $argv --dir  .]
set part         [get_arg $argv --part xc7a35tcsg324-1]
set top_name     [get_arg $argv --top  top]
set language     [get_arg $argv --lang VHDL]

set root [file normalize $project_dir]
set xpr  [file join $root $project_name]

puts "== create_project : $project_name ($part, top=$top_name, $language)"

if {[catch {

    create_project $project_name $xpr -part $part -force
    set_property target_language $language [current_project]
    set_property simulator_language Mixed [current_project]

    # --- sources HDL et contraintes -----------------------------------------
    set hdl {}
    foreach ext {vhd vhdl v sv} {
        set hdl [concat $hdl [collect_sources [file join $root rtl] $ext]]
    }
    if {[llength $hdl] > 0} {
        add_files -fileset sources_1 -norecurse $hdl
        puts "== [llength $hdl] fichier(s) HDL ajoute(s)"
    } else {
        puts "ATTENTION: aucun fichier HDL trouve dans rtl/"
    }

    set xdc [collect_sources [file join $root constraints] xdc]
    if {[llength $xdc] > 0} {
        add_files -fileset constrs_1 -norecurse $xdc
        puts "== [llength $xdc] contrainte(s) XDC ajoutee(s)"
    } else {
        puts "ATTENTION: aucune contrainte dans constraints/ (l'implementation peut passer, pas le bitstream)"
    }

    # --- top et ordre de compilation ---------------------------------------
    set_property top $top_name [current_fileset]
    update_compile_order -fileset sources_1

    # --- repertoires de travail versionnables ------------------------------
    foreach d {reports export scripts/generated} {
        file mkdir [file join $root $d]
    }

    puts "== projet cree : $xpr.xpr"

} err]} {
    puts stderr "ERROR: creation du projet impossible : $err"
    exit 1
}
