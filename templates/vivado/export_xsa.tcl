# =============================================================================
# export_xsa.tcl - export du materiel (.xsa) vers Vitis
#
# Usage :
#   vivado -mode batch -source scripts/export_xsa.tcl -nolog -nojournal \
#          -tclargs --xpr vivado_prj/prj.xpr --out export/prj.xsa --bit 1
#
# Variables :
#   --xpr   projet (obligatoire)
#   --out   fichier .xsa a produire            (defaut : export/design.xsa)
#   --bit   1 = inclure le bitstream           (defaut : 1)
#
# Version : `write_hw_platform` remplace `write_hw_def` depuis 2020.x.
# Le .xsa est ce que Vitis consomme : c'est LE point de jonction Vivado -> Vitis.
# =============================================================================

proc get_arg {args key default} {
    set idx [lsearch -exact $args $key]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        return [lindex $args [expr {$idx + 1}]]
    }
    return $default
}

set xpr [get_arg $argv --xpr ""]
set out [get_arg $argv --out "export/design.xsa"]
set bit [get_arg $argv --bit 1]

if {$xpr eq ""} {
    puts stderr "ERROR: --xpr <chemin/vers/projet.xpr> est obligatoire"
    exit 1
}

if {[catch {

    open_project $xpr
    set root [file dirname [file normalize $xpr]]
    set out  [file join $root $out]
    file mkdir [file dirname $out]

    set impl_status [get_property STATUS [get_runs impl_1]]
    if {[string match -nocase "*Not started*" $impl_status]} {
        error "impl_1 non lance : executer build.tcl avant l'export XSA"
    }

    if {$bit} {
        # -include_bit : le .xsa embarque le bitstream (necessaire pour un
        # demarrage standalone / BOOT.bin). -fixed : design fige (non extensible).
        write_hw_platform -fixed -include_bit -force -file $out
    } else {
        write_hw_platform -fixed -force -file $out
    }

    if {![file exists $out]} {
        error "l'export n'a produit aucun fichier : $out"
    }

    puts "== XSA : $out ([file size $out] octets)"
    puts "== pour Vitis : xsct scripts/create_app.tcl  ou  vitis -s scripts/create_app.py"

} err]} {
    puts stderr "ERROR: $err"
    exit 1
}
