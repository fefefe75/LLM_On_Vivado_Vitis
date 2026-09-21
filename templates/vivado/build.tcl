# =============================================================================
# build.tcl - synthese + implementation + bitstream + rapports (project mode)
#
# Usage :
#   vivado -mode batch -source scripts/build.tcl -nolog -nojournal \
#          -tclargs --xpr vivado_prj/prj.xpr --to bitstream --jobs 8
#
# Variables :
#   --xpr    chemin du .xpr (obligatoire)
#   --to     synthesis | implementation | bitstream      (defaut : bitstream)
#   --jobs   nombre de threads                           (defaut : 8)
#   --reset  1 = relancer de zero (reset_run)            (defaut : 0)
#   --allow-unconstrained  1 = accepter un design sans contraintes de broches
#           (validation de logique sur une partie, sans carte : voir plus bas)
#
# Comportement verifie sur Vivado v2025.2 :
#   * relancer un run deja termine sans reset echoue :
#       ERROR: [Common 17-69] Command failed: Run 'synth_1' needs to be reset
#     -> ce script reutilise un run a 100 % au lieu de planter ;
#   * un design sans IOSTANDARD ni LOC echoue a write_bitstream :
#       ERROR: [DRC NSTD-1] Unspecified I/O Standard
#       ERROR: [DRC UCIO-1] Unconstrained Logical Port
#       ERROR: [Vivado 12-1345] Error(s) found during DRC. Bitgen not run.
#       ERROR: [Common 17-39] 'write_bitstream' failed due to earlier errors.
#     -> les rapports sont produits QUAND MEME (pour diagnostiquer) et le code
#        de retour reste non nul.
# =============================================================================

proc get_arg {args key default} {
    set idx [lsearch -exact $args $key]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        return [lindex $args [expr {$idx + 1}]]
    }
    return $default
}

proc run_or_reuse {run_name jobs reset_flag to_step} {
    set progress [get_property PROGRESS [get_runs $run_name]]

    if {$progress eq "100%" && !$reset_flag} {
        puts "== $run_name : already complete (PROGRESS=100%), reused as is"
        return
    }
    if {$reset_flag || ($progress ne "" && $progress ne "0%")} {
        puts "== resetting $run_name"
        reset_run $run_name
    }

    if {$to_step ne ""} {
        puts "== launching $run_name (-jobs $jobs) up to $to_step"
        launch_runs $run_name -to_step $to_step -jobs $jobs
    } else {
        puts "== launching $run_name (-jobs $jobs)"
        launch_runs $run_name -jobs $jobs
    }
    wait_on_run $run_name

    set progress [get_property PROGRESS [get_runs $run_name]]
    set status   [get_property STATUS   [get_runs $run_name]]
    puts "== $run_name : PROGRESS=$progress STATUS=$status"

    if {$progress ne "100%"} {
        set run_dir [get_property DIRECTORY [get_runs $run_name]]
        error "$run_name a echoue ($progress) : $status - voir [file join $run_dir runme.log]"
    }
}

# Prepare un design SANS contraintes de broches : abaisse la severite des deux DRC
# qui bloquent la generation du bitstream. Vivado lui-meme indique cette methode
# dans le message d'erreur, et precise que pour un run il faut un pre-hook Tcl.
proc allow_unconstrained {root} {
    set hook [file join $root scripts allow_unconstrained_drc.tcl]
    file mkdir [file dirname $hook]
    set fh [open $hook w]
    puts $fh "# Genere par build.tcl (--allow-unconstrained 1)."
    puts $fh "# Validation de LOGIQUE uniquement : ce bitstream n'est pas pour une carte."
    puts $fh "set_property SEVERITY \{Warning\} \[get_drc_checks NSTD-1\]"
    puts $fh "set_property SEVERITY \{Warning\} \[get_drc_checks UCIO-1\]"
    close $fh
    set_property STEPS.WRITE_BITSTREAM.TCL.PRE $hook [get_runs impl_1]
    puts "== DRC NSTD-1/UCIO-1 lowered to Warning (pre-hook: $hook)"
}

set xpr       [get_arg $argv --xpr ""]
set to        [get_arg $argv --to bitstream]
set jobs      [get_arg $argv --jobs 8]
set reset     [get_arg $argv --reset 0]
set unconstra [get_arg $argv --allow-unconstrained 0]

if {$xpr eq ""} {
    puts stderr "ERROR: --xpr <chemin/vers/projet.xpr> est obligatoire"
    exit 1
}

if {[catch {

    open_project $xpr

    set root    [file dirname [file normalize $xpr]]
    set reports [file join $root reports]
    file mkdir $reports

    if {$unconstra} { allow_unconstrained $root }

    # --- synthese ----------------------------------------------------------
    run_or_reuse synth_1 $jobs $reset ""
    open_run synth_1 -name synth_1
    report_utilization      -file [file join $reports post_synth_utilization.rpt]
    report_timing_summary   -file [file join $reports post_synth_timing.rpt] -delay_type min_max
    close_design

    if {$to eq "synthesis"} {
        puts "== done (synthesis)"
        exit 0
    }

    # --- implementation (jusqu'au bitstream si demande) ---------------------
    # Le bitstream peut echouer (DRC, timing) : on note l'erreur et on produit
    # QUAND MEME les rapports post-implementation. Un agent doit pouvoir lire
    # pourquoi ca a echoue au lieu de deviner.
    set impl_error ""
    if {[catch {
        if {$to eq "bitstream"} {
            run_or_reuse impl_1 $jobs $reset write_bitstream
        } else {
            run_or_reuse impl_1 $jobs $reset ""
        }
    } e]} {
        set impl_error $e
        puts "== impl_1 FAILED: $e"
    }

    set wns 0.0
    if {[catch {
        open_run impl_1

        # WNS : a lire PENDANT que le design est ouvert (apres close_design,
        # get_timing_paths ne renvoie plus de chemin).
        set paths [get_timing_paths -delay_type max -max_paths 1]
        if {[llength $paths] > 0} {
            set wns [get_property SLACK [lindex $paths 0]]
        }
        puts "== TIMING: WNS = $wns ns"

        report_timing_summary -file [file join $reports timing_summary.rpt] \
            -max_paths 10 -report_unconstrained -warn_on_violation
        report_utilization    -file [file join $reports utilization.rpt]
        catch { report_drc                -file [file join $reports drc.rpt] }
        catch { report_clock_utilization  -file [file join $reports clock_utilization.rpt] }
        catch { report_power              -file [file join $reports power.rpt] }
        close_design
    } rerr]} {
        puts "ATTENTION: rapports post-implementation indisponibles : $rerr"
    }

    if {$impl_error ne ""} {
        error "$impl_error (rapports disponibles dans $reports)"
    }

    set proj_name [file rootname [file tail $xpr]]
    set bits [glob -nocomplain -directory [file join $root "${proj_name}.runs" impl_1] -type f *.bit]
    puts "== BITSTREAM: $bits"

    if {$wns < 0} {
        # Le bitstream existe mais le design ne tient pas la frequence : a dire
        # explicitement, jamais a masquer.
        error "timing not met (WNS=$wns ns): see $reports/timing_summary.rpt"
    }

    puts "== done"

} err]} {
    puts stderr "ERROR: $err"
    exit 1
}
