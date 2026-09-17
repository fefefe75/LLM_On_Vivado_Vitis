# 01 — Driving Vivado with Tcl: complete agent reference

> **Audience:** an LLM agent that has never touched Vivado and must create, build, report on,
> and program a Vivado design from a shell, and must debug its own failures.
> **Style:** exact commands, exact options, typical tool output, error → cause → fix tables.
> **Primary sources:** AMD documentation on `docs.amd.com` (UG835, UG894, UG892, UG893, UG908, UG910, UG949)
> plus AMD Adaptive Support answer records (`adaptivesupport.amd.com`). Every technical claim carries a URL.
> **Vivado versions:** command references quoted from **UG835 v2026.1** (published 2026-06-23) unless stated.
> Behaviour changes are annotated inline (`since 2022.1`, `removed …`, …). Older revisions used to date
> changes: UG835 v2018.1 (Mar 2018), v2020.1 (Jun 2020), v2022.1 (May 2022).
> **Everything below was verified by reading the actual AMD pages/PDFs, not from memory.**
> Claims that could not be verified against an AMD source are flagged `⚠ unverified`.

---

## 0. TL;DR — the four scripts an agent actually needs

| Goal | Entry point | Verify |
|---|---|---|
| Build a project from scratch | `vivado -mode batch -source create_project.tcl` | `.xpr` exists, no `ERROR:` in `vivado.log` |
| Build + bitstream (project mode) | `vivado -mode batch -source build.tcl` | `impl_1` `PROGRESS == 100%`, `.bit` exists |
| Build without a project | `vivado -mode batch -source build_nonproject.tcl` | `.dcp` / `.bit` exist, `report_route_status` clean |
| Program a board | `vivado -mode batch -source program.tcl` | `REGISTER.IR.BIT5_DONE == 1` |

Ready-to-copy versions of all four are in **§12**.

The single most important operational fact: **Vivado's process exit code is a poor success signal.**
A failing batch script normally still exits `0`; success must be decided from the log, from `catch`
return codes, and from run properties (`PROGRESS`, `STATUS`, `NEEDS_REFRESH`). See §2.4 and §5.

---

## 1. Mental model

### 1.1 Launch modes

Vivado is one binary with three interactive/batch personalities. They expose the same Tcl command set.

| Mode | Command | Behaviour |
|---|---|---|
| Batch (script) | `vivado -mode batch -source <script.tcl>` | Opens the Tcl shell, runs the script, **exits automatically** when the script ends |
| Tcl shell | `vivado -mode tcl` | Interactive Tcl console, no GUI |
| GUI | `vivado` or `vivado -mode gui` | Full IDE; also reachable from the Tcl shell with `start_gui` |

Sources: <https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/Tcl-Batch-Mode>,
<https://docs.amd.com/r/en-US/ug910-vivado-getting-started/Launching-the-Vivado-Tools-Using-a-Batch-Tcl-Script>,
<https://docs.amd.com/r/en-US/ug910-vivado-getting-started/Launching-the-Vivado-IDE-from-the-Command-Line-on-Windows-or-Linux>,
<https://docs.amd.com/r/en-US/ug893-vivado-ide/Launching-the-Vivado-Tools-Using-a-Batch-Tcl-Script>.

`vivado -help` prints the full option list; the install tree is
`<install_path>/Vivado/<version>/bin/vivado` and `settings64.sh` / `settings64.bat` puts it on `PATH`
(<https://docs.amd.com/r/en-US/ug893-vivado-ide/Launching-the-Vivado-IDE-from-the-Command-Line-on-Windows-or-Linux>).

### 1.2 Project Mode vs Non-Project Mode — different command sets

This is the distinction that trips up generated scripts.

- **Project Mode**: a `.xpr` project file plus filesets (`sources_1`, `constrs_1`, `sim_1`) and
  *runs*. Sources are added with `add_files` / `import_files`; synthesis and implementation are
  launched with `launch_runs`; the tool writes run directories, checkpoints and standard reports for you.
- **Non-Project Mode**: no project on disk. Sources are read with `read_vhdl` / `read_verilog` /
  `read_xdc`, and every step is an explicit command: `synth_design`, `opt_design`, `place_design`,
  `phys_opt_design`, `route_design`, `write_bitstream`. You are responsible for every checkpoint and report.

AMD's own warning: *"Some commands are specific to one mode and must not be mixed when creating
scripts. For example, in Project Mode, avoid base-level commands like `synth_design`, which are
specific to Non-Project Mode. Using Non-Project Mode commands in Project Mode prevents database
updates and automatic report generation."*
(<https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/Tcl-Command-Differences-in-Project-Mode-and-Non-Project-Mode>)

| Task | Project Mode | Non-Project Mode |
|---|---|---|
| Create container | `create_project`, `create_fileset` | `create_project -in_memory` (optional, in-memory only) |
| Add sources | `add_files` (`-fileset`), `import_files` | `read_vhdl`, `read_verilog`, `read_xdc`, `read_ip`, `read_edif` |
| Set top | `set_property top <m> [current_fileset]` | `synth_design -top <m>` |
| Synthesis | `launch_runs synth_1` + `wait_on_runs` | `synth_design` |
| Implementation | `launch_runs impl_1 [-to_step …]` | `opt_design`, `place_design`, `phys_opt_design`, `route_design` |
| Open a stage | `open_run impl_1` | `open_checkpoint <file>.dcp` (`read_checkpoint` + `link_design` for netlists) |
| Bitstream | `launch_runs impl_1 -to_step write_bitstream` or `write_bitstream` on an open run | `write_bitstream` |
| Reports | `report_*` (also auto-generated in the run dir) | `report_*` (you must call them) |

`create_project -in_memory` "supports the Non-Project design flow… will not result in a project file
or directory structure being written to disk"
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/create_project>).

### 1.3 What a "run" is (Project Mode)

A **run** is a named configuration of tool options plus a directory that holds its results
(`<project>.runs/synth_1`, `<project>.runs/impl_1`, …). A run has properties queried with
`get_property` and set with `set_property` — e.g. `STEPS.OPT_DESIGN.IS_ENABLED`,
`STEPS.ROUTE_DESIGN.TCL.POST`, `PROGRESS`, `STATUS`, `NEEDS_REFRESH`, `STRATEGY`, `FLOW`.
Runs are created with `create_run`; the default project already contains `synth_1` and `impl_1`.
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/create_run>,
<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/launch_runs>)

---

## 2. Batch invocation: the process contract

### 2.1 Canonical command lines

```bash
# Project-mode build
vivado -mode batch -source build.tcl -tclargs "PART=xc7a35tcpg236-1" "TOP=top"

# Silent, reproducible CI run (no .log, no .jou, no command echo)
vivado -mode batch -notrace -nolog -nojournal -source build.tcl -tclargs "PART=xc7a35tcpg236-1"
```

The `-tclargs` form is documented in UG835: *"The `-tclargs` option lets you specify arguments for
the Tcl script you are running… **Important: You must enclose the Tcl argument and value in quotes**
as shown in the example above, or there can be an error in handling the argument"* —
`vivado -mode batch -source script.tcl -tclargs "FPGA=115-2"`
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/Tcl-Batch-Mode>).

### 2.2 Launch flags

| Flag | Meaning | Source |
|---|---|---|
| `-mode batch` | run a script then exit | UG835 Tcl Batch Mode; UG910 |
| `-mode tcl` | interactive Tcl shell | UG835 Introduction; UG910 |
| `-source <file.tcl>` | script to run in batch mode | UG835 Tcl Batch Mode |
| `-tclargs <a> <b> …` | arguments available to the script as `$argv` | UG835 Tcl Batch Mode |
| `-log <file>` / `-journal <file>` | write the log/journal to a chosen path (AMD recommends these when launching from another directory) | <https://docs.amd.com/r/en-US/ug893-vivado-ide/Output-Files> |
| `-nolog` | do not write `vivado.log` | see note below |
| `-nojournal` | do not write `vivado.jou` | see note below |
| `-notrace` | do not echo every command into the log | see note below |
| `-quiet` | suppress the banner/startup chatter | ⚠ not found in UG835/UG893 topic text; verify with `vivado -help` |
| `-help` | list all command-line options | UG910 / UG893 |

⚠ **Note on `-nolog`, `-nojournal`, `-notrace`:** these three appear together in AMD's own support
forum as the standard CI invocation — *"My typical Vivado command line is:
`vivado -mode batch -nojournal -nolog -notrace -source <myscript.tcl> -tclargs [myscript_arguments]`"*
(<https://adaptivesupport.amd.com/s/question/0D52P00006hpZimSAE/vivado-command-line-options>), and
`-tclargs`/`-source`/`-mode batch` are in UG835. UG893 documents only `-log`/`-journal`. If an agent
needs certainty for a given version, run `vivado -help` once and parse the output.

### 2.3 What batch mode is *not* the same as

> "In batch mode, the unknown commands are not sent to the OS for execution. To make sure that a
> script works under all the three Vivado modes, it is recommended to explicitly use the `exec`
> command to execute external programs."
> — <https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Vivado-Integrated-Design-Environment-IDE/Tcl-Modes-versus-Batch-Mode>

Consequence for a generated script: never write a bare `mkdir`, `git`, `cp` … call — write
`exec mkdir -p $dir`, or use Tcl's own `file mkdir`.

### 2.4 Exit codes — do not trust them, then make them trustworthy

- AMD does not document a non-zero exit code for a failed batch script. AMD's own forum thread
  (>2021.2 users) reports *"If the script fails, Vivado exits but the return code is always 0"*
  (<https://adaptivesupport.amd.com/s/question/0D52E000075zU0HSAU/vivado-exit-code-in-batch-mode>).
  UG835 only says tool commands return `TCL_OK`/`TCL_ERROR` **inside** Tcl, and that
  `$ERRORINFO` (Tcl's `errorInfo`) is set
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/Introduction>, section *Return Codes*).
- The working pattern used in practice is: catch failures yourself and call `exit 1`
  (same thread: *"If you can catch the error in your TCL script then try using `exit 1`. This will
  cause Vivado to exit out with a return code of 1"*).
- ⚠ Beware of `-quiet`: command-level `-quiet` makes a command *"return TCL_OK regardless of any
  errors encountered during execution… Only errors occurring inside the command will be trapped"*
  (every UG835 command page, e.g. `write_bitstream`). Never combine `-quiet` with error detection.

**Recommended contract for an agent-driven build** (implemented in §12):

1. Every fallible call is wrapped: `if {[catch {…} msg]} { fail "step" $msg }` (§8).
2. After each run, check `PROGRESS == "100%"` and `STATUS`, not the process status (§5).
3. Set `set_param general.maxThreads` / use `-jobs` deliberately (§7).
4. The script ends with `exit 0` on success and `exit 1` (with `ERROR:` lines already printed) on failure.
5. The caller additionally greps `vivado.log` for `^ERROR:` / `^CRITICAL WARNING:` as a belt-and-braces check (§8.5).

### 2.5 How to detect failure — four independent layers

| Layer | Signal | Command |
|---|---|---|
| Tcl | command raised `TCL_ERROR` | `catch {…} msg` → `$msg`, `puts $errorInfo` |
| Run | run did not finish successfully | `get_property PROGRESS [get_runs impl_1]` ≠ `100%`; `get_property STATUS`; `get_property NEEDS_REFRESH` |
| Message ID | specific severity crossing | `<cmd> -quiet` OFF, or `get_msg_config -severity ERROR -count`, `get_msg_config -severity {CRITICAL WARNING} -count` |
| Log text | last resort, always works | `grep -c '^ERROR:' vivado.log`, `grep 'ERROR:' runs/impl_1/runme.log` |

`get_msg_config` syntax (UG835): `get_msg_config [-id <arg>] [-severity <arg>] [-rules] [-limit] [-count] [-quiet] [-verbose]`
— `-count` *"will display the total number of messages that have been generated with the matching
message id, or for the specified severity"*
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/get_msg_config>).

---

## 3. Project Mode — full flow, exact syntax

Syntax blocks below are copied from UG835 v2026.1 command pages (§13 lists every URL).

### 3.1 Create the project

```tcl
create_project [‑part <arg>] [‑force] [‑in_memory] [‑ip] [‑rtl_kernel] [‑quiet] [‑verbose] [<name>] [<dir>]
```

- `<name>` then `<dir>` are **positional**: *"the first argument without a preceding keyword is
  interpreted as the `<name>`, and the second argument without a preceding keyword is the `<dir>`."*
- `-force` is required to overwrite an existing project directory.
- Default project type is RTL; change with
  `set_property DESIGN_MODE {RTL|GateLvl|PinPlanning} [current_fileset]`.
- Example: `create_project project1 myDesigns` → `project1.xpr` + `project1.data/`.
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/create_project>)

```tcl
create_project $proj_name $proj_dir -part $part -force
```

### 3.2 Add sources, constraints, filesets

```tcl
add_files [‑fileset <arg>] [‑of_objects <args>] [‑norecurse] [‑copy_to <arg>] [‑force] [‑scan_for_includes] [‑quiet] [‑verbose] [<files>...]
```

- Files are added **by reference** (unlike `import_files`, which copies them into the project tree).
- Directories are searched recursively unless `-norecurse` is given.
- `-scan_for_includes` adds Verilog `` `include `` targets.
- Canonical AMD example, used verbatim in this project's scripts:
  `add_files -fileset constrs_1 -quiet c:/Design/top.xdc c:/Design/project_1`
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/add_files>)
- Other filesets: `add_files -fileset sim_1 <tb.v>`, and create new ones with
  `create_fileset [-constrset] [-simset] [-blockset] … <name>`
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/create_fileset>).
- IP and block designs are **not** `add_files` material: *"IP and Block Design sources are not added
  through the add_files command. These are compound files that are supported by separate commands
  such as `import_ip`, `read_bd`, and `read_ip`."* (same page) → use
  `add_files -norecurse path/to/ip.xci` for an existing `.xci` file, `read_bd`/`read_ip` for compound sources.

### 3.3 Top module and compile order

```tcl
set_property top <top_module> [current_fileset]
update_compile_order [‑force_gui] [‑fileset <arg>] [‑quiet] [‑verbose]
```

- `update_compile_order -fileset sources_1` "Update the compile order of the design sources in the
  current project" (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/update_compile_order>).
- AMD's own project-flow sample script runs `set_property top top [current_fileset]` followed by
  `update_compile_order -fileset sources_1` and `update_compile_order -fileset sim_1`
  (<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Compilation-with-a-Project-Flow>).
- If you use `synth_design -rtl`-style flows in a project, `find_top` returns candidate tops:
  `synth_design -top [lindex [find_top] 0]` (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/synth_design>).

### 3.4 Runs: create, configure, launch, wait

```tcl
create_run [‑constrset <arg>] [‑parent_run <arg>] [‑part <arg>] ‑flow <arg> [‑strategy <arg>] [‑report_strategy <arg>] [‑pr_config <arg>] [‑dfx_mode <arg>] [‑rm_instance <arg>] [‑quiet] [‑verbose] <name>
launch_runs [‑jobs <arg>] [‑scripts_only] [‑lsf <arg>] [‑sge <arg>] [‑cluster_configuration <arg>] [‑dir <arg>] [‑to_step <arg>] [‑next_step] [‑host <args>] [‑remote_cmd <arg>] [‑email_to <args>] [‑email_all] [‑pre_launch_script <arg>] [‑post_launch_script <arg>] [‑custom_script <arg>] [‑force] [‑quiet] [‑verbose] <runs>...
wait_on_runs [‑timeout <arg>] [‑exit_condition <arg>] [‑quiet] [‑verbose] <runs>...
```

Key facts, all from <https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/launch_runs> and
<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/wait_on_runs>:

- A run must exist (`create_run`) and be configured (`set_property`) before `launch_runs`.
- **To launch an implementation run, the parent synthesis run must already be complete.**
- `-jobs <n>`: number of parallel jobs on the local host (default 1). For remote hosts use
  `-host {machine1 2}`, optionally with `-remote_cmd`, `-email_to`, `-pre_launch_script`, `-post_launch_script`.
- `-to_step <arg>`: stop after a given implementation step, e.g. `place_design`. Valid implementation
  steps listed by AMD: `opt_design`, `power_opt_design`, `place_design`, (post-place) `power_opt_design`,
  `phys_opt_design`, `route_design`, `write_bitstream`. **Ignore `-to_step` when launching several runs**, and it is
  mutually exclusive with `-next_step`.
- *"the specified `-to_step` must be enabled for the implementation run using the `set_property`
  command, or the Vivado tool will return an error"* — e.g. enable physical optimization with
  `set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]`.
- `-scripts_only` writes a `runme.bat` per run instead of launching.
- `wait_on_runs -timeout <minutes>` (default `-1` = wait forever) and
  `-exit_condition {ALL|ANY_ONE|ANY_ONE_MET_TIMING}` (default `ALL`).
- The documented way to know a run **succeeded**:

```tcl
launch_runs synth_1
wait_on_runs synth_1
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    error "ERROR: synth_1 failed"
}
```

(Vivado's own example, <https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/wait_on_runs>.)

⚠ **Singular/plural naming changed in the docs.** `wait_on_run` is the documented command in UG835
v2018.1 and v2020.1; **`wait_on_runs`** is documented from v2022.1 onward (verified by grepping the
official PDFs). `reset_run` → **`reset_runs`** changed the same way (singular through v2018.1, plural
from v2020.1). UG894's v2026.1 sample scripts still *use* the singular `wait_on_run`; the reference
pages document the plural form. **In generated scripts, use the plural forms** (`wait_on_runs`,
`reset_runs`) — they are what current documentation defines.

Design directives/strategies are run properties:

```tcl
set_property STEPS.SYNTH_DESIGN.ARGS.GATED_CLOCK_CONVERSION on [get_runs synth_1]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.OPT_DESIGN.TCL.PRE  [pwd]/pre_opt_design.tcl [get_runs impl_1]
set_property STEPS.OPT_DESIGN.TCL.POST [pwd]/post_opt_design.tcl [get_runs impl_1]
set_property STEPS.ROUTE_DESIGN.TCL.POST [pwd]/post_route.tcl [get_runs impl_1]
```

(`STEPS.*.IS_ENABLED` and `STEPS.*.TCL.PRE/POST` verified in UG835 v2026.1 launch_runs examples and
in the UG894 project-flow sample script,
<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Compilation-with-a-Project-Flow>,
<https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/Configuring-Synthesis-and-Implementation-Runs>.)

### 3.5 Open a result and report

```tcl
open_run [‑name <arg>] [‑pr_config <arg>] [‑quiet] [‑verbose] <run>
```

`open_run synth_1 -name netlist_1` opens a synthesized design from a run
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/synth_design> example; the command itself is
part of the project-mode API). Then report:

```tcl
open_run impl_1
report_utilization  -file $out/util.rpt
report_timing_summary -file $out/timing.rpt
report_drc          -file $out/drc.rpt
```

Exact syntax of the three workhorse reports (UG835 v2026.1):

```tcl
report_utilization   [‑file <arg>] [‑json <arg>] [‑append] [‑pblocks <args>] [‑evaluate_pblock] [‑exclude_child_pblocks] [‑exclude_non_assigned] [‑cells <args>] [‑return_string] [‑slr] [‑packthru] [‑name <arg>] [‑no_primitives] [‑omit_locs] [‑hierarchical] [‑spreadsheet_file <arg>] [‑spreadsheet_table <arg>] [‑spreadsheet_depth <arg>] [‑hierarchical_depth <arg>] [‑hierarchical_percentages] [‑hierarchical_min_primitive_count <arg>] [‑quiet] [‑verbose]

report_timing_summary [‑check_timing_verbose] [‑delay_type <arg>] [‑no_detailed_paths] [‑setup] [‑hold] [‑max_paths <arg>] [‑nworst <arg>] [‑unique_pins] [‑path_type <arg>] [‑no_reused_label] [‑input_pins] [‑no_pr_attribute] [‑no_pblock] [‑routable_nets] [‑inter_slr <arg>] [‑slack_lesser_than <arg>] [‑report_unconstrained] [‑significant_digits <arg>] [‑no_header] [‑file <arg>] [‑append] [‑name <arg>] [‑return_string] [‑warn_on_violation] [‑datasheet] [‑cells <args>] [‑rpx <arg>] [‑quiet] [‑verbose]

report_drc           [‑name <arg>] [‑upgrade_cw] [‑checks <args>] [‑ruledecks <args>] [‑file <arg>] [‑rpx <arg>] [‑append] [‑waived] [‑no_waivers] [‑return_string] [‑json <arg>] [‑quiet] [‑verbose]
```

Notes:

- `report_drc` requires an **open design**; violations become objects readable with `get_drc_violations`,
  and rule decks with `get_drc_ruledecks` / `get_drc_checks`
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_drc>). Methodology DRCs live behind a
  separate command, `report_methodology` (same argument family).
- `report_timing_summary` "runs on an open Synthesized or Implemented Design";
  `-warn_on_violation` turns an unmet timing constraint into a Tcl-visible warning;
  `-return_string` (and `-json` on several reports) makes the report machine-readable
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_timing_summary>).
- Every `report_*` in UG835 shares the `-file` / `-append` / `-return_string` / `-quiet` / `-verbose`
  family, and `-quiet` **swallows errors inside the command** — do not use it in CI.

Timing pass/fail from Tcl (used by the sample scripts in §12):

```tcl
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
if {$wns < 0} { puts "TIMING FAIL: WNS=$wns ns" }
```

This exact idiom appears in AMD's own non-project sample
(<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Compilation-with-a-Non-Project-Flow>), and
`get_timing_paths` supports `-max_paths`, `-nworst`, `-setup`, `-hold`, `-slack_lesser_than`,
`-filter`, and `-return_string` (UG835 `get_timing_paths`).

### 3.6 Bitstream

```tcl
write_bitstream [‑force] [‑verbose] [‑raw_bitfile] [‑no_binary_bitfile] [‑mask_file] [‑readback_file] [‑logic_location_file] [‑bin_file] [‑reference_bitfile <arg>] [‑cell <arg>] [‑no_partial_bitfile] [‑quiet] <file>
```

- *"Writes a bitstream file for the current project. This command must be run on an Implemented
  Design. The bitstream written will be based on the open Implemented Design."*
- `-bin_file` also emits the header-less `.bin` (what flash programmers want).
- Compression: `set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]`.
- Encryption properties: `BITSTREAM.ENCRYPTION.ENCRYPT`, `…ENCRYPTKEYSELECT {BBRAM|EFUSE}`, `…KEY0`.
  ⚠ eFUSE key programming is one-time and irreversible — never do it automatically.
- Debug probes for hardware debug: `write_debug_probes [‑cell <arg>] [‑no_partial_ltxfile] [‑force] [‑quiet] [‑verbose] <file>`
  → `.ltx` (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_debug_probes>).
- (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_bitstream>)

### 3.7 Export the hardware platform (XSA) for Vitis / software

```tcl
write_hw_platform [‑fixed] [‑force] [‑include_bit] [‑include_bin] [‑include_sim_content] [‑minimal] [‑hw] [‑hw_emu] [‑rp <arg>] [‑rm <arg>] [‑static] [‑quiet] [‑verbose] [<file>]
```

- `<file>` must be `<name>.xsa`; it is **required** by the command reference.
- `-fixed` writes a fixed shell usable for software development but not for acceleration;
  `-force` overwrites; `-include_bit` keeps the bitstream inside the XSA (otherwise *"By default MCS
  files are created by write_hw_platform, and the bitstreams are discarded"*).
- AMD's canonical examples: `write_hw_platform -force C:/Data/vck190.xsa` and
  `write_hw_platform -hw_emu C:/Data/vck190.xsa`
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_hw_platform>).
- **Typical agent call:** `write_hw_platform -fixed -include_bit -force $out/$proj.xsa`
  (`-fixed` + `-include_bit` is the documented combination for a software-only platform,
  <https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Using-Project-Mode-vs.-Non-Project-Mode> region / UG1393 fixed-platform flow).
- ⚠ The design must be **synthesized, implemented or a checkpoint** — otherwise the tool answers
  `ERROR: [Common 17-69] Command failed: write_hw_platform is only supported for synthesized,
  implemented, or checkpoint …` (AMD forum thread
  <https://adaptivesupport.amd.com/s/question/0D52E00006ynOdKSAU/about-common-1769>).

**Version history of `write_hw_platform` (verified from the official PDFs):**

| Version | Option set |
|---|---|
| v2020.1 | `[-fixed] [-force] [-include_bit] [-minimal] [-quiet] [-verbose] [<file>]` |
| v2022.1 | + `[-include_sim_content] [-hw] [-hw_emu] [-rp <arg>] [-rm <arg>] [-static]` |
| v2026.1 | + `[-include_bin]` (the only addition since 2022.1) |

**`write_hwdef` (the older `.hwdef` path)** is present in UG835 v2018.1 and v2020.1
(`write_hwdef [-force] [-quiet] [-verbose] <file>`, *"Writes a hardware definition (.hwdef) file for
use in the software development tools (SDK)"*), and is **absent** from UG835 v2022.1 and v2026.1
(0 occurrences by grep). So: it disappeared between 2020.1 and 2022.1 — the exact removal release is
⚠ unverified; treat `write_hw_platform … .xsa` as the only supported export path in modern versions.

---

## 4. Non-Project Mode — full flow, exact syntax

No `.xpr`, no runs, no automatic reports. AMD's own complete example is at
<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Compilation-with-a-Non-Project-Flow>
(reproduced and hardened in §12.3).

### 4.1 Read sources and constraints

```tcl
read_vhdl     ‑library <arg> [‑vhdl2008] [‑vhdl2019] [‑quiet] [‑verbose] <files>
read_verilog  [‑library <arg>] [‑sv] [‑quiet] [‑verbose] <files>...
read_xdc      [‑cells <args>] [‑ref <arg>] [‑quiet_diff_pairs] [‑mode <arg>] [‑unmanaged] [‑no_add] [‑quiet] [‑verbose] <files>
```

- `read_vhdl`: the default VHDL library is `xil_defaultlib`; use `-library <lib>` for others
  (AMD example: `read_vhdl -library bftLib [glob ./Sources/hdl/bftLib/*.vhdl]`).
- `read_verilog -sv { f1.sv f2.sv }` creates a SystemVerilog compilation unit.
- `read_xdc` *"imports … into the current_instance level of the design hierarchy, which defaults to
  the top-level"*; **`⚠` constraints from the XDC overwrite existing constraints of the same name**.
- All three are documented as the non-project counterparts of `add_files`, *"when there is no project
  file to maintain and manage the various project source files."*
- (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/read_vhdl>,
  <https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/read_verilog>,
  <https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/read_xdc>)

### 4.2 Synthesize

```tcl
synth_design [‑name <arg>] [‑part <arg>] [‑constrset <arg>] [‑top <arg>] [‑include_dirs <args>] [‑generic <args>] [‑define <args>] [‑verilog_define <args>] [‑vhdl_define <args>] [‑flatten_hierarchy <arg>] [‑gated_clock_conversion <arg>] [‑directive <arg>] [‑rtl] [‑lint] [‑file <arg>] [‑bufg <arg>] [‑no_lc] [‑lut_cascade] [‑shreg_min_size <arg>] [‑mode <arg>] [‑fsm_extraction <arg>] [‑rtl_skip_mlo] [‑rtl_skip_ip] [‑rtl_skip_constraints] [‑srl_style <arg>] [‑keep_equivalent_registers] [‑resource_sharing <arg>] [‑cascade_dsp <arg>] [‑control_set_opt_threshold <arg>] [‑incremental_mode <arg>] [‑max_bram <arg>] [‑max_uram <arg>] [‑max_dsp <arg>] [‑max_bram_cascade_height <arg>] [‑max_uram_cascade_height <arg>] [‑global_retiming <arg>] [‑no_srlextract] [‑assert] [‑no_timing_driven] …
```

AMD's canonical non-project call: `synth_design -top top -part xc7k70tfbg676-2 -flatten_hierarchy none`
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/synth_design>). `-rtl -name rtl_1` only
elaborates and opens an RTL design (useful for early DRC/lint).

### 4.3 Checkpoints

```tcl
write_checkpoint [‑force] [‑cell <arg>] [‑logic_function_stripped] [‑encrypt] [‑key <arg>] [‑quiet] [‑verbose] [<file>]
read_checkpoint  [‑cell <arg>] [‑incremental] [‑directive <arg>] [‑auto_incremental] [‑fix_objects <args>] [‑dcp_cell_list <args>] [‑force_incr] [‑quiet] [‑verbose] [<file>]
open_checkpoint  [‑part <arg>] [‑ignore_timing] [‑quiet] [‑verbose] <file>
link_design      [‑name <arg>] [‑part <arg>] [‑constrset <arg>] [‑top <arg>] [‑mode <arg>] [‑pr_config <arg>] [‑reconfig_partitions <args>] [‑partitions <args>] [‑ignore_timing] [‑quiet] [‑verbose]
```

- `write_checkpoint` saves netlist+constraints(+placement/routing if present). The tool appends `.dcp`
  if you omit the extension. In project mode a synthesis DCP carries no timing constraints until
  `open_run`/`link_design` annotates them
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_checkpoint>).
- `open_checkpoint` is the non-project way to reopen a saved stage; `read_checkpoint` + `link_design`
  is the pattern for *importing* a netlist (e.g. third-party synthesis output).
- `read_checkpoint -incremental <routed.dcp>` / `-auto_incremental` enable incremental place & route
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/read_checkpoint>).
- `link_design` requires `DESIGN_MODE == GateLvl` for netlist designs; otherwise the tool errors with
  `ERROR: The design mode of 'sources_1' must be GateLvl.` The `-top` switch is required for
  third-party netlists. For RTL projects use `launch_runs` + `open_run` instead
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/link_design>).

### 4.4 Implement

```tcl
opt_design    [‑retarget] [‑propconst] [‑sweep] [‑bram_power_opt] [‑remap] [‑aggressive_remap] [‑resynth_remap] [‑resynth_area] [‑resynth_seq_area] [‑directive <arg>] [‑muxf_remap] [‑hier_fanout_limit <arg>] [‑bufg_opt] [‑mbufg_opt] [‑shift_register_opt] [‑dsp_register_opt] [‑srl_remap_modes <arg>] [‑control_set_merge] [‑control_set_opt] [‑merge_equivalent_drivers] [‑carry_remap] [‑memory_opt] [‑property_opt_only] [‑quiet] [‑verbose]
place_design  [‑directive <arg>] [‑subdirective <args>] [‑no_timing_driven] [‑eco] [‑timing_summary] [‑unplace] [‑post_place_opt] [‑no_psip] [‑psip_options <args>] [‑sll_align_opt] [‑clock_vtree_type <arg>] [‑no_bufg_opt] [‑ultrathreads] [‑no_noc_opt] [‑net_delay_weight <arg>] [‑quiet] [‑verbose]
phys_opt_design [‑fanout_opt] [‑placement_opt] [‑routing_opt] [‑slr_crossing_opt] [‑insert_negative_edge_ffs] [‑restruct_opt] [‑interconnect_retime] [‑lut_opt] [‑casc_opt] [‑cell_group_opt] [‑equ_drivers_opt] [‑critical_cell_opt] [‑dsp_register_opt] [‑bram_register_opt] [‑uram_register_opt] [‑bram_enable_opt] [‑shift_register_opt] [‑hold_fix] [‑aggressive_hold_fix] [‑retime] [‑force_replication_on_nets <args>] [‑directive <arg>] [‑critical_pin_opt] [‑clock_opt] [‑path_groups <args>] [‑tns_cleanup] [‑sll_reg_hold_fix] [‑memory_rewire_opt] [‑quiet] [‑verbose]
route_design  [‑unroute] [‑release_memory] [‑nets <args>] [‑physical_nets] [‑pins <arg>] [‑directive <arg>] [‑tns_cleanup] [‑no_timing_driven] [‑preserve] [‑delay] [‑auto_delay] ‑max_delay <arg> ‑min_delay <arg> [‑timing_summary] [‑finalize] [‑ultrathreads] [‑eco] [‑no_psir] [‑quiet] [‑verbose]
```

Behavioural facts worth encoding in an agent:

- `opt_design` "performs all four default optimizations: retarget, constant propagation, sweep, and
  Block RAM power optimization" — and *enabling some options explicitly disables the others*
  (`opt_design -sweep -retarget` "implicitly disabled" constant propagation and BRAM power opt).
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/opt_design>)
- `place_design -directive Explore` for hard designs; `-post_place_opt` then `phys_opt_design` then
  `route_design` is AMD's documented loop for post-place optimization
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/place_design>).
- `phys_opt_design` **requires a placed design** ("cannot be run prior to placement") and is normally
  run twice: post-place and post-route. Directives include `Explore`, `ExploreWithHoldFix`,
  `AggressiveFanoutOpt`.
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/phys_opt_design>)
- `route_design -nets <nets>` / `-pins <pins>` routes a subset; `-unroute` unroutes; `-directive
  RuntimeOptimized|Explore|…` picks a routing strategy. It can be multi-threaded via
  `general.maxThreads`.
  (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/route_design>)
- All three are multi-threadable: *"Refer to the `set_param` command for more information on setting
  the `general.maxThreads` parameter."* (same pages).

### 4.5 Non-project reporting and bitstream

Use the same `report_*` commands as §3.5 (reporting commands are *mode-agnostic*, per UG892), plus
`report_route_status` and `report_clock_utilization`, exactly as AMD's non-project sample does:

```tcl
route_design
write_checkpoint -force $outputDir/post_route.dcp
report_route_status -file $outputDir/post_route_status.rpt
report_timing_summary -file $outputDir/post_route_timing_summary.rpt
report_power -file $outputDir/post_route_power.rpt
report_drc -file $outputDir/post_imp_drc.rpt
write_verilog -force $outputDir/cpu_impl_netlist.v -mode timesim -sdf_anno true
write_bitstream -force $outputDir/cpu.bit
```

(<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Compilation-with-a-Non-Project-Flow>)

---

## 5. State introspection and run recovery

| Need | Command / property | Source |
|---|---|---|
| list runs | `get_runs [patterns] [-filter <expr>] [-regexp] [-nocase] [-of_objects …]` | UG835 `get_runs` |
| incomplete runs | `get_runs -filter {PROGRESS < 100}` | UG835 `get_runs` example |
| current run | `current_run [-synthesis|-implementation] [<run>]`, `current_run -implementation -quiet` | UG835 `current_run` |
| completion | `get_property PROGRESS [get_runs impl_1]` → `"100%"` | UG835 `wait_on_runs` |
| human status | `get_property STATUS [get_runs synth_1]` | AR 47491 |
| staleness | `get_property NEEDS_REFRESH [get_runs synth_1]` → `1` when a source changed | AR 47491 |
| stale report | `report_run_status [-quiet] [-verbose] <runs>` "Report reason for staleness of run." | UG835 `report_run_status` |
| reset and relaunch | `reset_runs [-prev_step] [-from_step <arg>] [-quiet] [-verbose] <runs>...` | UG835 `reset_runs` |
| open a stage | `open_run <run>` | UG835 `open_run` |

> AR 47491 states plainly: *"There is no single status check that can be performed to accomplish this
> goal in a Tcl script. However, there are multiple checks which can be done… Customers can use the
> `get_property` command… `STATUS [get_runs synth_1]`, `get_property PROGRESS [get_runs synth_1]` →
> `100%`, `get_property NEEDS_REFRESH [get_runs synth_1]` → `1`."*
> (<https://adaptivesupport.amd.com/s/article/47491>)

**Robust run checker (use this instead of trying to parse the process exit status):**

```tcl
proc assert_run_ok {run_name} {
    set st  [get_property STATUS       [get_runs $run_name]]
    set pr  [get_property PROGRESS     [get_runs $run_name]]
    set nr  [get_property NEEDS_REFRESH [get_runs $run_name]]
    puts "RUN $run_name : STATUS='$st' PROGRESS='$pr' NEEDS_REFRESH='$nr'"
    if {$pr ne "100%"}  { error "RUN FAILED: $run_name stopped at $pr (STATUS='$st')" }
    if {$nr}            { puts "WARNING: $run_name NEEDS_REFRESH=1 (sources changed since the run)" }
}
```

⚠ Exact `STATUS` strings are version/flow dependent (`synth_design Complete!`, `route_design Complete!`,
older ISE-era strings such as `XST Complete!` appear in AR 47491). **Gate on `PROGRESS`, log `STATUS`.**

---

## 6. Parallelism and resource control

| Knob | Scope | Command | Notes |
|---|---|---|---|
| `-jobs <n>` | *number of concurrent runs* (separate `vivado` processes / OOC module runs) | `launch_runs synth_1 -jobs 8`, `launch_runs impl_1 -jobs 8` | default 1; ignored/overridden per host when `-host` is used |
| `general.maxThreads` | threads **inside** one step | `set_param general.maxThreads 8`, read back with `get_param general.MaxThreads` | referenced by `synth_design`, `place_design`, `route_design`, `phys_opt_design`, `report_timing_summary` docs |
| `-host {machine n}` | distributed jobs | `launch_runs impl_1 -host {machine1 2} -host {machine2 4}` | needs `-remote_cmd` if ssh differs from the default |
| `-scripts_only` | generate `runme.bat` per run, launch nothing | `launch_runs impl_1 -scripts_only` | useful to let an external scheduler drive the runs |
| `-ultrathreads` | faster implementation steps | `place_design -ultrathreads`, `route_design -ultrathreads` | present in v2026.1 syntax for both commands |

Sources: <https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/launch_runs> (`-jobs`, `-host`,
`-scripts_only`), UG835 `set_param`/`get_param` pages, and the per-command "multi-threaded" notes
(§4.4, §3.5). Practical rule for CI: `-jobs` = number of synthesis/implementation runs to interleave;
`general.maxThreads` = cores available to each step; do not set both to the machine core count.

---

## 7. Tcl error handling that actually protects the build

### 7.1 `catch` / `error` / `errorInfo`

AMD's documented pattern (<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Handling-Tcl-Errors>):

```tcl
if {[catch { some_command } errorstring]} {
    puts "Error - $errorstring"
} else {
    puts "The code completed successfully"
}
```

`catch` returns 1 when a `TCL_ERROR` was caught, 0 otherwise; the optional second variable receives
the message. `error "message"` raises a user error (used to *bubble* a caught error upward, or to fail
on an unexpected condition). UG835 adds that Vivado commands return `TCL_OK`/`TCL_ERROR` and set the
global `$ERRORINFO`, printable with `puts $ERRORINFO`, which includes the failing command and line:

```
Line 6: Vivado% puts $errorInfo
Line 7: ERROR: [HD-Tcl 53] Cannot specify '-patterns' with '-of_objects'.
          While executing "get_ports -of objects $pin" (procedure "my_report" line 6)
```

(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/Introduction>, section *Return Codes*.)

**Agent-safe wrapper used throughout §12:**

```tcl
proc step {label script} {
    puts "==> $label"
    if {[catch {uplevel 1 $script} msg]} {
        puts "ERROR: step '$label' failed: $msg"
        puts "ERRORINFO: $::errorInfo"
        exit 1
    }
}
set ok 0
step "create project" { create_project ... }
```

Also documented: when a command errors out of a script, *"further execution of subsequent commands is
halted"* — that is the default, and it is what you want in a build.
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/Errors-Warnings-Critical-Warnings-and-Info-Messages>)

### 7.2 Command-line arguments (`-tclargs`)

`-tclargs` values arrive in the script's `argv` (list) / `argc`. AMD gives a full argument-parsing
proc using an `lshift` helper and a `switch -exact` loop
(<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Parsing-Command-Line-Arguments>):

```tcl
proc lshift {listVar} {
    upvar 1 $listVar L
    set r [lindex $L 0]
    set L [lreplace $L [set L 0] 0]
    return $r
}

proc parse_args {args} {
    while {[llength $args]} {
        set flag [lshift args]
        switch -exact -- $flag {
            -p - -ports { set ports [lshift args] }
            -v - -verbose { set verbose 1 }
            -h - -help { set help 1 }
            default { error "unknown option $flag" }
        }
    }
}
parse_args {*}$argv
```

Simplest robust variant used in §12 (supports `KEY=value` and bare flags):

```tcl
foreach a $argv {
    if {[regexp {^([A-Za-z_][A-Za-z0-9_]*)=(.*)$} $a -> k v]} {
        set ::ARGS($k) $v
    } else { lappend ::FLAGS $a }
}
proc opt {name default} { expr {[info exists ::ARGS($name)] ? $::ARGS($name) : $default} }
set part [opt PART xc7a35tcpg236-1]
```

### 7.3 Other script hygiene rules from AMD

- In batch mode, unknown commands are **not** forwarded to the OS → always use `exec`
  (<https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/Vivado-Integrated-Design-Environment-IDE/Tcl-Modes-versus-Batch-Mode>).
- Use `file mkdir` (Tcl) rather than shell `mkdir`; AMD's samples start with
  `set outputDir ./Tutorial_Created_Data/…; file mkdir $outputDir`.
- Syntax-check HDL before a long run: `check_syntax [-fileset <arg>] [-return_string] [-quiet] [-verbose]`.
- `-quiet` is a trap for CI (see §2.4). Use it only where an empty/absent object is legitimate.
- Reuse the journal: every GUI action is a Tcl command recorded in `vivado.jou`; *"You can use this
  file to develop scripts for either mode."*
  (<https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/Tcl-Command-Differences-in-Project-Mode-and-Non-Project-Mode>)

---

## 8. Logs, messages, and how to read them

### 8.1 Files produced by a run

| File | Written by | Contents / use |
|---|---|---|
| `vivado.log` | every session (unless `-nolog`) | full transcript of messages for the session |
| `vivado.jou` | every session (unless `-nojournal`) | the Tcl commands that were issued — replayable script |
| `vivado_<id>.backup.log` / `.backup.jou` | on launch | previous session's log/journal |
| `<project>.runs/<run>/runme.log` | each run | the run-local log: **this is where synthesis/implementation errors actually live** |
| `<project>.runs/<run>/runme.bat` / `runme.sh` | `launch_runs -scripts_only` | the exact command line that would run the step |
| `.Xil/`, `*.dcp`, `*.rpt`, `*.bit`, `<project>.cache/`, `<project>.hw/`, `<project>.gen/`, `<project>.ip_user_files/`, `<project>.sim/` | tool | outputs and caches (git-ignored, §10) |

Log/journal locations: *"The default location of the journal and log files depend on the operating
system: … Linux: directory from which Vivado IDE is opened"*, and *"use the `vivado -log` and
`-journal` options to specify a location."*
(<https://docs.amd.com/r/en-US/ug893-vivado-ide/Output-Files>)
`launch_runs -scripts_only` writes `runme.bat` per run
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/launch_runs>).

### 8.2 Message anatomy

> "Messages that result from individual commands appear in the log file… These messages are generally
> numbered to identify specific issues and are prefixed in the log file with 'INFO', 'WARNING',
> 'CRITICAL_Warning', 'ERROR' followed by a subsystem identifier and a unique number."
> Example: `INFO: [HD-LIB 1] Done reading timing library`
> (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/Errors-Warnings-Critical-Warnings-and-Info-Messages>)

Severity ladder: `INFO` (== `STATUS` but with an ID) < `WARNING` < `CRITICAL WARNING` < `ERROR`.
Only `ERROR` stops the script by default.

### 8.3 Subsystem IDs an agent will meet constantly

| Prefix | Subsystem | Typical meaning | Example |
|---|---|---|---|
| `[Common 17-*]` | Tcl/command infrastructure | argument errors, command failed, message-limit rules, licensing features | `[Common 17-69] Command failed`, `[Common 17-55] 'set_property' expects at least one object`, `[Common 17-165] Too many positional options`, `[Common 17-239] ERROR Messages are prohibited to be downgraded` |
| `[Vivado 12-*]` | constraints / design database | constraint object not found, illegal placement, DRC before bitgen | `[Vivado 12-584] No ports matched '<x>'`, `[Vivado 12-1387] No valid object(s) found for …`, `[Vivado 12-1411] Cannot set LOC property of ports`, `[Vivado 12-1345] Error(s) found during DRC. Bitgen not run` |
| `[Synth 8-*]` | Vivado synthesis (HDL) | inferred latches, multi-driven nets, bad port connections, unknown clocks | `[Synth 8-327] inferring latch`, `[Synth 8-6859] multi-driven net`, `[Synth 8-448] named port connection … does not exist`, `[Synth 8-3321] create_clock … unknown port/pin`, `[Synth 8-3917] port … driven by constant` |
| `[Place 30-*]` | placer | infeasible IO placement, poor IO/BUFG pairing, placer aborted | `[Place 30-58] IO placement is infeasible`, `[Place 30-99] Placer failed with error: …`, `[Place 30-574] Poor placement for routing between an IO pin and BUFG` |
| `[Drc 23-*]` / `[DRC *-*]` | design rule checks | rule violation, reported by `report_drc` and by bitstream generation | `[Drc 23-20] Rule violation (NSTD-1) Unspecified I/O Standard`, `[DRC UCIO-1] Unconstrained Logical Port` |
| `[IP_Flow 19-*]` | IP packaging/instantiation | locked IP, missing IP definition | `[IP_Flow 19-2162] IP 'x' is locked` |
| `[Board 49-67]` | board part | `board_part` definition not found (CRITICAL WARNING) | board file not installed / wrong board_part |
| `[Netlist 29-*]`, `[Project 1-560]` | netlist elaboration | unresolved black box | `CRITICAL WARNING: [Netlist 29-69] … ` |
| `[Simulator 14-*]`, `[USF-XSim 62-*]`, `[Vivado 12-4473]` | simulation launcher | simulation failed | `Detected error while running simulation` |
| `[HD-Tcl *]` | HD/Tcl bindings | bad argument combination inside a command | `[HD-Tcl 53] Cannot specify '-patterns' with '-of_objects'` |
| `[Device 21-436]` | device/part database | installed device family does not contain the part | `No parts matched 'xczu9eg…'` |

(IDs verified: `[Common 17-69]`, `[Common 17-55]`, `[Common 17-81]`, `[Common 17-239]`,
`[Common 17-361]`, `[HD-Tcl 53]` in UG835 v2026.1; `[Common 17-165]` in AR 46668; the rest in the ARs
and forum threads tabulated in §11.)

### 8.4 Message control from Tcl

```tcl
set_msg_config [‑id <arg>] [‑string <args>] [‑severity <arg>] ‑limit <arg> [‑new_severity <arg>] [‑suppress] [‑regexp] [‑quiet] [‑verbose]
get_msg_config [‑id <arg>] [‑severity <arg>] [‑rules] [‑limit] [‑count] [‑quiet] [‑verbose]
reset_msg_config …
```

Verified behaviours and examples (UG835 `set_msg_config` / `get_msg_config`):

- One action per call: *"An error is returned if more than one action is attempted in a single
  set_msg_config command."*
- Promote an INFO to a critical warning:
  `set_msg_config -id {[Common 17-81]} -new_severity "CRITICAL WARNING"`
- **Errors cannot be downgraded**: attempting it yields
  `WARNING: [Common 17-239] ERROR Messages are prohibited to be downgraded. Message 'Common 17-69' is not downgraded.`
- Target warnings containing a string: `set_msg_config -severity warning -string "clk" -id "17-35" -new_severity error`
- Limits: the default message limit is **100**; `set_msg_config -id {[Common 17-349]} -limit 10`
  (UG893 <https://docs.amd.com/r/en-US/ug893-vivado-ide/Suppressing-Messages>).
- Suppress entirely: `set_msg_config -id {…} -suppress`; restore with `reset_msg_config`.
- Inspect: `get_msg_config -rules` prints the rule table with current counts; `-count` gives the number
  of messages already emitted for an ID/severity. `-count` only counts the *launching* process, not
  sub-processes (`get_msg_config` doc).
- Severity change from the GUI equivalent: AMD's documented example promotes `Place 30-12`:
  `set_msg_config -id {Place 30-12} -new_severity {CRITICAL WARNING}`
  (<https://docs.amd.com/r/en-US/ug893-vivado-ide/Changing-Message-Severity>).
- Demoting critical warnings is explicitly dangerous: *"Use caution when demoting critical warnings,
  because these messages flag problems that might result in errors later in the design flow."* (same page).

**Promote-to-error recipe for CI** (fail the build on the quality warnings you care about):

```tcl
foreach id {{Synth 8-327} {Synth 8-6859} {Vivado 12-584} {Place 30-574}} {
    set_msg_config -id $id -new_severity ERROR
}
```

⚠ `-id` strings are matched with the bracketed form for some IDs
(UG835 shows both `-id "Synth 8-32"` and `-id {[Synth 8-32]}`); when in doubt pass the braced form.

### 8.5 Log triage recipes

```bash
# hard failures of the session
grep -n '^ERROR:' vivado.log
# run-local failures (synthesis/implementation)
grep -n -E '^ERROR:|^CRITICAL WARNING:' <project>.runs/impl_1/runme.log
# step boundaries and progress
grep -n -E "Starting (Synthesis|Implementation)|Phase |Command:|Finished" <project>.runs/impl_1/runme.log
# message-ID histogram (what to fix first)
grep -o -E '\[(Common|Synth|Place|Route|Vivado|Drc|DRC|IP_Flow|Netlist|Board)[^]]*\]' vivado.log | sort | uniq -c | sort -rn | head -20
# timing verdict
grep -E 'Timing constraints are not met|All user specified timing constraints are met' vivado.log
```

---

## 9. Programming the device (Hardware Manager over `hw_server`)

### 9.1 Connection sequence

AMD documents the Hardware Manager Tcl sequence as: **open the manager → connect to the server →
select the target → open the target** (and then program the device):

> "To access an AMD FPGA through the Hardware Manager, you must use the following Tcl command
> sequence: `open_hw` – Opens the Hardware Manager … `connect_hw_server` – Makes a connection to a
> local or remote Vivado hardware server application; `current_hw_target` – Defines the hardware
> target of the connected server; `open_hw_target` – Opens a connection to the hardware target."
> (<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/program_hw_devices>)

⚠ **Naming history:** the command reference page in v2026.1 is **`open_hw_manager`**
(`open_hw_manager [-quiet] [-verbose]`), and it exists as a documented command from **UG835 v2020.1**
onward; UG835 **v2018.1** documents **`open_hw`** instead. The `program_hw_devices` / `connect_hw_server`
*description* text still says "open_hw" (documentation lag). **Use `open_hw_manager` on 2020.1+.**
Both were verified by grepping the official PDFs.

Exact syntax (UG835 v2026.1):

```tcl
open_hw_manager   [‑quiet] [‑verbose]
connect_hw_server [‑url <arg>] [‑cs_url <arg>] [‑quiet] [‑verbose]        ;# default url localhost:3121
open_hw_target    [‑jtag_mode <arg>] [‑xvc_url <arg>] [‑auto_calibrate] [‑quiet] [‑verbose] [<hw_target>]
current_hw_target [‑quiet] [‑verbose] [<hw_target>]
current_hw_device [‑quiet] [‑verbose] [<hw_device>]
get_hw_targets    [‑of_objects <args>] [‑regexp] [‑nocase] [‑filter <arg>] [‑quiet] [‑verbose] [<patterns>]
get_hw_devices    [‑of_objects <args>] [‑regexp] [‑nocase] [‑filter <arg>] [‑quiet] [‑verbose] [<patterns>]
refresh_hw_device [‑update_hw_probes <arg>] [‑disable_done_check] [‑force_poll] [‑quiet] [‑verbose] [<hw_device>]
program_hw_devices [‑key <arg>] [‑clear] [‑skip_program_keys] [‑skip_program_rsa] [‑user_efuse <arg>] [‑user_efuse_128 <arg>] [‑control_efuse <arg>] [‑security_efuse <arg>] [‑only_export_efuse] [‑svf_file <arg>] [‑efuse_export_file <arg>] [‑disable_eos_check] [‑skip_reset] [‑force] [‑append] [‑type <arg>] [‑mpsoc_reset <arg>] [‑controls_efuse <arg>] [‑efuse_json <arg>] [‑select_efuse <arg>] [‑freq_efuse <arg>] [‑verbose] [‑finalize_efuse] [‑quiet] [<hw_device>...]
disconnect_hw_server [‑quiet] [‑verbose] [<hw_server>]
close_hw_target   [‑quiet] [‑verbose] [<hw_target>]
close_hw_manager  [‑quiet] [‑verbose]
```

AMD's documented connection example (serial-number form), including JTAG clock setup:

```tcl
connect_hw_server -url localhost:3121
current_hw_target [get_hw_targets */xilinx_tcf/Digilent/210203339395A]
set_property PARAM.FREQUENCY 15000000 [get_hw_targets */xilinx_tcf/Digilent/210203339395A]
open_hw_target
```

(<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Opening-a-Hardware-Target-Using-Tcl-Commands>)

### 9.2 Associate a bitstream and program

```tcl
# bitstream first, then program (project or non-project session)
set_property PROGRAM.FILE {/abs/path/design.bit} [get_hw_devices <part_or_index>]
set_property PROBES.FILE   {/abs/path/design.ltx} [get_hw_devices <part_or_index>]   ;# only for ILA/VIO debug
program_hw_devices [lindex [get_hw_devices] 0]
```

- The property names `PROGRAM.FILE` / `PROBES.FILE` are the ones used across UG908's programming flow
  (<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Associating-a-Programming-File-with-the-Hardware-Device>).
- AMD's own example for "program the first device in the JTAG chain":
  `program_hw_devices [lindex [get_hw_devices] 0]`
  (<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device>).
- Versal devices take a `.pdi` instead of `.bit` in `PROGRAM.FILE`.

### 9.3 Verify the programming worked

```tcl
# 7 series / UltraScale / UltraScale+ — first device
get_property REGISTER.IR.BIT5_DONE [lindex [get_hw_devices] 0]
# Versal — index 1 is the arm_dap in a single-device chain
get_property REGISTER.JTAG_STATUS.BIT[34]_DONE [lindex [get_hw_devices] 1]
# or rescan the device and re-read all its properties
refresh_hw_device [lindex [get_hw_devices] 0]
```

(<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device>)

`refresh_hw_device` "Refreshes the in-memory view of the device by scanning for debug and IBERT cores…
Use the `refresh_hw_device` after the `program_hw_devices` to keep the in-memory hardware debug objects
in sync with the state of the actual cores on the physical device."
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/refresh_hw_device>)

### 9.4 `hw_server` — start it, and its useful options

`hw_server` is the daemon that owns the JTAG cable; `connect_hw_server` talks to it
(<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Connecting-to-a-Hardware-Target-Using-hw_server>).

| Option | Purpose | Example |
|---|---|---|
| `-d` | daemon mode (output to system logger) | `hw_server -d` |
| `-L[file]` | log JTAG commands from clients (`-L-` = stdout) | `hw_server -L-`, `hw_server -Lmy_file.log` |
| `-s<port>` | set listening port | `hw_server -stcp::3122` |
| `-I <seconds>` | exit if no target connects within N s | `hw_server -I 20` |
| `-p[port]` | GDB-server port range (default 3000: Arm, 3001: Arm64, 3002/3003: MicroBlaze, 3004/3005: RISC-V) | `hw_server -p0` disables |
| `--init <file>` | startup option file (env: `HW_SERVER_INIT_FILE`) | `hw_server --init my_init.txt` |
| `-q` | suppress version banner | `hw_server -q` |
| `-e "<cmd>"` | run a command at startup (used for BSCAN user mask) | `hw_server -e "set bscan-switch-user-mask <mask>"` |

(<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Standard-hw_server-Options>,
<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Command-Line-Options-for-hw_server>,
and the BSCAN note in
<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device>)

Remote/XVC: `open_hw_target -xvc_url <host:port>` connects to a Xilinx Virtual Cable instead of a
local cable (UG835 `open_hw_target`; UG908 XVC sections).

JTAG clock rule: *"For non-Versal architectures, if your design contains debug cores, ensure that the
JTAG clock is 2.5 times slower than the debug hub clock."*
(<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device>)
Set it with `set_property PARAM.FREQUENCY <Hz> [get_hw_targets …]`.

---

## 10. Version control (git)

AMD compares two supported revision-control methodologies
(<https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/Comparison-between-Script-based-and-Source-based-Revision-Control-Methodologies>):

| | Script-based | Source-based |
|---|---|---|
| Commit | the *script* that regenerates the project (auto-generate with `write_project_tcl`) | the `.xpr` **and** the `.srcs/` tree |
| Size | small | medium |
| Compile time | slower — BD/IP must be rebuilt/regenerated | medium — available immediately after checkout |
| External sources | versioned separately | versioned separately |
| Read-only capable | BD must be writable (validation rewrites XCI); IP can be locked | same |

AMD's advice: *"With script-based methodology, you must run the script to completion before opening
the project. AMD does not typically revision control output products, so recompiling consumes
considerable compute time."*
(<https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/Script-based-Revision-Control-Methodology>)

Generate the regeneration script:

```tcl
write_project_tcl [‑paths_relative_to <arg>] [‑origin_dir_override <arg>] [‑ip_repo_path <arg>] [‑target_proj_dir <arg>] [‑force] [‑all_properties] [‑no_copy_sources] [‑absolute_remote_path] [‑no_ip_version] [‑absolute_path] [‑dump_project_info] [‑use_bd_files] [‑no_bd_xlnoc] [‑internal] [‑validate] [‑ignore_msg_control_rules] [‑quiet] [‑ignore_utils] [‑verbose] <file>
```

AMD example: `write_project_tcl -target_proj_dir "/tmp/test" ./script/recreate.tcl`
(<https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_project_tcl>).

### 10.1 `.gitignore` for a Vivado project (agent-ready)

```gitignore
# ── Vivado / Vitis generated ────────────────────────────────────────────────
*.Xil/
.Xil/
**/.Xil/
vivado.log
vivado.jou
vivado_*.backup.log
vivado_*.backup.jou
webtalk*.jou
webtalk*.log
usage_statistics_webtalk.*
*.pb
*.str
*.journal
hs_err_pid*.log
vivado_pid*.debug

# Project build products
*.runs/
*.cache/
*.hw/
*.sim/
*.gen/
*.ip_user_files/
*.srcs/**/imports/        # only if you use import_files and keep originals elsewhere

# Reports and bitstreams are build artefacts
*.bit
*.bin
*.rbt
*.msk
*.mcs
*.prm
*.ltx
*.dcp
*.rpt
*.xsa

# Vitis / software build output
*.Xil/
workspace/
Debug/
Release/
*.elf
*.o
*.d

# Editor / OS noise
.vscode/
.idea/
.DS_Store
```

**Do commit:** the `.xpr` (source-based methodology), `*.srcs/**/*.v|.sv|.vhd|.xdc` (your own hand-written
sources only — not `imports/` copies), `*.bd`/`.xci` when you own them, and the regeneration script
from `write_project_tcl` (script-based methodology). **Never commit:** `vivado.log`, `vivado.jou`,
`.Xil/`, any `*.runs/`, `*.cache/`, `*.hw/`, bitstreams or reports you can regenerate.

⚠ `*.dcp` is a judgement call: a reference checkpoint used as an **input** (e.g. incremental
implementation reference, or a delivered netlist) must be committed — artefacts that your own build
produces should not be. AMD's incremental flow explicitly consumes a "high quality reference
checkpoint" (<https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Using-Incremental-Implementation>).

---

## 11. The 25 most common Vivado errors: cause → exact fix

Each row is a real message ID with a verified source. **First rule: never act on the bare ID — the
text after the colon is the diagnosis.** Second rule: `vivado.log` gives the session view,
`<project>.runs/<run>/runme.log` gives the failing step's view.

| # | Message | Cause | Exact fix | Source |
|---|---|---|---|---|
| 1 | `ERROR: [Common 17-69] Command failed: <detail>` | Generic wrapper — the *detail* is the real error | Read the text after `Command failed:`; then `grep -n '^ERROR:' <project>.runs/synth_1/runme.log` | AR 58758, AMD forum (see #2/#3/#4) |
| 2 | `[Common 17-69] Command failed: Synthesis failed - please see the console or run log file for details` | HDL synthesis error | Open `<proj>.runs/synth_1/runme.log`, fix the first `[Synth 8-*]` error, `reset_runs synth_1`, relaunch | <https://adaptivesupport.amd.com/s/question/0D52E00006hpkXhSAI/common-1769-command-failed-synthesis-failed-please-see-the-console-or-run-log-file-for-details> |
| 3 | `[Common 17-69] Command failed: Run 'impl_1' has not been launched. Unable to open` | `open_run`/`write_bitstream` on a run that was never launched (or was reset) | `launch_runs impl_1 -to_step write_bitstream; wait_on_runs impl_1; open_run impl_1` | <https://adaptivesupport.amd.com/s/question/0D5KZ00000Zjjv00AB/error-common-1769-command-failed-run-impl1-has-not-been-launched-unable-to-open> |
| 4 | `[Common 17-69] Command failed: write_hw_platform is only supported for synthesized, implemented, or checkpoint …` | XSA export attempted on an RTL-only design | Finish `synth_design`/`launch_runs impl_1`, then `write_hw_platform -fixed -include_bit -force out.xsa` | <https://adaptivesupport.amd.com/s/question/0D52E00006ynOdKSAU/about-common-1769> |
| 5 | `[Common 17-69] Command failed: This design contains one or more cores for which bitstream generation is not supported` | IP core not licensed/not bitstream-capable for the target device | Check the licence for that IP, or remove/replace the core | <https://adaptivesupport.amd.com/s/article/58758> |
| 6 | `CRITICAL WARNING: [Common 17-55] 'set_property' expects at least one object` | The object query returned an empty collection (typo, wrong hierarchy, constraint applied too early) | Evaluate the query interactively after synthesis (`get_ports`, `get_pins`, `get_cells`), fix the name; only then `set_property` | <https://adaptivesupport.amd.com/s/article/56169> |
| 7 | `WARNING: [Vivado 12-584] No ports matched '<name>'` | XDC/`set_property` targets a port that does not exist at that stage | Correct the port name; if the port is generated by IP, constrain it in the IP's XDC (regenerate IP with the constraint) | AR 56169, AR 58260, AR 54799 |
| 8 | `CRITICAL WARNING: [Vivado 12-1387] No valid object(s) found for <constraint>` | A timing constraint (`create_clock`, `set_input_delay`, `set_false_path`, …) targets a nonexistent object | Verify the object exists post-synthesis; align constraints with the real netlist names; `report_clocks` / `get_clocks` to confirm | AR 57056, AR 54799, AR 69583 |
| 9 | `CRITICAL WARNING: [Vivado 12-1411] Cannot set LOC property of ports` | `PACKAGE_PIN` value invalid for the package, or the port is in a bank/interface that cannot use it | Fix the pin to a legal package pin of the exact part; check for conflicting IOSTANDARD/bank voltage | <https://adaptivesupport.amd.com/s/article/64283> |
| 10 | `ERROR: [Vivado 12-1345] Error(s) found during DRC. Bitgen not run.` | `write_bitstream` blocked by DRC violations | `open_run impl_1; report_drc` → fix each violation (often NSTD-1/UCIO-1, #19/#20) then re-run bitstream | AMD forum question `[Vivado 12-1345] Error(s) found during DRC` |
| 11 | `ERROR: [Synth 8-6859] multi-driven net on pin …` (also CRITICAL WARNING) | Two HDL drivers on the same net (typically a signal driven in two processes or a `reg` plus an `assign`) | Make exactly one driver per net, or merge into a single `always_comb`/process; check tri-state buffers and `initial` blocks | <https://adaptivesupport.amd.com/s/article/1034745> |
| 12 | `WARNING: [Synth 8-327] inferring latch for variable '<x>'` | Incomplete assignment in a combinational `always`/`process` (missing `else`, missing default) | Give every branch a value, or add a default assignment before the `if`/`case` | <https://adaptivesupport.amd.com/s/article/61378> (also UG901 synthesis guide) |
| 13 | `ERROR: [Synth 8-448] named port connection '<p>' does not exist for instance …` | Port name/case mismatch between instantiation and module (often VHDL↔Verilog) | Fix the port name; for IP, regenerate the instantiation template (`write_verilog` on the IP / "Open IP example design") | AMD forum questions for `Synth 8-448` |
| 14 | `WARNING: [Synth 8-3917] design <m> has port P[1] driven by constant` | Input tied to a constant (typo in the instantiation) | Verify the connection; ignore or silence if intentional | AMD forum question for `Synth 8-3917` |
| 15 | `CRITICAL WARNING: [Synth 8-3321] create_clock attempting to set clock on an unknown port/pin` | `create_clock` in an XDC referencing a name that does not exist after elaboration | Fix the object name; declare the clock on the real port/net, or with `-name` on a primary input | <https://adaptivesupport.amd.com/s/article/54799> |
| 16 | `ERROR: [Place 30-58] IO placement is infeasible. Number of unplaced IO Ports (N) is greater than …` | Not enough free IO sites / pins not constrained at all | Assign legal `PACKAGE_PIN` per port, reduce the port count, or use a bigger package | <https://adaptivesupport.amd.com/s/question/0D52E00006hpTbISAU/place-3058-io-placement-is-infeasible> |
| 17 | `ERROR: [Place 30-99] Placer failed with error: 'IO Clock Placer failed'` (or `'failed to commit all instances'`) | A preceding placement error aborted the placer | Fix the earlier `[Place 30-*]` message (usually #16 or #18) — `30-99` is a *consequence* | AMD forum/Digilent threads for `Place 30-99` |
| 18 | `ERROR: [Place 30-574] Poor placement for routing between an IO pin and BUFG` | A clock enters on an IO that is not clock-capable in that bank | Move the clock to a `MRCC`/`SRCC` pin (`IOSTANDARD` + `PACKAGE_PIN`), or add `CLOCK_DEDICATED_ROUTE FALSE` on the net **only** if you accept skew/uncertainty | <https://adaptivesupport.amd.com/s/article/64452> |
| 19 | `ERROR: [Drc 23-20] Rule violation (NSTD-1) Unspecified I/O Standard: X out of Y logical ports use … 'DEFAULT'` | Ports without `IOSTANDARD` | **Preferred:** add `IOSTANDARD` per port. **Accepted workaround:** `set_property SEVERITY {Warning} [get_drc_checks NSTD-1]` — then check bank voltages yourself | <https://adaptivesupport.amd.com/s/article/56354>, forum answer with the `SEVERITY` command |
| 20 | `ERROR: [DRC UCIO-1] Unconstrained Logical Port: …` | Ports without `PACKAGE_PIN` | **Preferred:** add `PACKAGE_PIN`. **Documented waiver:** `create_waiver -type DRC -id UCIO-1 -user <u> -desc {…} <objects>` | UG835 `create_waiver` example; same forum thread as #19 |
| 21 | `CRITICAL WARNING: [Board 49-67] The board_part definition was not found for <board>` | Board files not installed, or `board_part` set to a board not in the repo | Add the board repo (`set_property board_part_repo_paths … [current_project]`) or `set_property board_part <none>`; harmless if pins are constrained explicitly | AMD forum threads for `Board 49-67` (multiple) |
| 22 | `CRITICAL WARNING: [Netlist 29-69] …` / `ERROR: [Project 1-560] unresolved black box` | An instantiated module/IP has no netlist (not added, not generated, OOC synthesis missing) | Add/generate the IP (`generate_target`/`export_ip_user_files`), or add the missing HDL/EDIF/DCP to the fileset | AMD forum thread on `[Project 1-560]`, AR 36660 |
| 23 | `WARNING: [IP_Flow 19-2162] IP '<x>' is locked. Locked reason: …` | IP definition not found in the catalog, IP moved/shared output dir, or tool patch changed the IP version | Re-add the IP catalog/repo path, `upgrade_ip`, or regenerate the IP in a clean directory; see AR for the exact locked reason | AR 55874, AR 58832, AR 59525, AR 36582 |
| 24 | `ERROR: [Common 17-165] Too many positional options` | Tcl command syntax error — extra positional argument or wrong option spelling | Check the command syntax on its UG835 page; quote/brace arguments containing spaces; `catch` it and print `$errorInfo` | <https://adaptivesupport.amd.com/s/article/46668> |
| 25 | `WARNING: [Common 17-239] ERROR Messages are prohibited to be downgraded. Message 'Common 17-69' is not downgraded.` | You tried `set_msg_config -new_severity` to demote an ERROR | Do not demote errors; fix the underlying error instead (only WARNING/CRITICAL WARNING can be demoted) | UG835 `set_msg_config` |
| 26 | `ERROR/ WARNING: [Device 21-436] No parts matched '<part>'` | The device family is not installed in this Vivado installation | Install the device family (`xsetup`) or switch to an installed part; confirm with `get_parts` | AMD forum thread on a missing ZCU102 part |
| 27 | `ERROR: [Vivado 12-4473] Detected error while running simulation` / `[Common 17-39] 'launch_simulation' failed due to earlier errors` | Simulation compile/elaborate failed | Read `<proj>.sim/sim_1/behav/xsim/*.log` (elaborate.log / compile.log), fix the HDL/testbench, re-run | AMD forum threads for `Vivado 12-4473` and `Common 17-39` |
| 28 | `CRITICAL WARNING: [Constraints 18-515] set_max_delay … path segmentation …` | `set_max_delay`/`set_min_delay` startpoint is not a valid timing startpoint | Use a register clock pin or a valid startpoint as `-from` | AMD forum question for `Constraints 18-515` |
| 29 | `ERROR: … The specified -to_step … must be enabled for the implementation run` | `launch_runs -to_step phys_opt_design` while the step is disabled | `set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]` before launching | UG835 `launch_runs` |
| 30 | `CRITICAL WARNING: Timing constraints are not met` (report shows `WNS < 0`, negative `TNS`) | Design does not close timing at the requested clock period | See §11.1 | UG949 + `report_timing_summary` |

### 11.1 "Timing constraints are not met" — the ordered fix list

1. Confirm the number: `get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]`
   (copy from AMD's non-project sample). Negative = failing.
2. Look at the report: `report_timing_summary -max_paths 10 -file timing.rpt` → the 10 worst paths tell you
   whether it is logic depth, routing congestion or an over-tight constraint.
3. Check constraints are sane: unconstrained/mistaken clocks are the most common *false* failure
   (see `[Vivado 12-1387]`, `[Synth 8-3321]`, AR 69583 master record for clock constraints).
4. Implementation effort knobs, in increasing cost order:
   `route_design -directive Explore`, `place_design -directive Explore`,
   `phys_opt_design -directive ExploreWithHoldFix` (post-place, then post-route),
   `phys_opt_design -aggressive_hold_fix` for hold violations.
5. Architecture: pipeline the failing path, register the crossing, reduce fanout.
6. Only then relax the clock period — and remember the bitstream will still be produced: unmet timing
   is a **CRITICAL WARNING**, not an error, unless you make it one (`set_msg_config -severity {CRITICAL WARNING} -new_severity ERROR`).

### 11.2 Five-minute triage flowchart for an agent

```
build failed
├─ exit code != 0 (because your script called `exit 1`) → good, you know it failed
├─ grep '^ERROR:' vivado.log
│   ├─ [Common 17-69] Command failed: … → look one line up/after for the real ID (Synth/Place/Vivado)
│   ├─ [Synth 8-*] → HDL problem; open runs/synth_1/runme.log; fix RTL; reset_runs synth_1
│   ├─ [Place 30-*] / [Route 35-*] → constraints or device capacity; check PACKAGE_PIN/IOSTANDARD and utilization
│   ├─ [Vivado 12-*] → XDC/design-database mismatch; re-check object names after synthesis
│   ├─ [IP_Flow 19-*] → IP locked/out of date; upgrade_ip / re-add catalog
│   └─ [Common 17-*] (165/179/217) → Tcl syntax, resources, licensing
├─ no ERROR but the run looks wrong → get_property PROGRESS/STATUS/NEEDS_REFRESH (AR 47491)
└─ timing critical warning only → §11.1
```

---

## 12. Copy-paste scripts

All four scripts are self-contained, use only commands verified on the UG835 v2026.1 pages, print a
machine-readable `BUILD_RESULT: OK|FAIL …` line, and exit non-zero on failure (§2.4).
Invoke them with `vivado -mode batch -source <script>.tcl -tclargs "KEY=value" …`.

### 12.1 `create_project.tcl`

```tcl
# create_project.tcl — create a Vivado project, add sources, set the top, leave it on disk.
# Usage: vivado -mode batch -source create_project.tcl -tclargs "PROJ=blinky" "PART=xc7a35tcpg236-1" \
#          "TOP=top" "RTL=src/top.v src/uart.v" "XDC=constraints/top.xdc"
set script_dir [file dirname [file normalize [info script]]]

# ---------- argument handling (KEY=value form; §7.2) ----------
array set ARGS {}
foreach a $argv {
    if {[regexp {^([A-Za-z_][A-Za-z0-9_]*)=(.*)$} $a -> k v]} { set ARGS($k) $v }
}
proc opt {name def} { expr {[info exists ::ARGS($name)] ? $::ARGS($name) : $def} }

set proj_name [opt PROJ  my_proj]
set part      [opt PART  xc7a35tcpg236-1]
set top       [opt TOP   top]
set rtl_files [opt RTL   ""]
set xdc_files [opt XDC   ""]
set proj_root [opt PROJECT_DIR [file normalize $script_dir]]

# ---------- failure-safe step wrapper (§7.1) ----------
proc step {label body} {
    puts "==> $label"
    if {[catch {uplevel 1 $body} msg]} {
        puts "ERROR: step '$label' failed: $msg"
        puts "ERRORINFO: $::errorInfo"
        puts "BUILD_RESULT: FAIL step=$label"
        exit 1
    }
}

step "create project" {
    file mkdir $proj_root
    create_project $proj_name [file join $proj_root $proj_name] -part $part -force
    puts "project: [current_project]"
}

if {$rtl_files ne ""} {
    step "add RTL sources" { add_files -norecurse -scan_for_includes $rtl_files }
}
if {$xdc_files ne ""} {
    step "add constraints"  { add_files -fileset constrs_1 -norecurse $xdc_files }
}

step "set top + compile order" {
    set_property top $top [current_fileset]
    update_compile_order -fileset sources_1
}

step "save + report" {
    puts "files: [get_files -of_objects [get_filesets sources_1]]"
    puts "part : [get_property part [current_project]]"
    puts "top  : [get_property top [current_fileset]]"
}
puts "BUILD_RESULT: OK stage=create_project project=$proj_name"
exit 0
```

### 12.2 `build.tcl` (Project Mode, full flow to bitstream + reports + XSA)

```tcl
# build.tcl — project-mode build: synth -> impl -> bitstream -> reports -> optional XSA.
# Usage: vivado -mode batch -notrace -source build.tcl -tclargs \
#          "PROJ=blinky" "PART=xc7a35tcpg236-1" "TOP=top" "JOBS=8" "BIT=1" "XSA=1"
set script_dir [file dirname [file normalize [info script]]]

array set ARGS {}
foreach a $argv {
    if {[regexp {^([A-Za-z_][A-Za-z0-9_]*)=(.*)$} $a -> k v]} { set ARGS($k) $v }
}
proc opt {name def} { expr {[info exists ::ARGS($name)] ? $::ARGS($name) : $def} }

set proj_name [opt PROJ   blinky]
set part      [opt PART   xc7a35tcpg236-1]
set top       [opt TOP    top]
set jobs      [opt JOBS   1]
set do_bit    [opt BIT    1]
set do_xsa    [opt XSA    0]
set rtl_files [opt RTL    ""]
set xdc_files [opt XDC    ""]
set bench     [opt TB     ""]
set proj_root [opt PROJECT_DIR [file normalize $script_dir]]
set out_dir   [opt OUT    [file join $proj_root $proj_name build]]
set proj_path [file join $proj_root $proj_name]
file mkdir $out_dir

proc step {label body} {
    puts "==> $label"
    if {[catch {uplevel 1 $body} msg]} {
        puts "ERROR: step '$label' failed: $msg"
        puts "ERRORINFO: $::errorInfo"
        puts "BUILD_RESULT: FAIL step=$label"
        exit 1
    }
}

step "create/open project" {
    if {[file exists [file join $proj_path ${proj_name}.xpr]]} {
        open_project [file join $proj_path ${proj_name}.xpr]
    } else {
        file mkdir $proj_path
        create_project $proj_name $proj_path -part $part -force
    }
}
if {$rtl_files ne ""} { step "add RTL"         { add_files -norecurse -scan_for_includes $rtl_files } }
if {$xdc_files ne ""} { step "add constraints" { add_files -fileset constrs_1 -norecurse $xdc_files } }
if {$bench     ne ""} { step "add testbench"   { add_files -fileset sim_1 -norecurse $bench } }

step "configure sources" {
    set_property top $top [current_fileset]
    update_compile_order -fileset sources_1
}

# Fail fast on the warnings that most often become silent defects (§8.4)
step "promote key messages to errors" {
    foreach id {{Synth 8-327} {Synth 8-6859}} { set_msg_config -id $id -new_severity ERROR }
}

# ---------- status helper (AR 47491 + UG835 wait_on_runs) ----------
proc run_report {run_name} {
    set st [get_property STATUS        [get_runs $run_name]]
    set pr [get_property PROGRESS      [get_runs $run_name]]
    set nr [get_property NEEDS_REFRESH [get_runs $run_name]]
    puts "RUN_STATUS: run=$run_name status='$st' progress=$pr needs_refresh=$nr"
    return $pr
}

step "synthesis" {
    reset_runs synth_1
    launch_runs synth_1 -jobs $jobs
    wait_on_runs synth_1
    if {[run_report synth_1] ne "100%"} { error "synth_1 did not reach 100% (see runs/synth_1/runme.log)" }
    open_run synth_1 -name synth_1
    report_utilization    -file [file join $out_dir post_synth_util.rpt]
    report_timing_summary -file [file join $out_dir post_synth_timing_summary.rpt]
}

step "implementation (+ bitstream)" {
    if {$do_bit} {
        launch_runs impl_1 -to_step write_bitstream -jobs $jobs
    } else {
        launch_runs impl_1 -jobs $jobs
    }
    wait_on_runs impl_1
    if {[run_report impl_1] ne "100%"} { error "impl_1 did not reach 100% (see runs/impl_1/runme.log)" }
}

step "open implemented design + reports" {
    open_run impl_1
    report_utilization      -file [file join $out_dir post_route_util.rpt]
    report_timing_summary   -file [file join $out_dir post_route_timing_summary.rpt]
    report_drc              -file [file join $out_dir post_route_drc.rpt]
    report_methodology      -file [file join $out_dir post_route_methodology.rpt]
    report_route_status     -file [file join $out_dir post_route_status.rpt]
}

step "timing verdict" {
    set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
    set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]
    puts "TIMING: setup WNS=$wns ns  hold WHS=$whs ns"
    if {$wns < 0 || $whs < 0} { puts "TIMING_RESULT: FAIL" } else { puts "TIMING_RESULT: OK" }
}

if {$do_bit} {
    step "locate bitstream" {
        set bits [glob -nocomplain [file join $proj_path ${proj_name}.runs impl_1 *.bit]]
        if {[llength $bits] == 0} { error "no .bit found under ${proj_name}.runs/impl_1" }
        puts "BITSTREAM: [lindex $bits 0]"
        puts "BITSTREAM_BASENAME: [file tail [lindex $bits 0]]"
    }
}

if {$do_xsa} {
    step "export XSA" {
        # -fixed: software-usable fixed shell ; -include_bit: keep the bitstream inside the archive
        set xsa [file join $out_dir ${proj_name}.xsa]
        write_hw_platform -fixed -include_bit -force $xsa
        puts "XSA: $xsa"
    }
}

step "summarise" {
    # belt-and-braces: message counters (UG835 get_msg_config)
    puts "MESSAGES: errors=[get_msg_config -severity ERROR -count] critical=[get_msg_config -severity {CRITICAL WARNING} -count]"
}
puts "BUILD_RESULT: OK project=$proj_name out=$out_dir"
close_project
exit 0
```

### 12.3 `build_nonproject.tcl` (Non-Project Mode)

```tcl
# build_nonproject.tcl — no project file: read sources, synth, implement, report, bitstream.
# Usage: vivado -mode batch -notrace -source build_nonproject.tcl -tclargs \
#          "PART=xc7a35tcpg236-1" "TOP=top" "RTL=src/top.v src/uart.v" "XDC=constraints/top.xdc" "OUT=build"
set script_dir [file dirname [file normalize [info script]]]

array set ARGS {}
foreach a $argv {
    if {[regexp {^([A-Za-z_][A-Za-z0-9_]*)=(.*)$} $a -> k v]} { set ARGS($k) $v }
}
proc opt {name def} { expr {[info exists ::ARGS($name)] ? $::ARGS($name) : $def} }

set part      [opt PART  xc7a35tcpg236-1]
set top       [opt TOP   top]
set rtl_files [opt RTL   ""]
set vhd_files [opt VHDL  ""]
set xdc_files [opt XDC   ""]
set out_dir   [opt OUT   [file normalize [file join $script_dir build]]]
set direct    [opt DIRECTIVE ""]
file mkdir $out_dir

proc step {label body} {
    puts "==> $label"
    if {[catch {uplevel 1 $body} msg]} {
        puts "ERROR: step '$label' failed: $msg"
        puts "ERRORINFO: $::errorInfo"
        puts "BUILD_RESULT: FAIL step=$label"
        exit 1
    }
}

step "read sources" {
    if {$vhd_files ne ""} { read_vhdl -vhdl2008 $vhd_files }
    if {$rtl_files ne ""} { read_verilog -sv $rtl_files }
    if {$xdc_files ne ""} { read_xdc $xdc_files }
}

step "synthesis" {
    if {$direct ne ""} {
        synth_design -top $top -part $part -directive $direct
    } else {
        synth_design -top $top -part $part
    }
    write_checkpoint -force [file join $out_dir post_synth.dcp]
    report_utilization    -file [file join $out_dir post_synth_util.rpt]
    report_timing_summary -file [file join $out_dir post_synth_timing_summary.rpt]
}

step "opt + place" {
    opt_design
    place_design
    report_clock_utilization -file [file join $out_dir clock_util.rpt]
}

step "post-place physical optimisation (only if failing)" {
    set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
    puts "POST_PLACE_WNS: $wns"
    if {$wns < 0} { phys_opt_design }
    write_checkpoint        -force [file join $out_dir post_place.dcp]
    report_utilization      -file  [file join $out_dir post_place_util.rpt]
    report_timing_summary   -file  [file join $out_dir post_place_timing_summary.rpt]
}

step "route + reports + bitstream" {
    route_design
    write_checkpoint      -force [file join $out_dir post_route.dcp]
    report_route_status       -file [file join $out_dir post_route_status.rpt]
    report_timing_summary     -file [file join $out_dir post_route_timing_summary.rpt]
    report_power              -file [file join $out_dir post_route_power.rpt]
    report_drc                -file [file join $out_dir post_route_drc.rpt]
    write_bitstream -force [file join $out_dir ${top}.bit]
    puts "BITSTREAM: [file join $out_dir ${top}.bit]"
}

step "timing verdict" {
    set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
    set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]
    puts "TIMING: setup WNS=$wns ns  hold WHS=$whs ns"
}
puts "BUILD_RESULT: OK mode=non_project out=$out_dir"
exit 0
```

### 12.4 `program.tcl` (Hardware Manager)

```tcl
# program.tcl — program an FPGA over hw_server.
# Usage: vivado -mode batch -notrace -source program.tcl -tclargs \
#          "BIT=/abs/path/design.bit" "LTX=/abs/path/design.ltx" "HW_URL=localhost:3121" "PART_FILTER=*"
array set ARGS {}
foreach a $argv {
    if {[regexp {^([A-Za-z_][A-Za-z0-9_]*)=(.*)$} $a -> k v]} { set ARGS($k) $v }
}
proc opt {name def} { expr {[info exists ::ARGS($name)] ? $::ARGS($name) : $def} }

set bit_file [opt BIT ""]
set ltx_file [opt LTX ""]
set hw_url   [opt HW_URL localhost:3121]
set jtag_hz  [opt JTAG_HZ 15000000]
set target_p [opt TARGET_PATTERN *]

if {$bit_file eq ""} { puts "ERROR: pass BIT=<path to .bit/.pdi>"; puts "BUILD_RESULT: FAIL step=args"; exit 1 }
if {![file exists $bit_file]} { puts "ERROR: bitstream not found: $bit_file"; puts "BUILD_RESULT: FAIL step=args"; exit 1 }

proc step {label body} {
    puts "==> $label"
    if {[catch {uplevel 1 $body} msg]} {
        puts "ERROR: step '$label' failed: $msg"
        puts "ERRORINFO: $::errorInfo"
        puts "BUILD_RESULT: FAIL step=$label"
        exit 1
    }
}

step "open hardware manager" { open_hw_manager }
step "connect to hw_server"  { connect_hw_server -url $hw_url }

step "select and open target" {
    set targets [get_hw_targets $target_p]
    if {[llength $targets] == 0} { error "no hw_target matched '$target_p' (is the cable attached and hw_server running?)" }
    current_hw_target [lindex $targets 0]
    set_property PARAM.FREQUENCY $jtag_hz [current_hw_target]
    open_hw_target
    puts "TARGET: [current_hw_target]"
    puts "DEVICES: [get_hw_devices]"
}

step "attach bitstream (+ probes)" {
    set dev [lindex [get_hw_devices] 0]
    current_hw_device $dev
    refresh_hw_device -update_hw_probes false $dev
    set_property PROGRAM.FILE $bit_file $dev
    if {$ltx_file ne "" && [file exists $ltx_file]} { set_property PROBES.FILE $ltx_file $dev }
    puts "PROGRAM.FILE=[get_property PROGRAM.FILE $dev]"
}

step "program device" {
    set dev [lindex [get_hw_devices] 0]
    program_hw_devices $dev
    refresh_hw_device $dev
}

step "verify DONE" {
    set dev [lindex [get_hw_devices] 0]
    # 7 series / UltraScale / UltraScale+ : DONE lives in the IR register
    set done [get_property REGISTER.IR.BIT5_DONE $dev]
    puts "DONE: $done"
    if {![string match "1*" $done]} { error "device did not report DONE (got '$done')" }
}

step "close" { close_hw_target; disconnect_hw_server; close_hw_manager }
puts "BUILD_RESULT: OK stage=program bit=$bit_file"
exit 0
```

> For Versal designs, `PROGRAM.FILE` must point to a `.pdi`, and the DONE check uses
> `REGISTER.JTAG_STATUS.BIT[34]_DONE` on `[lindex [get_hw_devices] 1]`
> (<https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device>).

### 12.5 Driving the scripts from a shell

```bash
#!/usr/bin/env bash
set -euo pipefail
VIVADO=${VIVADO:-vivado}
LOG=$(mktemp)

# -notrace: no per-command echo; -nolog/-nojournal: no session files (CI); keep our own log
if ! "$VIVADO" -mode batch -notrace -nolog -nojournal \
        -source build.tcl -tclargs "PROJ=blinky" "PART=xc7a35tcpg236-1" "JOBS=$(nproc)" >"$LOG" 2>&1; then
    echo "Vivado exit code non-zero"; grep -nE '^ERROR:' "$LOG" | head -20; exit 1
fi

# second layer: the run-level truth
if ! grep -q 'BUILD_RESULT: OK' "$LOG"; then
    echo "No BUILD_RESULT: OK marker"; grep -nE '^ERROR:' "$LOG" | head -20; exit 1
fi

# third layer: message-ID scan
grep -oE '\[(Common|Synth|Place|Route|Vivado|Drc|DRC|IP_Flow|Netlist|Board)[^]]*\]' "$LOG" | sort | uniq -c | sort -rn | head
grep -E 'TIMING:|TIMING_RESULT:' "$LOG" || true
```

---

## 13. Source index

**Command references (UG835 v2026.1, unless noted)** — `https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/<page>`:

`Introduction` (Return Codes, `$ERRORINFO`) · `Tcl-Batch-Mode` ·
`Errors-Warnings-Critical-Warnings-and-Info-Messages` · `Overview-of-Tcl-Capabilities-in-Vivado` ·
`create_project` · `create_fileset` · `add_files` · `update_compile_order` · `create_run` ·
`launch_runs` · `wait_on_runs` · `get_runs` · `current_run` · `reset_runs` · `open_run` ·
`report_run_status` · `synth_design` · `read_vhdl` · `read_verilog` · `read_xdc` · `read_checkpoint` ·
`write_checkpoint` · `open_checkpoint` · `link_design` · `opt_design` · `place_design` ·
`phys_opt_design` · `route_design` · `write_bitstream` · `write_debug_probes` · `write_hw_platform` ·
`write_project_tcl` · `report_utilization` · `report_timing_summary` · `report_drc` ·
`report_methodology` · `report_route_status` · `set_msg_config` · `get_msg_config` · `set_property` ·
`get_property` · `set_param` · `get_param` · `get_timing_paths` · `check_syntax` · `create_waiver` ·
`open_hw_manager` · `connect_hw_server` · `open_hw_target` · `current_hw_target` · `current_hw_device` ·
`get_hw_targets` · `get_hw_devices` · `refresh_hw_device` · `program_hw_devices` ·
`disconnect_hw_server` · `close_hw_target` · `close_hw_manager`

Direct PDF (all commands, one file, verified working):
`https://docs.amd.com/api/khub/maps/WNXuVCcvkMYPmhaquvp10A/attachments/Ip33sO8j7KfUMrk9PYOkbg-WNXuVCcvkMYPmhaquvp10A/content`
(the official `ug835-vivado-tcl-commands-en-us-2026.1.pdf`, 2054 pages)

**Flow / methodology / versions used to date behaviour changes:**

- UG894 Using Tcl Scripting: `Compilation-with-a-Project-Flow`, `Compilation-with-a-Non-Project-Flow`,
  `Details-of-the-Sample-Script`, `Handling-Tcl-Errors`, `Error-Handling`, `Parsing-Command-Line-Arguments`,
  `Vivado-Integrated-Design-Environment-IDE/Tcl-Modes-versus-Batch-Mode`, `Loading-and-Running-Tcl-Scripts`,
  `Sourcing-Tcl-Scripts`, `Executing-a-Tcl-Script-at-Startup`, `Defining-Tcl-Procedures`,
  `Compilation-and-Reporting-Example-Scripts` — base `https://docs.amd.com/r/en-US/ug894-vivado-tcl-scripting/`
- UG892 Design Flows Overview: `Launching-the-Vivado-Tools-Using-a-Batch-Tcl-Script`,
  `Understanding-Project-Mode-and-Non-Project-Mode`,
  `Tcl-Command-Differences-in-Project-Mode-and-Non-Project-Mode`, `Using-Project-Mode-Tcl-Commands`,
  `Using-Non-Project-Mode-Tcl-Commands`, `Project-Mode-Tcl-Script-Examples`, `RTL-Project-Tcl-Script`,
  `Non-Project-Mode-Tcl-Script-Example`, `Configuring-Synthesis-and-Implementation-Runs`,
  `Using-Design-Checkpoints`, `Script-based-Revision-Control-Methodology`,
  `Comparison-between-Script-based-and-Source-based-Revision-Control-Methodologies` —
  base `https://docs.amd.com/r/en-US/ug892-vivado-design-flows-overview/`
- UG893 Using the Vivado IDE: `Output-Files` (log/journal/backups), `Changing-Message-Severity`,
  `Suppressing-Messages`, `Launching-the-Vivado-IDE-from-the-Command-Line-on-Windows-or-Linux`
- UG908 Programming and Debugging: `Opening-the-Hardware-Manager`,
  `Connecting-to-a-Hardware-Target-Using-hw_server`, `Opening-a-Hardware-Target-Using-Tcl-Commands`,
  `Associating-a-Programming-File-with-the-Hardware-Device`, `Programming-the-Hardware-Device`,
  `Command-Line-Options-for-hw_server`, `Standard-hw_server-Options`,
  `Vivado-Hardware-Manager-Clocking-Related-Error-Messages`
- UG910 Getting Started: `Launching-the-Vivado-Tools-Using-a-Batch-Tcl-Script`,
  `Launching-the-Vivado-Design-Suite-Tcl-Shell`
- UG949 Design Methodology: `Using-Project-Mode-vs.-Non-Project-Mode`, `Using-Incremental-Implementation`

**Version-comparison PDFs used to date changes (fetched and grepped):**

- UG835 v2020.1 — `https://docs.amd.com/api/khub/documents/sVk_6_gQCXtNma2FQ7FaJw/content`
- UG835 v2022.1 — `https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_1/ug835-vivado-tcl-commands.pdf`
- UG835 v2018.1 — `https://docs.amd.com/api/khub/documents/uj1iikLf1hk5kDwB9IzQmQ/content`

**Answer records / forum threads (error causes and fixes):**

| ID | URL |
|---|---|
| AR 47491 — how to get a run's status in Tcl | <https://adaptivesupport.amd.com/s/article/47491> |
| AR 56354 — `[Drc 23-20]` NSTD-1 Unspecified I/O Standard | <https://adaptivesupport.amd.com/s/article/56354> |
| AR 56169 — `[Common 17-55]` + `[Vivado 12-584]` | <https://adaptivesupport.amd.com/s/article/56169> |
| AR 58260 / AR 54799 / AR 57056 — `[Vivado 12-584]`, `[Vivado 12-1387]`, `[Synth 8-3321]` | `…/s/article/58260`, `/54799`, `/57056` |
| AR 69583 — create_clock / create_generated_clock master record | <https://adaptivesupport.amd.com/s/article/69583> |
| AR 64452 — `[Place 30-574]` IO pin ↔ BUFG | <https://adaptivesupport.amd.com/s/article/64452> |
| AR 1034745 — multi-driven nets (`Synth 8-6859`) | <https://adaptivesupport.amd.com/s/article/1034745> |
| AR 61378 — `[Synth 8-327]` inferring latch | <https://adaptivesupport.amd.com/s/article/61378> |
| AR 58758 — `[Common 17-69]` bitstream not supported for core | <https://adaptivesupport.amd.com/s/article/58758> |
| AR 46668 — `[Common 17-165]` Too many positional options | <https://adaptivesupport.amd.com/s/article/46668> |
| AR 64283 — `[Vivado 12-1411]` LOC property of ports | <https://adaptivesupport.amd.com/s/article/64283> |
| AR 55874 / 58832 / 59525 / 36582 — `[IP_Flow 19-2162]` IP is locked | `…/s/article/55874`, `/58832`, `/59525`, `/000036582` |
| AR 36660 — black-box errors | <https://adaptivesupport.amd.com/s/article/000036660> |
| Forum — Vivado exit code in batch mode | <https://adaptivesupport.amd.com/s/question/0D52E000075zU0HSAU/vivado-exit-code-in-batch-mode> |
| Forum — typical command line (`-nolog -nojournal -notrace … -tclargs`) | <https://adaptivesupport.amd.com/s/question/0D52P00006hpZimSAE/vivado-command-line-options> |
| Forum — `[Place 30-58] IO placement is infeasible` | <https://adaptivesupport.amd.com/s/question/0D52E00006hpTbISAU/place-3058-io-placement-is-infeasible> |
| Forum — `[Board 49-67] The board_part definition was not found` | <https://adaptivesupport.amd.com/s/question/0D52E00006iHqkYSAS/board-4967-the-boardpart-definition-was-not-found-for-digilentinccombasys3part011-this-can-happen-sometimes-when-you-use-custom-board-part-you-can-resolve-this-issue-by-setting-boardrepop> |
| Forum — `write_hw_platform is only supported for synthesized, implemented…` | <https://adaptivesupport.amd.com/s/question/0D52E00006ynOdKSAU/about-common-1769> |
| Forum — `Run 'impl_1' has not been launched` | <https://adaptivesupport.amd.com/s/question/0D5KZ00000Zjjv00AB/error-common-1769-command-failed-run-impl1-has-not-been-launched-unable-to-open> |
| Forum — `Synthesis failed - please see the console or run log file` | <https://adaptivesupport.amd.com/s/question/0D52E00006hpkXhSAI/common-1769-command-failed-synthesis-failed-please-see-the-console-or-run-log-file-for-details> |
| Forum — `[Common 17-217] Failed to load feature 'core'` | <https://adaptivesupport.amd.com/s/question/0D5Pd00001NZsXhKAL/error-common-17217-failed-to-load-feature-core-when-installing-vivado-20252> |
| Forum — `[Device 21-436] No parts matched` | <https://adaptivesupport.amd.com/s/question/0D54U00008UDG28SAH/zcu102-part-number-is-not-detecting> |
| Forum — `[Synth 8-448] named port connection … does not exist` | <https://adaptivesupport.amd.com/s/question/0D52E00006hpQNjSAM/synth-8448-named-port-port-does-not-exist-for-instance-vhdl-instantiated-in-verilog> |
| Forum — `[Vivado 12-4473]` / `[Common 17-39]` simulation failures | <https://adaptivesupport.amd.com/s/question/0D54U00008hwKheSAE/error-usfxsim62-elaborate-step-failed-with-errors-please-check-the-tcl-console-output-or-cusershpproject1project1simsim1behavxsimelaboratelog-file-for-more-information> |

---

## 14. Uncertainties to re-verify at runtime

The following are the only places where this note goes beyond what an AMD page states explicitly.
An agent that needs certainty (different Vivado version, different product family) should verify
each with one command.

1. **Exact exit code semantics.** AMD documents `TCL_OK`/`TCL_ERROR` *inside* Tcl but not the process
   exit status; the "always 0" behaviour and the `exit 1` workaround come from AMD support forums
   (>2021.2 reports), not from a manual. Always use the §12 layers (marker + `catch` + log grep).
2. **`-quiet` (launcher flag).** Not found in UG835/UG893 topic text; likely present
   (`vivado -help`). Do not rely on it for CI.
3. **`-nolog` / `-nojournal` / `-notrace`.** Confirmed in use in AMD's forum and consistent with
   `-log`/`-journal` in UG893, but no manual page enumerates them; verify with `vivado -help`.
4. **`run STATUS` string values** are not enumerated in the documentation; only
   `PROGRESS == "100%"` is stated by AMD. Gate on `PROGRESS`, print `STATUS` for humans.
5. **`write_hwdef` removal release.** Verified present in UG835 v2018.1 and v2020.1 and absent in
   v2022.1 and v2026.1 — the exact release that removed it (2021.x vs 2022.1) is unverified.
6. **`wait_on_run` (singular).** Documented through v2020.1 and used in v2026.1 UG894 *examples*
   while the v2026.1 reference page is `wait_on_runs`. Both apparently work; scripts here use the plural.
7. **`open_hw` vs `open_hw_manager`.** v2018.1 documents `open_hw`; v2020.1+ document
   `open_hw_manager`. The v2026.1 `program_hw_devices` *description* still says `open_hw`
   (documentation lag). Use `open_hw_manager` on 2020.1+.
8. **`PROGRAM.FILE` / `PROBES.FILE`** come from the UG908 GUI/property flow; they are standard in the
   Hardware Manager but are not part of a UG835 command syntax page. Confirmed by
   `report_property [lindex [get_hw_devices] 0]` on the target.
9. **`get_msg_config -severity ERROR -count`** counting across sub-processes: the UG835 text warns the
   count covers only the launching process, so use it as a hint, not as the sole gate.
10. **`-jobs` semantics** ("number of parallel jobs to run on the local host") — how the number maps to
    concurrent OOC module runs vs concurrent strategies depends on the project; measure before
    tuning a CI machine.


