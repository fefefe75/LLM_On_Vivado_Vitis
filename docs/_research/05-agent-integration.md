# 05 — Agent integration: how to package this knowledge for LLM agents

Research note · target audience: the maintainers of `LLM_On_Vivado_Vitis`

This note defines the **delivery layer** of the project. The other notes in `docs/_research/`
cover the engineering content (VHDL, cocotb, XDC, Vivado/Vitis flows, MCP). This one answers a
different question: *in what shape do we ship that content so that any AI can actually use it* —
including an 8B model running in Ollama on a laptop with 8k of context and no tool calling.

The repo currently ships a single file, `skills.md` (4 857 chars ≈ 1.2k tokens of French prose),
which is a *draft quickref*, not a deliverable. It is over the compact budget, it mixes the
quickref with MCP endpoint lists and a Vitis tutorial, and it has no skill-folder counterpart.
This note replaces that plan with three parallel deliverables (see §1).

---

## 1. The two formats to ship, and who each one is for

Two mechanisms exist in the wild, and they are not competitors — they cover different agents.

| | **A. Skill folders** | **B. Compact system prompt ("quickref")** |
|---|---|---|
| Shape | `skills/<name>/SKILL.md` (+ `references/`, `scripts/`, `assets/`) | one flat text/blob, 1 500–2 500 chars |
| Loaded | on demand, when the `description` matches the task | always, in the system prompt |
| Cost | ~100 tokens per skill at startup, ~1–2k when triggered | ~600 tokens, every single turn |
| Works for | Claude Code, Hermes Agent, Cline, Codex, Cursor, any agent with a filesystem + a read tool | Ollama, llama.cpp, LM Studio, vLLM, a raw `POST /v1/chat/completions` |
| Fails for | models with no filesystem/tool access (they never see the body) | any project big enough to need more than ~600 tokens of rules |
| Maintained by | Anthropic's open standard (agentskills.io), adopted by Hermes, Claude Code, Cline | this repo |

**Rule of thumb.** If the agent can read a file, ship skills. If it cannot, ship the quickref.
Ship both, because the same repo is consumed by both kinds of agent, and the quickref doubles as
the fallback for a skill-capable agent whose loader is broken or whose context is saturated.

### 1.1 Format A — the skill folder

A skill is *a directory*, not a file. The canonical layout, per Anthropic's Agent Skills docs and
the open standard at agentskills.io:

```
skills/
└── cocotb-testbench/
    ├── SKILL.md            # YAML frontmatter (name, description) + Markdown body
    ├── references/         # long material, read only when pointed at
    │   ├── ghdl-vs-questa.md
    │   └── cocotb-api.md
    ├── scripts/            # deterministic code, executed (never loaded into context)
    │   └── run_sim.sh
    └── assets/             # templates, Makefiles, XDC stubs copied verbatim
        └── Makefile.cocotb
```

Hard requirements from the spec (validator, not style):

* `SKILL.md` must start with `---` at byte 0 (no BOM, no leading blank line), close the YAML with
  `\n---\n`, and have a non-empty Markdown body.
* `name`: ≤64 chars, lowercase letters/digits/hyphens only, no XML tags, and the reserved words
  `anthropic`/`claude` are rejected.
* `description`: required, non-empty, ≤1 024 chars.
  ([Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#skill-structure))

Three levels of loading ("progressive disclosure", the core design principle of the format):

| Level | Content | When loaded | Token cost |
|---|---|---|---|
| 1 | `name` + `description` from frontmatter | always, at startup | ~100 tokens per skill |
| 2 | `SKILL.md` body | when the description matches the task | target < 5k tokens |
| 3+ | `references/*`, `scripts/*`, `assets/*` | only when `SKILL.md` points at them | zero until read; scripts cost only their output |
| ([Overview — how skills work](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#how-skills-work)) |

Hermes implements the same three levels with a slightly different vocabulary: level 0 =
`skills_list()` (the whole index, ~3k tokens for ~87 skills), level 1 = `skill_view(name)`,
level 2 = `skill_view(name, path)` for one reference file
([Hermes docs — Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)).
Claude Code adds a budget mechanic worth knowing: the skill listing is capped at **1% of the model's
context window**, and when it overflows the loader *strips descriptions*, starting with the
least-used skills — so a buried trigger silently stops working
([Claude Code — skills](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short)).

### 1.2 Format B — the compact quickref

One flat block of ~1 500–2 500 characters that goes into the system prompt (or the first user
message) of a model that has no skills, no filesystem and often no function calling. It is a
**cheat sheet, not documentation**: the model still knows what a `process` and a `rising_edge`
are; what it does not know is *our* layout, *our* naming, *our* command lines and *our* traps.

The full text is specified in §4. Size it by characters, not by tokens, because code-heavy text
tokenises at ~3 chars/token while English prose sits near 4–5.

### 1.3 What must stay identical in both

The quickref and the skills must not drift apart. Enforce it mechanically:

* one file is the source of truth per fact, and the other *points at it* (quickref may embed the
  same 10-line Tcl skeleton — duplication is acceptable and intended here, because the quickref
  cannot follow a link);
* anything that changes per project (part number, top entity, clock period) lives in the *project*
  (an `AGENTS.md` / config file), never in the quickref and never in a skill;
* every rule that appears in the quickref must also appear in the skill that owns the topic, and
  vice-versa — add a CI check that greps both for a small list of invariant strings (`create_clock`,
  `rising_edge`, `cocotb.start_soon`, `i_rst`).

---

## 2. How to write a `SKILL.md` that actually works

Anthropic's authoring guide is thin on rhetoric and heavy on observed failure modes
([best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
The rules below are that guide plus the hardline conventions the Hermes repo enforces in review
(local file: `~/.hermes/skills/software-development/hermes-agent-skill-authoring/SKILL.md`, itself
the operational walkthrough of Hermes' own skill standards).

### 2.1 The description is the whole game

The description is the only text the model sees when deciding whether to load the skill. Get it
wrong and the body never loads — the skill is dead code.

* **State what it does AND when to use it**, in third person. Anthropic's own example:
  `Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF
  files or when the user mentions PDFs, forms, or document extraction.`
* **For this repo, start the trigger clause with `Use when …`** and put it *early*: some loaders
  truncate the index entry (Hermes truncates at 57 chars + `…` in the system-prompt index; Claude
  Code can strip descriptions entirely under budget pressure). Make the first ~60 characters a
  self-contained capability statement with the matching keywords.
* Third person only. `Processes X` ✅ — `I can help you…` ❌, `You can use this to…` ❌.
* No marketing words: "powerful", "comprehensive", "advanced", "seamless" carry zero selection
  signal and are rejected in the Hermes review.
* Include synonyms the user will actually type (`testbench`, `sim`, `simulation`) — matching is
  lexical, not semantic reasoning.
* Practical compromise for this repo: the descriptions in §3 are ~120–180 chars (Anthropic allows
  1 024). The Hermes repo caps descriptions at 60 chars because *its* index is a wall of 87 skills;
  we are nowhere near that, so buy the extra selection accuracy, but keep the first clause inside
  60 characters.

### 2.2 The body

* **Imperatives, with the reason attached.** "Run the simulation before synthesis: synthesis hides
  functional bugs until a board is burnt" changes behaviour; "be careful with synthesis" does not.
* **Concrete, copy-pasteable examples.** Real part number (`xc7z020clg400-1`), real entity name,
  real command. Abstract placeholders (`<your_file>`) cost the model a decision every time.
* **Match the degree of freedom to the fragility.** Fragile, sequence-critical operations get an
  exact command with "do not add flags"; open-ended design work gets a goal and a checklist
  ([best practices — degrees of freedom](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
  A `create_project.tcl` skeleton is low-freedom; "write the datapath" is high-freedom.
* **One topic per skill.** If a skill needs a sub-heading that has nothing to do with its
  description, it is two skills.
* **No router/hub skills.** A skill whose content is "load skill X instead" adds a hop and
  duplicates X's own triggers — Hermes rejects these in review, and the same argument holds here.
  Ship an `INDEX` in the README instead.
* **Numbered procedure, each step ending in a checkable criterion** ("done when `results.xml`
  contains `failure=0`"), plus a `## Pitfalls` and a `## Verification` section. These are the
  minimum sections in the Hermes convention.
* **No machine-local paths.** `skills/…`, `scripts/…` — never `/home/you/…`. A skill is portable
  or it is broken.

### 2.3 Progressive disclosure: keep `SKILL.md` short, push detail into `references/`

This is the single most important structural rule, and the one the current `skills.md` violates.

* `SKILL.md` target: **≤500 lines**, and for this repo **4–8 KB (≈1–2k tokens)**. Measured on this
  machine: 87 skills, median 8.8 KB (≈2.2k tokens), max 78 KB
  (`~/.hermes/skills/` — e.g. `research/arxiv/SKILL.md` 10 KB with a Quick Reference table,
  `autonomous-ai-agents/hermes-agent/SKILL.md` 13 KB supported by **19** files under `references/`
  and 3 under `templates/`).
* Real example of the pattern done well, from the local Hermes skills:
  `research/grounded-citations/SKILL.md` (12.6 KB) keeps the invariants inline and delegates to
  `references/citation-formats.md`, `references/grounding-rationale.md` and
  `scripts/sources.py` — the script's code never enters the context window, only its output.
* **References one level deep, never nested.** `SKILL.md` → `references/x.md` is fine;
  `SKILL.md` → `advanced.md` → `details.md` causes partial reads (`head -100`) and lost
  information ([best practices — avoid deeply nested references](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
* **Any reference file >100 lines gets a table of contents at the top**, so a partial read still
  reveals what exists.
* **Scripts are for determinism, references for facts, `SKILL.md` for decisions.** Say explicitly
  which one you mean: "Run `scripts/check_timing.sh`" (execute) vs "See `scripts/tcl_template.tcl`
  for the flow" (read as reference).
* Name files by content (`xdc-clock-constraints.md`), never `doc2.md`.

### 2.4 What must NOT go into a skill

* **Anything the model already knows.** "VHDL is a hardware description language used for FPGAs…"
  is pure token tax. Anthropic's rule: only add what the model does not have.
* **Time-sensitive statements** ("as of Vivado 2023.2 use X"). Put the version in `platforms`/
  prerequisites and move superseded material into an `## Old patterns` section, or delete it.
* **Tool/licence-specific secrets and licence files.** Never.
* **Project-specific state** (this board's pinout, this repo's top entity). That belongs in the
  project's `AGENTS.md` / XDC, not in a skill.
* **Duplicated procedures across skills.** One owner per topic. Synthesis flow lives in the build
  skill; the VHDL skill links to it, it does not re-explain it.
* **`README`-style marketing or contribution guides.** Those are for humans and belong in
  `README.md`.
* **Whole-file dumps of boilerplate.** Ship them under `assets/` and tell the model to copy them.
* **The MCP tool list verbatim.** It changes; reference the tool by fully qualified name instead
  (`Vivado:run_synthesis`), which is also required to avoid "tool not found" errors.

---

## 3. Recommended skills for this repo (8)

Names are folder names under `skills/`. Descriptions are ready to paste into the frontmatter
(the first clause stays inside 60 characters so it survives index truncation). "Points at" lists
the annex files the skill owns.

**1. `vivado-project-tcl`**
> Create and rebuild a Vivado project from batch Tcl scripts. Use when starting a new Vivado
> project, regenerating `vivado_project/`, adding HDL/constraint sources, or scripting a
> headless Vivado run.
*Contains:* the canonical `create_project` → `add_files` → `set_property top` → `update_compile_order`
flow, `catch`/error handling, timing-check gating, `-mode batch` invocation, what is generated vs
committed.
*Points at:* `references/tcl-command-reference.md`, `scripts/create_project.tcl`,
`assets/gitignore-vivado`.

**2. `vhdl-synthesizable`**
> Write synthesisable VHDL-2008 for Xilinx FPGAs. Use when adding or editing a `.vhd` file, defining
> an entity/architecture, inferring a register, mux, FSM or BRAM, or fixing a synthesis warning.
*Contains:* `i_`/`o_`/`s_`/`C_`/`p_` naming, synchronous reset style, small entity granularity,
`numeric_std` only, latch avoidance, one entity per file, named port maps, inferrable templates for
register/FSM/BRAM/DSP.
*Points at:* `references/vhdl-patterns.md`, `references/xilinx-inference.md`,
`assets/entity_template.vhd`.

**3. `cocotb-testbench`**
> Write and run cocotb testbenches for VHDL designs. Use when a module needs verification, a test
> fails or times out, or a simulation must be scripted.
*Contains:* the async test skeleton, clock/reset helpers, `RisingEdge`/`Timer` discipline, asserts
instead of prints, `results.xml`, `Makefile` variables (`SIM=ghdl|questa`), running a single test.
*Points at:* `references/cocotb-api.md`, `references/makefile-variables.md`,
`assets/Makefile.cocotb`, `scripts/run_sim.sh`.

**4. `xdc-constraints-clocks`**
> Write XDC pin and clock constraints. Use when adding pin/package constraints, defining
> `create_clock`, setting input/output delays, or debugging unconstrained-path warnings.
*Contains:* `create_clock` for the board oscillator, one clock per domain, generated clocks, false
paths only with justification, pin assignments inside the correct I/O standard block, the
"bitstream fails without a clock constraint" trap.
*Points at:* `references/xdc-command-reference.md`, `assets/top_template.xdc`.

**5. `vivado-build-timing`**
> Run Vivado synthesis and implementation and close timing. Use when building a bitstream, reading
> timing reports, fixing failing paths, or reporting resource utilisation.
*Contains:* `run_synthesis`/`run_implementation`/`write_bitstream` in batch mode, where the logs
live (`*.runs/*/runme.log`), reading WNS/TNS, the order of fixes (constrain first, restructure
second, pipeline third, frequency last), utilisation reporting.
*Points at:* `references/timing-reports.md`, `scripts/build_hw.tcl`,
`scripts/report_timing.sh`.

**6. `vitis-embedded-software`**
> Build Vitis platforms and bare-metal apps from a Vivado export. Use when moving a design to
> software, writing bare-metal C for a Xilinx IP driver, or debugging a board bring-up.
*Contains:* the export step (`write_hw_platform`/`.xsa`) and why the old `.hwdef` flow is legacy,
create platform → create application → build → boot, an `xgpiops`/AXI-GPIO example, address map
lookup, "application sees no IP" troubleshooting.
*Points at:* `references/xsa-export.md`, `assets/hello_world.c`.

**7. `agent-mcp-vivado`**
> Drive Vivado/Vitis through MCP tools or generated command scripts. Use when an agent must read
> HDL, edit Tcl, launch a build or a test without a human at the keyboard.
*Contains:* the tool surface (read file, write file, run build, run test, fetch log), fully
qualified MCP names, poll/back-off on long builds, the fallback path when no MCP server exists
(generate `.tcl`/`.sh`, ask the human to run it, parse the log file), and the evidence rule
(never claim a build outcome you did not read in a log).
*Points at:* `references/mcp-tool-surface.md`, `references/no-mcp-fallback.md`,
`scripts/report_state.sh`.

**8. `eda-error-triage`**
> Diagnose Vivado, GHDL and cocotb error messages. Use when a build or simulation fails and the
> message is unclear, or when a result looks plausible but wrong.
*Contains:* a symptom → cause → fix table (unresolved reference, port mismatch, `not a constant`,
cocotb timeout, failing timing, bitstream refusal, `x` propagation), where to grep in the logs, the
rule "fix the first error, not the last", and how to capture a minimal reproduction.
*Points at:* `references/error-catalogue.md`, `references/vivado-log-locations.md`.

**Deliberately not created:** no `INDEX`/router skill (§2.2), no `quickref` skill (it is Format B,
a file at the repo root), no `fpga-basics` skill (the model knows what an FPGA is).

---

## 4. Compact quickref (Format B): required content and exclusions

### 4.1 What must be in it (in this priority order)

1. **Project layout** — the exact directory names. A local LLM cannot guess whether HDL lives in
   `src/`, `hdl/` or `rtl/`, and every file it writes goes to the wrong place if you skip this.
2. **VHDL conventions** — port prefixes (`i_`/`o_`/`s_`/`C_`/`p_`), one entity per file, clocked
   process shape, reset polarity, `numeric_std`, and the explicit forbidden list. This is the
   "house style" the model cannot infer.
3. **Tcl skeleton** — the 8-line create/add/top sequence plus the `catch` idiom. Without it the
   model invents plausible-but-wrong Tcl (`create_project -name` etc.).
4. **cocotb skeleton** — the async test shape, `start_soon(Clock(...))`, an `assert`. This is the
   highest-value block in the whole file: it is the gate that protects synthesis.
5. **Shell commands** — the four commands that actually run things (`ghdl -a`, `make SIM=ghdl`,
   `vivado -mode batch`, and where the log is).
6. **Common failures** — symptom → one-line fix, 5–6 entries. This is where a small model burns
   the most turns when it is missing.

### 4.2 What must be excluded to stay under 2 500 characters

* Vivado GUI navigation, project wizard, board-part catalogue → skills only.
* The Vitis tutorial and C snippets (the `XGpio` example in the current `skills.md`) → Vitis skill.
* The MCP endpoint table → MCP skill. A model without MCP cannot use it, and a model with MCP has
  the tool schemas at runtime.
* Documentation conventions (`--! @brief` comment style, README rules) → `AGENTS.md`.
* Long "do not do this" prose lists → 6 one-line entries in `COMMON FAILURES` maximum.
* Complete testbench examples with generics, multiple tests, scoreboards → skill.
* Anything version-specific that will rot (tool version numbers, GUI menu paths).

### 4.3 The quickref, verbatim (2 492 chars ≈ 620 tokens at 4 chars/token)

**Status: draft to commit as `quickref.md` at the repo root. Character count must be re-checked on
every edit (`wc -c quickref.md` ≤ 2500).**

```
FPGA / Vivado / Vitis -- AGENT QUICKREF (VHDL-2008, cocotb)

LAYOUT (repo root)
  src/hdl/<block>/<entity>.vhd      one entity per file, file name = entity name
  tb/<block>/testbench_<block>.py   + Makefile
  src/constraints/<top>.xdc         scripts/*.tcl         export/
  vivado_project/ = generated, git-ignored, never hand-edit

VHDL CONVENTIONS
  i_* input port | o_* output port | s_* internal signal | C_* constant | p_* process
  sync: process(i_clk) begin if rising_edge(i_clk) then if i_rst = '1' then ... end if; end if; end process;
  reset active HIGH, synchronous only
  named ports: u_add : entity work.adder port map (i_a => s_a, o_y => s_y);
  use ieee.std_logic_1164.all; use ieee.numeric_std.all;  arithmetic on unsigned/signed only
  forbidden: std_logic_arith, std_logic_unsigned, arithmetic on std_logic_vector, inferred latches

TCL SKELETON (scripts/create_project.tcl)
  set TOP datapath ; set PART xc7z020clg400-1
  create_project -force $TOP ./vivado_project -part $PART
  add_files -fileset sources_1 -scan_for_includes src/hdl
  add_files -fileset constrs_1 src/constraints
  set_property top $TOP [current_fileset]
  if {[catch {update_compile_order -fileset sources_1} err]} { puts "ERROR: $err" ; exit 1 }
  # run:  vivado -mode batch -source scripts/create_project.tcl

COCOTB TESTBENCH (tb/<block>/testbench_<block>.py)
  @cocotb.test()
  async def test_basic(dut):
      cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
      dut.i_rst.value = 1 ; await RisingEdge(dut.i_clk) ; dut.i_rst.value = 0
      dut.i_data.value = 42
      for _ in range(4): await RisingEdge(dut.i_clk)
      assert int(dut.o_data.value) == 42, f"got {int(dut.o_data.value)}"
  no testbench ships without an assert

SHELL
  ghdl -a --std=08 src/hdl/alu/alu.vhd            # syntax only, fast
  cd tb/alu && make SIM=ghdl                      # run cocotb, writes results.xml
  vivado -mode batch -source scripts/build_hw.tcl # synth + impl + bitstream
  grep -E "ERROR|CRITICAL" vivado_project/*.runs/*/runme.log

COMMON FAILURES
  cocotb timeout      -> clock not started, or waiting on the wrong edge
  unresolved reference-> file missing from add_files, or entity name != file name
  port mismatch       -> width/direction mismatch in port map
  synth "not constant"-> use to_integer(unsigned(sig)), not a bare integer
  timing not met / bitstream fails -> missing create_clock in the XDC
  ALWAYS simulate before synthesising; report the log line you actually read.
```

### 4.4 How to deliver it to a local model

* **Ollama:** `num_ctx` defaults to **4096 tokens** regardless of the model's training context
  ([Ollama FAQ](https://docs.ollama.com/faq)); raise it before trusting any 8k plan —
  `OLLAMA_CONTEXT_LENGTH=8192 ollama serve`, or `/set parameter num_ctx 8192`, or
  `"options": {"num_ctx": 8192}` on the API call. Since Ollama 0.12-ish the default scales with
  VRAM (<24 GiB → 4k, 24–48 GiB → 32k, ≥48 GiB → 256k)
  ([Context length](https://docs.ollama.com/context-length)). Note that `num_ctx` is a *sliding
  buffer*, not a hard cap: when it fills, older tokens are shifted out and the quickref can be the
  first casualty — keep the prompt short rather than relying on a huge window.
* **Bake it in:** `ollama create vivado-agent -f Modelfile` with a `SYSTEM` instruction holding
  the quickref ([Modelfile reference](https://docs.ollama.com/modelfile)). This is more reliable
  than pasting it into the first chat message.
* **llama.cpp:** `-c 8192` (or higher) and, for tool use, the server's built-in tools mode
  (`--tools all` / `--agent`) exposes file read/write over the API — a local, MCP-free alternative
  ([server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)).
* **Hermes:** put the quickref in `SOUL.md` or the project's `.hermes.md`; skills are loaded
  automatically on top ([Context files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)).
* Send the quickref **once**, in the system role. Re-pasting it in every message is the classic way
  to blow a 4k window.

---

## 5. How an agent should work in this repo

### 5.1 The loop

```
read project state
  → write / edit HDL
  → simulate (cocotb)          ← GATE: no synthesis while red
  → fix, re-simulate
  → synthesise / implement (build skill)
  → read the log, report with evidence
```

1. **Read the state first, always.** Directory listing, `AGENTS.md`, the entity index, the last
   log. Never start editing from memory of a previous session: the repo is the truth. A scripted
   `scripts/report_state.sh` (git status, module list, last run status, failing tests) makes this
   one tool call instead of ten.
2. **One entity (or one test) per iteration.** Small diffs are reviewable and diagnosable; a
   five-file change that fails to synthesise is a rabbit hole.
3. **Write the HDL and its testbench together.** A new module without a testbench is not finished —
   the testbench is what makes the next steps affordable.
4. **Simulation is a hard gate.** No synthesis, no implementation, no bitstream, no board
   programming until the cocotb test passes. Vivado synthesis will happily accept a functionally
   broken design, and the failure then appears as an unexplained `x` on hardware hours later. State
   the gate explicitly in the skills and in the quickref ("ALWAYS simulate before synthesising").
5. **Then build, then read.** Synthesis/implementation output is a report, not a verdict: the model
   must read `runme.log` / the timing summary and quote the line.
6. **Report with evidence.** "Synthesis passed, WNS = +0.412 ns at 100 MHz
   (`post_route_timing_summary.rpt`)" — not "it should work". If a command failed, say what failed
   and stop, rather than silently switching approach.

### 5.2 Verification obligations

| Claim | Minimum evidence |
|---|---|
| "the module works" | a cocotb run with `failures=0` in `results.xml` |
| "it synthesises" | a `synth_design` completion line from the real log |
| "timing is met" | WNS/TNS values read from the timing report |
| "the bitstream exists" | the `.bit`/`.bin` path plus the `write_bitstream` log line |
| "the software runs" | a serial console transcript |

Model-generated log excerpts are the single most common fabrication risk in this project. The
`agent-mcp-vivado` skill must require the literal line.

### 5.3 Working without MCP

An LLM with no tool access still executes — it just does it through the human.

1. **Generate the script, do not describe the action.** Write `scripts/create_project.tcl`,
   `scripts/build_hw.tcl`, `scripts/run_sim.sh` in full.
2. **Emit one exact command line** and nothing else: `vivado -mode batch -source
   scripts/build_hw.tcl`. Ask for its stdout, or the file it writes.
3. **Define the output contract before the run** — which file the script writes
   (`vivado_project/*.runs/synth_1/runme.log`, `tb/alu/results.xml`), so step 4 is mechanical.
4. **Parse the artifact, never the chat.** Ask for the file (or a grep of it), not a paraphrase:
   "paste `grep -E 'ERROR|CRITICAL' runme.log`".
5. **Never proceed on an assumed success.** If the output is missing, the next step is to ask for
   it again — not to write the next file.
6. Same pattern for MCP-capable agents when the server is down: the generated script path is the
   fallback, and the skill should say so explicitly.

This is also why `scripts/` and `assets/` are part of the deliverable: a deterministic script is
worth more to a small model than three paragraphs of instructions.

---

## 6. Project context files: `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `README.md`

### 6.1 Division of labour

| File | Owner / purpose | Content |
|---|---|---|
| `README.md` | humans | what the project is, install, how to build and test, folder map, licence |
| `AGENTS.md` | every coding agent | the agent-facing facts: exact build/test commands, layout rules, house style, "before you finish, run X" |
| `CLAUDE.md` | Claude Code (and anything that reads it) | **pointer only** — must not duplicate `AGENTS.md` |
| `.cursorrules` | legacy Cursor | **pointer only**, and only if the repo wants Cursor support |
| `.hermes.md` / `HERMES.md` | Hermes | **pointer only**, highest priority if present |

AGENTS.md is deliberately *not* the README: it exists so agents get a predictable place for build
steps and conventions that would clutter the human README, and it is now stewarded by the Agentic
AI Foundation under the Linux Foundation ([agents.md](https://agents.md/)).

### 6.2 How Hermes (and most agents) find them

Hermes scans the working directory in priority order — `.hermes.md` → `AGENTS.md` → `CLAUDE.md` →
`.cursorrules`, **first match wins** — and walks up to the git root; `CLAUDE.md` is also picked up
progressively from subdirectories
([Context files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)).
Because it is first-match-wins, files that duplicate each other are not "extra safety" — they are
silently ignored files that rot.

### 6.3 Structure that does not duplicate

1. **`AGENTS.md` is the single source of truth.** `CLAUDE.md`, `.cursorrules` and `.hermes.md` are
   symlinks to it, or one-line files containing "See `AGENTS.md`." The agents.md FAQ recommends
   exactly this migration trick: `mv AGENT.md AGENTS.md && ln -s AGENTS.md AGENT.md`.
2. **Facts in context files, procedures in skills.** `AGENTS.md` says *where things are and which
   command to run*; a skill says *how to do the work*. If a section of `AGENTS.md` is a numbered
   procedure, it is a missing skill — Claude Code's own guidance is that a section of `CLAUDE.md`
   that has grown into a procedure belongs in a skill
   ([Claude Code — skills](https://code.claude.com/docs/en/skills)).
3. **`AGENTS.md` carries the skill index** — one line per skill (name + description) so an agent
   without automatic skill discovery can still find them.
4. **Nested `AGENTS.md` for subprojects** (one under `tb/`, one under `scripts/` if they diverge).
   The nearest file wins, and agents read them automatically; the OpenAI monorepo carries 88 of
   them.
5. **Budget `AGENTS.md` at ~1 KB (≈250 tokens).** It is in *every* prompt of *every* session. Put
   the long version behind a link.
6. **No secrets, no absolute paths, no machine names.** Context files are committed and shared.

Suggested minimal `AGENTS.md` skeleton:

```markdown
# AGENTS.md
## Build & test (run these exact commands)
- lint HDL:   ghdl -a --std=08 src/hdl/**/*.vhd
- simulate:   cd tb/<block> && make SIM=ghdl
- build:      vivado -mode batch -source scripts/build_hw.tcl
## Layout            (see README.md for the full map)
src/hdl/<block>/  tb/<block>/  src/constraints/  scripts/  export/
## House rules
- one entity per file, file name = entity name; i_/o_/s_/C_/p_ prefixes
- NEVER synthesise before the cocotb test passes
- vivado_project/ is generated: never edit, never commit
## Skills (load the matching one before starting)
vivado-project-tcl, vhdl-synthesizable, cocotb-testbench, xdc-constraints-clocks,
vivado-build-timing, vitis-embedded-software, agent-mcp-vivado, eda-error-triage
```

---

## 7. Size, token and context recommendations

### 7.1 Budgets

| Artifact | Target size | ≈ tokens | Rationale |
|---|---|---|---|
| skill `description` | 120–180 chars (first 60 self-contained) | ~30–45 | loaded for **every** skill on every turn |
| `SKILL.md` body | 4–8 KB, ≤500 lines | 1–2k | Anthropic: metadata ~100 tok/skill, body < 5k tok, "under 500 lines" ([best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)) |
| one `references/*.md` | 5–15 KB, with a TOC | 1.5–4k | read only when pointed at; one at a time |
| `scripts/*` | any size | ~0 | executed, only stdout enters context |
| `AGENTS.md` | ~1 KB | ~250 | present in every prompt |
| `quickref.md` | 1 500–2 500 chars | ~450–650 | format-B system prompt |

Rule: **a skill that exceeds 8 KB is two skills, or one skill plus a reference.**

### 7.2 Chunking a project that does not fit

* **Index before content.** Auto-generate `src/hdl/INDEX.md` (entity, file, ports, width, one-line
  role) and `tb/INDEX.md`. The model then reads 30 lines instead of 5 000, and asks for the one
  entity it needs.
* **One entity + its testbench per context window.** That pair is the natural unit of work; it also
  matches the "one iteration" rule in §5.1.
* **Never load the whole `vivado_project/`.** Logs are grepped, not read; the generated tree is
  excluded from context entirely (`.gitignore` + an explicit rule in `AGENTS.md`).
* **References by section, not by file.** A 15 KB reference with a TOC can be entered at the right
  heading — which only works if the TOC exists (§2.3).
* **Summarise, then drop.** When a session must continue, compress the state into a short
  `docs/state.md` (goal, done, next, open error) rather than carrying the transcript.

### 7.3 Load order for an 8k-context model

Assume 8 192 tokens total. Reserve ~1 500 for the model's reply and template overhead → ~6 500
usable.

| Order | Load | ≈ tokens | Why this order |
|---|---|---|---|
| 1 | `quickref.md` (or `AGENTS.md`) | 0.6k | rules of the house, cheap, always needed |
| 2 | `src/hdl/INDEX.md` + directory listing | 0.4k | makes every later read targeted |
| 3 | the **one** skill whose trigger matched, body only | 1.5k | procedures |
| 4 | at most **one** reference section from that skill | 1.5k | detail only if steps 1–3 were not enough |
| 5 | the entity/testbench under edit + the failing log excerpt | 2.0k | the actual work |
| — | total | ≈6.0k | ~0.5k headroom for a second turn |

Hard rules that follow from the table:

* **Never load two skill bodies into one window.** With 8k, two 2k-token bodies plus a reference
  leaves nothing for the code being edited. If a task genuinely spans two skills, split it into two
  sessions.
* **Prefer execution to reading.** For a small model, "run `scripts/run_sim.sh` and paste the last
  20 lines" beats loading a 4k-token cocotb tutorial.
* **Set the window explicitly.** Ollama's 4 096-token default ([FAQ](https://docs.ollama.com/faq))
  will truncate this plan silently; raise `num_ctx`/`OLLAMA_CONTEXT_LENGTH` to 8 192+ before
  blaming the prompt.
* **Test on the smallest model you support.** Anthropic's guidance — a skill that works for a large
  model may be too terse for a small one; test across sizes and keep the smallest in the loop
  ([best practices — test with all models](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
  For us: the quickref must pass with an 8B quantised model at 8k, or it is not finished.

---

## 8. Sources

**Agent Skills format (Anthropic / open standard)**
* Skills overview — three levels of loading, `name`/`description` rules, ~100-token metadata:
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>
  (mirror: <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview>)
* Skill authoring best practices — conciseness, degrees of freedom, progressive disclosure,
  one-level references, TOC for >100-line files, eval-first development:
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
* Engineering blog — anatomy of a skill, progressive disclosure, code execution, security:
  <https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills>
* Open standard / portability: <https://agentskills.io/> ·
  reference skills: <https://github.com/anthropics/skills>
* Claude Code skills — where skills load, direct invocation, listing budget (1% of context,
  descriptions stripped under pressure):
  <https://code.claude.com/docs/en/skills>

**Project context files**
* AGENTS.md — README-for-agents, nested files, symlink migration, no required fields:
  <https://agents.md/>
* Hermes context files — discovery order `.hermes.md` → `AGENTS.md` → `CLAUDE.md` →
  `.cursorrules`, git-root walk, subdirectory discovery:
  <https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files>

**Hermes Agent (skill implementation of reference)**
* Documentation home: <https://hermes-agent.nousresearch.com/docs>
* Skills system — level 0/1/2 loading, `skill_manage` actions, skills hub, agentskills.io
  compatibility:
  <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills>
* Local skills inspected for this note (real conventions, not invented):
  * `~/.hermes/skills/software-development/hermes-agent-skill-authoring/SKILL.md` — full
    frontmatter shape, description ≤60 chars hardline, 57-char index truncation, section order,
    no router skills, no machine-local paths
  * `~/.hermes/skills/research/grounded-citations/` — SKILL.md + `references/` + `scripts/`,
    the model of level-3 delegation (12.6 KB / 257 lines)
  * `~/.hermes/skills/research/arxiv/SKILL.md` — Quick Reference table style (10 KB)
  * `~/.hermes/skills/autonomous-ai-agents/hermes-agent/` — 19 reference files + 3 templates
    behind a 13 KB SKILL.md
  * corpus statistics used above: 87 `SKILL.md` files under `~/.hermes/skills/`, sizes 2.3–78 KB,
    median 8.8 KB

**Local model runtimes and context**
* Ollama FAQ — default context 4 096, `num_ctx`, `OLLAMA_CONTEXT_LENGTH`:
  <https://docs.ollama.com/faq>
* Ollama context length — VRAM-based defaults (<24 GiB → 4k, 24–48 GiB → 32k, ≥48 GiB → 256k),
  64k recommended for agent/coding tasks: <https://docs.ollama.com/context-length>
* Ollama Modelfile — `SYSTEM`, `PARAMETER`, `TEMPLATE`:
  <https://docs.ollama.com/modelfile>
* llama.cpp server — `-c/--ctx-size`, built-in tools/agent mode (`--tools all`) as an MCP-free
  path for local models:
  <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>

**Project-internal reference**
* `skills.md` at the repo root (4 857 chars ≈ 1.2k tokens) — the current draft quickref this note
  supersedes: keep its content, split it into `quickref.md` (§4.3) plus the eight skills (§3),
  and drop the MCP table and Vitis tutorial from the always-loaded block.
