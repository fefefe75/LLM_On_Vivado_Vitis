#!/usr/bin/env python3
"""The MCP tool loop, replayed by a scripted client. No LLM in this run.

WHAT THIS IS: a plain MCP client that calls the server in the order an agent is
expected to follow — write the RTL, simulate it, synthesize it, read the timing
report. The sequence and the VHDL text are fixed in this file; nothing here decides
anything. Every tool call and every line of output is real (the server runs as a
stdio subprocess, exactly as Hermes / Claude Desktop / VS Code would start it): if
a tool fails, you see the failure.

WHAT THIS IS NOT: a recorded LLM session. No model picks the next call and no model
reads the results back. To see that, connect the server to your agent and let it
work; this script exists so the loop can be replayed, timed and diffed with no model
involved.

Usage: python3 mcp_tool_loop.py --workspace <dir> [--to implementation]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

C, Y, G, D, R = "\033[1;36m", "\033[1;33m", "\033[1;32m", "\033[2m", "\033[0m"

COUNTER = """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Synchronous counter, enable + synchronous active-high reset.
entity counter is
    generic (
        C_WIDTH : positive := 8
    );
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;
        i_en    : in  std_logic;
        o_count : out std_logic_vector(C_WIDTH - 1 downto 0)
    );
end entity counter;

architecture rtl of counter is
    signal s_count : unsigned(C_WIDTH - 1 downto 0) := (others => '0');
begin
    o_count <= std_logic_vector(s_count);
    p_count : process (i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_count <= (others => '0');
            elsif i_en = '1' then
                s_count <= s_count + 1;
            end if;
        end if;
    end process p_count;
end architecture rtl;
"""

XDC = """# 100 MHz on the counter clock (minimal: no pin assignment, see docs/06)
create_clock -name sys_clk -period 10.000 [get_ports i_clk]
"""


def payload(result):
    data = getattr(result, "data", None)
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    return data


def step(n, total, call, note=""):
    print(f"\n{Y}[{n}/{total}]{R} {call}" + (f"  {D}{note}{R}" if note else ""))


def line(text, pad=""):
    print(f"      {pad}{text}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(Path.cwd()))
    ap.add_argument("--repo", default=str(Path.home() / "Documents/projet_vivado_llm/LLM_On_Vivado_Vitis"))
    ap.add_argument("--tool-root", default=str(Path.home() / "vivado" / "2025.2"))
    ap.add_argument("--to", default="implementation")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    ws = Path(args.workspace).resolve()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "mcp")
    env["PATH"] = f"{Path.home()}/Documents/mon_env/mon_env/bin:{env['PATH']}"
    env["FASTMCP_SHOW_SERVER_BANNER"] = "false"   # the server's banner would pollute the trace
    env["FASTMCP_LOG_LEVEL"] = "ERROR"
    transport = StdioTransport(
        command=str(repo / "mcp" / ".venv" / "bin" / "python"),
        args=["-m", "vivado_mcp", "--workspace", str(ws), "--tool-root", args.tool_root],
        env=env,
    )

    print(f"{C}scripted MCP client -> Vivado/Vitis MCP server{R}  {D}(stdio, workspace = {ws}){R}")
    print(f"{D}no model in this run: the calls below are the fixed loop an agent is expected to{R}")
    print(f"{D}follow. Every tool call and every output line is real.{R}")
    async with Client(transport) as client:
        tools = sorted(t.name for t in await client.list_tools())
        line(f"tools exposed by the server: {len(tools)}")
        for i in range(0, len(tools), 6):
            line(f"{D}{', '.join(tools[i:i+6])}{R}")

        total = 8

        step(1, total, "env_info(deep=True)", "what is really installed")
        info = payload(await client.call_tool("env_info", {"deep": True}))
        for name in ("vivado", "xsim", "ghdl", "cocotb-config", "make"):
            t = info.get("tools", {}).get(name)
            if not t or not t.get("found"):
                continue
            version = (t.get("version") or "").split("|")[0].strip().replace("(lin64)", "").strip()
            line(f"{name:<14} {version[:44]}")

        step(2, total, 'write_text_file("rtl/counter.vhd")', "the RTL an agent would write")
        line(str(payload(await client.call_tool(
            "write_text_file", {"path": "rtl/counter.vhd", "content": COUNTER}))))

        step(3, total, 'write_text_file("constraints/top.xdc")', "1 clock, 100 MHz")
        line(str(payload(await client.call_tool(
            "write_text_file", {"path": "constraints/top.xdc", "content": XDC}))))

        step(4, total, 'cocotb_run("tb", sim="ghdl")', "SIMULATION before any synthesis")
        r = payload(await client.call_tool("cocotb_run", {"tb_dir": "tb", "sim": "ghdl", "seed": 1234}))
        job_tb = r["id"]
        line(f"job {job_tb}  ({r['kind']})  -> {r['status']}")

        step(5, total, f'wait_for_job("{job_tb}")', "bounded wait: it never blocks forever")
        t0 = time.time()
        r = payload(await client.call_tool("wait_for_job", {"job_id": job_tb, "max_wait_s": 120}))
        j = r["job"]
        line(f"status={j['status']}  returncode={j['returncode']}  duration={j['duration_s']} s"
             f"  {D}(real wait {time.time()-t0:.1f} s){R}")

        step(6, total, 'cocotb_results("tb")', "the verdict, per test")
        r = payload(await client.call_tool("cocotb_results", {"tb_dir": "tb"}))
        if isinstance(r, dict):
            for t in r.get("testcases", []):
                line(f"{str(t.get('status','?')).upper():<7} {t.get('module','?')}.{t.get('name','?')}"
                     f"   {t.get('sim_time_ns','?')} ns")
            line(f"TESTS={r.get('tests')} PASS={r.get('passed')} FAIL={r.get('failures')} "
                 f"ERRORS={r.get('errors')}   all_passed={r.get('all_passed')}")
        else:
            line(str(r))

        step(7, total, "vivado_run(scripts/create_project.tcl)", "project, sources, constraints")
        r = payload(await client.call_tool("vivado_run", {
            "script_path": "scripts/create_project.tcl",
            "tclargs": ["--name", "prj", "--part", "xc7z020clg400-1", "--top", "counter"],
            "timeout_s": 900}))
        r = payload(await client.call_tool("wait_for_job", {"job_id": r["id"], "max_wait_s": 300}))
        line(f"status={r['job']['status']}  returncode={r['job']['returncode']}")

        step(8, total, f"vivado_run(build.tcl --to {args.to})", "synthesis, implementation, reports")
        t0 = time.time()
        r = payload(await client.call_tool("vivado_run", {
            "script_path": "scripts/build.tcl",
            "tclargs": ["--xpr", "prj/prj.xpr", "--to", args.to, "--jobs", "4",
                        "--allow-unconstrained", "1"],
            "timeout_s": 2400}))
        job_build = r["id"]
        line(f"job {job_build} started, the client polls it (bounded waits)")
        r = payload(await client.call_tool("wait_for_job", {"job_id": job_build, "max_wait_s": 600}))
        j = r["job"]
        line(f"status={j['status']}  returncode={j['returncode']}  duration={j['duration_s']} s"
             f"  {D}(real wait {time.time()-t0:.1f} s){R}")

        print(f"\n{C}-- job_log(errors_only=True): what broke, if anything --{R}")
        log = payload(await client.call_tool("job_log", {"job_id": job_build, "errors_only": True}))
        line(f"errors: {log.get('error_count', '?')}    warnings: {log.get('warning_count', '?')}")
        scan = payload(await client.call_tool(
            "job_log", {"job_id": job_build, "pattern": "== ", "tail": 12}))
        for m in (scan.get("matches") or [])[-4:]:
            line(str(m).strip()[:104], pad=f"{G}")

        print(f"\n{C}-- project_status(\"prj\"): where are the reports? (starts nothing) --{R}")
        st = payload(await client.call_tool("project_status", {"project_dir": "prj"}))
        line(f"runs found: {', '.join(st.get('runs_found', []))}")
        timings = st.get("artefacts", {}).get("timing", [])
        for t in timings[:3]:
            line(str(t), pad=f"{D}")

        rpt = f"prj/{timings[0]}" if timings else "prj/reports/timing_summary.rpt"
        print(f"\n{C}-- report_summary(\"{rpt}\") --{R}")
        r = payload(await client.call_tool("report_summary", {"path": rpt}))
        t = r.get("timing", {})
        line(f"parsed={t.get('parsed')}   WNS={t.get('wns_ns')} ns   TNS={t.get('tns_ns')} ns   "
             f"WHS={t.get('whs_ns')} ns")
        line(f"critical paths reported: {len(t.get('worst_paths', []))}   timing_met={t.get('timing_met')}")
        for w in (t.get("worst_paths") or [])[:2]:
            line(f"{w.get('slack_ns')} ns  {w.get('source')} -> {w.get('destination')}"
                 f"  ({w.get('logic_levels')} logic level(s))")

        print(f"\n{G}== loop complete: write RTL -> simulate -> synthesize -> read the timing{R}")
        print(f"{G}   report. The sequence is scripted; the tool calls and their outputs are not.{R}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
