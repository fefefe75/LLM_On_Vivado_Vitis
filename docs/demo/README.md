# Demo — the MCP tool loop, replayed by a scripted client

## What this is, and what it is not

**It is**: a plain MCP client (`mcp_tool_loop.py`) that calls the server over stdio in the
order an agent is expected to follow — write the RTL, simulate it, synthesize it, read the
timing report. Every tool call, every result and every line of output in the recording comes
from a real run of the server against real Vivado 2025.2 and GHDL 6.0.0 on this machine.

**It is not**: a recorded LLM session. There is no model in that loop. The sequence is fixed
in the script, the counter's VHDL is written in the script, and nothing decides anything at
run time. Calling this "an agent driving Vivado" would be an overstatement, and the whole
point of this repository is not to make that kind of statement.

So why keep it? Because a scripted client can be replayed, timed and diffed on demand, with
no model and no API key: it is a **regression test of the tool layer**, and the GIF is a
by-product. To watch a model pick its own calls, connect the server to your agent (Hermes,
Claude Desktop, VS Code, Cline…) — that is what the server is for, and the loop below is the
one it will walk.

| File | What it is |
|---|---|
| `mcp-tool-loop.gif` | 1280x720, ~12 s: the front-page animation, rendered from the cast |
| `mcp-tool-loop.cast` | the **raw recording** (asciinema v2), untouched |
| `mcp-tool-loop.txt` | the same session as plain text (ANSI stripped), for grep and diffing |
| `mcp_tool_loop.py` | the client: fixed sequence, fixed RTL, real calls |
| `cast2gif.py` | the renderer: `.cast` → terminal screen (pyte) → PNG frames (Pillow) → GIF (ffmpeg) |

## The session that was recorded

One process starts the MCP server over **stdio** (exactly how Hermes, Claude Desktop or
VS Code start it), points it at a scratch workspace (`/tmp/fpga_demo`, never this repository)
and calls tools in a loop. Nothing is staged; the numbers below are what the tools returned
that day (Vivado 2025.2, GHDL 6.0.0, cocotb 2.0.1, Fedora 44):

| Step | Tool call | Real result |
|---|---|---|
| 1 | `env_info(deep=True)` | Vivado v2025.2 (64-bit), XSim v2025.2, GHDL 6.0.0, cocotb 2.0.1, GNU make 4.4.1 |
| 2 | `write_text_file("rtl/counter.vhd")` | `written (871 characters)` |
| 3 | `write_text_file("constraints/top.xdc")` | `written (133 characters)` — a 100 MHz `create_clock` |
| 4–5 | `cocotb_run("tb")` + `wait_for_job` | `status=ok`, 1.0 s |
| 6 | `cocotb_results("tb")` | `TESTS=3 PASS=3 FAIL=0 ERRORS=0`, `all_passed=True` |
| 7 | `vivado_run(create_project.tcl)` | `status=ok returncode=0` |
| 8 | `vivado_run(build.tcl --to implementation)` | `status=ok`, 82.2 s |
| 9 | `job_log(errors_only=True)` | `errors: 0  warnings: 0`, `== impl_1 : PROGRESS=100% STATUS=route_design Complete!` |
| 10 | `project_status("prj")` | runs found: `impl_1`, `synth_1`; reports listed |
| 11 | `report_summary(...counter_timing_summary_routed.rpt)` | `WNS=7.915 ns  TNS=0.0  WHS=0.163  timing_met=True`, worst path `s_count_reg[5]/C -> s_count_reg[6]/D` |

## Reproduce it

```bash
python3 -m venv mcp/.venv && mcp/.venv/bin/pip install -r mcp/requirements.txt asciinema pyte pillow
mkdir -p /tmp/fpga_demo/rtl /tmp/fpga_demo/tb /tmp/fpga_demo/scripts
cp templates/vivado/create_project.tcl templates/vivado/build.tcl /tmp/fpga_demo/scripts/
cp examples/01-counter-cocotb/tb/Makefile examples/01-counter-cocotb/tb/test_counter.py \
   examples/01-counter-cocotb/tb/run_tests.py /tmp/fpga_demo/tb/
mcp/.venv/bin/python docs/demo/mcp_tool_loop.py --workspace /tmp/fpga_demo
```

Record it again and rebuild the GIF (the renderer needs `pyte` and `Pillow`):

```bash
mcp/.venv/bin/asciinema rec --overwrite --cols 100 --rows 30 \
  --command "mcp/.venv/bin/python docs/demo/mcp_tool_loop.py --workspace /tmp/fpga_demo" \
  /tmp/mcp-tool-loop.cast
mcp/.venv/bin/python docs/demo/cast2gif.py /tmp/mcp-tool-loop.cast /tmp/mcp-tool-loop.gif \
  --fps 10 --idle-max 2.5
```

## What is honest about this artefact

- **No model, no decision.** See above: fixed sequence, fixed VHDL. What is exercised is the
  tool layer, and the first line of the recording says so out loud.
- **Idle time is compressed.** Step 8 takes 82.2 s of Vivado with nothing on screen;
  `cast2gif.py` caps every silent gap at 2.5 s of playback, so the GIF lasts ~12 s
  instead of ~94 s. No other edit: the text is the terminal's own output, replayed
  through a real terminal emulator.
- **It is a rendered terminal, not a screen capture** (pyte reconstructs the screen,
  Pillow draws it, ffmpeg encodes it). Colours and layout come from the recording,
  the font is JetBrains Mono.
- **The flow stops at `--to implementation`**: the counter has no pin assignment and
  no I/O standard, so `write_bitstream` would be refused by Vivado's DRCs. Post-route
  timing is real; there is no bitstream in this demo.
- **The RTL written is this repository's own counter**, not a new design: the demo is
  about the *tool loop*, and the counter is the smallest thing whose timing report
  means anything.
- **The workspace is a scratch directory** (`/tmp/fpga_demo`). The demo never writes
  inside the repository, which is also why it doubles as a check that
  `--workspace` confinement works.
- **Language**: the tool results shown here are the ones already in English. The rest
  of the server — tool docstrings and most messages — is still French
  (`mcp/vivado_mcp/*.py`, ~171 lines): the translation is in progress, tracked in
  `docs/README.md`.
