# AGENTS.md — instructions for AI agents using or contributing to this repo

If you are an LLM agent (Claude, GPT, Gemini, Qwen, Llama, DeepSeek, local model, ...)
this file tells you how to work. Read it before touching anything.

## What this repository is

A knowledge pack that lets **any** LLM design FPGA projects: VHDL, testbenches,
constraints, Vivado builds, Vitis embedded software. Nothing here needs a
proprietary license to be read or reused; the tools do, but there are free
alternatives documented in `docs/01-toolchain.md`.

## The loop you must follow

```
1. READ      the project state: file tree, .xdc, existing entities, logs, SKILL.md
2. WRITE     HDL incrementally: one entity/architecture per file, one concern per file
3. VERIFY    by SIMULATION before any synthesis (never skip this step)
4. SYNTHESIZE only when simulation passes
5. REPORT    what you ran, what the tool printed, what you changed
```

Rule: **never claim a design works without a simulation log or a build log to back it.**
If you cannot run the tools, say so and produce the exact Tcl/shell script for a human to run.

## Where to look first

| You need to...                      | Read                                              |
|-------------------------------------|---------------------------------------------------|
| Start a project                     | `README.md` → Quickstart, `templates/vivado/`      |
| Write synthesizable VHDL            | `skills/vhdl-synthesizable/SKILL.md`               |
| Write a testbench / verify          | `skills/cocotb-testbench/SKILL.md`, `docs/04-cocotb-recipes.md` |
| Drive Vivado from the command line  | `skills/vivado-tcl-project/SKILL.md`, `docs/02-vivado-tcl.md` |
| Add pins / clocks / timing          | `docs/06-constraints-xdc.md`, `docs/07-timing-closure.md` |
| Build embedded software (Zynq/PS)   | `skills/vitis-embedded/SKILL.md`, `docs/08-vitis.md`      |
| Debug a failing build               | `docs/10-troubleshooting.md`                       |
| Call Vivado through MCP tools       | `mcp/README.md`                                    |

If your context window is small (< 16k tokens), do not read `docs/` wholesale:
load one `SKILL.md` (they are short) and only the reference file it points to.

## Conventions in this repo (they are deliberate)

- **One module per file**, file name = entity name (lowercase, `_` separators).
- Ports: `i_` input, `o_` output, `s_` internal signal, `C_` constant, `p_` process label.
- Synchronous design, single clock, **synchronous active-high reset** unless the
  use case demands otherwise. One reset style per design — never mix.
- Simulation must run with a **fixed seed** and must be reproducible.
- Generated directories (`sim_build/`, `.Xil/`, `*.xpr` outputs) are never committed.
- Every template in `templates/` is a *starting point*; adapt, don't duplicate.

## Do not

- Do not invent Tcl/Vivado options: if unsure, search `docs/` and the AMD docs
  linked there, or run `<tool> -help` and quote the real output.
- Do not edit an .xpr, .xsa or a netlist by hand: regenerate it from a script.
- Do not remove the simulation step to "save time".
- Do not add a dependency on a paid simulator to an example that can run on GHDL.

## Notes for contributors

- Keep commands copy-pasteable, one per line, no ellipsis.
- State the tool version for anything version-dependent (Vitis has two
  incompatible generations: classic/XSCT ≤ 2023.1 and unified ≥ 2023.2).
- Add sources: a claim about Vivado/Vitis behaviour needs a docs.amd.com link.
- French/English: English is the primary language of the repo; the French
  README and quickref are kept in sync (see `README.fr.md`, `prompts/quickref.fr.md`).
