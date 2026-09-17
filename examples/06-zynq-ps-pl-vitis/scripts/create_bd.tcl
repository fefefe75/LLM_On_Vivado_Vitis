# =============================================================================
# create_bd.tcl - projet Zynq-7000 avec un block design minimal (PS + AXI GPIO)
#
# Usage :
#   vivado -mode batch -source scripts/create_bd.tcl -nolog -nojournal \
#          -tclargs --part xc7z020clg400-1 --name zynq_prj
#
# ATTENTION : ce script n'a PAS ete execute (aucune carte Zynq disponible lors de
# l'ecriture). Les noms d'IP proviennent du catalogue standard (processing_system7_0,
# axi_gpio_0) et peuvent varier selon la version. Le lancer une premiere fois, lire
# les erreurs, corriger les noms avec :
#     get_ipdefs -filter {NAME =~ "*processing_system7*"}
#     get_ipdefs -filter {NAME =~ "*axi_gpio*"}
# =============================================================================

proc get_arg {args key default} {
    set idx [lsearch -exact $args $key]
    if {$idx >= 0 && ($idx + 1) < [llength $args]} {
        return [lindex $args [expr {$idx + 1}]]
    }
    return $default
}

set part [get_arg $argv --part xc7z020clg400-1]
set name [get_arg $argv --name zynq_prj]
set root [pwd]

if {[catch {

    create_project $name $root/$name -part $part -force
    set_property target_language VHDL [current_project]

    # --- block design -------------------------------------------------------
    create_bd_design "system"

    # PS7 : processeur + DDR + horloges. board_part laisse vide -> configuration
    # par defaut du PS (a adapter a la carte reelle).
    create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 processing_system7_0
    apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
        -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} \
        [get_bd_cells processing_system7_0]

    # GPIO du PL : 4 sorties, menees a des ports externes (donc au brochage)
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio axi_gpio_0
    set_property -dict [list CONFIG.C_GPIO_WIDTH {4} \
                             CONFIG.C_ALL_OUTPUTS {1} \
                             CONFIG.C_IS_DUAL {0}] [get_bd_cells axi_gpio_0]

    # interconnect PS -> GPIO (maitre PS, esclave GPIO)
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
        -config {Master "/processing_system7_0/M_AXI_GP0" Clk "Auto"} \
        [get_bd_intf_pins axi_gpio_0/S_AXI]

    # ports externes : les LED du PL
    create_bd_port -dir O -from 3 -to 0 led
    connect_bd_net [get_bd_pins axi_gpio_0/gpio_io_o] [get_bd_ports led]

    regenerate_bd_layout
    validate_bd_design
    save_bd_design

    # --- wrapper + top ------------------------------------------------------
    make_wrapper -files [get_files system.bd] -top
    add_files -norecurse [glob $root/$name/$name.gen/sources_1/bd/system/hdl/system_wrapper.vhd]
    set_property top system_wrapper [current_fileset]
    update_compile_order -fileset sources_1

    # --- contraintes d'horloge du PL ---------------------------------------
    # L'horloge FCLK_CLK0 est generee par le PS : on la contraint cote PL.
    file mkdir $root/$name/constraints
    set fh [open $root/$name/constraints/pl_timing.xdc w]
    puts $fh "# Horloge PL issue du PS (FCLK_CLK0), a ajuster selon la config du PS"
    puts $fh "create_clock -period 10.000 -name fclk_clk0 \[get_pins -hierarchical -filter \{NAME =~ *FCLK_CLK0\}\]"
    puts $fh "create_clock -period 10.000 -name fclk_clk0_bd \[get_pins -hierarchical -filter \{NAME =~ *FCLK_CLK0*}\]"
    close $fh
    add_files -fileset constrs_1 -norecurse $root/$name/constraints/pl_timing.xdc

    puts "== block design cree. Etape suivante : build.tcl --to bitstream"
    puts "== puis : export_xsa.tcl  ->  vitis -s create_app.py"

} err]} {
    puts stderr "ERROR: $err"
    puts stderr "piste : verifier les noms d'IP avec 'get_ipdefs -filter {NAME =~ \"*axi_gpio*\"}'"
    puts stderr "        et la config du PS7 avec 'get_property CONFIG.* [get_bd_cells processing_system7_0]'"
    exit 1
}
