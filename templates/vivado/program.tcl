# =============================================================================
# program.tcl - programmation du FPGA par JTAG
#
# Usage :
#   vivado -mode batch -source scripts/program.tcl -nolog -nojournal \
#          -tclargs --bit build/top.bit [--device xc7z020_1] [--url localhost:3121]
#
# ATTENTION : cet script RECONFIGURE la carte. Le design en cours est perdu.
# Il ne doit etre lance qu'apres accord explicite de l'utilisateur (cote MCP :
# program_fpga(confirm=True)).
# =============================================================================

proc get_arg {args key default} {
    set idx [lsearch -exact $args $key]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        return [lindex $args [expr {$idx + 1}]]
    }
    return $default
}

set bit    [get_arg $argv --bit ""]
set device [get_arg $argv --device ""]
set url    [get_arg $argv --url "localhost:3121"]

if {$bit eq ""} {
    puts stderr "ERROR: --bit <fichier.bit ou .pdi> est obligatoire"
    exit 1
}
if {![file exists $bit]} {
    puts stderr "ERROR: bitstream introuvable : $bit"
    exit 1
}

if {[catch {

    open_hw_manager
    connect_hw_server -url $url
    open_hw_target

    if {$device eq ""} {
        set devices [get_hw_devices]
        if {[llength $devices] == 0} {
            error "aucun device JTAG detecte (cable branche ? pilotes udev installes ? cable ?)"
        }
        set device [lindex $devices 0]
    }
    puts "== device : $device"

    current_hw_device $device
    refresh_hw_device -update_hw_probes false $device

    set_property PROGRAM.FILE $bit $device
    program_hw_devices $device
    refresh_hw_device $device

    puts "== programmation terminee : $device <- $bit"

    close_hw_manager

} err]} {
    puts stderr "ERROR: $err"
    puts stderr "aide : 'lsusb | grep -i xilinx' doit voir le cable ; sinon installer les"
    puts stderr "       regles udev de cable (scripts/install_drivers/install_digilent.sh) ou lancer hw_server a la main."
    exit 1
}
