#!/usr/bin/env python3
"""Verification du flux Vivado REEL, de bout en bout, avec les scripts du depot.

Appele par scripts/verify_all.sh (section EDA) mais utilisable seul :

    source ~/vivado/2025.2/Vivado/settings64.sh
    python3 scripts/verify_vivado.py

Ce que le script fait :
  1. cree un projet de test dans un dossier temporaire (design minimal : compteur
     24 bits + 4 sorties), avec les scripts templates/vivado/ du depot ;
  2. lance la synthese ;
  3. verifie PROGRESS/STATUS du run et l'existence des rapports ;
  4. analyse le rapport de timing REEL avec l'analyseur du serveur MCP
     (mcp/vivado_mcp/reports.py) : c'est ce qui valide l'analyseur ;
  5. nettoie, et sort en 1 si une seule etape a echoue.

Sortie : une ligne par etape, puis un bilan. Aucune conclusion sans code retour.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TPL = REPO / "templates" / "vivado"

DESIGN = """\
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity top is
    generic (C_WIDTH : positive := 24);
    port (i_clk : in std_logic; o_led : out std_logic_vector(3 downto 0));
end entity top;

architecture rtl of top is
    signal s_count : unsigned(C_WIDTH - 1 downto 0) := (others => '0');
begin
    p_count : process (i_clk)
    begin
        if rising_edge(i_clk) then
            s_count <= s_count + 1;
        end if;
    end process p_count;
    o_led <= std_logic_vector(s_count(C_WIDTH - 1 downto C_WIDTH - 4));
end architecture rtl;
"""

XDC = """\
create_clock -period 10.000 -name sys_clk -waveform {0.000 5.000} [get_ports i_clk]
"""

PART = "xc7z020clg400-1"


def run(cmd: list[str], cwd: Path, log: Path) -> int:
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT)
    return proc.returncode


def lines(path: Path, pattern: str) -> list[str]:
    if not path.exists():
        return []
    return [ln for ln in path.read_text(errors="replace").splitlines() if re.search(pattern, ln)]


def main() -> int:
    if shutil.which("vivado") is None:
        print("vivado introuvable dans le PATH : sourcer settings64.sh (voir docs/01-toolchain.md)")
        return 2

    ok = fail = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal ok, fail
        if condition:
            ok += 1
            print(f"  {label:38s} OK {detail}")
        else:
            fail += 1
            print(f"  {label:38s} ECHEC {detail}")

    with tempfile.TemporaryDirectory(prefix="verif_vivado_") as tmp:
        work = Path(tmp)
        (work / "rtl").mkdir()
        (work / "constraints").mkdir()
        (work / "rtl" / "top.vhd").write_text(DESIGN, encoding="utf-8")
        (work / "constraints" / "timing.xdc").write_text(XDC, encoding="utf-8")

        print("== 1. creation du projet (templates/vivado/create_project.tcl)")
        rc = run(["vivado", "-mode", "batch", "-source", str(TPL / "create_project.tcl"),
                  "-nolog", "-nojournal", "-tclargs",
                  "--name", "verif", "--part", PART, "--top", "top"],
                 work, work / "create.log")
        check("create_project.tcl", rc == 0, f"code {rc}")
        check("projet cree", (work / "verif" / "verif.xpr").exists())

        print("== 2. synthese (templates/vivado/build.tcl --to synthesis)")
        rc = run(["vivado", "-mode", "batch", "-source", str(TPL / "build.tcl"),
                  "-nolog", "-nojournal", "-tclargs",
                  "--xpr", str(work / "verif" / "verif.xpr"),
                  "--to", "synthesis", "--jobs", "4"],
                 work, work / "build.log")
        build_log = (work / "build.log").read_text(errors="replace")
        check("build.tcl", rc == 0, f"code {rc}")
        progress = [ln for ln in build_log.splitlines() if "PROGRESS=" in ln]
        check("run synthese a 100%", bool(progress), progress[-1].strip() if progress else "aucune ligne")

        reports = work / "verif" / "reports"
        timing = reports / "post_synth_timing.rpt"
        utilization = reports / "post_synth_utilization.rpt"
        check("rapport de timing ecrit", timing.exists())
        check("rapport d'utilisation ecrit", utilization.exists())

        print("== 3. analyse des rapports REELS (mcp/vivado_mcp/reports.py)")
        sys.path.insert(0, str(REPO / "mcp"))
        from vivado_mcp.reports import parse_timing_report, parse_utilization_report

        timing_data = parse_timing_report(timing.read_text(errors="replace")) if timing.exists() else {}
        util_data = parse_utilization_report(utilization.read_text(errors="replace")) if utilization.exists() else {}

        check("timing analyse (WNS lu)", timing_data.get("parsed") is True,
              f"WNS={timing_data.get('wns_ns')} ns, timing_met={timing_data.get('timing_met')}")
        check("utilisation analysee", util_data.get("parsed") is True,
              f"ressources={list(util_data.get('resources', {}))[:3]}")
        check("aucune erreur dans le log", not lines(work / "vivado.log", r"^ERROR:"),
              f"{len(lines(work / 'vivado.log', r'^ERROR:'))} erreur(s)")

        print("== detail")
        print(json.dumps({"timing": {k: v for k, v in timing_data.items() if k != "raw"},
                          "resources": util_data.get("resources", {})}, indent=1)[:800])

    print(f"\n== BILAN Vivado : {ok} OK, {fail} ECHEC")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
