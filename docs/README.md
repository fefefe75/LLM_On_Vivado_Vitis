# Documentation — index

Primary language: English. The reference material is being translated file by file:
the files that are still French are marked as such in the table below. Every technical
claim about Vivado/Vitis is either sourced (AMD docs) or **measured** on Vivado 2025.2 —
measured facts are flagged as such, and anything that could not be verified is stated
explicitly.

| File | Content | Verification status | Language |
|---|---|---|---|
| [`01-toolchain.md`](01-toolchain.md) | Linux install, paths, `settings64.sh`, licences, udev, free toolchain | tools detected, real versions on the reference machine | FR (translation pending) |
| [`02-vivado-tcl.md`](02-vivado-tcl.md) | project mode / non-project mode, complete scripts, logs, pitfalls | flow executed all the way to the **bitstream** (2025.2) | FR (translation pending) |
| [`03-simulation.md`](03-simulation.md) | XSim vs GHDL vs cocotb: commands and limits | XSim and GHDL run on the same testbench, identical verdicts | FR (translation pending) |
| [`04-cocotb-recipes.md`](04-cocotb-recipes.md) | testbench recipes, scoreboard, reference models | executed (cocotb 2.0.1 + GHDL 6.0.0) | FR (translation pending) |
| [`06-constraints-xdc.md`](06-constraints-xdc.md) | clocks, I/O, minimal constraints | commands verified; pin assignment is board-dependent | FR (translation pending) |
| [`07-timing-closure.md`](07-timing-closure.md) | reading WNS/TNS/WHS/THS, closing timing | real reports analysed | FR (translation pending) |
| [`08-vitis.md`](08-vitis.md) | classic Vitis (xsct) vs unified (`vitis -s`), XSA, boot | `vitis -s`/`xsct` present and tested with `--version`; full flow not executed (no Zynq board) | FR (translation pending) |
| [`10-troubleshooting.md`](10-troubleshooting.md) | **catalogue of real errors** with fixes | messages copied from Vivado 2025.2 | FR (translation pending) |
| [`11-agent-workflow.md`](11-agent-workflow.md) | how an agent must work (loop, checks, reports) | — | FR (translation pending) |
| `_research/` | raw research notes (AMD/cocotb/MCP sources), raw material | sources cited, not fully re-read line by line | EN (this file's own `README.md` is still FR) |

Two other sets of documents:

- `../AGENTS.md`: contract for an agent working **in this repository**.
- `../mcp/README.md`: the MCP server (tools, security, client configuration); it has a
  French mirror at `../mcp/README.fr.md`.

## What is proven, and how

The whole thing replays with a single command:
```bash
bash scripts/verify_all.sh    # 11 checks: examples, templates, MCP, Tcl,
                              # and (if Vivado is in PATH) a real synthesis
                              # whose reports are then analysed
```
The script prints `OK` only on a null exit code, and `IGNORE` (never `OK`) for
whatever it could not execute.

| Claim | Evidence |
|---|---|
| The full Vivado flow works | `top.bit` 4 MB generated, `STATUS=write_bitstream Complete!`, WNS 7.317 ns |
| The Tcl scripts are valid | `tclsh … check_tcl_syntax.tcl` (8/8) + `scripts/check_tcl.py` (procedures actually executed) |
| The testbenches pass | `make` on the examples: `tests/test_reports.py` and quoted outputs |
| The MCP server drives a real Vivado | real synthesis through `vivado_run` (rc=0, 28.6 s), `job_log`, `report_summary` |
| The report analysers are correct | **authentic** fixtures in `mcp/tests/fixtures/` (Vivado 2025.2) |

## What is not proven

- **JTAG programming** (`program_hw_devices`): no board attached.
- The **full Vitis flow** (platform + application + boot): no Zynq target.
- A **timing-violating** design (WNS < 0): only a synthetic fixture covers it.
- **Large devices** (UltraScale+, Versal): no licence of that kind here.
