# =============================================================================
# nonproject_build.tcl - flux NON-PROJECT (sans .xpr) : plus rapide, plus
# adaptable, ideal pour un agent qui construit un design jetable.
#
# Usage :
#   vivado -mode batch -source scripts/nonproject_build.tcl -nolog -nojournal \
#          -tclargs --part xc7a35tcsg324-1 --top top --out build
#
# Variables :
#   --part  partie ciblee                        (defaut : xc7a35tcsg324-1)
#   --top   entite top-level                     (defaut : top)
#   --out   dossier de sortie                    (defaut : build)
#   --clock periode de l'horloge en ns (contrainte generee si aucun XDC) (defaut : 10)
#
# Differences cles avec le flux projet :
#   - pas de .xpr, pas de runs : tout se fait dans le repertoire courant ;
#   - les etapes sont explicites (synth / opt / place / route / bitstream) ;
#   - on peut donc s'arreter a l'etape voulue pour un diagnostic rapide.
# =============================================================================

proc get_arg {args key default} {
    set idx [lsearch -exact $args $key]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        # Tcl evalue "1+1" comme index (donc $idx+1 marche par chance), mais
        # [expr {...}] est explicite et lisible : on garde cette forme.
        return [lindex $args [expr {$idx + 1}]]
    }
    return $default
}

set part  [get_arg $argv --part xc7a35tcsg324-1]
set top   [get_arg $argv --top  top]
set out   [get_arg $argv --out  build]
set clock [get_arg $argv --clock 10]

if {[catch {

    file mkdir $out

    puts "== lecture des sources"
    set vhdl [glob -nocomplain -directory rtl -type f *.vhd]
    foreach f $vhdl { read_vhdl -vhdl2008 $f }
    set vlog [glob -nocomplain -directory rtl -type f *.v *.sv]
    foreach f $vlog { read_verilog $f }

    if {[llength $vhdl] == 0 && [llength $vlog] == 0} {
        error "aucune source HDL trouvee dans rtl/"
    }

    # Un design sans contrainte d'horloge est "unconstrained" : Vivado ne peut
    # pas verifier le timing. On genere une horloge sur le premier port d'horloge
    # trouve si aucun XDC n'en declare.
    set xdc [glob -nocomplain -directory constraints -type f *.xdc]
    if {[llength $xdc] > 0} {
        foreach f $xdc { read_xdc $f }
    } else {
        puts "ATTENTION: aucun XDC ; horloge generee sur l'entree d'horloge (periode $clock ns)"
        # create_clock doit viser un PORT existant : a adapter au design.
        # (remplacer 'clk' par le nom reel du port d'horloge)
        create_clock -period $clock -name clk [get_ports clk]
    }

    puts "== synthese"
    synth_design -top $top -part $part -flatten_hierarchy rebuilt

    write_checkpoint -force [file join $out post_synth.dcp]
    report_utilization -file [file join $out post_synth_utilization.rpt]
    report_timing_summary -file [file join $out post_synth_timing.rpt]

    puts "== opt_design / place_design / phys_opt_design / route_design"
    opt_design
    place_design
    phys_opt_design
    route_design

    puts "== rapports"
    report_timing_summary -file [file join $out timing_summary.rpt] -max_paths 10 -warn_on_violation
    report_utilization    -file [file join $out utilization.rpt]
    report_drc            -file [file join $out drc.rpt]
    report_route_status   -file [file join $out route_status.rpt]

    puts "== bitstream"
    write_bitstream -force [file join $out "$top.bit"]

    set paths [get_timing_paths -delay_type max -max_paths 1]
    set wns 0.0
    if {[llength $paths] > 0} { set wns [get_property SLACK [lindex $paths 0]] }
    puts "== TIMING: WNS = $wns ns"

    if {$wns < 0} {
        error "timing non respecte (WNS=$wns ns) : voir $out/timing_summary.rpt"
    }

    puts "== termine : $out/$top.bit"

} err]} {
    puts stderr "ERROR: $err"
    exit 1
}
