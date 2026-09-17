# =============================================================================
# synth_vivado.tcl - synthese + placement-routage REELS du mini-GPU (mode non-projet)
#
# Ce script ne se contente pas de verifier que le design compile : il donne le cout
# materiel par lane et la frequence maximale atteignable, sur la puce cible.
#
# Usage :
#   source ~/vivado/2025.2/Vivado/settings64.sh
#   vivado -mode batch -source scripts/synth_vivado.tcl \
#          -tclargs --part xc7z020clg400-1 --lanes 16 --iterations 128
#
# Options : --part, --lanes, --w, --h, --iterations, --out (dossier de sortie),
#           --no-par (s'arreter apres la synthese)
#
# Verifie : Vivado v2025.2 (voir README pour les chiffres obtenus).
# =============================================================================

set script_dir [file dirname [file normalize [info script]]]
set racine     [file dirname $script_dir]
set rtl        [file join $racine "rtl"]

# ---------------------------------------------------------------- arguments
proc get_arg {args nom defaut} {
    set idx [lsearch -exact $args $nom]
    if {$idx < 0} {
        return $defaut
    }
    return [lindex $args [expr {$idx + 1}]]
}

set part       [get_arg $argv --part       "xc7z020clg400-1"]
set lanes      [get_arg $argv --lanes      "16"]
set largeur    [get_arg $argv --w          "640"]
set hauteur    [get_arg $argv --h          "480"]
set max_iter   [get_arg $argv --iterations "128"]
set out_dir    [get_arg $argv --out        [file join $racine "build"]]
set faire_par  [expr {[lsearch -exact $argv --no-par] < 0}]

file mkdir $out_dir

puts "== configuration : part=$part lanes=$lanes image=${largeur}x${hauteur} iter=$max_iter"

# --------------------------------------------------------------- lecture RTL
# L'ordre compte pour VHDL : le package d'abord, puis le lane, puis le GPU.
read_vhdl -vhdl2008 [file join $rtl "mandelbrot_pkg.vhd"]
read_vhdl -vhdl2008 [file join $rtl "mandelbrot_lane.vhd"]
read_vhdl -vhdl2008 [file join $rtl "mandelbrot_gpu.vhd"]
read_vhdl -vhdl2008 [file join $rtl "top_mandelbrot.vhd"]

# ------------------------------------------------------------ contraintes
# Sans XDC, aucune horloge n'est definie : report_timing_summary ne contient alors
# aucun chemin et `get_timing_paths` ne renvoie rien (erreur [Common 17-55] rencontree).
set xdc [file join $racine "constraints" "timing.xdc"]
if {[file exists $xdc]} {
    read_xdc $xdc
    puts "== contraintes : $xdc"
} else {
    puts "== ATTENTION : pas de fichier $xdc, le timing ne sera pas analysable"
}

# --------------------------------------------------------------- synthese
# Les generiques se passent a synth_design : c'est le pendant de la ligne -g... de GHDL.
synth_design -top top_mandelbrot -part $part -generic "C_LANES=$lanes" -generic "C_IMG_W=$largeur" -generic "C_IMG_H=$hauteur" -generic "C_MAX_ITER=$max_iter"

report_utilization      -file [file join $out_dir "utilization_synth.rpt"]
report_timing_summary   -file [file join $out_dir "timing_synth.rpt"] -delay_type max
set chemin_synth [get_timing_paths -quiet -delay_type max -max_paths 1]
set wns_synth "indisponible"
if {[llength $chemin_synth] > 0} {
    set wns_synth [get_property SLACK $chemin_synth]
} else {
    puts "== ATTENTION : aucun chemin de timing (horloge non contrainte ?)"
}

if {$faire_par} {
    opt_design
    place_design
    route_design
    report_utilization    -file [file join $out_dir "utilization_impl.rpt"]
    report_timing_summary -file [file join $out_dir "timing_impl.rpt"] -delay_type max
    write_checkpoint -force [file join $out_dir "top_mandelbrot_routed.dcp"]
}

# ------------------------------------------------------------------- resultats
set luts   [llength [get_cells -hier -quiet -filter {REF_NAME =~ LUT*}]]
set ffs    [llength [get_cells -hier -quiet -filter {REF_NAME =~ FD* || REF_NAME =~ LD* || REF_NAME =~ FDRE*}]]
# PIEGE MESURE : `-filter {PRIMITIVE_GROUP == DSP}` renvoie 0 cellule alors que le
# rapport d'utilisation compte 195 DSP48E1. Le filtre fiable porte sur REF_NAME.
set dsps   [llength [get_cells -hier -quiet -filter {REF_NAME =~ DSP48*}]]
set brams  [llength [get_cells -hier -filter {PRIMITIVE_GROUP == BLOCKRAM}]]

set n_lanes [expr {double($lanes)}]
puts "================ RESULTAT ($part, $lanes lanes) ================"
puts [format "LUT          : %6d  (%7.1f par lane)" $luts  [expr {$luts / $n_lanes}]]
puts [format "Bascule      : %6d  (%7.1f par lane)" $ffs   [expr {$ffs / $n_lanes}]]
puts [format "DSP          : %6d  (%7.1f par lane)" $dsps  [expr {$dsps / $n_lanes}]]
puts [format "BRAM         : %6d" $brams]
puts [format "WNS synthese : %s ns" $wns_synth]
if {$faire_par} {
    set chemin [get_timing_paths -quiet -delay_type max -max_paths 1]
    if {[llength $chemin] > 0} {
        set wns [get_property SLACK $chemin]
        set periode 10.0
        set horloges [get_clocks -quiet *]
        if {[llength $horloges] > 0} {
            set periode [get_property PERIOD [lindex $horloges 0]]
        }
        puts [format "WNS apres P&R: %s ns  (contrainte de periode : %s ns)" $wns $periode]
        puts [format "Frequence max estimee : %.1f MHz" [expr {1000.0 / ($periode - $wns)}]]
    } else {
        puts "WNS apres P&R: indisponible (aucun chemin)"
    }
}
puts "==============================================================="
puts "Rapports dans $out_dir"

if {$wns_synth ne "indisponible" && $wns_synth < 0} {
    puts "ATTENTION : WNS negatif a la synthese."
    exit 1
}
exit 0
