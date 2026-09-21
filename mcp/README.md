# Vivado / Vitis MCP server — the bridge between an LLM and the FPGA tools

An LLM cannot drive Vivado: it does not know how to launch a batch, follow a 40-minute
synthesis run, or find the only useful `ERROR:` line in a 30 000-line log. This MCP
server gives it exactly that, in 18 tools.

It is **generic**: no particular project is hard-coded, everything is configured through
`--workspace`.

## Installation

```bash
cd LLM_On_Vivado_Vitis/mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # or: .venv/bin/pip install -e .
.venv/bin/python -m vivado_mcp --workspace ~/mon_projet --selftest   # verification
```

`--selftest` prints what is actually installed (Vivado, Vitis, xsct, GHDL, cocotb…)
without opening any transport. **Always start there** when something does not work.

## Launch

```bash
# Standard mode (stdio): the MCP client launches the server
.venv/bin/python -m vivado_mcp --workspace ~/mon_projet

# HTTP mode (shared server) — NEVER EXPOSE without authentication
.venv/bin/python -m vivado_mcp --workspace ~/mon_projet --transport http --port 8000
```

| Option | Effect |
|---|---|
| `--workspace` | project root; **every** write is confined to it |
| `--tool-root` | AMD root (`/tools/Xilinx`) if Vivado/Vitis is not in the `PATH` |
| `--transport` | `stdio` (default), `http`, `sse` |
| `--selftest` | opens nothing, prints the detected environment |

Environment variables: `FPGA_MCP_WORKSPACE`, `FPGA_MCP_RUNS_DIR`, `FPGA_MCP_TOOL_ROOT`,
`FPGA_MCP_TIMEOUT` (max delay per job, default 3600 s).

## Exposed tools

| Tool | When to use it |
|---|---|
| `project_tree` | **first**: understand the project structure |
| `read_text_file` / `write_text_file` | read a `.vhd`/`.xdc`, write a module or a testbench |
| `grep` | find an entity, a port, a signal, an error |
| `env_info` | know what is actually installed before prescribing a flow |
| `vivado_run` | run a Vivado Tcl script in batch (synthesis, impl., bitstream, reports) |
| `vitis_run` | run `xsct` (≤ 2023.1) or `vitis -s` (≥ 2023.2) |
| `cocotb_run` | run a cocotb testbench (`make`) — the verification before synthesis |
| `job_status` / `wait_for_job` / `job_list` | follow a job (asynchronous, never blocks) |
| `job_log` | **diagnostics**: errors and warnings extracted, filtered lines |
| `job_cancel` | stop a run that has gone haywire |
| `report_summary` | parse a report: messages by code, WNS/TNS/WHS/THS, resources |
| `cocotb_results` | PASS/FAIL verdict per test (reads `results.xml`) |
| `project_status` | state of a project: runs, timing, bitstreams (launches nothing) |
| `list_hw_targets` | visible JTAG targets |
| `program_fpga` | program the board — **hardware action, `confirm=True` mandatory** |

## Expected work loop

```
env_info()                    -> which tools are present
project_tree()                -> structure
write_text_file("rtl/x.vhd")  -> RTL
cocotb_run("tb/x")            -> SIMULATION (mandatory before any synthesis)
cocotb_results("tb/x")        -> PASS/FAIL
vivado_run(script_path="scripts/build.tcl")
job_status(id, wait_s=30)     -> running / finished
job_log(id)                   -> errors only
report_summary(".../timing_summary.rpt") -> WNS/TNS
```

A Vivado run lasts from a few seconds to several hours: the tools never block longer
than requested (bounded `wait_s`). The LLM polls the progress.

## Security — what the code actually enforces

| Barrier | Where | Tested behaviour |
|---|---|---|
| Workspace confinement | `safety.resolve_in_workspace` | `../secret`, `/etc/passwd`, `~/x` and symlinks pointing outside the workspace are refused (`tests/test_safety.py`) |
| Binary allow-list | `config.EDA_BINARIES` | `rm`, `curl`, or an absolute path are refused; `shell=True` is never used |
| Generated Tcl scripts | `safety.write_tcl` | sanitised file name, atomic write inside `scripts/generated/` |
| Bounded output | `jobs.JobManager` | log truncated at 50 MB, sliding `tail` of 400 lines, at most 40 errors reported |
| Clean shutdown | `jobs._kill` | `SIGTERM` on the process **group**, then `SIGKILL` after 8 s |
| Hardware actions | `tools.program_fpga` | explicit refusal until `confirm=True` is provided (and the user agrees) |
| Forced batch mode | `config.base_env` | `DISPLAY=""`: no GUI opens behind the agent's back |

### What this does NOT protect against — read this before deploying

Everything above is a **filesystem and binary allow-list**. It does not make the
server a sandbox, and earlier versions of this file overstated that. The honest
version:

- **`vivado_run` and `vitis_run` execute arbitrary Tcl.** The server only decides
  *which file* is handed to `vivado -source`; Tcl is a full language, so an
  `exec rm -rf ~` or an `exec curl … | sh` inside the submitted script runs with
  the server's privileges. Workspace confinement constrains the file tools, not
  what the Tcl itself does.
- **`write_text_file` followed by `cocotb_run` is arbitrary code execution.**
  `cocotb_run` runs `make` inside a testbench directory; an agent that first writes
  that directory's `Makefile` chooses what `make` executes.
- **`vitis_run` / `xsct`** have the same property, plus JTAG access when a cable is
  attached.

So the trust model is the same as for any MCP server that invokes a compiler or a
simulator — no better, no worse. If you point a model you do not fully trust at it:

1. run it in a **container** (or a dedicated VM / unprivileged user) with only the
   project directory bind-mounted;
2. never expose the `http` transport without authentication;
3. keep the workspace outside your home directory, so a stray `exec rm -rf` cannot
   take your documents with it.

## Client configuration

`configs/` contains ready-to-copy examples:

| Client | File |
|---|---|
| Claude Desktop | `configs/claude_desktop_config.json` |
| Hermes Agent | `configs/hermes-config-snippet.yaml` (`mcp_servers:` in `~/.hermes/config.yaml`) |
| VS Code / Copilot | `configs/vscode-mcp.json` |
| Cline | `configs/cline_mcp_settings.json` |

Replace the paths (`/chemin/vers/venv/bin/python`, `PYTHONPATH`, `--workspace`).
An LLM **without** an MCP client can still work: the Tcl scripts in
`templates/vivado/` are made to be run by hand.

## Tests

```bash
cd mcp
python -m pytest -q          # 52 tests
```

What is actually verified (not mocks): launching real processes (`make`, `python3`),
success/failure detection, error extraction from logs, **timeout that kills the
process**, cancellation, persistence of `runs/*.json`, parsing of an authentic
cocotb 2.0.1 `results.xml`, serialisation of paths, and starting the server as a
**stdio subprocess** with a real MCP client (tool listing + call).

## Assumed limitations

- **Vivado 2025.2 / Vitis 2025.2 are installed on the reference machine**, and the
  documented flows were run there (synthesis → bitstream, WNS 7.317 ns, a real
  synthesis driven through `vivado_run` in rc=0 / 28.6 s). What remains unverified:
  JTAG programming (no board), the complete end-to-end Vitis flow on a Zynq target,
  and a design actually violating timing (only a synthetic fixture covers it). The
  Vivado report parsers degrade cleanly (`"parsed": false` + raw text) if the layout
  changes: they will not lie.
- **cocotb does not support XSim** (verified in cocotb 2.0.1): in a Vivado-only
  environment, use a VHDL testbench (`examples/04-vhdl-testbench-xsim`) or simulate
  the same RTL with GHDL.
- Jobs live in the server's memory (the logs and one JSON per job stay on disk in
  `.mcp_runs/`): after a restart, `job_list` starts from zero.
- The server is **batch-only**: no interactive Vivado session, no GUI.
