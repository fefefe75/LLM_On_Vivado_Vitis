# 02 — Vitis (embedded software side of the Vivado → Vitis flow)

> Reference note for the *Vivado (PL) → Vitis (PS)* toolchain.
> **Scope**: bare-metal / standalone software flow only (Hello World, BSP, FSBL, boot image,
> deployment). Linux/PetaLinux appears only where the boot image needs it.
>
> **Written from official AMD sources only** (docs.amd.com / AMD Adaptive Support / Xilinx
> GitHub). Vitis was **not installed** on the machine where this note was written, so nothing
> here was executed — every command is reproduced from the documentation, with the source URL
> inline. Items I could **not** verify are flagged `⚠️ UNVERIFIED` and listed in
> [§ 12](#12-what-i-could-not-verify).

---

## 1. The single most important fact: there are **two incompatible Vitis generations**

The commands, the script language, and the on-disk project layout have **nothing in common**
between the two. An LLM (or a human) that mixes them produces scripts that cannot run.

| Release range | Launcher | IDE | Scripting interface | Script language | Status |
|---|---|---|---|---|---|
| **2019.2 → 2023.1** | `vitis` (GUI), `xsct`, `xsdb` | Vitis **Classic** IDE | **XSCT / XSDB** | **Tcl** | Legacy — still the documented flow in UG1400 ≤ 2023.1 |
| **2023.2 → 2024.2** | `vitis` = **Unified IDE**, `vitis --classic` = Classic | **Vitis Unified IDE** (new default) + Classic available | **Vitis Python API / CLI** *and* XSCT | **Python** (`vitis -s x.py`) — classic Tcl still there via `xsct` | both generations coexist |
| **2025.1 → 2025.2** | `vitis` only | Unified IDE only | Vitis Python API; XSDB for debug | Python | **Vitis Classic IDE removed**; XSCT deprecated |
| **2026.1** | `vitis` only | Unified IDE only | Vitis Python API + XSDB | Python | **XSCT end of life** |

Evidence for the timeline:

- The Vitis Unified IDE is the default GUI from **2023.2**; to launch classic you must run
  `vitis --classic`, and doing so requires the *full* Vitis install (not the Embedded-only
  installer) — [UG1400 2023.2, "Changed Behavior Summary"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Software-Platform-Release-Notes).
- **Starting with 2025.1 you can no longer use the Vitis Classic IDE**, and the Classic→Unified
  migration utility only exists in 2023.2 / 2024.1 / 2024.2 —
  ["Migrating from the Classic Vitis IDE to Vitis Unified IDE" (UG1400, current)](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Migrating-from-the-Classic-Vitis-IDE-to-Vitis-Unified-IDE).
- **XSCT reaches end of life in 2026.1**; the official replacement is *XSDB for hardware
  debugging and JTAG operations* + *the Vitis Python API for project management and scripting* —
  [UG1742 2026.1, "Deprecated Features"](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Deprecated-Features).
- In 2025.2 the tool already prints `WARNING: XSCT has been deprecated ... it's recommended to
  start new projects with SDT workflow` (observed in a PetaLinux build log,
  [AMD partner write-up](https://www.centennialsoftwaresolutions.com/help/fix-missing-libtinfo-so-5) —
  the deprecation itself is also documented in
  [UG1400 2025.2, "XSCT to Python API Migration"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/XSCT-to-Python-API-Migration)).

**Practical rule for this repo:** target **Vitis 2022.2 / 2023.1** with the XSCT flow if you have
an older Vivado (which is the common case for Zynq-7000 teaching boards such as the ZedBoard /
ZC702), and **Vitis 2023.2+** with the Python flow for anything newer. Never mix the two command
sets in a single script.

---

## 2. Part A — Classic Vitis + XSCT (Vivado/Vitis 2019.2 → 2023.1)

Primary source: **UG1400, *Vitis Unified Software Platform Documentation: Embedded Software
Development***, versions 2021.2 → 2023.1 (from 2023.2 the same document number describes the
Unified IDE; the classic chapters were frozen at 2023.1).
`https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded`

### 2.1 Vocabulary and workspace layout (classic)

| Term | Meaning in the classic flow |
|---|---|
| **Workspace** | Directory that holds project data + metadata; set with `setws`. |
| **XSA** | Vivado *Xilinx Support Archive*: processor config, peripheral connections, address map, PS init code. The **only** hardware hand-off file. |
| **Platform project** | XSA (hardware) + software components (domains/BSPs, boot components such as FSBL). Editable in the workspace; read-only in the repository. |
| **Domain** | A BSP or OS + driver collection, tied to one processor (or a cluster of isomorphic cores, e.g. `ps7_cortexa9_0`, `psu_cortexa53_0`/`psu_cortexa53`). |
| **System project** | Group of applications that run *simultaneously*; two standalone apps on the same processor cannot coexist, two Linux apps can. Auto-created when you create the first app, named `<appname>_system`. |
| **Application (software project)** | Sources + headers → compiles to an **ELF**. Each app needs a domain. |

Source: [UG1400 2023.1, "Workspace Structure in the Vitis Software Platform"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Workspace-Structure-in-the-Vitis-Software-Platform).

On-disk consequences (verified from the same document):

- The application ELF is at `<app_name>/Debug/<app_name>.elf` — the doc's own JTAG examples use
  `dow dhrystone/Debug/dhrystone.elf` and `dow /tmp/workspace/hello/Debug/hello.elf`
  ([UG1400 2023.1, XSDB usage examples](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Running-an-Application-in-Non-Interactive-Mode)).
- The boot image created from the IDE lands in
  `<Application_project_name>/_ide/bootimage/BOOT.bin`
  ([UG1400 2023.1, "Creating a Boot Image"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Boot-Image)).

### 2.2 Step 0 — export the `.xsa` from Vivado

GUI (documented in UG1400): create project → create block design → generate bitstream →
**File > Export > Export Hardware**, select the *Fixed Platform* option
([UG1400 2023.1, "Creating a Hardware Design (XSA File)"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Hardware-Design-XSA-File)).

Scriptable equivalent (Vivado Tcl):

```tcl
# In the Vivado project, after implementation (and write_bitstream if you want the PL config in the XSA)
set_property platform.default_output_type "sd_card"   [current_project]
set_property platform.design_intent.embedded "true"   [current_project]
set_property platform.design_intent.server_managed "false" [current_project]
set_property platform.design_intent.external_host "false"  [current_project]
set_property platform.design_intent.datacenter "false"     [current_project]

# Embedded software flow only  -> "fixed" platform, with the bitstream inside
write_hw_platform -fixed -include_bit -force ./system.xsa
```

- `write_hw_platform` syntax and options (`-fixed`, `-force`, `-include_bit`, `-include_bin`,
  `-minimal`, `-hw`, `-hw_emu`, `-static`, `-rp`, `-rm`):
  [UG835, `write_hw_platform`](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_hw_platform).
  Note: *"A call to `write_hw_platform` without the `-fixed` option creates an extensible
  platform"* ([UG909, "Using Export Hardware"](https://docs.amd.com/r/en-US/ug909-vivado-partial-reconfiguration/Using-Export-Hardware)) —
  for bare-metal embedded work you want `-fixed`.
- The exact `set_property platform.*` + `write_hw_platform` sequence is reproduced from
  [XD101, "Export Hardware XSA" (2024.2)](https://docs.amd.com/r/2024.2-English/Vitis-Tutorials-Vitis-Platform-Creation/Export-Hardware-XSA).
- `-include_bit` is only needed if a downstream tool needs the bitstream (Linux `fpga-manager`,
  or a JTAG flow that configures the PL from the XSA). `-include_bit` requires a *real* bitstream:
  `INFO: [Vivado 12-12733] No bit file available for '-include_bit'` otherwise
  ([AMD Adaptive Support thread](https://adaptivesupport.amd.com/s/question/0D54U00005Sf8kiSAB/how-to-specify-the-bitstream-filename-in-the-tcl-script-nonproject-workflow-such-that-writehwplatform-can-use-includebit)).

### 2.3 End-to-end XSCT script (Zynq-7000 example, `ps7_cortexa9_0`)

Run it with `xsct this_script.tcl` (XSCT is the *Tcl* command-line interface to the Vitis IDE;
its scripting language is Tcl — [UG1400 2023.1, "Software Command-Line Tool"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Software-Command-Line-Tool)).

```tcl
# ---------------------------------------------------------------
# 00 - workspace
# ---------------------------------------------------------------
setws /home/me/zynq_ws
# setws -switch /home/me/other_ws   ;# close current WS and switch

# ---------------------------------------------------------------
# 01 - platform project from the Vivado XSA, with a default standalone domain
#      -hw   : XSA exported by Vivado (also accepts a pre-defined name: zc702, zc706, zcu102, zed)
#      -proc : processor to create the default domain on
#      -os   : OS of that default domain (standalone | linux | freertos)
# ---------------------------------------------------------------
platform create -name zc702_platform -hw /home/me/hw/system.xsa \
                -proc ps7_cortexa9_0 -os standalone
platform active zc702_platform

# ---------------------------------------------------------------
# 02 - (optional) additional / explicitly-named domains
# ---------------------------------------------------------------
domain create -name a9_standalone -os standalone -proc ps7_cortexa9_0 \
              -support-app {Hello World}

# ---------------------------------------------------------------
# 03 - build the platform: builds the BSPs and the boot components (FSBL ...)
# ---------------------------------------------------------------
platform generate
# platform generate -domains a9_standalone     ;# build only some domains

# ---------------------------------------------------------------
# 04 - application
#      -platform/-domain may be omitted if an active platform+domain exists
#      -hw/-proc form creates the app straight from an XSA instead of a platform
#      templates: {Hello World}, {Empty Application(C)}, {Zynq FSBL}, {Memory Tests}, ...
#      list them with:  repo -apps
# ---------------------------------------------------------------
app create -name hello -platform zc702_platform -domain a9_standalone \
           -template "Hello World"
app build -name hello

# ---------------------------------------------------------------
# 05 - boot image: build the SYSTEM project.
#      This builds the platform project (=> fsbl.elf), writes a .bif and runs bootgen
#      => BOOT.bin
# ---------------------------------------------------------------
sysproj build -name hello_system

# ---------------------------------------------------------------
# 06 - (optional) re-run bootgen by hand with edited BIF
# ---------------------------------------------------------------
# exec bootgen -arch zynq -image output.bif -w -o /home/me/BOOT.bin

# ---------------------------------------------------------------
# 07 - program QSPI flash
# ---------------------------------------------------------------
exec program_flash -f /home/me/BOOT.bin -flash_type qspi_single \
     -blank_check -verify -cable type xilinx_tcf url tcp:localhost:3121
```

Steps 00–07 above are the documented flow, including the exact `program_flash` invocation —
[UG1400 2023.1, "Creating a Bootable Image and Program the Flash"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Bootable-Image-and-Program-the-Flash).
The document states explicitly: *"The Vitis environment creates a platform project and system
project when an application project is created. The platform project includes boot components
such as FSBL"* (same page).

**FLASH type values** (Vitis *Program Flash* tool): for Zynq devices `qspi_single`,
`qspi_dual_parallel`, `qspi_dual_stacked`, `nand_8`, `nand_16`, `nor`, `emmc`; supported image
formats for QSPI are **BIN or MCS**, and BIN only for NAND/NOR
([UG1400 2025.2, "Programming Flash"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Programming-Flash)).

### 2.4 XSCT command reference (the ones you will actually use)

Every row below is quoted from UG1400 2023.1, *Chapter 23: XSCT Commands*.

| Command | Syntax | What it does / returns | Source |
|---|---|---|---|
| `setws` | `setws [OPTIONS] [path]` | Set/create the Vitis workspace. `-switch <path>` closes the current WS first. Returns nothing, or an error string if `path` is a file. | [setws](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/setws) |
| `platform create` | `platform create -name <n> -hw <xsa> [-proc <p>] [-os <os>] [-arch 32-bit\|64-bit] [-out <dir>] [-prebuilt] [-no-boot-bsp] [-xpfm <path>]` | Creates a platform project from an XSA. `-hw` alone = platform only; `-hw` + `-proc` + `-os` = also creates the **default domain**. `-out` disables use from the Vitis IDE. | [platform create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-create) |
| `platform active` | `platform active [platform-name]` | Set/get the active platform (empty string if none). | [platform active](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-active) |
| `platform generate` | `platform generate [-domains <list>]` | Builds the active platform (BSPs + boot components) and adds it to the repository. | [platform generate](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-generate) |
| `domain create` | `domain create -name <n> -os <os> -proc <p> [-arch] [-support-app <app>] [-sd-dir] [-sysroot]` | Creates a domain **in the active platform**. `-proc` accepts a Tcl list for SMP Linux. | [domain create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/domain-create) |
| `app create` | `app create -name <n> -platform <p> -domain <d> -template <t>` **or** `app create -name <n> -hw <xsa> -proc <p> -os <os> -lang c\|c++ -template <t>` **or** `app create ... -sysproj <sp>` | Creates an application. If `-platform`/`-domain` are omitted the active ones are used; if `-sysproj` is omitted a system project `<appname>_system` is created. | [app create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/app-create) |
| `app build` | `app build [-name <n>] [-all]` | Builds an application (or all). Prints the build log to the console. | [app build](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/app-build) |
| `sysproj build` | `sysproj build -name <system-project>` | Builds the system project → platform/FSBL + BIF + bootgen run. | [Creating a Bootable Image…](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Bootable-Image-and-Program-the-Flash) |
| `repo` | `repo -apps` / `repo -platforms` / `repo -libraries` | Lists the templates/platforms/libraries available. | [app create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/app-create) |
| `connect` | `connect [-host <h>] [-port <p>] [-url tcp:<h>:<p>] [-list] [-set <ch>] [-new] [-xvc-url <u>] [-symbols]` | Connect to **hw_server** / TCF agent (default port **3121**). | [connect](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/connect) |
| `targets` | `targets [<id>]`, `targets -set -filter {name =~ "ARM*#1"}`, `-nocase`, `-regexp`, `-index <n>`, `-timeout <s>`, `-target-properties` | List targets / select the active target. | [targets](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/targets) |
| `dow` | `dow [options] <file.elf>` — or `dow -data <file> <addr>` | Download an ELF to the active target (or a raw binary to an address). Options include `-clear`, `-force`, `-keepsym`, `-vaddr`, `-relocate-section-map <addr>`. | [dow](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/dow) |
| `con` | `con [-addr <a>] [-block] [-timeout <s>]` | Resume the active target. `-block` waits until the core stops or times out. | [con](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/con) |
| `rst` | `rst [-processor] [-cores] [-system] [-srst] [-por] [-ps] [-dap] [-stop] [-start] [-endianness] [-isa] [-clear-registers]` | Reset. `-system` is the **default**. `-cores` (core+peripherals group) only on Zynq / ZynqMP / Versal; `-dap`, `-type`, `-ps` are device-specific. | [rst](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/rst) |
| `fpga` | `fpga <bitstream>` or `fpga -file <bs> [-partial] [-state] …` | Configure the PL from a `.bit`. | [fpga](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/fpga) |
| `loadhw` | `loadhw [-file] <xsa>` | Load a hardware design (XSA / `.xml`) so the debugger knows the memory map and PS init. | [loadhw](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/loadhw) |
| `mrd` / `mwr` | `mrd <addr>` / `mwr <addr> <value>` | Read/write memory (register poking from the console). | [UG1400 2023.1, "Memory and Register accesses from XSCT"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/XSCT-Interface-Examples) |
| `rrd` / `rwr` | `rrd <reg>` / `rwr <reg> <value>` | Read/write core registers. | [UG1400 2023.1, XSCT Commands](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/XSCT-Commands) |

### 2.5 Deploy over JTAG with XSCT/XSDB (bare-metal, no flash)

Documented non-interactive XSDB script (`xsdb test.tcl`, or paste into `xsct`); the comments
and the command order are the doc's own:

```tcl
connect -url TCP:xhdbfarmc7:3121

# Select the target whose name starts with Arm and ends with #0.
# On Zynq, this selects "Arm Cortex-A9 MPCore #0"
targets -set -filter {name =~ "Arm* #0"}

rst
fpga     ZC702_HwPlatform/design_1_wrapper.bit
loadhw   ZC702_HwPlatform/system.xsa
source   ZC702_HwPlatform/ps7_init.tcl
ps7_init
ps7_post_config
dow      dhrystone/Debug/dhrystone.elf

# Set a breakpoint at exit
bpadd -addr &exit

# Resume execution and block until the core stops (breakpoint) or 5 s timeout
con -block -timeout 5
```

Source: [UG1400 2023.1, "Running an Application in Non-Interactive Mode"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Running-an-Application-in-Non-Interactive-Mode).

Notes:
- On modern Vivado/Vitis, `loadhw` / the platform's `ps7_init.tcl` (Zynq-7000) or
  `psu_init.tcl` (ZynqMP) is normally invoked for you; the explicit `source ps7_init.tcl` form
  above is the documented one and is still valid.
- `ps7_init()` (Zynq-7000) / `psu_init()` (ZynqMP) comes from the XSA-generated init Tcl; for
  Zynq where the FSBL does PS init, you only need it when booting *without* an FSBL (JTAG boot).
- JTAG targets appear as `PS TAP`, `PMU`, `PL`, `PSU`, `Cortex-A53 #0..#3`, etc. — the
  `targets` / `ta` output shown in the KRS how-to
  ([xilinx.github.io/KRS](https://xilinx.github.io/KRS/sphinx/build/html/docs/howto.html)) shows
  a real ZynqMP JTAG chain.

---

## 3. Part B — Vitis Unified IDE + `vitis` CLI / Python API (2023.2 → 2026.1)

### 3.1 Launch options — exact syntax and script language

From [UG1400 2023.2, "Vitis Unified IDE Launch Options"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Unified-IDE-Launch-Options)
(the `-h` output below is quoted verbatim from that page):

```
Syntax: vitis [--classic | -a | -w | -i | -s | -h | -v]

Options:
   Launches New Vitis IDE (default option).
  -classic/--classic
         Launch classic Vitis IDE.
  -a/--analyze [<summary file | folder | waveform file: *.[wdb|wcfg]>]
         Open the summary file in the Analysis view.
  -w/--workspace <workspace_location>
         Launches Vitis IDE with the given workspace location.
  -i/--interactive
         Launches Vitis python interactive shell.
  -s/--source <python_script>
         Runs the given python script.
  -j/--jupyter
         Launches Vitis Jupyter Web UI.
  -h/--help
         Display help message.
  -v/--version
         Display Vitis version.
```

**Answer to the "which language?" question** — `vitis -s` takes a **Python** script
(`.py`), *not* Tcl:

- `-s/--source <python_script>` / *"Batch mode executes the specified Python script and exits:
  `vitis -s <script>.py`"* ([same page](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Unified-IDE-Launch-Options)).
- *"the scripting language for AMD Vitis CLI is based on the Python"*
  ([UG1400 2024.2, "Python API: A command-line tool…"](https://docs.amd.com/r/2024.2-English/ug1400-vitis-embedded/Python-API-A-command-line-tool-for-creating-and-managing-projects-in-Vitis)).
- The classic interface stays Tcl: *"the scripting language for XSCT is based on the tools
  command language (Tcl)"* ([UG1400 2023.1](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Software-Command-Line-Tool)).
- Batch mode is also demonstrated in the tutorials: `vitis -s unified_workspace.py ../zcu102/design_1_wrapper.xsa`
  ([XD260 2023.2, "Build Vitis Unified Workspace"](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Build-Vitis-Unified-Workspace))
  and `vitis -s path/to/python_script.py`
  ([XD260 2023.2, "Launching Vitis CommandLine Interface (CLI)"](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Launching-Vitis-CommandLine-Interface-CLI)).

⚠️ The name *"Vitis Unified IDE"* is overloaded in older material: **UG1553** (*Vitis Unified
IDE and Common Command-Line Reference Manual*, 2023.1) documents the **Classic-era**
`v++`/system-project flow, not the 2023.2 IDE. Don't cite it for the new Python API.

Other entry points:

| Command | Purpose |
|---|---|
| `vitis -w <ws>` | Open the Unified IDE on an existing workspace |
| `vitis -i` | Interactive Python shell (`Vitis [1]:`) |
| `vitis -s script.py [args]` | Batch Python; args are forwarded (`vitis -s platform_creation.py --platform_name <> --xsa_path <> …`) |
| `vitis -a` | Analysis view (replaces Vitis Analyzer) |
| `vitis -j` | Jupyter web UI |
| `source <Vitis>/settings64.sh` | **Required before running the CLI** — *"Before running the script, you must set up the environment variables for the Vitis Unified IDE"* |

### 3.2 Concepts in the Unified flow

| Concept | Unified IDE meaning | Classic equivalent |
|---|---|---|
| **Workspace** | Directory holding `vitis-comp.json` per component + `_ide/workspace_journal.py` | workspace |
| **XSA → SDT** | The **System Device Tree (SDT)** is generated from the XSA by `SDTGEN` at platform creation; hardware metadata is extracted by the **Lopper** Python framework, which also generates `xparameters.h` and driver init files | XSA parsed ad-hoc by HSI |
| **Platform component** | A *project* that defines a platform (`.xpfm` output); created from a fixed or extensible XSA | platform project |
| **Domain** | BSP/OS + drivers for one processor; Linux domains need BIF + boot component dir + SD dir | domain |
| **Application component** | Sources → ELF; **can only be created from a platform `.xpfm`**, not from a raw `fixed.xsa` | application project |
| **System project** | Groups components that run together | system project |
| **User Managed Mode** | Point Vitis at your own Makefile/CMake project and use the IDE only for build/run/debug | — |
| **Workspace journal** | `_ide/workspace_journal.py` — auto-generated Python that replays everything you did (creation, builds, config edits) | — |

Sources: [UG1400 2025.2 "Workspace Structure…"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Workspace-Structure-in-the-Vitis-Software-Platform);
[UG1400 2023.2 "Changed Behavior Summary"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Software-Platform-Release-Notes) (SDT/Lopper/xparameters.h);
[UG1400 2023.2 "Creating a Platform Component from XSA"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Creating-a-Platform-Component-from-XSA) (*"When you enable Generate Boot Artifacts … the tool automatically generates both the FSBL and PMU firmware components required for your platform"*);
[UG1400 2023.2 "User Managed Flow"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/User-Managed-Flow);
[UG1393 2024.1 "Create and Build Application Component"](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Create-and-Build-Application-Component) (*"An application component can be created only with platform=xpfm. fixed.xsa is not supported."*).

### 3.3 End-to-end Unified-IDE Python script (Zynq-7000, bare-metal)

Verified API names/examples come from:
[UG1400 2025.2 "Platform"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Platform),
[UG1400 2025.2 "Application"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Application),
[UG1400 2025.2 "System Project"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/System-Project),
[UG1393 2024.1 "Create and Build Platform Component"](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Create-and-Build-Platform-Component).

```python
# file: build_ws.py     ->  run with:  vitis -s build_ws.py
import vitis

# 0. client + workspace
client = vitis.create_client()
client.set_workspace(path="./vitis_ws")     # created if missing

# 1. platform component from the Vivado XSA (fixed.xsa)
#    os="standalone" -> bare-metal BSP ; cpu is the processor instance
#    hw_design also accepts a built-in platform name, e.g. "zc702"/"zcu102"
platform = client.create_platform_component(
    name="zc702_platform",
    hw_design="/home/me/hw/system.xsa",
    os="standalone",
    cpu="ps7_cortexa9_0",
    domain_name="standalone_a9",
    architecture="32-bit",
    compiler="gcc",
)

# 2. (optional) extra domains
# platform.add_domain(cpu="psu_cortexr5_0", os="freertos", name="r5_freertos",
#                     display_name="r5_freertos", generate_dtb=True, architecture="32-bit")

# 3. build the platform (BSP + boot artifacts such as the FSBL)
platform = client.get_component(name="zc702_platform")
platform.build()

# 4. the platform's delivered artifact is an .xpfm
xpfm = client.find_platform_in_repos("zc702_platform")
#    -> <ws>/zc702_platform/export/zc702_platform/zc702_platform.xpfm

# 5. application component
app = client.create_app_component(
    name="hello",
    platform=xpfm,
    domain="standalone_a9",
    template="hello_world",      # "empty" for a blank app
)
app.import_files(from_loc="./src", files=["main.c"], dest_dir_in_cmp="src")
app.build()

# 6. system project (groups components that run together)
sys_proj = client.create_sys_project(name="system_project", platform=xpfm)
sys_proj.add_component(name="hello")
sys_proj.build()

vitis.dispose()
```

Exact snippets above are documented almost verbatim:

- `create_platform_component(name = "platform", hw_design = "zcu102", cpu = "psu_cortexa53_0", os = "standalone", domain_name = "standalone_psu_cortexa53_0", generate_dtb = False, architecture = "64-bit", compiler = "gcc")` then `platform.build()` ([UG1400 2025.2, Platform](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Platform)).
- `create_app_component(name="hello_world", platform="/vitis_2025.2_ws/platform/export/platform/platform.xpfm", domain="standalone_psu_cortexa53_0", template="hello_world")` then `comp.build()` ([UG1400 2025.2, Application](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Application)).
- `client.find_platform_in_repos(plat_name)`, `create_sys_project(name=…, platform=…, template="empty_accelerated_application")`, `sys_proj.add_component(name=…)`, `sys_proj_comp.build()`, `vitis.dispose()` ([UG1400 2025.2, System Project](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/System-Project)).

**Boot image in the Unified flow — GUI only (documented).** UG1400 2023.2 → 2025.2 describe
boot image creation exclusively through the wizard: *"Create Boot Image from Flow Navigator"* or
*"Vitis > Create Boot Image"*, where you set the **Output Bif File Path** and **Output Image
path** ([UG1400 2025.2, "Creating a Boot Image"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Creating-a-Boot-Image)).
The workspace journal is documented to log only *component creation, component builds, and
configuration-file modifications* ([UG1400 2025.2, "Workspace Journal Coverage"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Workspace-Journal-Coverage)),
so a Python API for boot-image generation is **not documented** in the releases I read
(see [`⚠️ UNVERIFIED`](#12-what-i-could-not-verify)). In practice: generate `BOOT.bin` with
`bootgen` directly (§ 5) if you need a scriptable path.

### 3.4 Running `vitis -s` with your own Python — the version trap

AMD ships its own interpreter and expects you to use it; a system `python3` will typically fail
to `import vitis`:

```bash
export XILINX_VITIS=<install>/2025.2/Vitis
source <install>/2025.2/Vitis/cli/examples/customer_python_utils/setup_vitis_env.sh
# then either the bundled interpreter...
$VITIS_INSTALL_PATH/2025.2/Vitis/tps/lnx64/python-3.13.0/bin/python
# ...or, after the setup script, your own ./python
$VITIS_INSTALL_PATH/2025.2/Vitis/tps/lnx64/python-3.13.0/bin/python -s sample_testcase.py
```

Source: [UG1400 2025.2, "Enabling the Vitis API to be used in a Python ENV"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Enabling-the-Vitis-API-to-be-used-in-a-Python-ENV)
(the bundled interpreter is `tps/lnx64/python-3.13.0` in 2025.2; older releases ship 3.8/3.10 —
⚠️ I did not verify the per-release interpreter versions).

### 3.5 `v++` — what it is, and how it differs from the embedded flow

`v++` is the **Vitis compiler** for *application acceleration* — HLS/AI-Engine kernels and the
link/package steps — **not** the embedded C/C++ application compiler (which is `arm-none-eabi-gcc`
/ `aarch64-none-elf-gcc` driven by the IDE/CMake).

```
v++ MODES ([UG1393 2024.1, "v++ Command"]):
  --compile (-c) : compile C/C++/AIE kernels -> .xo (PL kernels) or libadf.a (AI Engine)
  --link    (-l) : link .xo + libadf.a + platform (.xpfm) -> .xclbin / .xsa / .vma
  --package (-p): package libadf.a into the xclbin, and generate an SD-card or QSPI/OSPI boot file
```

Sources: [UG1393 2024.1, "v++ Command"](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/v-Command);
[UG1393 2024.1, "v++ General Options"](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/v-General-Options) (`--compile/--link/--package`, `--config`, `--platform`, `--freqhz`, `--export_archive`, …);
[UG1393 2024.1, "Linking with the v++ Command"](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Linking-with-the-v-Command).

Typical acceleration one-liners (from UG1393/UG1701):

```bash
v++ -c -k mm2s --platform xilinx_zcu102_base_202210_1 -t hw  -o mm2s.xo mm2s.cpp
v++ -l    --platform xilinx_zcu102_base_202210_1 -t hw  -o binary_container_1.xclbin mm2s.xo
v++ --link --export_archive --platform <>.xsa --config system.cfg <>.xo ./lib<>.a -o <vma>.vma
```

**Vitis Embedded vs Vitis HLS vs Vitis AI** (three different products under one installer):

| Product | What it builds | Input | Output | Fixed vs extensible HW |
|---|---|---|---|---|
| **Vitis Embedded** | C/C++ apps on Arm cores / MicroBlaze (bare-metal, FreeRTOS, Linux) | `.xsa` (fixed) | `.elf`, BSP, `BOOT.bin` | fixed XSA only, HW not modified |
| **Vitis HLS** | C/C++ → RTL **PL kernels** | C/C++ + directives | `.xo`, RTL, IP | needs Vivado for RTL impl. |
| **Vitis AI / AI Engine** | DNN inference on DPU (Vitis AI) and AI Engine graphs (AIE compiler) | trained models / AIE graph code | `.xclbin`, DPU overlays | extensible / AIE-capable devices |

- Platform classes (`Embedded`, `Embedded Acceleration`, `Data Center Acceleration`) and the fact
  that *"the Vitis tool cannot modify the hardware design"* for embedded platforms:
  [UG1400 2025.2, "Workspace Structure…"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Workspace-Structure-in-the-Vitis-Software-Platform).
- *"The embedded installer does not support accelerated flows"* (repeated note in the Python API
  chapter): [UG1400 2025.2, "System Project"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/System-Project).
- Product-scope description (Vitis Embedded for C/C++ on Arm; AI Engine compilers; Vitis HLS;
  Vitis Model Composer): [amd.com — AMD Vitis Unified Software Platform](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vitis.html).

---

## 4. Artifacts: what is produced where

| Artifact | Produced by | Default location |
|---|---|---|
| `.xsa` | Vivado `write_hw_platform -fixed -include_bit -force` | wherever you write it (Vivado project export dir) |
| `.bit` / `.bin` (bitstream) | Vivado `write_bitstream`; optionally embedded in the XSA | `<project>.runs/impl_1/*.bit`; inside XSA with `-include_bit` |
| `.pdi` | **Versal**: Vivado produces a base PDI; **`bootgen`** produces/consumes PDIs for Versal boot images (`{ type = bootimage, file = base.pdi }`) | next to the Vivado project / bootgen `-o` path |
| `.hwh` | Vivado, inside the XSA (hardware handoff) | inside XSA |
| `.elf` (app) | `app build` (classic) / `app.build()` (python) | classic: `<app>/Debug/<app>.elf`; Unified: `<app_component>/build/<config>/…` |
| `fsbl.elf`, `pmufw.elf` | platform build with boot components enabled | classic: inside the platform project; Unified: platform component's boot-artifact output |
| `.bif` | IDE/system project, or hand-written | classic: `<app>_system/…` (system project), content printed in the boot-image wizard |
| `BOOT.bin` (= `boot.bin`, `BOOT.BIN`) | `bootgen` (run by `sysproj build`, or manually) | classic IDE: `<Application_project_name>/_ide/bootimage/BOOT.bin`; Unified: the **Output Image path** you choose in the wizard |
| `.mcs` | `bootgen -o file.mcs` | same as `-o` (MCS is supported for Zynq/ZynqMP/Versal monolithic devices) |
| `.xpfm` | platform component build (Unified) | `<ws>/<platform>/export/<platform>/<platform>.xpfm` |

Sources: [UG1400 2023.1, "Creating a Boot Image"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Boot-Image);
[UG1393 2024.1, "Create and Build Platform Component"](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Create-and-Build-Platform-Component);
[UG1283, "o"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/o);
[UG909 "Using Export Hardware"](https://docs.amd.com/r/en-US/ug909-vivado-partial-reconfiguration/Using-Export-Hardware) (PDI/HWH contents of the XSA per Vivado option);
[UG1400 2025.2, "Output Files"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Output-Files) (compiler outputs).

---

## 5. `bootgen` — what it does, and a complete BIF

**What bootgen does** (one sentence, from the source): it *"stitches binary files together and
generates device boot images"*, driven by a **BIF** (Boot Image Format, `*.bif`) text file, and
it is *"the same tool as is called from the XSCT, so any scripts developed here or in the XSCT
will work in the other tool"* —
[UG1400 2023.1, "Using Bootgen on the Command Line"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Using-Bootgen-on-the-Command-Line),
[UG1400 2023.1, "Creating a Boot Image"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Boot-Image).
It builds the boot header + image header table + partition header table, converts each input
(`.elf` → loadable sections, `.bit` → header-stripped bitstream, `.bin` → raw) into partitions,
and can encrypt/authenticate each partition
([UG1283 2022.2, "Boot Image Format (BIF)"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Boot-Image-Format-BIF),
[UG821, "Boot Image Creation"](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/Boot-Image-Creation)).

### 5.1 BIF syntax

```
<image_name>:
{
    // common attributes (apply to the whole image)
    [attribute1] <argument1>

    // partitions, in boot order
    [attribute2, attribute3=<argument>] <elf>
    [attribute2, attribute3=<argument>, attribute4=<argument>] <bit>
    <bin>
}
```

Rules, quoted: the BIF *"specifies each component of the boot image, in order of boot"*; one data
file = one partition (an ELF with non-contiguous loadable sections can become **several**
partitions); attributes use the `[attr, attr=<arg>]` form and order is irrelevant; `//` and
`/* */` comments are allowed; file paths may be given
([UG1283 2022.2 / UG1400 2023.1, "BIF Syntax and Supported File Types"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/BIF-Syntax-and-Supported-File-Types)).

Supported inputs: `.elf` (symbols/headers stripped), `.bit`/`.rbt` (BIT header stripped),
`.bin`, `.dtb`, `image.gz`, `.int` (register init), `.nky` (AES key), `.pub/.pem` (RSA key),
`.sig`; and for Versal `.cdo/.npi/.rnpi`, `.rcdo`, plus `.bin/.pdi` as a *source* image to append
to ([UG821, BIF File Attributes](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/BIF-File-Attributes)).

### 5.2 Complete BIF — Zynq-7000 (FSBL + bitstream + bare-metal app)

Order is **mandatory**: the first partition must be the FSBL, the bitstream must come *immediately
after* it, and FSBL hands off to the first application in BIF order — *"The order within the BIF
file is important. Bitstream must be the partition after FSBL. Bitstream is not mandatory."*
([UG821, Boot and Configuration](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/Boot-and-Configuration)).

```tcl
/* boot.bif - Zynq-7000 standalone: FSBL + PL bitstream + bare-metal app */
the_ROM_image:
{
    [bootloader] fsbl.elf
    system.bit
    hello.elf
}
```

```bash
bootgen -arch zynq -image boot.bif -w -o BOOT.bin
```

The `[init] <file>.int` form (PS register initialisation, e.g. MIO/clock setup) can be added as
the first line — see the documented sample:

```tcl
the_ROM_image:
{
    [init] init_data.int
    [bootloader] fsbl.elf
    Partition1.bit
    Partition2.elf
}
```
([UG1283 2022.2, "image"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/image),
[UG1283 2022.2, "split"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/split)).

### 5.3 Complete BIF — Zynq UltraScale+ MPSoC

```tcl
/* boot.bif - ZynqMP bare-metal: FSBL(A53) + PMU FW + PL bitstream + R5 app */
the_ROM_image:
{
    [bootloader, destination_cpu=a53-0] fsbl_a53.elf
    [destination_cpu=pmu] pmu_fw.elf
    [destination_device=pl] system.bit
    [destination_cpu=r5-0] app_r5.elf
}
```

The `destination_device=pl` attribute is the documented way to mark a partition as the PL
bitstream on ZynqMP — AMD's own example is *"[bootloader,destination_cpu=a53-0]fsbl.elf /
[destination_device=pl]system.bit / [destination_cpu=r5-1]app.elf"*
([UG1283 2022.2, `destination_device`](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/destination_device)).
Base example for the FSBL/PMU/R5 combination quoted from
[UG1283 2022.2, "PMU Firmware Load by FSBL"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/PMU-Firmware-Load-by-FSBL):

```tcl
the_ROM_image:
{
    [bootloader, destination_cpu=a53-0] fsbl_a53.elf
    [destination_cpu=pmu] pmu_fw.elf
    [destination_cpu=r5-0] app_r5.elf
}
```

Linux variant on ZynqMP (real offsets, `bl31` at EL3, U-Boot at EL2, `image.ub` at
offset 0x1E40000 / load 0x10000000) — [UG1283 2022.2, "Booting Linux"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Booting-Linux):

```tcl
the_ROM_image:
{
    [bootloader, destination_cpu = a53-0]fsbl_a53.elf
    [destination_cpu=pmu]pmu_fw.elf
    [destination_cpu=a53-0, exception_level=el-3, trustzone]bl31.elf
    [destination_cpu=a53-0, exception_level=el-2] u-boot.elf
    [offset=0x1E40000, load=0X10000000, destination_cpu=a53-0]image.ub
}
```

```bash
bootgen -arch zynqmp -image boot.bif -w -o BOOT.bin
```

> In the Vivado/Vitis ecosystem, an XSA/vivado-produced portable image plus `bootgen` is also how
> PDI-based Versal boot images are made (`{ type = bootimage, file = base.pdi }` inside a BIF) —
> [UG1283 2026.1, "offset"](https://docs.amd.com/r/en-US/ug1283-bootgen-user-guide/offset).

### 5.4 bootgen command reference (the subset that matters here)

| Option | Meaning | Source |
|---|---|---|
| `-arch <zynq\|zynqmp\|fpga\|versal>` | Target architecture. **`zynq` is the default.** | [Commands and Descriptions](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Commands-and-Descriptions) |
| `-image <file.bif>` | Input BIF file | [image](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/image) |
| `-o <file.bin\|file.mcs>` | Output boot image (BIN or MCS) | [o](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/o) |
| `-w on` / `-w` | Overwrite an existing output file (`-w on` == `-w`; **default is on**) | [w](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/w) |
| `-log <error\|warning\|info\|trace>` | Console + `bootgen_log.txt` verbosity (default `warning`) | [log](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/log) |
| `-nonbooting` | Build an *intermediate* boot image (no boot header) | [nonbooting](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/nonbooting) |
| `-split bin\|mcs` | One output file per partition (+ boot header) | [split](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/split) |
| `-padimageheader <0\|1>` | Pad image/partition header tables to the max partition count to align following partitions (default 1; max partitions: **14 for Zynq**, **32 for ZynqMP**) | [padimageheader](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/padimageheader) |
| `-p <partname>` | Device part name (used when generating an encryption key) | [Command Reference](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Command-Reference) |
| `-process_bitstream <bin\|mcs>` | Write the *bitstream alone* as bin/mcs | [process_bitstream](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/process_bitstream) |
| `-encrypt <bbram\|efuse>`, `-generate_keys`, `-generate_hashes`, `-bif_help` | Security / helper options | [Commands and Descriptions](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Commands-and-Descriptions) |

`bootgen` is also installed standalone and lives inside the Vitis install
([UG1283 2022.2, "Installing Bootgen"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Installing-Bootgen)).

---

## 6. FSBL, and the "0x100000 / 0x104000" question

### 6.1 What the FSBL is and does

Boot is a **two-stage** process:

1. **BootROM (stage 0, in silicon, not writable)** configures one Arm core + the boot peripheral
   and fetches the FSBL from the boot device. *"The programmable logic (PL) is not configured by
   the BootROM."* On Zynq-7000 it copies the FSBL into **OCM**, and *"the size of the FSBL loaded
   into OCM is limited to 192 kilobyte. The full 256 kilobyte is available after the FSBL begins
   executing."*
2. **FSBL (stage 1)**, which: initialises the PS with the config data from the XSA; **programs the
   PL from the bitstream** if one is present; **loads the second-stage bootloader or bare-metal
   application into DDR**; and hands off (invalidating I-cache and disabling cache/MMU before
   handing to U-Boot).

Sources: [UG821, "First Stage Bootloader"](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/First-Stage-Bootloader)
and [UG821, "Boot and Configuration"](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/Boot-and-Configuration)
(*"FSBL does not remap the DDR; consequently, DDR that is lower than 1Mb cannot be used."*).

FSBL operation has four stages — **Initialization → Boot device initialization → Partition
loading → Handoff** ([UG1137, "Phases of FSBL Operation"](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/Phases-of-FSBL-Operation)).
Its footprint can be tuned with documented compile flags (`FSBL_DEBUG`, `FSBL_SD_EXCLUDE`,
`FSBL_QSPI_EXCLUDE`, `FSBL_BS_EXCLUDE`, …) set in `UserConfig.cmake`
([UG1137, "Setting FSBL Compilation Flags"](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/Setting-FSBL-Compilation-Flags)).

Where the FSBL/RAM addresses live in the image:

- **Zynq-7000 boot header** ([UG1283 2022.2, "Zynq-7000 SoC Boot Header"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Zynq-7000-SoC-Boot-Header)):

  | Offset | Field |
  |---|---|
  | `0x20` | Width detection word (QSPI) `0xAA995566` |
  | `0x24` | Header signature `0x584c4e58` (`X`,`N`,`L`,`X`) |
  | `0x28` | Key source (`0x00000000` = unencrypted) |
  | `0x30` | **Source offset** — location of the FSBL in the image |
  | `0x34` | FSBL image length (after decryption) |
  | `0x38` | **FSBL load address (RAM)** — dest. RAM address to copy the FSBL to |
  | `0x3C` | **FSBL execution address (RAM)** — entry vector |
  | `0x40` | Total FSBL length (incl. cert + padding) |

- **ZynqMP boot header** ([UG1283 2022.2, "Zynq UltraScale+ MPSoC Boot Header"](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Zynq-UltraScale-MPSoC-Boot-Header)):
  `0x2C` = FSBL execution address in OCM or XIP base; `0x30` = source offset (start of PMUFW if a
  PMUFW exists, else start of FSBL); `0x34` = PMU image length (0–128 KB); `0x3C` = FSBL image
  length (**0–250 KB**); `0x98` = image header table pointer.
  (The numeric *values* of the OCM load addresses are device memory-map facts, not in the bootgen
  table — see § 12.)

### 6.2 `0x100000` and `0x104000` — verified verdict

**`0x00100000` is real and important**: it is the **default DDR base address / entry point of a
standalone Zynq-7000 Cortex-A9 application**, i.e. where the FSBL copies your app and where the
program counter starts. The console dump in UG1400 shows exactly that:

```
section, .text: 0x00100000 - 0x001037f3
Setting PC to Program Start Address 0x00100000
```

([UG1400 2023.1](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/XSCT-Interface-Examples) —
same output in UG1400 2023.2). It is consistent with the UG821 statement that DDR below 1 MB
cannot be used by a Zynq-7000 design.

`0x100000` also appears as a **convenience destination address** in JTAG flows, e.g.
`dow -data system.dtb 0x100000` (loading a device tree) and `con -addr 0x100000` (resume from an
address) — [UG1400 2023.1, dow](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/dow),
[UG1400 2023.1, con](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/con).

**`0x104000` does not appear anywhere in the official documents I searched.** I grepped the full
text of UG1400 2022.2–2023.2, UG1283 2022.2 and UG821 for `0x104000`, `104000` and `0x1040`: the
only hit anywhere near it is the **MMU translation table section** of the Zynq-7000 standalone
linker script:

```
section, .mmu_tbl: 0x00104000 - 0x00107fff
```
([UG1400 2023.2 console dump](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Running-the-Application-Component)).

So the most probable origin of "0x104000" in circulating material is the **`.mmu_tbl` address of
the default Zynq-7000 linker script** (DDR base `0x00100000` + 16 KB), *not* a boot-image offset.
**Do not put `[offset = 0x104000]` in a BIF on the strength of it.** If a boot image genuinely
needs a partition at an absolute offset, use the documented attribute and pick the value yourself:

```tcl
all:
{
    [bootloader] fsbl.elf
    u-boot.elf
    [load=0x3000000, offset=0x500000] uImage.bin
    [load=0x2A00000, offset=0xa00000] devicetree.dtb
    [load=0x2000000, offset=0xc00000] uramdisk.image.gz
}
```
([UG1283, "offset"](https://docs.amd.com/r/en-US/ug1283-bootgen-user-guide/offset) — *"Sets the
absolute offset of the partition in the boot image"*; `-padimageheader` and `alignment=` are the
tools that control where a partition actually lands when you do *not* specify an offset).

---

## 7. Hello World bare-metal

### 7.1 The official template source

`Hello World` template (`lib/sw_apps/hello_world/src/helloworld.c` in the AMD embedded software
repository) — this is exactly what `-template "Hello World"` / `template="hello_world"` copies
into a new app:

```c
#include <stdio.h>
#include "platform.h"
#include "xil_printf.h"

int main()
{
    init_platform();

    print("Hello World\n\r");
    print("Successfully ran Hello World application");
    cleanup_platform();
    return 0;
}
```

Source: [Xilinx/embeddedsw — helloworld.c](https://github.com/Xilinx/embeddedsw/blob/master/lib/sw_apps/hello_world/src/helloworld.c)
(MIT-licensed, © AMD). The `Hello World` template exists in every release; the docs' own debug
sessions show `main() at ../src/helloworld.c: 60: init_platform();`
([UG1400 2023.2](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Running-the-Application-Component)).

For a **blank** project, pick `Empty Application` / `Empty Application(C)` instead — that template
name is used explicitly in the XSCT docs (`... -proc psu_cortexa53_0 -template {Empty Application(C)}`,
[UG1400 2023.1](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/XSCT-Interface-Examples)).

### 7.2 BSP / Xilinx driver example (AXI GPIO + `xil_printf`)

The canonical bare-metal driver example is the AXI GPIO one — and it is also the **best
illustration of the 2023.2 `DEVICE_ID` → `BASEADDR` break**:

```c
#include "xparameters.h"
#include "xgpio.h"
#include "xil_printf.h"

#define LED 0x01   /* Assumes bit 0 of GPIO is connected to an LED */

/* The following constants map to the XPAR parameters created in the
 * xparameters.h file.
 */
#ifndef SDT
#define GPIO_EXAMPLE_DEVICE_ID  XPAR_GPIO_0_DEVICE_ID     /* classic / IDT flow */
#else
#define XGPIO_AXI_BASEADDRESS   XPAR_XGPIO_0_BASEADDR     /* SDT flow (2023.2+) */
#endif

#define LED_DELAY     10000000
#define LED_CHANNEL   1

XGpio Gpio; /* The Instance of the GPIO Driver */

int main(void)
{
    int Status;

#ifndef SDT
    Status = XGpio_Initialize(&Gpio, GPIO_EXAMPLE_DEVICE_ID);
#else
    Status = XGpio_Initialize(&Gpio, XGPIO_AXI_BASEADDRESS);
#endif
    if (Status != XST_SUCCESS) {
        xil_printf("Gpio Initialization Failed\r\n");
        return XST_FAILURE;
    }

    XGpio_SetDataDirection(&Gpio, LED_CHANNEL, ~LED);

    while (1) {
        XGpio_DiscreteWrite(&Gpio, LED_CHANNEL, LED);
        /* ... delay ... */
        XGpio_DiscreteWrite(&Gpio, LED_CHANNEL, 0);
        /* ... delay ... */
    }
}
```

Adapted from the official example
[Xilinx/embeddedsw — XilinxProcessorIPLib/drivers/gpio/examples/xgpio_example.c](https://github.com/Xilinx/embeddedsw/blob/master/XilinxProcessorIPLib/drivers/gpio/examples/xgpio_example.c)
(the `#ifndef SDT` / `#else` split and both `XGpio_Initialize` call forms are in the upstream file,
added in driver version 4.10 "Added SDT support"). Other official GPIO examples in the same
directory: `xgpio_intr_tapp_example.c`, `xgpio_low_level_example.c`, `xgpio_tapp_example.c`.

### 7.3 Where the drivers and `xparameters.h` come from

- Drivers/libraries live in the BSP that the platform build generates for each domain. UG1400
  keeps only a pointer: *"Drivers and libraries are hosted on the AMD wiki"*
  ([UG1400 2023.1, "Drivers and Libraries"](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Drivers-and-Libraries))
  → bare-metal drivers & libraries are the `Xilinx/embeddedsw` repository
  ([github.com/Xilinx/embeddedsw](https://github.com/Xilinx/embeddedsw)), and the classic BSP
  layout is: `include/` (with `xparameters.h`), `lib/` (`libc.a`, `libm.a`, `libxil.a`),
  `libsrc/` (driver sources + makefiles), plus `.mss` for the domain — *"The include file
  `xparameters.h` is also created using the tool in this directory. This file defines base
  addresses of the peripherals in the system, #defines needed by drivers, OSs, libraries, and
  user programs"*
  ([UG1400 2023.1, HSI Commands](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Hardware-Software-Interface-HSI-Commands)).
- **Classic (≤ 2023.1)**: `xparameters.h` is generated by the **HSI** API from the XSA
  (`::hsi::utils::define_include_file $drv_handle "xparameters.h"`), and it contains
  `XPAR_<IP>_DEVICE_ID` **and** `XPAR_<IP>_BASEADDR` symbols, derived from the XSA address map
  ([UG1400 2023.1, HSI Commands](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Hardware-Software-Interface-HSI-Commands)).
- **Unified (2023.2+)**: the XSA is turned into a **System Device Tree (SDT)** which **Lopper**
  (Python) consumes to emit `xparameters.h` and driver init files — *"While `xparameters.h` is
  still generated by Lopper Framework, it does not contain `DEVICE_ID` definitions. Instead the
  `BASEADDR` definition is used."* and *"compiling a migrated application directly might result
  [in] compilation errors. If your application relies on DeviceID for IP driver initialization,
  refer to AR: Standalone Application Migration Details."*
  ([UG1400 2023.2, "Changed Behavior Summary"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Software-Platform-Release-Notes),
  [UG1400 2023.2, "Standalone Application Component Migration Details"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Standalone-Application-Component-Migration-Details)).
- Modern drivers compile with `#ifndef SDT` guards so that the *same* source works in both
  generations — that is what the GPIO example above demonstrates. So: **when writing driver code
  for a mixed-version audience, use the `#ifndef SDT` pattern, or use only `X<Drv>_Initialize`
  with the `BASEADDR` macro.**

---

## 8. Deployment to the board

### 8.1 JTAG (debug / temporary bring-up, nothing persisted)

Classic: the XSCT/XSDB script in [§ 2.5](#25-deploy-over-jtag-with-xsctxsdb-bare-metal-no-flash)
(`connect` → `targets -set -filter` → `rst` → `fpga <bit>` → `loadhw <xsa>` →
`source ps7_init.tcl; ps7_init; ps7_post_config` → `dow <elf>` → `con`).
For a ZynqMP JTAG boot sequence, the KRS how-to shows the real chain and `boot_jtag`
([xilinx.github.io/KRS](https://xilinx.github.io/KRS/sphinx/build/html/docs/howto.html)).

Unified: use the IDE's run/debug launch configuration on a **Target Connection** (the Unified IDE
keeps target connections and multi-cable/multi-device support —
[UG1400 feature table](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Unified-IDE-Features-versus-Classic-IDE-Features)),
or drive the hardware side with **XSDB** (the documented XSCT replacement for JTAG/debug).

### 8.2 SD card (FAT32) — the standard way to run `BOOT.bin`

**Zynq-7000** (UG585, *Zynq-7000 SoC TRM*, Boot and Configuration > BootROM Code > SD Card Boot):

- *"For the BootROM to read the BOOT.BIN file, the SD card must be partitioned so that the first
  partition is a FAT 16/32 file system. Additional non-FAT partitions are permitted, but the
  BootROM does not read the other partitions."*
  → [File Partitions](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/File-Partitions)
- *"Reads BOOT.BIN from the root of the SD file system and copies it into OCM after parsing the
  required BootROM Header."* → [BootROM Steps](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/BootROM-Steps)
- *"In SD card boot mode, the BootROM does not perform a header search and does not support
  multiboot."* → [BootROM Header Search and Multiboot](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/SD-Card-Boot)
- Header search on other media happens on 32-KB boundaries, limited to the first 16/32 MB for
  QSPI (depending on single/dual configuration) → [BootROM Header Search Stepping and Range](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/BootROM-Header-Search-Stepping-and-Range).

**Zynq UltraScale+ MPSoC** (UG1137, SD Boot Mode): FAT 16/32 is used to read the boot images;
MultiBoot image search up to 8 192 files; **exFAT is not supported**; bootgen produces `boot.bin`
which you *"write the boot.bin file into an SD card using a SD card reader"*; with PetaLinux the
FAT32 partition holds `boot.bin` + kernel + device tree while the root filesystem lives on an
EXT4 partition; boot pins: SD1 = `0x5`, SD0 = `0x3`, SD with level shifter = `0xE`
([UG1137, SD Boot Mode](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/SD-Boot-Mode)).

Practical Zynq-7000 recipe: partition the card MBR, partition 1 = FAT32 (a few hundred MB is
plenty), copy `BOOT.bin` **to the root of partition 1**, set the boot-mode pins to SD, insert and
power-cycle.

### 8.3 QSPI flash (production boot)

Produce `BOOT.bin`, then either

- **XSCT/`program_flash`** (classic, scriptable):

  ```tcl
  exec program_flash -f /path/BOOT.bin -flash_type qspi_single \
       -blank_check -verify -cable type xilinx_tcf url tcp:localhost:3121
  ```

  ([UG1400 2023.1](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Bootable-Image-and-Program-the-Flash));
  also `qspi_dual_parallel`, `qspi_dual_stacked`, `nand_8`, `nand_16`, `nor`, `emmc`
  ([UG1400 2025.2, "Programming Flash"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Programming-Flash));

- or the IDE wizard **Vitis > Program Flash** (Unified) / *Program Flash* (classic): select the
  system project, connection, image file, offset, flash type, optional *Blank check after erase*
  and *Verify after Flash*
  ([UG1400 2025.2, "Programming Flash"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Programming-Flash),
  [XD260 2023.2, "Program Flash"](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Program-Flash)).

Then set the boot-mode pins to QSPI and power-cycle — *"Make sure that the Program Flash is
successful. We can verify, by setting the bootmode to QSPI on our board"*
([XD260 2023.2](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Program-Flash)).

### 8.4 Board not detected

Cable drivers are a **post-install sudo step** on Linux (the installer stopped doing it in
Vivado 2015.4 *"due to requiring root or sudo access"*):

- Script: `<install>/data/xicom/cable_drivers/lin64/install_script/install_drivers/install_drivers`
  ([UG973, "Installing Cable Drivers"](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Installing-Cable-Drivers)).
- The script installs udev rules into `/etc/udev/rules.d/` — observed filenames are
  `52-xilinx-pcusb.rules`, `52-xilinx-ftdi-usb.rules`, `52-xilinx-digilent-usb.rules`; reload with
  `udevadm control --reload-rules` (or `service udev restart`) and re-plug the cable. ⚠️ The
  filenames come from the installer's own output as quoted by third parties
  ([example](https://wiki.to.infn.it/vlsi/workbook/fpga/arty),
  [example](https://reddit.com/r/FPGA/comments/l5in82/vivado_hardware_manager_on_linux_and_cable_drivers)),
  not from an AMD prose document — see § 12.
- Missing `libtinfo5` / `libncurses5` on modern distros breaks the tools outright:
  *"Without libtinfo5 Vivado will not start"* ([AMD AR#63794](https://adaptivesupport.amd.com/s/article/63794)).

---

## 9. Common Vitis errors (cause → fix)

Message strings are quoted as they are commonly reported; where a message is community-sourced
rather than AMD-documented I say so.

| Symptom | Most likely cause | Fix | Source |
|---|---|---|---|
| `make: *** No rule to make target '../src/lscript.ld', needed by 'myapp.elf'. Stop.` | The generated makefiles (`Debug/subdir.mk`) reference a file that is not where they think it is — classic pattern: a **relative** path to a linker script / source imported from outside the workspace (via `importsources -soft-link`), or a file added/moved after the build folder was generated. | Use an **absolute** path to the linker script in the build settings; or delete the `Debug/` directory and rebuild (regenerates `subdir.mk`). | [AMD forum thread](https://adaptivesupport.amd.com/s/question/0D52E00007IPhniSAD/bug-report-vitis-as-traditional-sdk), [AMD forum thread](https://adaptivesupport.amd.com/s/question/0D52E00007G0PcKSAV/sdk-fails-to-build-after-i-add-a-new-c-source-file), [AMD forum thread](https://adaptivesupport.amd.com/s/question/0D52E00006hpsKDSAY/no-rule-to-make-target-xxxxxxxo) |
| `make: *** No rule to make target 'C:/Temp/.../lscript.ld', needed by '...elf'` (Windows path) | Same family: project moved / path too long / workspace copied from another machine | Shorten + simplify paths (e.g. `C:/VIVADO/myproj`), delete `Debug/`, rebuild; in the platform: *Update Hardware Specification* → *Clean Project* → *Build Project*. | [AMD forum thread](https://adaptivesupport.amd.com/s/question/0D54U00008fG90cSAC/i-am-trying-to-implement-the-zybo-z7-pcam5-video-demo-but-keep-getting-an-error-in-vitis), [AMD forum thread](https://adaptivesupport.amd.com/s/question/0D52E00006hpMnkSAE/xilinxvitis-zybo-z720-pcam-5c) |
| `fatal error: xparameters.h: No such file or directory` (and/or `xil_printf.h`) | The **BSP for the domain was never built / the include path is wrong**: the app was created or migrated without a successful platform/domain build, or the design was migrated across versions so `xparameters.h` is stale/absent. Also classic cause: XSA/BSP version mismatch (e.g. driver version too old for the IP version). | Build the platform first (classic: `platform generate`; Unified: build the platform component), then rebuild the app; if the XSA changed, *Update Hardware Specification* + regenerate the BSP; verify the `‑I <bsp>/include` flag is present in the compile line. Historical AMD answer record for the same error: **AR#34804**. | [AMD AR#34804 listed in AR#34609 index](https://xilinx.com/support/answers/34609.html); community reproductions: [Digilent forum](https://forum.digilent.com/topic/13862-nexys-video-dma-audio-demo-is-broken), [Digilent forum](https://forum.digilent.com/topic/21030-vitis-20201-compile-trouble) |
| `undefined reference to 'XGpio_Initialize'` / `'xil_printf'` / `_sbrk`… at link time | Driver **header** is visible (so the compile passes) but the driver/library is not in the BSP or not linked — i.e. the peripheral isn't in the design/LTX, or the library (`libxil.a`) isn't pulled in; or a C++ app linking C objects. | Re-generate the BSP so the driver is compiled into `libxil.a`; check the peripheral appears in the XSA (else its driver is absent by design); for C++ wrappers use `extern "C"`. ⚠️ Message-level advice only — I found no single AMD document that enumerates this error. | Deduced from the BSP layout (`lib/`, `libxil.a`, `libsrc/`) documented in [UG1400 2023.1, HSI Commands](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Hardware-Software-Interface-HSI-Commands) |
| `ERROR: [Hsi 55-1594] Core intc of version 3.5 not found in repositories` + `xparameters.h: No such file or directory` | **Version mismatch**: an old XSA/BSP opened with a newer tool (or vice-versa) — the IP version in the design is unknown to this release's driver repository. | Use the release the design was made with, or re-create the BSP and re-import settings; upgrade the IP in Vivado. | [Digilent forum, quoting the XSCT log](https://forum.digilent.com/topic/13862-nexys-video-dma-audio-demo-is-broken) |
| `Could not retrieve Flash Part information. Please check hardware server connection` | No hw_server connection when opening Program Flash | Check the Target Connection (hw_server, default port 3121) before opening the wizard. | [UG1400 2025.2, "Programming Flash"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Programming-Flash) |
| `INFO: [Vivado 12-12733] No bit file available for '-include_bit'` | `write_hw_platform -include_bit` run in a shell that has no bitstream (no `write_bitstream`, non-project flow) | Run implementation → `write_bitstream` first (or re-run `write_hw_platform -include_bit` after opening the routed DCP and writing the bitstream). | [AMD forum thread](https://adaptivesupport.amd.com/s/question/0D54U00005Sf8kiSAB/how-to-specify-the-bitstream-filename-in-the-tcl-script-nonproject-workflow-such-that-writehwplatform-can-use-includebit) |
| `no such file or directory` / “platform cannot be created” when the `.xsa` path is wrong (XSCT `platform create -hw <xsa>`, `app create -hw <xsa>`) | The XSA path is wrong, the file is not an XSA (e.g. an old `.hdf`/`.xml`), or it was deleted after the platform was created. XSCT returns *"Error string, if the platform cannot be created"* rather than a friendly message. | Verify the path and the extension; re-export with `write_hw_platform -fixed`; for an existing platform use *Update Hardware Specification* instead of recreating. | [UG1400 2023.1, platform create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-create); ⚠️ the exact error wording is not documented (see § 12) |
| Board/cable not detected, `There is no active target available for server at localhost` | No USB cable driver / udev rules, or hw_server not running | Run `install_drivers` (see § 8.4), reload udev, re-plug, start `hw_server`; for remote hosts use `connect -host <ip> -port 3121`. | [UG973, "Installing Cable Drivers"](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Installing-Cable-Drivers), [UG1400 2023.1, connect](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/connect) |
| `libtinfo.so.5: cannot open shared object file` / `INFO: libtinfo.so.5 required` when launching the tools or XSCT | Missing legacy ncurses on modern distros | `apt install libtinfo5 libncurses5` (distro-dependent; on 24.04 they are not in the default repo). | [AMD AR#63794](https://adaptivesupport.amd.com/s/article/63794), [UG973/AMD forum on installLibs.sh](https://adaptivesupport.amd.com/s/question/0D5KZ00000pp7QE0AY/installlibssh-needs-update-for-vivadovitis-20242-on-ubuntu-24042-lts) |
| `import vitis` fails / `ModuleNotFoundError` / wrong-version errors when running a Python script outside the IDE | You are using the **system Python** instead of the Vitis environment/bundled interpreter | `source <Vitis>/settings64.sh` then `source <Vitis>/cli/examples/customer_python_utils/setup_vitis_env.sh`, and use `<Vitis>/tps/lnx64/python-<ver>/bin/python` (2025.2 ships 3.13). Never `pip install` into the system interpreter for this. | [UG1400 2025.2, "Enabling the Vitis API to be used in a Python ENV"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Enabling-the-Vitis-API-to-be-used-in-a-Python-ENV) |
| `xsct`/`xsdb`/`tclsh` segfault on Linux (e.g. with `rlwrap`) | `rlwrap` incompatibility in the wrapper scripts | Remove `rlwrap` from the launch path or install `rlwrap` and fix the path in `<install>/Vitis/<ver>/bin/xsct` etc. | [ArchWiki: Xilinx Vivado § xsct, xsdb, xmd, and tclsh segfault](https://wiki.archlinux.org/title/Xilinx_Vivado) ⚠️ community documentation |
| `Vitis: cannot open libssl.so.10` / `cmake: error while loading shared libraries: libssl.so.10` when creating a platform component | CMake bundled with Vitis expects the RHEL 9 libs; on other distros the lookup fails | Symlink the bundled `tps/lnx64/cmake-*/libs/Rhel/9/*` into `/usr/lib` (distro-specific). | [ArchWiki](https://wiki.archlinux.org/title/Xilinx_Vivado) ⚠️ community documentation |
| `WARNING: XSCT has been deprecated. It will still be available for several releases. In the future, it's recommended to start new projects with SDT workflow.` | Deprecation notice, not an error — but a sign you are on ≥ 2025.1 | Migrate project management to the Vitis Python API / XSDB. | [UG1400 2025.2, "XSCT to Python API Migration"](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/XSCT-to-Python-API-Migration), [UG1742 2026.1, "Deprecated Features"](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Deprecated-Features) |
| License errors when running `v++` linking / AI Engine / HLS cosim | Licence-gated flow, not a broken install | See the licensing table: **embedded software development needs no PL/hardware licence**; System Design, RTL generation, PL kernels, AI Engine and HLS cosim are gated to licensed devices; **HLS C synthesis and C simulation need no licence**. | [UG1742 2026.1, "Licensing"](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Licensing), [amd.com Vitis product page](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vitis.html) |

### 9.1 Environment / OS sanity checklist (Linux)

- Supported OS versions are enumerated per release; e.g. 2026.1 supports RHEL/Alma/Rocky 8.10–10.x,
  Ubuntu 22.04.3+ and 24.04.x, SUSE 15 SP4+, Windows 10 22H2 / 11 23H2+; disk: **35 GB for Vitis
  Embedded, 200 GB for the full Vitis install**; RAM 32 GB (recommend 64 GB)
  ([UG1742 2026.1, "Installation Requirements"](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Installation-Requirements)).
- The **AMD Vitis Embedded Installer** installs only the embedded flow (no acceleration/AIE);
  the **AMD Unified Installer** contains Vitis + Vivado + PetaLinux, and only the full install can
  launch `vitis --classic`
  ([UG1400 2023.2, "Installation"](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Installation)).
- After a full install on Linux, run `installLibs.sh` (mentioned in the installation chapter) —
  and be aware it has needed updates on newer Ubuntu
  ([AMD forum](https://adaptivesupport.amd.com/s/question/0D5KZ00000pp7QE0AY/installlibssh-needs-update-for-vivadovitis-20242-on-ubuntu-24042-lts)).

---

## 10. Copy-paste cheat sheet

```bash
# ---------- Vivado (PL) ----------
vivado -mode batch -source export_xsa.tcl        # -> system.xsa

# ---------- Vitis classic (Tcl) ----------
xsct build_app.tcl                               # setws/platform/app/sysproj/exec program_flash
xsdb run_jtag.tcl                                # connect/targets/rst/fpga/loadhw/dow/con

# ---------- Vitis unified (Python) ----------
source /tools/Xilinx/Vitis/2025.2/settings64.sh
vitis -s build_ws.py                             # create/build platform + app + system project
vitis -w ./vitis_ws                              # open the resulting workspace in the IDE

# ---------- bootgen (either generation) ----------
bootgen -arch zynq   -image boot.bif -w -o BOOT.bin     # Zynq-7000
bootgen -arch zynqmp -image boot.bif -w -o BOOT.bin     # Zynq UltraScale+ MPSoC
```

| Need | Classic (≤2023.1) | Unified (2023.2+) |
|---|---|---|
| Set workspace | `setws <dir>` | `client.set_workspace(path=…)` |
| Platform | `platform create -hw <xsa> -proc <p> -os standalone` + `platform generate` | `client.create_platform_component(name=…, hw_design=<xsa>, cpu=…, os="standalone")` + `.build()` |
| Domain | `domain create -name … -os standalone -proc …` | `platform.add_domain(cpu=…, os=…, name=…)` |
| App | `app create -name … -platform … -domain … -template "Hello World"` + `app build` | `client.create_app_component(name=…, platform=<xpfm>, domain=…, template="hello_world")` + `.build()` |
| System project | implicit (`<app>_system`) or `sysproj` | `client.create_sys_project(name=…, platform=…)` + `.add_component()` |
| Boot image | `sysproj build` (runs bootgen) | GUI wizard (*Create Boot Image*); otherwise call `bootgen` yourself |
| JTAG run | `connect`/`targets`/`rst`/`fpga`/`loadhw`/`dow`/`con` in XSCT/XSDB | IDE launch config + target connection; XSDB for CLI |
| Flash | `program_flash -f … -flash_type qspi_single` | IDE *Program Flash* wizard |

---

## 11. Sources

All URLs were fetched/verified on **2026-09-17**.

**Vitis embedded (UG1400)**
- [UG1400 2023.1 — Software Command-Line Tool (XSCT overview)](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Software-Command-Line-Tool)
- [UG1400 2023.1 — Workspace Structure](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Workspace-Structure-in-the-Vitis-Software-Platform)
- [UG1400 2023.1 — Creating a Hardware Design (XSA File)](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Hardware-Design-XSA-File)
- [UG1400 2023.1 — Creating a Platform Project from XSA](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Platform-Project-from-XSA)
- [UG1400 2023.1 — Adding a Standalone Domain](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Adding-a-Standalone-Domain)
- [UG1400 2023.1 — Creating a Hello World Application](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Hello-World-Application)
- [UG1400 2023.1 — XSCT Commands](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/XSCT-Commands) · [setws](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/setws) · [platform create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-create) · [platform active](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-active) · [platform generate](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/platform-generate) · [domain create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/domain-create) · [app create](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/app-create) · [app build](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/app-build) · [repo](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/repo) · [connect](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/connect) · [targets](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/targets) · [dow](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/dow) · [con](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/con) · [rst](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/rst) · [fpga](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/fpga) · [loadhw](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/loadhw)
- [UG1400 2023.1 — Creating a Bootable Image and Program the Flash (full XSCT example)](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Bootable-Image-and-Program-the-Flash)
- [UG1400 2023.1 — XSCT Interface Examples](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/XSCT-Interface-Examples)
- [UG1400 2023.1 — Running an Application in Non-Interactive Mode (XSDB script)](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Running-an-Application-in-Non-Interactive-Mode)
- [UG1400 2023.1 — Creating a Boot Image](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Creating-a-Boot-Image) · [BIF Syntax and Supported File Types](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/BIF-Syntax-and-Supported-File-Types) · [Using Bootgen on the Command Line](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/Using-Bootgen-on-the-Command-Line) · [fsbl_config](https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/fsbl_config)
- UG1400 **2023.1 PDF** (full text used for greps): `https://docs.amd.com/api/khub/maps/PHwa3sDuk6G_sjX_v9CnHw/attachments/uqXPsAhO1tWFbTo4n3Uz_Q-PHwa3sDuk6G_sjX_v9CnHw/content` (rendered as `ug1400-vitis-embedded-en-us-2023.1.pdf`)
- UG1400 **2023.2 PDF**: `ug1400-vitis-embedded-en-us-2023.2.pdf` (map `X1QD5u5YoN5xSktsiEhkDA`)
- [UG1400 2023.2 — Launch Options](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Unified-IDE-Launch-Options) · [Release notes / Changed Behavior](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Vitis-Software-Platform-Release-Notes) · [Creating a Platform Component from XSA](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Creating-a-Platform-Component-from-XSA) · [Creating an Application Component](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Creating-an-Application-Component) · [Creating a Boot Image](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Creating-a-Boot-Image) · [User Managed Flow](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/User-Managed-Flow) · [Python Vitis Commands](https://docs.amd.com/r/2023.2-English/ug1400-vitis-embedded/Python-Vitis-Commands)
- [UG1400 2024.2 — Python API: command-line tool](https://docs.amd.com/r/2024.2-English/ug1400-vitis-embedded/Python-API-A-command-line-tool-for-creating-and-managing-projects-in-Vitis)
- [UG1400 2025.2 — Platform](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Platform) · [Application](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Application) · [System Project](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/System-Project) · [Enabling the Vitis API in a Python ENV](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Enabling-the-Vitis-API-to-be-used-in-a-Python-ENV) · [Programming Flash](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Programming-Flash) · [Creating a Boot Image](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Creating-a-Boot-Image) · [Workspace Structure](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Workspace-Structure-in-the-Vitis-Software-Platform) · [Workspace Journal Coverage](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Workspace-Journal-Coverage) · [XSCT to Python API Migration](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/XSCT-to-Python-API-Migration) · [Python XSDB Commands](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Python-XSDB-Commands) · [Output Files](https://docs.amd.com/r/2025.2-English/ug1400-vitis-embedded/Output-Files)
- [UG1400 current — Migrating from the Classic Vitis IDE](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Migrating-from-the-Classic-Vitis-IDE-to-Vitis-Unified-IDE) · [Unified IDE vs Classic IDE features](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Unified-IDE-Features-versus-Classic-IDE-Features)

**Bootgen (UG1283) / boot image layout**
- [UG1283 2022.2 — BIF Syntax and Supported File Types](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/BIF-Syntax-and-Supported-File-Types) · [Boot Image Format (BIF)](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Boot-Image-Format-BIF) · [Zynq-7000 SoC Boot Image Layout](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Zynq-7000-SoC-Boot-Image-Layout) · [Zynq-7000 SoC Boot Header](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Zynq-7000-SoC-Boot-Header) · [Zynq UltraScale+ MPSoC Boot Header](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Zynq-UltraScale-MPSoC-Boot-Header) · [Commands and Descriptions](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Commands-and-Descriptions) · [image](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/image) · [o](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/o) · [w](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/w) · [log](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/log) · [split](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/split) · [padimageheader](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/padimageheader) · [PMU Firmware Load by FSBL](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/PMU-Firmware-Load-by-FSBL) · [Booting Linux](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/Booting-Linux) · [fsbl_config](https://docs.amd.com/r/2022.2-English/ug1283-bootgen-user-guide/fsbl_config)
- [UG1283 current — offset](https://docs.amd.com/r/en-US/ug1283-bootgen-user-guide/offset) · [Boot Image Layout](https://docs.amd.com/r/en-US/ug1283-bootgen-user-guide/Boot-Image-Layout)
- [UG1283 2022.2 PDF](https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_2/ug1283-bootgen-user-guide.pdf)

**Zynq-7000 / ZynqMP software & boot**
- [UG821 — First Stage Bootloader](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/First-Stage-Bootloader) · [Boot and Configuration](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/Boot-and-Configuration) · [Boot Image Creation](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/Boot-Image-Creation) · [BIF File Attributes](https://docs.amd.com/r/en-US/ug821-zynq-7000-swdev/BIF-File-Attributes)
- [UG585 — SD Card Boot: File Partitions](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/File-Partitions) · [BootROM Steps](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/BootROM-Steps) · [BootROM Header Search Stepping and Range](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/BootROM-Header-Search-Stepping-and-Range) · [Boot Device Content](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Boot-Device-Content)
- [UG1137 — SD Boot Mode](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/SD-Boot-Mode) · [Boot Image Creation](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/Boot-Image-Creation) · [Phases of FSBL Operation](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/Phases-of-FSBL-Operation) · [Setting FSBL Compilation Flags](https://docs.amd.com/r/en-US/ug1137-zynq-ultrascale-mpsoc-swdev/Setting-FSBL-Compilation-Flags)

**Vivado side / XSA / cable drivers / licensing / release notes**
- [UG835 — write_hw_platform](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_hw_platform) · [UG909 — Using Export Hardware](https://docs.amd.com/r/en-US/ug909-vivado-partial-reconfiguration/Using-Export-Hardware) · [XD101 — Export Hardware XSA](https://docs.amd.com/r/2024.2-English/Vitis-Tutorials-Vitis-Platform-Creation/Export-Hardware-XSA) · [UG1701 — Fixed XSA](https://docs.amd.com/r/en-US/ug1701-vitis-accelerated-embedded/Fixed-XSA) / [Extensible XSA](https://docs.amd.com/r/en-US/ug1701-vitis-accelerated-embedded/Extensible-XSA)
- [UG973 — Installing Cable Drivers](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Installing-Cable-Drivers) · [AMD AR#63794 — required Ubuntu packages](https://adaptivesupport.amd.com/s/article/63794)
- [UG1742 2026.1 — Installation Requirements](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Installation-Requirements) · [Licensing](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Licensing) · [Deprecated Features](https://docs.amd.com/r/en-US/ug1742-vitis-release-notes/Deprecated-Features)
- [amd.com — AMD Vitis Unified Software Platform](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vitis.html)

**Vitis acceleration (for the `v++` / platform-component distinction)**
- [UG1393 2024.1 — v++ Command](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/v-Command) · [v++ General Options](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/v-General-Options) · [Create and Build Platform Component](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Create-and-Build-Platform-Component) · [Create and Build Application Component](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Create-and-Build-Application-Component) · [Vitis Interactive Python Shell](https://docs.amd.com/r/2024.1-English/ug1393-vitis-application-acceleration/Vitis-Interactive-Python-Shell)

**Tutorials / examples**
- [XD260 2023.2 — Launching Vitis CLI](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Launching-Vitis-CommandLine-Interface-CLI) · [Create Vitis workspace](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Create-Vitis-workspace) · [Build Vitis Unified Workspace](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Build-Vitis-Unified-Workspace) · [Program Flash](https://docs.amd.com/r/2023.2-English/Vitis-Tutorials-Embedded-Software/Program-Flash)
- [Xilinx/embeddedsw — helloworld.c](https://github.com/Xilinx/embeddedsw/blob/master/lib/sw_apps/hello_world/src/helloworld.c) · [xgpio_example.c](https://github.com/Xilinx/embeddedsw/blob/master/XilinxProcessorIPLib/drivers/gpio/examples/xgpio_example.c)
- [Xilinx/bootgen (open-source bootgen)](https://github.com/Xilinx/bootgen)

**Third-party / community (explicitly marked as such above)**
- [ArchWiki — Xilinx Vivado troubleshooting](https://wiki.archlinux.org/title/Xilinx_Vivado) · [AMD Adaptive Support threads on `No rule to make target`](https://adaptivesupport.amd.com/s/question/0D52E00007IPhniSAD/bug-report-vitis-as-traditional-sdk) · [Digilent forum: xparameters.h / BSP version mismatch](https://forum.digilent.com/topic/13862-nexys-video-dma-audio-demo-is-broken)

---

## 12. What I could NOT verify

Be careful with the following — this note does **not** stand behind them as verified:

1. **`0x104000` in a boot context.** Grep of the full text of UG1400 2022.2/2023.1/2023.2,
   UG1283 2022.2 and UG821 for `0x104000` / `104000` / `0x1040` produced **no boot-image hit**.
   The only nearby value is the `.mmu_tbl` section at `0x00104000` in the Zynq-7000 standalone
   linker script (see § 6.2). Treat any "0x104000 boot offset" claim as unsourced until someone
   points at a real AMD document.
2. **Numeric FSBL load/execution addresses.** UG1283 documents the *fields* (`0x38` load, `0x3C`
   exec for Zynq-7000; `0x2C` exec for ZynqMP) but not the values. The conventional Zynq-7000
   values (FSBL in OCM, app at `0x00100000`) are consistent with UG821/UG1400 console output, but
   I did not fetch UG585/UG1085 memory-map tables to confirm the exact OCM base for each device.
   For ZynqMP I did **not** verify the OCM base address (commonly cited as `0xFFFC0000`).
3. **Exact error strings.** UG1400 documents the *semantics* of failures (`"Error string, if the
   platform cannot be created"`) but never lists the messages. Messages quoted in § 9 as
   community/forum sourced are marked as such: the `No rule to make target …` variants,
   `xparameters.h: No such file or directory`, `Hsi 55-1594`, and the "no such file XSA" wording
   are **not** AMD-documented strings.
4. **A Python API for boot-image generation.** UG1400 2023.2 → 2025.2 document boot image creation
   only through the GUI wizard; the documented workspace-journal coverage is component creation,
   builds, and config-file edits. I found **no** documented `create_boot_image()`-style API. It may
   exist in `<Vitis>/cli/api_docs/build/html/vitis.html` (installed docs) — that file is not
   published online, so I could not check it.
5. **udev rule filenames.** UG973 documents only the `install_drivers` script path; the
   `52-xilinx-*.rules` names come from installer output quoted by third parties.
6. **Per-release Python interpreter versions bundled with Vitis** (2025.2 = 3.13 verified; older
   releases not checked), and whether `vitis -s` accepts a `.tcl` file. The documented signature
   is explicitly `<python_script>`, and no AMD page I read says Tcl is accepted — but the
   possibility of a hidden Tcl path was not positively excluded by testing.
7. **`xsct <script.tcl>` command-line flags.** UG1400 explains XSCT semantics and shows the
   non-interactive script being passed "as a launch argument to XSDB", but I did not find a page
   listing `xsct`/`xsdb` CLI switches (`-eval`, `-tcf`, …) — do not document invented flags.
8. **ZynqMP/Versal SD-boot detail parity with Zynq-7000.** FAT16/32 + `boot.bin` on ZynqMP is
   confirmed by UG1137; the equivalent sentence for Versal was not fetched.
9. **Nothing was executed.** No Vitis/Vivado install was available, so no script in this note was
   run against a real tool or board. All command syntax is documentation-derived.
