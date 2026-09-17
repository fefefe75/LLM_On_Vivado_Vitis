# HDL Simulation for LLM Agents — Reference Note

**Scope:** how an autonomous agent (no human at the keyboard) should build, elaborate and run HDL
simulations to validate VHDL/Verilog, both on a **zero-licence** open-source stack and on **AMD
Vivado XSim** / **Siemens Questa**.

**Verification legend used throughout this document**

- `[V-local]` — executed and confirmed on this workstation on 2026-09-17 (see "Local environment").
- `[V-doc]` — read from official documentation (URL cited).
- `[V-src]` — read directly in the installed cocotb 2.0.1 source tree.
- `[unverified]` — plausible but *not* machine-checked here; treat as a hypothesis to test.

---

## 0. Local environment (what actually exists here)

| Item | Value | Source |
|---|---|---|
| OS | Fedora release 44 (Forty Four), kernel 7.2.5-200.fc44.x86_64 | `[V-local]` `/etc/fedora-release`, `uname -r` |
| cocotb | **2.0.1** in `<VENV>/lib/python3.12/site-packages` (Python 3.12.14) | `[V-local]` `cocotb.__version__`, `cocotb-config --version` |
| GHDL | **6.0.0 mcode** (`ghdl -r` prints "static elaboration, mcode JIT code generator") at `/tmp/ghdl_tool/bin/ghdl` | `[V-local]` `ghdl --version` |
| Questa | **Questa Intel Starter FPGA Edition-64 2023.3** at `~/intelFPGA_lite/23.1std/questa_fse/bin/` (`vsim`, `vlog`, `vcom` on PATH) | `[V-local]` `vsim -version` |
| Icarus Verilog | **not installed** (`iverilog`, `vvp` not found) | `[V-local]` `command -v` |
| Verilator | **not installed** | `[V-local]` `command -v` |
| Vivado / XSim | **not installed** (`xvlog`, `xelab`, `xsim`, `vivado` not found; no `/tools/Xilinx`, `/opt/Xilinx`) | `[V-local]` |

A full cocotb regression (3 tests, VHDL, GHDL) plus a Pitfall probe suite (4 tests) were run
successfully during the writing of this note; every API claim marked `[V-local]` comes from those runs.

---

## 1. Simulator panorama for agents

### 1.1 Decision table

| Simulator | Language | Licence / cost | Agent friendliness | cocotb `SIM=` | Notes |
|---|---|---|---|---|---|
| **GHDL** | VHDL only (some VHDL/Verilog co-sim via `--vpi`) | GPL-2.0-or-later (free, open source) | ★★★★★ pure CLI, no licence file, fast mcode backend | `ghdl` | The default VHDL choice for agents. Verified working here. |
| **Icarus Verilog** | Verilog/SystemVerilog (IEEE-1364 focused) | GPL-2.0-only (free) | ★★★★☆ CLI, 4-state, good enough for RTL | `icarus` | Needs ≥ 11.0 for cocotb. FST waveforms, no VHDL, weakest SystemVerilog coverage. |
| **Verilator** | Verilog/SystemVerilog (synthesizable subset) | LGPL-3.0-only OR Artistic-2.0 (free) | ★★★☆☆ needs a C++ toolchain + `make`, 2-state | `verilator` | Fastest free simulator, but **2-state**: no X/Z, no `#delay` in the DUT, no non-synthesizable constructs. cocotb requires **≥ 5.036**. |
| **XSim (Vivado)** | VHDL, Verilog, SystemVerilog (mixed) | Bundled with Vivado; Vivado WebPACK is free-of-charge but **registration/entitlement** required, no open source | ★★★☆☆ excellent CLI (`xvlog`/`xvhdl`/`xelab`/`xsim`) but a multi-GB install and it is **not supported by cocotb** | *none* | Use it via a hand-written TCL/Make flow (§2). Official mixed-language vendor simulator. |
| **Questa / ModelSim** | VHDL, Verilog, SystemVerilog (mixed) | Commercial licence for full Questa; **Questa Intel Starter FPGA Edition** is free but requires a working licence file | ★★★★☆ `vlib`/`vlog`/`vcom`/`vsim -c -do script` | `questa` (compat) / `questa-qisqrun` | Full FLI/VHPI/VPI. The free Starter edition **can compile but cannot always check out a licence** — see §1.4. |
| NVC | VHDL | free (Apache-2.0/GPL) | ★★★★☆ | `nvc` | cocotb ≥ 1.19.1; VHPI, good VHDL-2008. |
| Xcelium (Cadence) | mixed | commercial | ★★★★☆ | `xcelium` | VHDL toplevel needs Xcelium ≥ 23.09.004 `[V-doc]`. |
| Riviera-PRO / Active-HDL (Aldec) | mixed | commercial | ★★★☆☆ | `riviera` / `activehdl` | `SIM=aldec` deprecated → use `riviera`. |
| VCS (Synopsys) | mixed | commercial | ★★★★☆ | `vcs` | VPI only, no VHPI `[V-doc]`. |
| DSim (Siemens) | mixed | free licence available | ★★★☆☆ | `dsim` | cocotb support **experimental**, DSim ≥ 2025 `[V-doc]`. |
| CVC (Tachyon DA) | Verilog | free | ★★☆☆☆ | `cvc` | No Python runner. |

cocotb's own list of Makefile-selectable simulators is authoritative and was read from the installed
package `[V-src]`:

```
cocotb_tools/makefiles/simulators/Makefile.{activehdl,cvc,dsim,ghdl,icarus,ius,
  modelsim,nvc,questa,questa-compat,questa-qisqrun,riviera,vcs,verilator,xcelium}
```
→ **there is no `Makefile.xsim` and no `XSim` runner** (§1.3, §2.1).

### 1.2 Language-to-simulator mapping

| DUT language | Zero-licence stack | Vendor stack | Agent recommendation |
|---|---|---|---|
| VHDL | **GHDL** (first), NVC (second) | XSim, Questa, Xcelium | GHDL; use `--std=08` consistently (§5 pitfall 7) |
| Verilog / SystemVerilog | **Icarus** for 4-state accuracy, **Verilator** for speed | XSim, Questa, VCS | Icarus by default; Verilator only when 2-state is acceptable |
| VHDL + Verilog mixed | GHDL can load VPI Verilog but not a true mixed flow | **XSim** or **Questa** | XSim/Questa — the open-source stacks are single-language |
| Gate-level / SDF / timing | (not supported) | XSim, Questa | vendor simulator mandatory |

### 1.3 The XSim/cocotb gap — read this before designing the agent flow

- cocotb 2.0.1 ships **no XSim Makefile and no `xsim` runner** `[V-src]`.
- The cocotb documentation's "Simulator Support" page lists Icarus, Verilator, VCS, Riviera-PRO,
  Active-HDL, Questa, ModelSim, Incisive, Xcelium, **GHDL**, NVC, CVC and DSim — **XSim/Vivado
  Simulator is absent** `[V-doc]` <https://docs.cocotb.org/en/stable/simulator_support.html>.
- The Python runner's supported set was read from the source `[V-src]`
  `cocotb_tools/runner.py` → `get_runner()`:

```python
supported_sims = {"icarus": Icarus, "questa": Questa, "ghdl": Ghdl, "riviera": Riviera,
                  "verilator": Verilator, "xcelium": Xcelium, "nvc": Nvc, "vcs": Vcs,
                  "dsim": Dsim}
```

**Consequences for the agent design**

1. A `SIM=xsim` invocation must **fail fast with a clear message**, not "simulator not found".
2. For Vivado-only environments, run XSim through its native CLI (`xvlog`/`xvhdl`/`xelab`/`xsim`)
   and keep the *reference model* in Python **outside** the simulator: generate a stimulus vector
   file (or an `.mif`/`.hex`/CSV), run the HDL testbench, dump a VCD/WDB, and compare in Python.
   That is the portable pattern; it needs no cocotb-xsim bridge.
3. Third-party bridges exist (`themperek/cocotb-vivado`, `kiran-vuksanaj/vicoco`,
   `olofk/edalize` xsim issue) but they are community code; the cocotb-vivado README itself warns
   that only top-level ports are accessible and that edge triggers only work on clocks driven from
   Python. `[V-doc]` <https://github.com/themperek/cocotb-vivado>,
   <https://github.com/kiran-vuksanaj/vicoco>
   Do **not** make them a load-bearing dependency of an unattended agent.

### 1.4 Questa on this machine — real limitation

`make SIM=questa` (Verilog DUT) reached the simulation stage and then failed on licensing `[V-local]`:

```
# vlog -work work -sv -timescale 1ns/1ps -mfcu "+acc" counter.v     ← compile OK, 0 errors
# vsim -onfinish exit -pli .../libcocotbvpi_modelsim.so work.counter
# ** License Issue: License server does not support this feature (intelqsimstarter)
# ** License Issue: Invalid host. (<USER_HOME>/license.dat)
# ** Error: Failure to obtain a Verilog simulation license.
```

So Questa Intel Starter FPGA Edition is **installed and usable as a compiler**, but unusable as a
simulator until a valid licence is configured. An agent must detect this from the exit code and the
log (`Failure to obtain a ... license`) and fall back to GHDL/Icarus rather than report a test failure.
Also documented `[V-doc]`: ModelSim **PE** and its OEM derivatives (Microsemi/Intel/Lattice
Editions) do not support VHDL **FLI** at all — the symptom is
`** Error (suppressible): (vsim-FLI-3155) The FLI is not enabled in this version of ModelSim.`
ModelSim DE/SE and Questa do support FLI.

### 1.5 Installation

#### Fedora / RHEL (dnf)

```bash
# --- GHDL (VHDL) ------------------------------------------------------------
sudo dnf install ghdl            # meta-package: pulls the default backend build
# explicit backends, pick ONE:
sudo dnf install ghdl-mcode      # mcode/JIT: fastest analysis, no GCC back-end needed  (recommended)
sudo dnf install ghdl-llvm       # LLVM code generation (for co-sim / coverage)
sudo dnf install ghdl-gcc        # GCC backend
# optional pre-compiled Xilinx/Intel/Lattice primitive libraries:
sudo dnf install ghdl-grt ghdl-mcode-grt

# --- Icarus Verilog ---------------------------------------------------------
sudo dnf install iverilog        # provides iverilog + vvp

# --- Verilator --------------------------------------------------------------
sudo dnf install verilator       # plus a C++ toolchain: gcc-c++ make perl

# --- Waveform viewer --------------------------------------------------------
sudo dnf install gtkwave         # reads VCD, FST, LXT*, GHW
```

Fedora package facts `[V-doc]`:
- `ghdl` — Fedora 44 ships `6.0.0-4.20260307gite589c69.fc44`, licence
  `GPL-2.0-or-later AND GPL-3.0-or-later AND …` —
  <https://packages.fedoraproject.org/pkgs/ghdl/ghdl/>
- `iverilog` — Fedora 44 ships `13.0-7.fc44`, licence `GPL-2.0-only` —
  <https://packages.fedoraproject.org/pkgs/iverilog/iverilog/>
- `verilator` — Fedora 44 ships `5.046-3.fc44`, licence `LGPL-3.0-only OR Artistic-2.0` —
  <https://packages.fedoraproject.org/pkgs/verilator/verilator/>
- `gtkwave` — <https://packages.fedoraproject.org/pkgs/gtkwave>
- Related GHDL sub-packages (`ghdl-mcode`, `ghdl-llvm`, `ghdl-grt`, `ghdl-mcode-grt`,
  `ghdl-llvm-grt`) are listed on the same page. `[V-doc]`

#### Ubuntu / Debian (apt)

```bash
sudo apt update
# --- GHDL -------------------------------------------------------------------
sudo apt install ghdl             # meta-package
sudo apt install ghdl-mcode       # amd64 mcode backend (recommended, exists from jammy 1.0 up)
sudo apt install ghdl-llvm        # alternative backend
# --- Icarus -----------------------------------------------------------------
sudo apt install iverilog
sudo apt install gtkwave
# --- Verilator (needs a C++ toolchain) --------------------------------------
sudo apt install verilator
sudo apt install g++ make perl
```

Ubuntu package facts `[V-doc]`:
- `ghdl` in noble (24.04 LTS) is `4.1.0+dfsg-0ubuntu2.1`, `universe`, and *depends* on
  `ghdl-common` + one backend (`ghdl-mcode` on amd64) —
  <https://packages.ubuntu.com/noble/ghdl>
- `ghdl-mcode` exists for jammy (1.0.0) and noble (4.1.0) —
  <https://packages.ubuntu.com/ghdl-mcode>
- `iverilog` in noble is `12.0-2build2`, `universe` —
  <https://packages.ubuntu.com/noble/iverilog>
- Verilator upstream documents `apt-get install verilator` and warns that distribution packages are
  almost never the newest release — <https://verilator.org/guide/latest/install.html>

#### Installing GHDL without root (no `sudo`) — the pattern actually used here

GHDL is distributed as a self-contained tarball, which is the right approach for a sandboxed
agent `[V-doc]` <http://ghdl.github.io/ghdl/getting.html>:

```bash
mkdir -p ~/tools && cd ~/tools
# pick the asset for your platform from
#   https://github.com/ghdl/ghdl/releases   (e.g. ghdl-*-x86_64-linux-ubuntu*.tgz
#                                            or ghdl-*-x86_64-linux-musl*.tgz for a static build)
tar -xzf ghdl-*-x86_64-linux-*.tgz
export PATH="$PWD/$(ls -d ghdl-*/ | head -1)bin:$PATH"
ghdl --version          # → "GHDL 6.0.0 ... mcode JIT code generator"
```

**Backend choice matters for cocotb** `[V-doc]`: GHDL upstream recommends **mcode** (fastest analysis,
and the only backend that supports `--time-resolution`); cocotb's GHDL Makefile only injects
`--time-resolution=` when it detects `mcode` in `ghdl --version` `[V-src]`.

#### XSim / Questa installation

- **XSim** ships inside Vivado. Non-negotiable steps: install Vivado (WebPACK/Standard), then
  `source /opt/Xilinx/Vivado/<ver>/settings64.sh` in **every** shell before `xvlog`/`xelab`/`xsim`
  exist `[V-doc]` <https://itsembedded.com/dhd/vivado_sim_1/>.
- **Questa** ships with Intel Quartus Prime Lite/Pro ("Questa Intel Starter FPGA Edition") under
  `<install>/questa_fse/bin`; the licence file must be reachable (`LM_LICENSE_FILE` / `license.dat`).
  `[V-local]` (installed, licence checkout failed here).

#### Limitations to encode in the agent's simulator-selection logic

| Simulator | Hard limits the agent must know |
|---|---|
| GHDL | VHDL only. Implements **VPI**, not VHPI, so cocotb cannot see "9-value signals" or VHDL-specific objects `[V-doc]`. VHDL-2008 needs `--std=08` on **both** analyse/elaborate **and** run. A VHDL file with a component instantiation must be given in dependency order (`[V-local]`, §6 pitfall 8). |
| Icarus | Verilog only. cocotb requires ≥ 11.0 `[V-doc]`. Waveform output is **FST**, not VCD, by default. Weak SystemVerilog; no `wire`/`logic` distinctions beyond IEEE-1364. |
| Verilator | 2-state, synthesizable subset: no X/Z, no `delay`/`initial`-with-time in DUT, no `force`/`release` semantics. Needs `verilator` ≥ 5.036 `[V-doc]`. Requires a C++ toolchain at build time. `waves=True` must be given to **build**, not only to test. |
| XSim | Not supported by cocotb. Multi-GB install + `settings64.sh`. VHDL *variables* are not traceable `[V-doc]` (AMD AR 63628: "Vivado Simulator does not yet support tracing of VHDL variables"). |
| Questa/ModelSim | Licence required. FLI absent from PE/OEM editions `[V-doc]`. Qt/Questa 2025.2+ switches to the QIS/Qrun flow automatically `[V-doc]`. |

---

## 2. XSim from the command line

XSim has **no cocotb Makefile**, so an agent driving Vivado must own this flow itself (§2.1 is a
ready template). The sequence is always three steps: **parse → elaborate → simulate**.

### 2.1 Parse (compile) — `xvlog` / `xvhdl`

```bash
source /opt/Xilinx/Vivado/2023.2/settings64.sh   # required in every new shell

# Verilog / SystemVerilog
xvlog counter.v                                   # plain Verilog (IEEE-1364)
xvlog --sv counter.sv                             # SystemVerilog
xvlog -sv -i ./include -d SIMULATION -d WIDTH=8 counter.sv   # includes + macro defines
xvlog -prj sim.prj                                # read the file list from a .prj
xvlog -f filelist.f                               # read a plain file list

# VHDL
xvhdl counter.vhd
xvhdl -prj vhdl.prj
```

`xvlog` syntax `[-d [define] <name>[=<val>]] [-f <file>] [-i <dir>] [-prj <file>] [-sv]` is documented
in UG900 "Parsing Design Files, xvhdl and xvlog" `[V-doc]`
<https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Parsing-Design-Files-xvhdl-and-xvlog>.
`.prj` syntax is documented in UG900 "Project File (.prj) Syntax" `[V-doc]`
<https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Vivado-Simulator-Quick-Reference-Guide>.

Output of this stage: compiled objects plus `xvlog.log`, `xvhdl.log`, `xsim.dir/`, `*.pb` (protobuf
caches) in the working directory `[V-doc]` (same tutorial: `ls` shows
`xelab.log xsim.dir xvhdl.pb xvlog.pb …`).

### 2.2 Elaborate — `xelab`

```bash
xelab -debug typical -top tb -snapshot tb_snapshot                              # SV/Verilog DUT
xelab -debug all     -top tb -snapshot tb_snapshot                              # full debug visibility
xelab -prj sim_xsim.prj -s tb_snapshot xil_defaultlib.testbench                 # project-file flow
xelab --timescale 1ns/1ps -top tb -snapshot tb_snapshot                         # explicit time scale
xelab -L unisims_ver -L secureip -top tb -snapshot tb_snapshot                  # vendor libraries
```

- `xelab -debug <level>`: `typical` = "settings that work for most designs", `all` = full visibility
  (needed to probe internal signals / all objects) `[V-doc]` (UG900 "Vivado Simulator Elaboration
  Options" describes `xsim.elaborate.debug_level` with exactly those two meanings).
- `-s` / `-snapshot` names the snapshot; `-prj` lets `xelab` implicitly run `xvlog`/`xvhdl` itself,
  which is the documented way to skip the parser stage `[V-doc]`
  <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/xelab>.
- Elaboration prints e.g. `Time Resolution for simulation is 1ps`, `Built simulation snapshot <name>`
  `[V-doc]` (itsembedded part 1 transcript).

### 2.3 Simulate — `xsim`

```bash
xsim tb_snapshot -R                     # run to completion ("run all")
xsim tb_snapshot --tclbatch run.tcl     # run a TCL script (waves, checks, exit)
xsim tb_snapshot -R -tclbatch waves.tcl
xsim --gui tb_snapshot.wdb              # open a saved waveform database in the GUI
xsim --gui tb_snapshot                  # start the GUI and run interactively
xsim --help
```

Verified option semantics `[V-doc]`: `xsim top -R` = "Simulates the design through completion",
`xsim top -gui` opens the GUI (UG900 Quick Reference Guide,
<https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Vivado-Simulator-Quick-Reference-Guide>);
`--tclbatch` = batch TCL file; the snapshot directory contains a generated
`xsim.dir/<snapshot>/xsim_script.tcl` which `xsim` sources at startup, and the invocation is logged
in the same file as a comment, e.g.:

```tcl
source xsim.dir/rs_erasure/xsim_script.tcl
# xsim {rs_erasure} -maxdeltaid 10000 -autoloadwcfg -tclbatch {rs_erasure.tcl}
```

`[V-doc]` (UG900 document content mirrored by the AMD TIP index; also `xsim -R` transcript in
itsembedded part 1 shows `xsim_script.tcl` + `-autoloadwcfg -runall`).

### 2.4 Batch TCL script — the agent's scripted run

`run.tcl` (feed with `xsim <snapshot> --tclbatch run.tcl`):

```tcl
# --- wave capture: WDB (native, viewable with `xsim --gui <snap>.wdb`) ------
log_wave -recursive /*
# --- or VCD (open_vcd / log_vcd / close_vcd mirror the Verilog $dump* tasks)
open_vcd sim.vcd
log_vcd *
# --- optional: pin the signals you actually want ---------------------------
add_wave -r /tb/*
# --- run & clean exit ------------------------------------------------------
run 10 us
# run all                       ; # alternative: run to completion
close_vcd
quit
```

Command facts `[V-doc]`:
- VCD: UG900 "Using the Value Change Dump Feature" — "For the VCD feature, the Tcl commands listed
  in the following table model the Verilog system tasks: `open_vcd` … `log_vcd` …"
  <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Using-the-Value-Change-Dump-Feature>
- `add_wave [-r] <path>`, `save_wave_config <file>.wcfg`, `log_wave -recursive` and
  `restart`/`run`/`run -all` are the standard xsim Tcl commands; real AMD-shipped scripts use
  exactly `add_wave -r /` / `save_wave_config rs_erasure.wcfg` `[V-doc]` (AMD TIP document content,
  and the AMD support thread on `add_wave` with generate-loop names
  <https://adaptivesupport.amd.com/s/question/0D52E00006hpZERSA2/vivado-addwave-nothing-was-found>).
- Non-GUI runs still write the **WDB** (`<snapshot>.wdb`) which can be opened afterwards with
  `xsim --gui <snapshot>.wdb` `[V-doc]`
  <https://adaptivesupport.amd.com/s/question/0D52E00006hpU5gSAE/simulation-in-nonproject-mode>.

### 2.5 Directory layout produced by the flow

```
SIM/
├── xvlog.log  xvhdl.log  xelab.log  xsim.log      # per-tool logs (agent should grep these)
├── xvlog.pb   xvhdl.pb   xelab.pb                 # protobuf caches
├── xsim.dir/<snapshot>/                           # elaborated snapshot + xsim_script.tcl
├── <snapshot>.wdb                                 # waveform database
├── sim.vcd                                        # if open_vcd/log_vcd used
├── *.jou                                          # webtalk journal junk
└── webtalk*.backup.log                            # ditto
```

Clean target: `rm -rf *.jou *.log *.pb *.wdb xsim.dir *.vcd` `[V-doc]` (itsembedded part 3).

### 2.6 Non-project, copy-paste-able XSim Makefile (no cocotb)

```makefile
# Makefile — XSim batch flow, no cocotb. Run: make            (or: make waves)
VIVADO      ?= /opt/Xilinx/Vivado/2023.2
XIL          = $(VIVADO)/bin
TB_TOP       ?= tb
SNAP         ?= $(TB_TOP)_snapshot
RUN_TIME     ?= 10us
SOURCES_SV   ?=
SOURCES_V    ?=
SOURCES_VHDL ?= ../src/dut.vhd
COMP_OPTS    ?= -i ./include -d SIMULATION

export PATH := $(XIL):$(PATH)

.PHONY: all compile elab sim waves clean
all: sim

compile:
	@test -n "$(SOURCES_VHDL)" && xvhdl --incr --relax $(COMP_OPTS) $(SOURCES_VHDL) || true
	@test -n "$(SOURCES_SV)"   && xvlog --sv --incr --relax $(COMP_OPTS) $(SOURCES_SV) || true
	@test -n "$(SOURCES_V)"    && xvlog    --incr --relax $(COMP_OPTS) $(SOURCES_V)  || true

elab: compile
	xelab -debug typical -timescale 1ns/1ps -top $(TB_TOP) -snapshot $(SNAP)

sim: elab
	xsim $(SNAP) -R -tclbatch run.tcl

waves: $(SNAP).wdb
	xsim --gui $(SNAP).wdb

$(SNAP).wdb: sim

clean:
	rm -rf *.jou *.log *.pb *.wdb xsim.dir *.vcd
```

> **Version note the agent must handle:** in the 2026.1 toolchain the Quick Reference uses
> `-timescale`/`-debug` spellings as shown; older or newer releases may require `--timescale`.
> Always first run `xelab --help | grep -i timescale` in the *actual* installation and adapt, rather
> than assuming. `[unverified]` for release-specific flag spelling.

---

## 3. cocotb 2.0.1 — verified API reference

Everything below was read from the installed package `[V-src]`
(`<VENV>/lib/python3.12/site-packages/lib/python3.12/site-packages/`)
and/or executed `[V-local]`.

### 3.1 Package layout changed in 2.0 — **makefiles moved**

| 1.x | 2.0.1 |
|---|---|
| `cocotb/share/makefiles/Makefile.sim` | **`cocotb_tools/makefiles/Makefile.sim`** |
| `cocotb/share/makefiles/simulators/Makefile.<sim>` | **`cocotb_tools/makefiles/simulators/Makefile.<sim>`** |
| `cocotb/config.py` | `cocotb_tools/config.py` (CLI `cocotb-config` still works) |
| `cocotb.runner` | **`cocotb_tools.runner`** (`cocotb/runner.py` no longer exists) |

`cocotb-config --makefiles` correctly returns `…/cocotb_tools/makefiles` `[V-local]`.
**Do not hard-code `cocotb/share/makefiles`** — it does not exist in a 2.0 wheel; a legacy Makefile
using it fails with "Aucun fichier ou dossier de ce nom".

### 3.2 The four-line contract

```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

@cocotb.test(timeout_time=10, timeout_unit="us")   # always set a timeout
async def my_test(dut):
    Clock(dut.clk, 10, unit="ns").start()          # 2.0: start() schedules it itself
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    assert int(dut.q.value) == 0
```

Note `@cocotb.test` now works **without parentheses** as well (`@cocotb.test` directly) — `[V-src]`
`cocotb._decorators`. `@cocotb.test` returns the decorated object (`Test`), not the raw function.

### 3.3 `cocotb.clock.Clock` — the `units` → `unit` rename

`[V-src]` `cocotb/clock.py`, `[V-local]` runtime:

```python
Clock(signal, period, unit="step", impl=None, *,
      units=None,             # DEPRECATED alias, warns
      set_action=None,        # Immediate | Deposit (default) | Force
      period_high=None)       # 2.0: asymmetric clock support
```

- `Clock(dut.clk, 10, "ns")` — positional `unit` works.
- `Clock(dut.clk, 10, units="ns")` → `DeprecationWarning: The 'units' argument has been renamed to 'unit'.` `[V-local]`
- `unit=None` was **removed**; use `"step"` `[V-src]`.
- `period` must be an even number of simulator steps if `period_high` is not given `[V-src]`.
- `.start()` now starts the clock itself (`cocotb.start_soon` internally) and returns a `Task`;
  `.stop()` cancels it; `.cycles(n, edge_type=RisingEdge)` awaits n edges `[V-src]`.
- `.impl` is `"gpi"` (C, fast) when `COCOTB_TRUST_INERTIAL_WRITES` is set, else `"py"`.
  With GHDL the cocotb Makefiles export `COCOTB_TRUST_INERTIAL_WRITES=1`, so `impl == "gpi"` `[V-local]`.
- Version removal `[V-src]`: the old `Clock(..., cycles=N)` argument for a finite number of toggles is gone.

### 3.4 Triggers — `cocotb.triggers`

Full public set in 2.0.1 `[V-src]` (`cocotb/triggers.py::__all__`):

```
ClockCycles, Combine, Edge, Event, FallingEdge, First, GPITrigger, Lock, NextTimeStep,
NullTrigger, ReadOnly, ReadWrite, RisingEdge, SimTimeoutError, Timer, Trigger, ValueChange,
Waitable, current_gpi_trigger, with_timeout
```

Usage that was executed successfully `[V-local]`:

```python
from cocotb.triggers import RisingEdge, FallingEdge, Timer, ReadOnly, ClockCycles, with_timeout
await Timer(5, unit="ns")          # or Timer(5, "ns")
await RisingEdge(dut.clk)
await ReadOnly()                    # signals readable, stable; writes raise RuntimeError
await ClockCycles(dut.clk, 3)
await with_timeout(RisingEdge(dut.ready), 1, "us")   # raises SimTimeoutError
```

- Writing during `ReadOnly` raises
  `RuntimeError: Attempting settings a value during the ReadOnly phase.` (sic — cocotb's own typo,
  do not "fix" it in a string match) `[V-local]`.
- `Join` moved to `cocotb.task`; importing it from `cocotb.triggers` emits a warning `[V-src]`.
- `with_timeout(trigger, timeout_time, timeout_unit="step", round_mode=None)` accepts a Trigger,
  a Waitable, a Task or a coroutine `[V-src]`.

### 3.5 Values, handles and types

```python
dut.q.value                     # getter → LogicArray for vector signals, Logic for 1-bit
dut.q.value = 0x1F              # setter (deposit)
dut.sig.set(Force(1))           # 2.0: Force/Deposit/Immediate/Freeze/Release
dut.sig.value = Immediate(1)    # no-delay subset
```

`[V-src]` `cocotb/handle.py`, `cocotb/types/_logic_array.py`, `cocotb/types/_logic.py`.

**Breaking change discovered by running:** the classic
`dut.q.value.integer` / `dut.q.value.binstr` are **deprecated in 2.0** `[V-src]` `[V-local]`:

| Old (deprecated, warns) | Replacement |
|---|---|
| `logic_array.integer` (get) | `logic_array.to_unsigned()` |
| `logic_array.integer = v` (set) | `logic_array[:] = v` |
| `logic_array.signed_integer` | `logic_array.to_signed()` |
| `logic_array.signed_integer = v` | `logic_array[:] = LogicArray.from_signed(v, len(la))` |
| `logic_array.binstr` | `str(logic_array)` |
| `logic_array.binstr = s` | `logic_array[:] = s` |
| `logic_array.buff` | `logic_array.to_bytes(byteorder="big")` |
| `logic_array.buff = b` | `logic_array[:] = LogicArray.from_bytes(b, len(la), byteorder="big")` |
| `handle.setimmediatevalue(v)` | `handle.set(Immediate(v))` |

Real warning text captured `[V-local]`:
`DeprecationWarning: logic_array.integer getter is deprecated. Use logic_array.to_unsigned() instead.`

Also verified `[V-local]`: `int(dut.q.value)` uses unsigned interpretation
(`LogicArray.__int__` → `to_unsigned()`), `LogicArray("1010").to_unsigned() == 10`,
`str(LogicArray("1010")) == "1010"`, and 1-bit signals expose `.value` as `Logic`
(which is `bool`/`int`-convertible).

**X/U handling** `[V-local]`:

```
before reset q=LogicArray('UUUUUUUU', Range(7, 'downto', 0))  is_resolvable=False
int(q) → ValueError: Can't convert LogicArray to int: it contains non-0/1 values
str(q) → 'UUUUUUUU'
```

So: **never** `int()` an uninitialised signal — check `.is_resolvable` first (or set
`COCOTB_RESOLVE_X` to control how X/Z/U map onto integers `[V-src]` `cocotb_tools/config.py` help text).

**Types** `[V-src]` `cocotb/types/__init__.py`: `AbstractArray, AbstractMutableArray, Array, Bit,
IndexingChangedWarning, Logic, LogicArray, Range`.

**Simulation time** `[V-src]`: `cocotb.simtime.get_sim_time(unit="ns")`, plus
`cocotb.utils.get_sim_steps()` / `get_time_from_sim_steps()`.

### 3.6 Concurrency, queues, tasks

```python
cocotb.start_soon(coro())        # schedule; runs when the caller yields  [V-local ✓]
t = await cocotb.start(coro())   # start immediately and await/branch it
task.cancel()                    # 2.0: kill() is deprecated → cancel()
from cocotb.queue import Queue, PriorityQueue, LifoQueue, QueueEmpty, QueueFull
q.put_nowait(x); x = await q.get()
```

- `cocotb.start_soon()` is **not** async; the new task does not execute until the caller awaits `[V-src]`.
- `task.kill()` → `@deprecated("`task.kill()` is deprecated in favor of `task.cancel()`")` `[V-src]`.
- `Task.retval`, `Task.__bool__`, `_finished` were removed in 2.0 `[V-src]`.
- `cocotb.queue` provides asyncio-style queues backed by cocotb `Event`s — verified working with a
  producer task started by `cocotb.start_soon` `[V-local]`.

### 3.7 Test management

`[V-src]`/`[V-doc]`:

- `@cocotb.test(timeout_time=…, timeout_unit="step", expect_fail=False, expect_error=Exception, skip=False, stage=0, name=None)`
- `cocotb.end_test(msg=None)` — end as if passed (respects xfail/expect_*)
- `cocotb.pass_test(msg=None)` — force pass (deprecated in 2.1)
- `cocotb.parametrize(...)` (2.0) — declarative parametrisation (see §4.6)
- `@cocotb.parametrize(arg1=[0,1], arg2=["a","b"])` above `@cocotb.test()` generates a test per
  Cartesian-product combination, named `my_test/arg1=0/arg2=a` `[V-src]`

### 3.8 Makefile variables (`Makefile.sim` embeds the authoritative help)

`make help` prints these; the full list from the installed `Makefile.sim` `[V-src]`:

```
Makefile-based Test Scripts
---------------------------
GUI                       Set this to 1 to enable the GUI mode in the simulator
SIM                       Selects which simulator Makefile to use
WAVES                     Enable wave traces dump for Riviera-PRO and Questa
VERILOG_SOURCES           A list of the Verilog source files to include
VHDL_SOURCES              A list of the VHDL source files to include
VHDL_SOURCES_<lib>        VHDL source files to include in *lib* (GHDL/NVC/ModelSim/Questa/…)
VHDL_LIB_ORDER            Compilation order of VHDL libraries (NVC/ModelSim/Questa/…)
SIM_CMD_PREFIX            Prefix for simulation command invocations
COMPILE_ARGS              Arguments to pass to compile (analysis) stage
SIM_ARGS                  Arguments to pass to execution of compiled simulation
EXTRA_ARGS                Arguments for compile AND execute phases
COCOTB_PLUSARGS           Plusargs to pass to the simulator
COCOTB_HDL_TIMEUNIT       Default time unit for simulation       (default 1ns)
COCOTB_HDL_TIMEPRECISION  Default time precision for simulation  (default 1ps)
CUSTOM_COMPILE_DEPS       Add additional dependencies to the compilation target
CUSTOM_SIM_DEPS           Add additional dependencies to the simulation target
SIM_BUILD                 Scratch directory for the simulator    (default sim_build)
SCRIPT_FILE               Simulator script to run (e.g. wave traces)
```

Modern (non-deprecated) names, with the legacy aliases shown by `Makefile.deprecations` `[V-src]`:

| Use this | Legacy alias (warns) |
|---|---|
| `COCOTB_TOPLEVEL` | `TOPLEVEL` |
| `COCOTB_TEST_MODULES` | `MODULE` |
| `COCOTB_TESTCASE` | `TESTCASE` |
| `COCOTB_PLUSARGS` | `PLUSARGS` |
| `COCOTB_USER_COVERAGE` | `COVERAGE` |
| — | `RTL_LIBRARY` → `TOPLEVEL_LIBRARY` |

`[V-local]`: `make … TOPLEVEL=counter MODULE=test_counter` still runs the intended tests (a
`Using X is deprecated` warning is emitted). Migrate when generating code.

Environment variables (read from the installed sources and `cocotb-config --help-vars` `[V-src]`):

```
COCOTB_TOPLEVEL COCOTB_TEST_MODULES COCOTB_TESTCASE COCOTB_TEST_FILTER
COCOTB_RESULTS_FILE COCOTB_RANDOM_SEED COCOTB_LOG_LEVEL COCOTB_LOG_PREFIX
COCOTB_ANSI_OUTPUT COCOTB_REDUCED_LOG_FMT COCOTB_ATTACH COCOTB_ENABLE_PROFILING
COCOTB_PDB_ON_EXCEPTION COCOTB_RESOLVE_X COCOTB_USER_COVERAGE COCOTB_HDL_TIMEPRECISION
COCOTB_TRUST_INERTIAL_WRITES COCOTB_SCHEDULER_DEBUG COCOTB_WAVEFORM_VIEWER
COCOTB_PLUSARGS COCOTB_REWRITE_ASSERTION_FILES LIBPYTHON_LOC GPI_EXTRA
WAVES GUI SIM HDL_TOPLEVEL_LANG
# COCOTB_LIST_TESTS and COCOTB_RESULTS_ATTACHMENTS exist only from cocotb 2.1 on [V-doc]
```

Verified `[V-local]`:
- `COCOTB_TEST_FILTER="test_generic_visible"` ran exactly 1 test of 3.
- `COCOTB_RANDOM_SEED=42` logged `Seeding Python random module with supplied seed 42` —
  reproducible stimulus in one env var.
- `COCOTB_TESTCASE` selects test **names**; `COCOTB_TEST_FILTER` is a **regex** `[V-doc]`.
- Result file: `results.xml` (xUnit), checked by `python -m cocotb_tools.check_results results.xml`,
  which is what makes `make` exit non-zero on test failure `[V-src]`.

### 3.9 The Python runner (`cocotb_tools.runner`)

`[V-src]` `cocotb_tools/runner.py`, `[V-doc]` <https://docs.cocotb.org/en/stable/runner.html>.
Officially "experimental and subject to change".

```python
from cocotb_tools.runner import get_runner, VHDL, Verilog, VerilatorControlFile

runner = get_runner("ghdl")                 # icarus | questa | ghdl | riviera | verilator
                                            # xcelium | nvc | vcs | dsim
runner.build(                              # ── build ──
    sources=[...],                          # language-agnostic; .vhd/.v/.sv/.vlt auto-tagged
    vhdl_sources=[...], verilog_sources=[...],   # deprecated since 2.0 → use `sources`
    includes=[...], defines={...}, parameters={...},  # parameters: Verilog params / VHDL generics
    build_args=[...], hdl_toplevel="counter", hdl_library="top",
    always=False, build_dir="sim_build", clean=False, verbose=False,
    timescale=("1ns", "1ps"), waves=False, log_file=None,
)
runner.test(                               # ── test ──
    test_module="test_counter", hdl_toplevel="counter", hdl_toplevel_library="top",
    hdl_toplevel_lang=None, testcase=None, test_filter=None, seed=None,
    elab_args=[...], test_args=[...], plusargs=[...], extra_env={...},
    waves=False, gui=False, parameters=None, build_dir=None, test_dir=None,
    results_xml=None, pre_cmd=[...], timescale=None,
)
```

Verified behaviours `[V-local]`:

- `get_runner(<bad name>)` → `ValueError: Simulator 'xsim' is not in supported list: icarus, questa,
  ghdl, riviera, verilator, xcelium, nvc, vcs, dsim` `[V-src]` (exact wording from source).
- `defines` are converted with `_as_sv_literal` for Verilog (`-Dname="value"`) and are **not**
  auto-converted for VHDL; use `as_vhdl_literal()`/`as_sv_literal()` explicitly if you need literals
  (the 2.0 changelog in the docstring says defines are no longer implicitly converted) `[V-src]`.
- Simulator-specific limitations are in each class docstring `[V-src]`:

| Runner | Documented limits (from the class docstring) |
|---|---|
| `Icarus` | `hdl_toplevel` **required**; `waves=True` must be on `build` if waves/gui used in `test`; `timescale` must be given to build; no `pre_cmd`. |
| `Verilator` | `waves=True` must be on `build`; `hdl_toplevel` required; no `pre_cmd`. |
| `Ghdl` | no `pre_cmd`. VPI only. |
| `Questa` | no `timescale` argument. FLI+VHPI for VHDL, VPI for Verilog. |

- **GHDL runner pitfall found by experiment** `[V-local]`: `build()` compiles into
  `build_dir` and `test()` runs in `test_dir` (which defaults to `build_dir`), but
  `build_args` are **not** forwarded to the run command. For a VHDL-2008 design the run therefore
  fails with `ghdl:error: cannot find entity or configuration counter` unless `--std=08` is also
  passed to `test`. And if you set `test_dir` to the project directory (so Python can import the
  test module) you must additionally tell GHDL where the library lives. Both workarounds verified:

```python
# A) keep test_dir == build_dir, make the project importable via PYTHONPATH
runner.build(sources=[p/"counter.vhd"], hdl_toplevel="counter",
             build_args=["--std=08"], build_dir=bd)
runner.test(hdl_toplevel="counter", test_module="test_counter", build_dir=bd,
            test_args=["--std=08"], extra_env={"PYTHONPATH": str(p)})      # ✓ PASS

# B) run in the project dir and point GHDL at the library explicitly
runner.test(hdl_toplevel="counter", test_module="test_counter", build_dir=bd, test_dir=p,
            test_args=["--std=08", f"--workdir={bd}", f"-P{bd}"])          # ✓ PASS
```

### 3.10 Waveforms per simulator

| Simulator | How the agent produces waves | File |
|---|---|---|
| GHDL | `SIM_ARGS=--vcd=x.vcd` (or `--fst`, `--wave` for GHW, `--vcdgz`) | VCD / FST / GHW / GZ-VCD |
| Icarus | `WAVES=1` (`make SIM=icarus WAVES=1`) → FST in `sim_build/<top>.fst`; `+dumpfile_path=<path>` to relocate | **FST** (not VCD) |
| Verilator | `EXTRA_ARGS += --trace --trace-structs` (+ `--trace-fst` for FST) | `dump.vcd` / `dump.fst` |
| Questa | `WAVES=1` → `log -recursive /*` in the generated `runsim.do`; `GUI=1` for the GUI | WLF |
| XSim | `log_wave -recursive /*` (WDB) or `open_vcd`/`log_vcd` Tcl in `-tclbatch` | WDB / VCD |
| Runner API | `waves=True` on `build()` **and** `test()`; `WAVES=1` env overrides | per simulator |

GHDL waveform formats were **all executed** `[V-local]`: `--vcd=v.vcd`, `--fst=f.fst`,
`--wave=w.ghw`, `--vcdgz=g.vcd.gz` each produced the corresponding file with a green test run.
`[V-doc]` GHDL wave export <https://ghdl.github.io/ghdl/using/Simulation.html#export-waves>.
`[V-doc]` cocotb waveform tables <https://docs.cocotb.org/en/stable/simulator_support.html>.

Viewer: **GTKWave** reads VCD/FST/LXT/GHW `[V-doc]` <https://gtkwave.sourceforge.net/>;
cocotb can auto-open a viewer after a run via `GUI=1`, choosing Surfer then GTKWave, overridable
with `COCOTB_WAVEFORM_VIEWER` `[V-doc]`.

### 3.11 Reading and writing files inside a testbench

cocotb tests are plain Python, so use the normal file APIs, but be explicit about the working
directory — the simulator's CWD is `SIM_BUILD` (Makefile flow) or `test_dir`/`build_dir` (runner flow):

```python
from pathlib import Path

HERE = Path(__file__).resolve().parent          # the *source* dir, always safe to anchor on

async def test_vectors_from_file(dut):
    golden = [int(line, 16) for line in (HERE / "vectors.txt").read_text().splitlines()]
    got = []
    for exp in golden:
        dut.din.value = exp >> 8
        await RisingEdge(dut.clk)
        got.append(int(dut.dout.value))
    (HERE / "results.txt").write_text("\n".join(map(str, got)))   # relative-safe output
```

Rules an agent should follow:
1. Anchor every path on `Path(__file__).resolve().parent` — never on `os.getcwd()`.
2. Never assume the VCD/log path: pass it explicitly (`SIM_ARGS=--vcd=...`,
   `EXTRA_ARGS += --trace`, `COCOTB_RESULTS_FILE=...`).
3. Write artefacts into `SIM_BUILD` or the project dir; the flow's `clean` target deletes the former.
4. For simulator-side file I/O (VHDL `textio`, Verilog `$readmemh`/`$fopen`), the path is resolved
   against the **simulator's** CWD — build absolute paths into the generated TB `[unverified]` in
   detail, but the XSim forum answer for `$readmemh` files confirms this asymmetry
   <https://adaptivesupport.amd.com/s/question/0D52E00006iHvF5SAK/include-txt-files-for-xsim-simulation>.

### 3.12 Good practices checklist

1. **Always** set `@cocotb.test(timeout_time=…, timeout_unit=…)`. Without it a deadlock makes the
   agent hang forever. `[V-local]`: with `SIM_ARGS=--stop-time=50ns` and no timeout the 3 tests
   reported `TESTS=3 PASS=0 FAIL=3` — a clear signal, but by default you would get a hang.
2. **Clock helper**: one `Clock(...)` per test, `start()`, then await edges. Never hand-roll a clock
   unless you need phase/duty control.
3. **Reset helper**: a single `async def reset_dut(dut, cycles=2)` used by every test — deterministic
   starting state, no reliance on VHDL/Verilog `initial` blocks.
4. **Assertions with messages**: `assert int(dut.q.value) == 5, f"expected 5, got {int(dut.q.value)}"`.
   Plain `assert` gives pytest-grade messages only if pytest is installed (here it is not:
   `pytest not found, install it to enable better AssertionError messages` `[V-local]`).
5. **Fail loudly, not silently**: catch only what you mean to catch; use
   `cocotb.end_test()` only for deliberate early exits.
6. **Reproducible randomness**: seed Python explicitly —
   `rng = random.Random(cocotb.RANDOM_SEED)` — so a failure can be replayed with
   `COCOTB_RANDOM_SEED=<value>` `[V-local]`.
7. **Concurrency**: one driver task per interface (`cocotb.start_soon(driver())`), scoreboards in a
   separate task reading a `Queue`; never interleave manual `await` chains across processes.
8. **Time units**: always pass `unit=` explicitly (`Timer(5, unit="ns")`); `"step"` is the raw
   simulator step and its meaning depends on `COCOTB_HDL_TIMEPRECISION` (default 1 ps → a
   `Timer(5)` is 5 ps, not 5 ns!). Verified `[V-local]`: GHDL was invoked with
   `--time-resolution=ps` derived from `COCOTB_HDL_TIMEPRECISION=1ps`.
9. **Keep the reference model in Python** (numpy/scipy) — the strongest capability of a
   cocotb-based agent — and compare cycle by cycle, not just at the end (§4.4, §4.5).
10. **`make` exit code is the contract**: `make` fails when `cocotb_tools.check_results` finds a
    failure in `results.xml`. Parsing `results.xml` is more reliable for an agent than scraping logs.
11. **Log level**: `COCOTB_LOG_LEVEL=DEBUG` for debugging; default INFO is quiet enough to read.
12. **Idempotence**: pass `always=True` (runner) or `rm -rf sim_build` when the DUT changed but the
    file list did not; stale `sim_build` is a classic source of "old code still passing".

---

## 4. Copy-paste Makefile templates

All templates below were validated against the real cocotb 2.0.1 layout
(`include $(shell cocotb-config --makefiles)/Makefile.sim`) `[V-local]`/`[V-doc]`.

### 4.1 GHDL (VHDL) — **verified working end-to-end here**

```makefile
# Makefile — VHDL DUT on GHDL
SIM           ?= ghdl
TOPLEVEL_LANG ?= vhdl

VHDL_SOURCES  += $(PWD)/counter.vhd
# dependency order is mandatory; list packages before users:
# VHDL_SOURCES += $(PWD)/pkg_util.vhd $(PWD)/counter.vhd

COCOTB_TOPLEVEL      = counter        # VHDL *entity* name (not the architecture)
COCOTB_TEST_MODULES  = test_counter   # basename of test_counter.py

# --std=08 is required for VHDL-2008 and must apply to analyse, elaborate AND run;
# EXTRA_ARGS is the only variable that reaches all three phases.
EXTRA_ARGS    += --std=08
# VCD out: make SIM_ARGS="--vcd=counter.vcd"   (or export SIM_ARGS below)
# SIM_ARGS    += --vcd=counter.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
```

Selecting an architecture: `make ARCH=rtl`. Selecting the library:
`make TOPLEVEL_LIBRARY=work` (default `work`; `RTL_LIBRARY` is the deprecated spelling) `[V-src]`.

### 4.2 Icarus Verilog

```makefile
# Makefile — Verilog/SystemVerilog DUT on Icarus
SIM           ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/counter.v
# VERILOG_SOURCES += $(PWD)/pkg.sv $(PWD)/counter.sv
VERILOG_INCLUDE_DIRS += $(PWD)/include     # becomes -I<dir>

COCOTB_TOPLEVEL     = counter
COCOTB_TEST_MODULES = test_counter

EXTRA_ARGS   += -DDEBUG=1 -Pcounter.WIDTH=8    # raw iverilog args (defines, params)
# WAVES=1 -> FST in sim_build/<toplevel>.fst (Icarus does NOT write VCD by default)
# make WAVES=1

include $(shell cocotb-config --makefiles)/Makefile.sim
```

`[V-src]`: the Icarus Makefile always compiles with `-g2012` and writes a `+timescale+` command file;
`WAVES=1` injects a generated `cocotb_iverilog_dump.v` and `-fst`. cocotb needs Icarus ≥ 11.0 `[V-doc]`.

### 4.3 Verilator

```makefile
# Makefile — Verilog/SystemVerilog DUT on Verilator (2-state!)
SIM           ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/counter.sv
COCOTB_TOPLEVEL     = counter
COCOTB_TEST_MODULES = test_counter

# traces MUST be enabled at build time
EXTRA_ARGS += --trace --trace-structs            # -> dump.vcd
# EXTRA_ARGS += --trace --trace-fst --trace-structs   # -> dump.fst
# EXTRA_ARGS += --coverage                            # -> coverage.dat
COCOTB_HDL_TIMEUNIT      = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

include $(shell cocotb-config --makefiles)/Makefile.sim
```

`[V-src]`: the Verilator Makefile hard-codes `--vpi --public-flat-rw --prefix Vtop` and links
`libcocotbvpi_verilator`; it **errors out** if `verilator --version` < 5.036. VCD/FST/SAIF are
mutually exclusive per build `[V-doc]`.

### 4.4 Questa / ModelSim

```makefile
# Makefile — mixed VHDL/Verilog on Questa / ModelSim
SIM           ?= questa            # or: modelsim, questa-compat, questa-qisqrun
TOPLEVEL_LANG ?= verilog           # or vhdl

VERILOG_SOURCES += $(PWD)/counter.v
VHDL_SOURCES    += $(PWD)/counter.vhd
VERILOG_INCLUDE_DIRS += $(PWD)/include

COCOTB_TOPLEVEL     = counter
COCOTB_TEST_MODULES = test_counter

VHDL_GPI_INTERFACE ?= fli          # or vhpi (Questa >= 2022.3; PE editions have NO fli)
# WAVES=1 -> log -recursive /* ; GUI=1 -> -gui and the sim stays alive
# EXTRA_ARGS   += +define+DEBUG=1   # vlog/vcom options (also accepted via COMPILE_ARGS)
# SIM_ARGS     += -gWIDTH=8         # vsim runtime options

include $(shell cocotb-config --makefiles)/Makefile.sim
```

`[V-src]`/`[V-doc]`: 2.0 auto-selects the flow — Questa ≥ 2025.2 uses **QIS/Qrun**
(`SIM=questa-qisqrun`), older versions and ModelSim use **compat** (`SIM=questa-compat`, commands
`vlog`/`vopt`/`vsim` with `+acc`). The generated `runsim.do` on this machine was `[V-local]`:

```tcl
onerror { quit -f -code 1 }
vmap -c
vlib sim_build/work
vmap work sim_build/work
vlog -work work -sv -timescale 1ns/1ps -mfcu +acc  counter.v
vsim -onfinish exit -pli .../libcocotbvpi_modelsim.so work.counter
onbreak resume
run -all
quit
```

Also verified: `SIM=questa` + Verilog needs `VERILOG_SOURCES` only; a **VHDL** toplevel additionally
requires the FLI library to exist in the edition (§1.4).

### 4.5 XSim — there is no cocotb Makefile

Two options:

**(a) cocotb-free XSim Makefile** → §2.6. This is what an agent should generate for Vivado.

**(b) cocotb-with-XSim**: not possible with stock cocotb 2.0.1; use a community bridge
(`themperek/cocotb-vivado`, `kiran-vuksanaj/vicoco`) or export the simulation from the Vivado GUI
(`export_simulation`) and drive the generated `.sh`. `[V-doc]`
<https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/export_simulation>.

### 4.6 How to choose the toplevel

| Case | Setting | Notes |
|---|---|---|
| VHDL entity | `COCOTB_TOPLEVEL = <entity>` | architecture via `ARCH=<name>`; library via `TOPLEVEL_LIBRARY` (default `work`) |
| Verilog module | `COCOTB_TOPLEVEL = <module>` | Icarus uses `-s <module>`; Verilator `--top-module <module>` `[V-src]` |
| Package-only VHDL top | not simulatable | a cocotb TB needs an entity/architecture pair |
| Multiple TBs | `COCOTB_TEST_MODULES = a,b` | comma-separated; all matching tests run across all modules (2.0 change: previously only the first match ran) `[V-doc]` |
| Test selection | `COCOTB_TESTCASE=test_a,test_b` (names) or `COCOTB_TEST_FILTER='test_[ab].*'` (regex) | verified `[V-local]` |
| Runner API | `hdl_toplevel=` (build **and** test) | `Icarus`/`Verilator` **require** it, else `ValueError` `[V-src]` |
| VHDL generic / Verilog param | Makefile: `EXTRA_ARGS += -gWIDTH=8` (GHDL/Questa) / `-Ptop.WIDTH=8` (Icarus) / `-G` (Verilator); Runner: `parameters={"WIDTH": 8}` | `[V-src]` |

---

## 5. cocotb recipe library for agents

### 5.1 Combinational DUT (no clock)

```python
@cocotb.test(timeout_time=1, timeout_unit="ms")
async def test_alu_comb(dut):
    for a, b in [(1, 2), (0xFF, 1), (7, 7)]:
        dut.a.value = a
        dut.b.value = b
        await Timer(1, unit="ns")          # let the combinational logic settle
        assert int(dut.y.value) == expected(a, b), \
            f"a={a} b={b}: got {int(dut.y.value)} want {expected(a, b)}"
```

### 5.2 Synchronous DUT with async vs sync reset

```python
async def reset_async(dut, cycles=2):
    """Active-low async reset."""
    dut.rst_n.value = 0
    dut.en.value = 0
    await RisingEdge(dut.clk); await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

async def reset_sync(dut, cycles=2):
    """Synchronous reset: assert, clock it, release, clock once more."""
    dut.rst_n.value = 0
    dut.en.value = 0
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
```

`[V-local]` verified: after `reset_async`, `int(dut.q.value) == 0`.

### 5.3 Bus driver (reusable)

```python
class BusDriver:
    """Simple valid/ready request driver."""
    def __init__(self, dut, clk, timeout=1, timeout_unit="us"):
        self.dut, self.clk = dut, clk
        self.timeout, self.timeout_unit = timeout, timeout_unit

    async def send(self, data: int, *, valid_delay=0):
        self.dut.valid.value = 1
        self.dut.data.value = data
        for _ in range(valid_delay):
            await RisingEdge(self.clk)
        await with_timeout(RisingEdge(self.dut.ready), self.timeout, self.timeout_unit)
        # ready is seen high on this edge: complete the handshake
        await RisingEdge(self.clk)
        self.dut.valid.value = 0


@cocotb.test()
async def test_single_transfer(dut):
    Clock(dut.clk, 10, unit="ns").start()
    await reset_async(dut)
    drv = BusDriver(dut, dut.clk)
    await drv.send(0xAB)
    assert dut.valid.value == 0
```

### 5.4 Scoreboard (queue + reference model)

```python
from cocotb.queue import Queue

class Scoreboard:
    def __init__(self, log):
        self.expected, self.actual, self.errors = Queue(), Queue(), []

    async def run(self):
        while True:
            exp, got = await self.expected.get(), await self.actual.get()
            if exp != got:
                self.errors.append((exp, got))
                cocotb.log.error("MISMATCH expected=0x%X got=0x%X", exp, got)

    def check(self):
        assert not self.errors, f"{len(self.errors)} mismatches, first: {self.errors[0]}"
```

Start it once per test with `sb = Scoreboard(cocotb.log); cocotb.start_soon(sb.run())`, then
`sb.expected.put_nowait(...)` / `sb.actual.put_nowait(...)` from monitor tasks. `[V-local]`:
`Queue` + `start_soon` producer/consumer verified working on GHDL.

### 5.5 FIFO test (fill / drain / full / empty / overflow)

```python
@cocotb.test(timeout_time=100, timeout_unit="us")
async def test_fifo_fill_and_drain(dut):
    Clock(dut.clk, 10, unit="ns").start()
    await reset_sync(dut)

    data = list(range(DEPTH))
    for i, d in enumerate(data):                    # fill
        dut.wr_en.value, dut.din.value = 1, d
        await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.full.value) == 1, "FIFO should be full after DEPTH writes"

    for i, d in enumerate(data):                    # drain (FIFO order!)
        dut.rd_en.value = 1
        await RisingEdge(dut.clk)
        assert int(dut.dout.value) == d, f"word {i}: got {int(dut.dout.value)} want {d}"
    dut.rd_en.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.empty.value) == 1, "FIFO should be empty after DEPTH reads"
```

Add the overflow case explicitly (write while `full`, read while `empty`) — that is where real FIFO
bugs live.

### 5.6 Simplified AXI-Stream slave model

```python
class AXISSlave:
    """Minimal AXI4-Stream sink: accepts one beat per cycle when tready is high."""
    def __init__(self, dut, clk, tdata="tdata", tvalid="tvalid",
                 tready="tready", tlast="tlast"):
        self.dut, self.clk = dut, clk
        self.n = dict(tdata=tdata, tvalid=tvalid, tready=tready, tlast=tlast)
        self.rx = Queue()

    async def run(self, ready_prob=1.0, rng=None):
        d = self.dut
        getattr(d, self.n["tready"]).value = 1
        while True:
            await RisingEdge(self.clk)
            if int(getattr(d, self.n["tvalid"]).value) == 1 and \
               int(getattr(d, self.n["tready"]).value) == 1:
                self.rx.put_nowait((int(getattr(d, self.n["tdata"]).value),
                                    int(getattr(d, self.n["tlast"]).value)))
```

Then in the test: `cocotb.start_soon(slave.run())`, push beats, and pull from `slave.rx` to check
`tlast` framing. Back-pressure testing = drive `tready` low for N cycles
(`await Timer(N * 10, unit="ns")` or toggle it in a task) and assert no beat is lost.

### 5.7 Compare against a Python/numpy reference model

```python
import numpy as np

@cocotb.test(timeout_time=1, timeout_unit="ms")
async def test_against_numpy_fir(dut):
    Clock(dut.clk, 10, unit="ns").start()
    await reset_async(dut)

    rng = np.random.default_rng(cocotb.RANDOM_SEED)      # reproducible
    taps = np.array([1, 0, -1], dtype=np.int64)
    stim = rng.integers(-2**7, 2**7 - 1, size=64)

    # reference model in Python
    padded = np.concatenate([np.zeros(len(taps) - 1, dtype=np.int64), stim])
    expected = np.convolve(padded, taps[::-1], mode="valid")   # same convention as the RTL

    got = []
    for x in stim:
        dut.din.value = int(x)
        dut.valid.value = 1
        await RisingEdge(dut.clk)
        got.append(int(dut.dout.value))
    got = np.array(got, dtype=np.int64)

    bad = np.nonzero(got != expected)[0]
    assert bad.size == 0, (
        f"{bad.size}/{len(stim)} samples differ; first index {bad[0]}: "
        f"got {got[bad[0]]} expected {expected[bad[0]]}"
    )
```

Notes that save hours:
- Settle the pipeline correctly (`mode="valid"`, latency taps) — most "mismatches" are convention errors.
- Convert with `int(...)`/`.to_unsigned()`; never compare a `LogicArray` to a Python int
  (`LogicArray('1010') == 10` is `False`).
- Use `LogicArray.from_signed(x, n)` / `to_signed()` for signed paths.
- numpy is optional; a pure-Python list works and removes a dependency from the agent's environment.

### 5.8 Waiting N cycles

```python
async def wait_cycles(clk, n=1):
    for _ in range(n):
        await RisingEdge(clk)

# or, for a *cost* rather than a *count*:
from cocotb.triggers import ClockCycles
await ClockCycles(clk, n)
await clk.cycles(n)          # Clock instance method [V-src]
```

Prefer cycle counts over `Timer(...)` in synchronous designs: timers silently desynchronise if the
clock period changes.

### 5.9 Failing cleanly with a useful message

```python
def expect(actual, expected, *, what="", ctx=""):
    if actual != expected:
        raise AssertionError(
            f"{what}: got 0x{actual:X} want 0x{expected:X} "
            f"@ {cocotb.simtime.get_sim_time('ns')} ns {ctx}"
        )
```

Rules: include **simulation time**, the **expected vs actual**, and the **stimulus coordinates**
(loop index, address). Never `assert False`; never swallow an exception "to keep the regression green".
For an expected failure use `@cocotb.test(expect_fail=True)`; for an expected exception use
`expect_error=SomeException` (a tuple of types is allowed in 2.0) `[V-src]`.

### 5.10 Parametrised tests

```python
# 1) cocotb 2.0 declarative form (generates one test per combination)
@cocotb.test(timeout_time=50, timeout_unit="us")
@cocotb.parametrize(WIDTH=[4, 8, 16], RESET="async", SYNC="sync")
async def test_widths(dut, WIDTH, RESET, SYNC):
    ...
```

Note the signature above matches `cocotb.parametrize`'s documented calling convention (`dut` plus the
generated kwargs) `[V-src]` — this is the form that generates names like `test_widths/WIDTH=4`.

```python
# 2) explicit per-configuration test functions (simplest, most robust for an agent)
def make_test(width, reset_kind):
    @cocotb.test(name=f"test_{width}_{reset_kind}")
    async def _t(dut):
        ...
    return _t
```

For the *stimulus* dimension, parametrise in the Makefile instead
(`make EXTRA_ARGS="-gWIDTH=$w"`) so that the generic is compiled once per value — generics cannot be
changed at runtime in VHDL.

---

## 6. The 20 classic pitfalls

Legend: **[V]** = reproduced/verified on this machine.

1. **No timeout → infinite hang.** `@cocotb.test(timeout_time=…, timeout_unit=…)` is mandatory for
   unattended runs. Without it a missing `ready` or a deadlocked handshake blocks the agent forever.
   **[V]** with `--stop-time` all three tests flipped to FAIL, proving the tests really do wait.
2. **`Clock(dut.clk, 10, units="ns")`** — `units` is deprecated in 2.0; the parameter is **`unit`**.
   **[V]** warning: `The 'units' argument has been renamed to 'unit'.`
3. **`Clock(..., None)`** — passing `None` as the unit was **removed** in 2.0; use `"step"`.
4. **Silent time-unit bugs.** `Timer(5)` means 5 *simulator steps*; with the default
   `COCOTB_HDL_TIMEPRECISION=1ps` that is 5 ps, not 5 ns. Always `Timer(5, unit="ns")`. **[V]**
   GHDL was run with `--time-resolution=ps`.
5. **`'U'` / `'X'` values leaking into integers.** Reading an uninitialised VHDL signal gives
   `LogicArray('UUUUUUUU')` and `int()` raises
   `ValueError: Can't convert LogicArray to int: it contains non-0/1 values`. Check
   `.is_resolvable`, or reset first, or set `COCOTB_RESOLVE_X`. **[V]**
6. **`.value.integer` / `.value.binstr` are deprecated in 2.0.** Use `.to_unsigned()` /
   `.to_signed()` / `str(value)`. They still work but emit `DeprecationWarning` on every access
   (log spam that hides real problems). **[V]**
7. **VHDL-2008 needs `--std=08` at run time too.** `build_args` in the runner and `COMPILE_ARGS` in
   the Makefile do **not** cover `ghdl -r`; use `EXTRA_ARGS` (Makefile) or `test_args` (runner).
   **[V]** without it: `ghdl:error: cannot find entity or configuration counter`.
8. **VHDL compilation order is mandatory (GHDL/Questa).** Packages and entities that are
   instantiated must appear **before** their users in `VHDL_SOURCES`; GHDL `-i` stops at the first
   error and does not reorder. For multiple libraries use `VHDL_SOURCES_<lib>` +
   `VHDL_LIB_ORDER`, whose consistency is validated by the makefile `[V-src]`.
9. **The `work` library.** GHDL/Questa default to `work`; the cocotb **runner** defaults
   `hdl_library`/`hdl_toplevel_library` to **`top`** `[V-src]` — mixing the two gives errors like
   "cannot find entity". Keep both on `work`, or pass them explicitly.
10. **Library location vs working directory.** `ghdl -r` must be run where the library was built
    (`--workdir`/`-P`), while Python must find the test module. Mixed `test_dir`/`PYTHONPATH` setups
    break; use the two verified recipes in §3.9. **[V]**
11. **Delta cycles / `ReadOnly`.** Writes during the read-only phase raise
    `RuntimeError: Attempting settings a value during the ReadOnly phase.` **[V]** Do all drives
    before the edge (or before `await ReadOnly()`), and remember signal updates appear only after a
    delta step.
12. **`make` "Nothing to be done" false greens.** Makefile mode skips re-simulation when
    `results.xml` is newer than the sources; an edited Python test may be ignored.
    `make clean` / `rm -rf sim_build results.xml`, or use `always=True` with the runner.
13. **Stale `sim_build`.** Switching simulator without cleaning leaves a foreign library/`modelsim.ini`
    and produces confusing errors (also documented for the ModelSim `GUI=1` case `[V-doc]`).
14. **Name resolution / escaped identifiers.** VHDL `gen[i].sig` and Verilog generate-loop names are
    painful; in cocotb prefer `dut.gen[i].sig`, and in XSim TCL use
    `add_wave {{/path/\R[0].blk}}` with doubled braces (documented workaround). `[V-doc]`
15. **VHDL generics are **`LogicArray`**, not `int`.** `dut.WIDTH.value` returned
    `LogicArray('00000000000000000000000000001000')` — so `dut.WIDTH.value == 8` is `False` and
    comparison silently "fails". Use `int(dut.WIDTH.value)`. GHDL also prints
    `Unable to map vpiConst type 0 onto GPI type, guessing this is a logic vector`. **[V]**
16. **Generic/parameter access is read-only at run time.** `dut.WIDTH.value = 12` raises
    `TypeError: Attempted setting an immutable object` (`is_const` is `True` for generics/params/
    constants) `[V-src]`. Recompile for a new value.
17. **File paths in tests.** `os.getcwd()` is the simulator's build dir, not your project. Anchor on
    `Path(__file__).resolve().parent`; write artefacts to explicit absolute paths. **[V]** (the
    simulator ran with CWD `sim_build/` in the Makefile flow).
18. **cocotb 1.x → 2.0 breaking changes** (all `[V-src]`):
    * `cocotb/share/makefiles/…` → **`cocotb_tools/makefiles/…`**
    * `cocotb.runner` → **`cocotb_tools.runner`**
    * `Clock(..., units=)` → `unit=`; `Clock(..., cycles=N)` **removed** (use `.stop()`)
    * `task.kill()` → `task.cancel()`; `Task.retval`/`__bool__`/`_finished` **removed**
    * `handle.setimmediatevalue()` → `handle.set(Immediate(v))`
    * `logic_array.integer`/`binstr`/`signed_integer`/`buff` deprecated
    * `expect_error=True/False` must now be an exception type (bool form removed)
    * `Join` moved to `cocotb.task`; `TestFactory` is superseded by `cocotb.parametrize`
      (TestFactory survives but is legacy)
    * `verilog_sources`/`vhdl_sources` deprecated in favour of `sources`
    * runner `defines` are no longer implicitly converted to HDL literals
    * 2.0 runs **all** tests matching a name across all `COCOTB_TEST_MODULES` (1.x ran only the first)
19. **Assuming cocotb can drive XSim.** It cannot: no `Makefile.xsim`, no runner, absent from the
    Simulator Support page. Calling `get_runner("xsim")` raises `ValueError`. **[V]**
20. **Licence/edition traps with vendor simulators.** Questa Intel Starter compiled cleanly then
    failed with `Failure to obtain a Verilog simulation license`; ModelSim PE has no VHDL FLI
    (`vsim-FLI-3155`). An agent must classify these as *infrastructure* failures, not DUT failures,
    and fall back to an open-source simulator. **[V]** + `[V-doc]`

**Bonus — reproducible-failure drill for an agent:** when a test fails, re-run with
`COCOTB_RANDOM_SEED=<seed from the log>` (the seed is printed: `Seeding Python random module with
<class> seed <n>`) plus `WAVES=1` / `SIM_ARGS=--vcd=…`, and grep `results.xml` — never re-run without
the seed and hope. **[V]** (`COCOTB_RANDOM_SEED=42` → `Seeding Python random module with supplied seed 42`.)

---

## 7. Agent decision procedure (summary)

```
1. Detect simulators:  shutil.which() for ghdl, iverilog, vvp, verilator, xsim/xelab, vsim
2. Pick by language & presence:
      VHDL      → ghdl → nvc → xsim → questa
      Verilog   → icarus → verilator → xsim → questa
      mixed     → xsim / questa (or fail with an explicit explanation)
3. Generate a Makefile from §4 (or a runner script from §3.9) with COCOTB_TOPLEVEL and
   COCOTB_TEST_MODULES set explicitly, plus EXTRA_ARGS for --std=08 / defines.
4. Run: make SIM=<sim> [-e KEY=VAL …]      → parse results.xml, not stdout
5. If infra error (no binary / no licence / unsupported sim): downgrade simulators and retry,
   never report a DUT bug.
6. If a test fails: replay with COCOTB_RANDOM_SEED=<seed> and WAVES=1, then triage.
```

---

## 8. Sources

**cocotb (2.0.1)**
- Simulator support matrix — <https://docs.cocotb.org/en/stable/simulator_support.html>
- Quickstart — <https://docs.cocotb.org/en/stable/quickstart.html>
- Makefile build system & variables — <https://docs.cocotb.org/en/stable/building.html>
- Python runner — <https://docs.cocotb.org/en/stable/runner.html>
- Library reference — <https://docs.cocotb.org/en/stable/library_reference.html>
- Writing testbenches — <https://docs.cocotb.org/en/stable/writing_testbenches.html>
- Installed package read locally (`[V-src]`):
  `…/site-packages/cocotb_tools/{config.py,runner.py,makefiles/**}`,
  `…/cocotb/{clock.py,triggers.py,handle.py,queue.py,task.py,_decorators.py,types/_logic_array.py}`
- CLI introspection `[V-local]`: `cocotb-config --version | --makefiles | --lib-dir | --help-vars`

**GHDL**
- Installing — <http://ghdl.github.io/ghdl/getting.html>
- Invoking GHDL — <https://ghdl.github.io/ghdl/using/InvokingGHDL.html>
- Simulation (runtime) options & waveform export — <https://ghdl.github.io/ghdl/using/Simulation.html>
- Fedora packages — <https://packages.fedoraproject.org/pkgs/ghdl/ghdl/>
- Ubuntu packages — <https://packages.ubuntu.com/noble/ghdl>, <https://packages.ubuntu.com/ghdl-mcode>

**Icarus / Verilator / viewers**
- iverilog Fedora — <https://packages.fedoraproject.org/pkgs/iverilog/iverilog/>
- iverilog Ubuntu — <https://packages.ubuntu.com/noble/iverilog>
- Icarus upstream — <https://github.com/steveicarus/iverilog>
- Verilator install — <https://verilator.org/guide/latest/install.html>
- verilator Fedora — <https://packages.fedoraproject.org/pkgs/verilator/verilator/>
- GTKWave — <https://gtkwave.sourceforge.net/>

**AMD Vivado Simulator (XSim) — UG900**
- UG900 home — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation>
- Quick reference — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Vivado-Simulator-Quick-Reference-Guide>
- Parsing (`xvhdl`/`xvlog`) — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Parsing-Design-Files-xvhdl-and-xvlog>
- Command options — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/xelab-xvhdl-and-xvlog-xsim-Command-Options>
- `xelab` — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/xelab>
- Elaboration options — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Vivado-Simulator-Elaboration-Options>
- VCD feature (`open_vcd`/`log_vcd`) — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Using-the-Value-Change-Dump-Feature>
- `export_simulation` — <https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/export_simulation>
- VHDL variables not traceable — <https://adaptivesupport.amd.com/s/article/63628>
- Batch-mode Q&A (+ `.prj` usage) — <https://adaptivesupport.amd.com/s/question/0D52E00006hpaMrSAI/using-vivado-simulator-xsim-in-batch-mode>
- `add_wave` generate-loop workaround — <https://adaptivesupport.amd.com/s/question/0D52E00006hpZERSA2/vivado-addwave-nothing-was-found>
- Scripted XSim walk-through (mirror used where TIP was unfetchable) —
  <https://itsembedded.com/dhd/vivado_sim_1/>, <https://itsembedded.com/dhd/vivado_sim_3/>

**cocotb + XSim bridges (community, use with care)**
- <https://github.com/themperek/cocotb-vivado>
- <https://github.com/kiran-vuksanaj/vicoco>
- <https://github.com/olofk/edalize> (open issue: xsim + cocotb integration)

### Verification caveats

- `docs.amd.com` renders through a JavaScript app; direct HTTP extraction returned the app shell, so
  UG900 statements above are sourced from (a) the AMD TIP search index snippets that quote the
  pages verbatim, (b) the vendor PDF's mirrored copies, and (c) the community walk-through that
  transcribes real `xelab`/`xsim` transcripts. Option names marked `[unverified]` **must** be
  re-checked with `xelab --help` / `xsim --help` on the target installation before being hard-coded.
- XSim itself could not be executed here (Vivado is not installed), so all XSim command lines are
  documentation-based, not machine-verified.
- Questa was exercised only up to the licence checkout; its full flow is therefore unverified on
  this machine.
