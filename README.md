# LLM on Vivado & Vitis

**Everything an AI agent (or a human) needs to design, verify and build FPGA projects
with AMD/Xilinx Vivado and Vitis on Linux — as a knowledge pack *and* a working MCP
server.**

The point is not "a tutorial for humans". It is: *any* LLM — a local 8B model behind
Ollama, or a frontier model in a coding agent — gets enough precise, **verified**
information to write synthesizable VHDL, write and run testbenches, drive Vivado in
batch, read its own error logs, and build an embedded application with Vitis. No
Vivado experience required beforehand, no proprietary tool needed to start.

- Target platform: **Linux only** (bash, `settings64.sh`, no Windows `.bat` paths).
- Tool versions: verified on **Vivado / Vitis 2025.2**; differences for 2020.2+ and
  2023.2+ are flagged where they matter.
- Project-agnostic: nothing here is tied to a particular board or design. The
  `examples/` show the *structure*, not "the" project.

---

## Quickstart — 2 minutes, no licence

```bash
# 1. free simulator + test framework (no root needed)
curl -sL -o /tmp/ghdl.tgz \
  https://github.com/ghdl/ghdl/releases/download/v6.0.0/ghdl-mcode-6.0.0-ubuntu24.04-x86_64.tar.gz
mkdir -p /tmp/ghdl_tool && tar xzf /tmp/ghdl.tgz -C /tmp/ghdl_tool --strip-components=1
python3 -m venv ~/.venv-fpga && . ~/.venv-fpga/bin/activate && pip install "cocotb>=2.0,<3"

# 2. run a verified example
cd examples/01-counter-cocotb/tb
PATH=/tmp/ghdl_tool/bin:$PATH make          # -> TESTS=3 PASS=3 FAIL=0
PATH=/tmp/ghdl_tool/bin:$PATH make WAVES=1  # -> counter.ghw (GTKWave / Surfer)
```

## Quickstart — real Vivado (batch, from a script)

```bash
source ~/vivado/2025.2/Vivado/settings64.sh          # or /tools/Xilinx/Vivado/2025.2/...
vivado -mode batch -source templates/vivado/create_project.tcl -nolog -nojournal \
       -tclargs --name prj --part xc7z020clg400-1 --top top
vivado -mode batch -source templates/vivado/build.tcl -nolog -nojournal \
       -tclargs --xpr prj/prj.xpr --to bitstream --jobs 4
# -> == impl_1 : PROGRESS=100% STATUS=write_bitstream Complete!
#    == TIMING: WNS = 7.317 ns
#    == BITSTREAM: prj/prj.runs/impl_1/top.bit
```
Both scripts are idempotent (a completed run is reused, not crashed into), always
produce reports even when the bitstream fails, and exit non-zero on failure — which
is what an agent must check. `--allow-unconstrained 1` handles the "verify the logic
without a board" case (see `docs/10-troubleshooting.md` §3).

---

## Three ways to plug an LLM into this

| Way | For | How |
|---|---|---|
| **MCP server** | agents with tool calling (Claude Desktop/Code, VS Code+Copilot, Cline, Continue, Hermes…) | `mcp/` — 18 tools: run Vivado/Vitis, follow a job, filter its log, parse reports, run cocotb, program the FPGA (with confirmation). See [`mcp/README.md`](mcp/README.md) |
| **Skills** | agents that load instructions on demand | `skills/*/SKILL.md` (one per task: Vivado Tcl project, synthesizable VHDL, cocotb testbench, XDC, timing, Vitis, MCP, troubleshooting) |
| **Compact prompt** | any local LLM, no tool support | paste [`prompts/quickref.md`](prompts/quickref.md) (EN) or [`prompts/quickref.fr.md`](prompts/quickref.fr.md) as the system prompt; task recipes in [`prompts/recipes.md`](prompts/recipes.md) |

An agent without MCP is not stuck: every step exists as a script it can ask the user
to run (`templates/vivado/*.tcl`, `templates/cocotb/*`).

---

## What's inside

```
AGENTS.md              contract for an AI agent working in this repo (read first)
prompts/               quickref (EN/FR), full system prompt, task recipes
skills/                SKILL.md per task, with references/
docs/                  the reference material (see docs/README.md for the index)
  ├── 01-toolchain.md         Linux install, paths, licences, udev, free toolchain
  ├── 02-vivado-tcl.md        project + non-project flows, logs, verified pitfalls
  ├── 03-simulation.md        XSim vs GHDL vs cocotb, with real outputs
  ├── 04-cocotb-recipes.md    testbench patterns that actually run
  ├── 06/07                   XDC constraints, timing closure
  ├── 08-vitis.md             xsct (≤2023.1) vs `vitis -s` (≥2023.2), XSA, boot
  ├── 10-troubleshooting.md   catalogue of REAL Vivado error messages → fix
  ├── 11-agent-workflow.md    the loop an agent must follow
  └── _research/              raw research notes with sources
templates/             vivado/ tcl scripts · cocotb/ makefiles+helpers · vhdl/ skeletons
                       constraints/ · project/ (project skeleton + Makefile toolbox)
examples/              01 counter · 02 ALU · 03 FIFO · 04 pure-VHDL testbench (XSim)
                       05 RISC-V datapath (reference structure) · 06 PS/PL + Vitis
mcp/                   the MCP server (Python), client configs, its own test suite
scripts/               check_tcl.py (validates every Tcl script), helpers
```

## Verification policy of this repository

Every non-obvious claim is either measured or explicitly flagged as unverified.
Nothing here is presented as fact because it "sounds right".

| Verified (on this machine) | How |
|---|---|
| Full Vivado flow to a bitstream | executed on Vivado 2025.2; `top.bit` 4 MB, WNS 7.317 ns |
| Tcl scripts are structurally valid | `tclsh` `info complete` on all 8 scripts + real execution |
| Testbenches pass | `make` on every example; outputs quoted in the READMEs |
| The MCP server drives real Vivado | synthesis launched through it (rc=0, 28.6 s), logs and reports parsed |
| Report/log parsers | unit tests against **authentic** Vivado 2025.2 reports and a real cocotb `results.xml` |
| XSim and GHDL agree | same VHDL testbench: 4695 checks, 0 errors, same end time under both |

Not verified, and said so in the docs: JTAG programming (no board attached), full
Vitis flow (no Zynq target), a timing-violating design (synthetic fixture), large
devices (no licence). Known limitations of the ecosystem are documented too — e.g.
**cocotb does not support XSim**, which changes how you verify a Vivado-only project.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Rules that matter: keep commands
copy-pasteable, state the tool version for anything version-dependent, cite an AMD
source for Vivado/Vitis behaviour, and never claim something works without a log.

## Licence

MIT (see [`LICENSE`](LICENSE)). Vivado, Vitis and XSim are proprietary AMD tools and
are **not** distributed here; the free toolchain used by the examples (GHDL, cocotb,
Icarus, Verilator, GTKWave) is open source.
