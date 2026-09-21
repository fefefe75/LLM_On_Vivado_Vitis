# Demo — an agent driving Vivado and cocotb through the MCP server

| File | What it is |
|---|---|
| `agent-loop.gif` | 1280x720, ~12 s: the front-page animation |
| `agent-loop.cast` | the **raw recording** (asciinema v2), untouched — the GIF is a render of this file |
| `agent-loop.txt` | the same session as plain text (ANSI stripped), for grep and diffing |
| `agent_loop_demo.py` | the driver: a small MCP client that runs the loop below |
| `cast2gif.py` | the renderer: `.cast` → terminal screen (pyte) → PNG frames (Pillow) → GIF (ffmpeg) |

## The session that was recorded

One process starts the MCP server over **stdio** (exactly how Hermes, Claude Desktop
or VS Code start it), points it at a scratch workspace (`/tmp/fpga_demo`, never this
repository) and calls tools in a loop. Nothing is staged; the numbers below are what
the tools returned that day (Vivado 2025.2, GHDL 6.0.0, cocotb 2.0.1, Fedora 44):

| Step | Tool call | Real result |
|---|---|---|
| 1 | `env_info(deep=True)` | Vivado v2025.2 (64-bit), XSim v2025.2, GHDL 6.0.0, cocotb 2.0.1, GNU make 4.4.1 |
| 2 | `write_text_file("rtl/counter.vhd")` | `written (871 characters)` |
| 3 | `write_text_file("constraints/top.xdc")` | `written (133 characters)` — a 100 MHz `create_clock` |
| 4–5 | `cocotb_run("tb")` + `wait_for_job` | job `20260921-101717-cocotb-ghdl-f1a5c2`, `status=ok`, 1.1 s |
| 6 | `cocotb_results("tb")` | `TESTS=3 PASS=3 FAIL=0 ERRORS=0`, `all_passed=True` |
| 7 | `vivado_run(create_project.tcl)` | `status=ok returncode=0` |
| 8 | `vivado_run(build.tcl --to implementation)` | `status=ok`, 84.7 s |
| 9 | `job_log(errors_only=True)` | `errors: 0  warnings: 0`, `== impl_1 : PROGRESS=100% STATUS=route_design Complete!` |
| 10 | `project_status("prj")` | runs found: `impl_1`, `synth_1`; reports listed |
| 11 | `report_summary(...counter_timing_summary_routed.rpt)` | `WNS=7.915 ns  TNS=0.0  WHS=0.163  timing_met=True`, worst path `s_count_reg[5]/C -> s_count_reg[6]/D` (2 logic levels) |

## Reproduce it

```bash
python3 -m venv mcp/.venv && mcp/.venv/bin/pip install -r mcp/requirements.txt asciinema pyte pillow
mkdir -p /tmp/fpga_demo/rtl /tmp/fpga_demo/tb /tmp/fpga_demo/scripts
cp templates/vivado/create_project.tcl templates/vivado/build.tcl /tmp/fpga_demo/scripts/
cp examples/01-counter-cocotb/tb/Makefile examples/01-counter-cocotb/tb/test_counter.py \
   examples/01-counter-cocotb/tb/run_tests.py /tmp/fpga_demo/tb/
mcp/.venv/bin/python docs/demo/agent_loop_demo.py --workspace /tmp/fpga_demo
```

Record it and rebuild the GIF (the renderer needs `pyte` and `Pillow`):

```bash
mcp/.venv/bin/asciinema rec --overwrite --cols 100 --rows 30 \
  --command "mcp/.venv/bin/python docs/demo/agent_loop_demo.py --workspace /tmp/fpga_demo" \
  /tmp/agent-loop.cast
mcp/.venv/bin/python docs/demo/cast2gif.py /tmp/agent-loop.cast /tmp/agent-loop.gif \
  --fps 10 --idle-max 2.5
```

## What is honest about this artefact

- **Idle time is compressed.** Step 8 takes 84.7 s of Vivado with nothing on screen;
  `cast2gif.py` caps every silent gap at 2.5 s of playback, so the GIF lasts ~12 s
  instead of ~97 s. No other edit: the text is the terminal's own output, replayed
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
