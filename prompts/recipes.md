# Task recipes

Each recipe is a fixed procedure an agent can follow without improvising.
Commands are copy-pasteable. `<project>` = the repository root of your FPGA project.

---

## 1. Start a new Vivado project from nothing

```bash
mkdir -p <project>/{rtl,tb,constraints,scripts,reports,export}
cp /path/to/templates/vivado/create_project.tcl <project>/scripts/
$EDITOR <project>/scripts/create_project.tcl      # set PART and PROJECT_NAME
vivado -mode batch -source <project>/scripts/create_project.tcl -nolog -nojournal -tclargs --part xc7a35tcsg324-1
```
Success check: `<PROJECT_NAME>.xpr` exists and the log has no `ERROR:`.
Never edit the `.xpr` afterwards; re-run the script with `-force`.

## 2. Add a VHDL module

1. Write `rtl/<name>.vhd`: entity `<name>`, one architecture `rtl`, ports `i_*`/`o_*`.
2. Add it to the testbench Makefile (`VHDL_SOURCES`) **before** modules that instantiate it.
3. Write the testbench (recipe 3) and get a green run *before* adding it to the Vivado build.
4. Only then: `add_files -fileset sources_1 $path` in the project script, or re-run
   `create_project.tcl` with `[glob rtl/*.vhd]`.

## 3. Write a cocotb testbench for an existing module

Copy `templates/cocotb/Makefile.ghdl`, `templates/cocotb/helpers.py` and a test skeleton:
```bash
mkdir -p tb/<name> && cp templates/cocotb/{Makefile.ghdl,helpers.py} tb/<name>/
mv tb/<name>/Makefile.ghdl tb/<name>/Makefile
```
Fill in `VHDL_SOURCES`, `COCOTB_TOPLEVEL`, `COCOTB_TEST_MODULES`.
Test body order (this order matters, see example 01):
1. set all inputs, 2. start clock, 3. hold reset 3 cycles, release,
4. drive stimulus, 5. sample on falling edge or with `ReadOnly`, 6. assert with context,
7. `Scoreboard.report()` at the end.

Minimum viable assertions: reset behaviour, nominal behaviour, boundary values,
one illegal/ignored operation, one randomised run with a fixed seed.

## 4. Fix a failing simulation

```bash
cd tb/<name> && make 2>&1 | tee sim.log
grep -nE "ERROR|AssertionError|Traceback|TESTS=" sim.log
```
- `cannot find entity or configuration X` -> `--std=08` missing at run, wrong
  `COCOTB_TOPLEVEL`, or `build_dir != test_dir` (Python runner).
- Value read is one cycle late/early -> sampling phase; read on `FallingEdge` or after
  `ReadOnly`, and set inputs before releasing reset.
- `'U'`/`'X'` on a signal -> signal never driven (missing assignment in a branch, or a
  different name in the port map).
- Test hangs -> no timeout; add a `Timer` watchdog and a cycle limit.

## 5. Close timing

```bash
vivado -mode batch -source scripts/impl.tcl -nolog -nojournal   # runs impl_1 and writes reports
grep -A6 "Design Timing Summary" reports/timing_summary.rpt
```
Order of action, most effective first:
1. put a register in the middle of the long path (pipeline the operand),
2. reduce the combinational tree (split comparator, use `unsigned` compare),
3. `set_max_delay`/`set_multicycle_path` **only** with a documented multi-cycle protocol,
4. lower the clock constraint to the achievable frequency and say so explicitly,
5. re-run `launch_runs impl_1 -to_step route_design -directive Explore`.

## 6. Bitstream + program the FPGA

```bash
vivado -mode batch -source scripts/build_hw.tcl -nolog -nojournal   # ... -to_step write_bitstream
ls <project>.runs/impl_1/*.bit
vivado -mode batch -source templates/vivado/program.tcl -nolog -nojournal
```
JTAG must be visible: `lsusb | grep -i xilinx`; cable drivers need udev rules (see
`docs/01-toolchain.md`). `program_hw_devices` is a *hardware* action: ask a human before
running it on shared equipment.

## 7. Zynq PS + PL, then a Vitis "Hello World"

1. Vivado: block design (Zynq PS + your VHDL module, AXI interconnect if needed),
   `make_wrapper`, then run implementation and bitstream.
2. `write_hw_platform -fixed -include_bit -force -file export/design.xsa`
3. Vitis (>= 2023.2 unified): `vitis -s scripts/create_app.py`; classic
   (<= 2023.1): `xsct scripts/create_app.tcl`. Templates: `templates/vitis/`.
4. Build the app, then deploy: JTAG (`dow`/`con`) or SD card with `BOOT.bin` (bootgen + `.bif`).
5. Verify: read back `xparameters.h` (base addresses) rather than typing addresses by hand.

## 8. Add an AXI4-Lite register bank (PL, no IP wizard)

1. Write pure VHDL: `axi_lite_slave.vhd` (AW/W/B/AR/R channels) + a register file module.
2. Test it with cocotb first (drive the five channels, check handshakes and readback).
3. In the block design, either instantiate your VHDL directly or package it as an IP
   (`ipx::package_project` in `templates/vivado/package_ip.tcl`).
4. Map it in the PS address space, re-export the XSA, and use the address from
   `xparameters.h` in the C code.

## 9. Debug on hardware

Add an ILA to the nets you suspect, re-run implementation, program, then trigger.
```tcl
create_debug_core u_ila_0 ila
set_property C_DATA_DEPTH 4096 [get_debug_cores u_ila_0]
set_property C_NUM_OF_PROBES 3 [get_debug_cores u_ila_0]
connect_debug_port u_ila_0/clk [get_nets i_clk_IBUF]
```
Report the captured waveform facts (values + cycle numbers), not impressions.

## 10. Report progress honestly

```
Changed:    <files, one line each>
Ran:        <exact command>
Result:     <PASS/FAIL + numbers: TESTS=, WNS=, LUT/FF %>
Unverified: <what you could not run and why>
Next:       <one concrete step>
```
