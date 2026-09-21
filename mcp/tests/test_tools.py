"""Tests des outils et de la gestion des jobs — avec de VRAIS processus.

Aucun Vivado n'est nécessaire : on exécute `make` et `python3` (tous deux dans la
liste blanche) sur des scripts bidons qui produisent des logs réalistes. Cela
prouve que le lancement, le suivi, le filtrage d'erreurs, le timeout et
l'annulation fonctionnent réellement.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from vivado_mcp.config import Settings
from vivado_mcp.tools import FpgaTools


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "counter.vhd").write_text(
        "entity counter is end entity;\n-- ERROR: [Synth 8-327] inferring latch\n",
        encoding="utf-8",
    )
    tb = tmp_path / "tb" / "counter"
    tb.mkdir(parents=True)
    (tb / "Makefile").write_text(
        "all:\n"
        "\t@echo \"INFO     cocotb.regression running test_counter.test_ok (1/1)\"\n"
        "\t@echo \"ERROR: [Synth 8-327] inferring latch\"\n"
        "\t@echo \"WARNING: [Synth 8-3331] unconnected port\"\n"
        "\t@echo \"TESTS=1 PASS=1 FAIL=0\"\n",
        encoding="utf-8",
    )
    (tb / "sim_build").mkdir()
    (tb / "sim_build" / "results.xml").write_text(
        '<testsuites name="results"><testsuite name="all" package="all">'
        '<testcase name="test_ok" classname="test_counter" time="0.001" sim_time_ns="50.0" />'
        "</testsuite></testsuites>\n",
        encoding="utf-8",
    )
    (tmp_path / "Makefile").write_text(
        "fail:\n\t@echo \"ERROR: [Common 17-69] Command failed\"\n\t@exit 1\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def tools(workspace: Path) -> FpgaTools:
    return FpgaTools(Settings.from_env(workspace=str(workspace)))


# --------------------------------------------------------------------------- #
# fichiers
# --------------------------------------------------------------------------- #


def test_project_tree_ignores_build_dirs(tools: FpgaTools) -> None:
    tree = tools.project_tree(".", depth=3)
    assert "counter.vhd" in tree
    assert "sim_build" not in tree
    assert ".mcp_runs" not in tree


def test_read_write_roundtrip(tools: FpgaTools) -> None:
    assert "written" in tools.write_text_file("rtl/nouveau.vhd", "entity nouveau is end entity;\n")
    assert "entity nouveau" in tools.read_text_file("rtl/nouveau.vhd")


def test_read_refuses_outside(tools: FpgaTools) -> None:
    with pytest.raises(PermissionError):
        tools.read_text_file("/etc/passwd")


def test_grep_finds_pattern(tools: FpgaTools) -> None:
    hits = tools.grep("inferring latch", ".")
    assert "counter.vhd" in hits
    assert tools.grep("motif_absent_xyz", ".") == "aucun resultat"


def test_write_refuses_existing_without_overwrite(tools: FpgaTools) -> None:
    tools.write_text_file("a.vhd", "un\n")
    with pytest.raises(FileExistsError):
        tools.write_text_file("a.vhd", "deux\n", overwrite=False)


# --------------------------------------------------------------------------- #
# environnement
# --------------------------------------------------------------------------- #


def test_env_info_lists_real_tools(tools: FpgaTools) -> None:
    payload = json.loads(tools.env_info())
    assert payload["workspace"]
    assert "make" in payload["tools"]
    assert payload["tools"]["make"]["found"] is True        # make est installe et autorise
    assert payload["tools"]["vivado"]["found"] in (True, False)   # detecte, present ou non
    assert any("XSim" in note for note in payload["notes"])


# --------------------------------------------------------------------------- #
# jobs
# --------------------------------------------------------------------------- #


def test_job_success_and_log_scan(tools: FpgaTools) -> None:
    job = tools.cocotb_run("tb/counter", sim="ghdl")
    assert job["status"] in ("running", "ok")
    summary = json.loads(tools.job_status(job["id"], wait_s=20))
    assert summary["status"] == "ok", summary
    assert summary["returncode"] == 0

    log = json.loads(tools.job_log(job["id"]))
    assert log["error_count"] == 1
    assert log["warning_count"] == 1
    assert any("8-327" in line for line in log["errors"])
    assert any("TESTS=1 PASS=1 FAIL=0" in line for line in log["tail"])

    filtered = json.loads(tools.job_log(job["id"], pattern="TESTS="))
    assert filtered["matches"]


def test_job_failure_is_reported(tools: FpgaTools) -> None:
    jobs = tools.jobs
    make = tools.settings.resolve_binary("make")
    job = jobs.start("make", [make, "fail"], cwd=tools.settings.workspace,
                     env=tools.settings.base_env(), timeout_s=30)
    summary = json.loads(tools.job_status(job.id, wait_s=20))
    assert summary["status"] == "failed"
    # GNU make renvoie 2 quand une recette echoue (1 = erreur de makefile)
    assert summary["returncode"] != 0
    scan = jobs.get(job.id).scan()
    assert any("Common 17-69" in line for line in scan["errors"])


def test_job_timeout_kills_process(tools: FpgaTools) -> None:
    """Un job qui depasse son delai doit etre tue et marque 'timeout'."""
    jobs = tools.jobs
    python = tools.settings.resolve_binary("python3")
    started = time.time()
    job = jobs.start("sleep", [python, "-c", "import time; time.sleep(60)"],
                     cwd=tools.settings.workspace, env=tools.settings.base_env(), timeout_s=2)
    summary = json.loads(tools.job_status(job.id, wait_s=30))
    assert summary["status"] == "timeout", summary
    assert time.time() - started < 45
    assert "depasse" in (summary["error"] or "")


def test_job_cancel(tools: FpgaTools) -> None:
    jobs = tools.jobs
    python = tools.settings.resolve_binary("python3")
    job = jobs.start("sleep", [python, "-c", "import time; time.sleep(60)"],
                     cwd=tools.settings.workspace, env=tools.settings.base_env(), timeout_s=120)
    time.sleep(1.0)
    payload = json.loads(tools.job_cancel(job.id))
    assert payload["status"] == "cancelled"
    assert jobs.get(job.id).status == "cancelled"


def test_job_unknown_id_is_clear(tools: FpgaTools) -> None:
    with pytest.raises(KeyError) as excinfo:
        tools.job_status("job-inexistant")
    assert "job inconnu" in str(excinfo.value)


def test_job_list_and_persistence(tools: FpgaTools) -> None:
    job = tools.cocotb_run("tb/counter")
    tools.job_status(job["id"], wait_s=20)
    listing = json.loads(tools.job_list())["jobs"]
    assert listing and listing[0]["id"] == job["id"]
    meta = tools.settings.runs_dir / f"{job['id']}.json"
    assert meta.exists()
    assert json.loads(meta.read_text())["status"] == "ok"
    assert (tools.settings.runs_dir / f"{job['id']}.log").exists()


def test_job_missing_binary(tools: FpgaTools) -> None:
    """Un binaire absent doit produire un job 'error' lisible, pas une exception."""
    job = tools.jobs.start("nope", ["/inexistant/binaire"], cwd=tools.settings.workspace,
                           env=tools.settings.base_env(), timeout_s=5)
    assert job.status == "error"
    assert "introuvable" in (job.error or "")


# --------------------------------------------------------------------------- #
# rapports + actions matérielles
# --------------------------------------------------------------------------- #


def test_cocotb_results_reads_real_xml(tools: FpgaTools) -> None:
    payload = json.loads(tools.cocotb_results("tb/counter"))
    assert payload["parsed"] is True
    assert payload["tests"] == 1 and payload["all_passed"] is True


def test_project_status_without_vivado(tools: FpgaTools) -> None:
    payload = json.loads(tools.project_status("."))
    assert payload["project_dir"]
    assert payload["runs_found"] == []
    assert "timing" not in payload


def test_program_fpga_requires_confirmation(tools: FpgaTools) -> None:
    payload = tools.program_fpga("faux.bit", confirm=False)
    assert payload["refused"] is True
    assert "confirm=True" in payload["reason"]


def test_vivado_run_needs_exactly_one_source(tools: FpgaTools) -> None:
    with pytest.raises(ValueError):
        tools.vivado_run()                                   # aucun script
    with pytest.raises(ValueError):
        tools.vivado_run(tcl="puts 1", script_path="scripts/x.tcl")   # les deux


def test_vivado_run_without_installed_vivado(tools: FpgaTools) -> None:
    """Vivado absent : message explicite qui dit quoi faire, pas une trace Python."""
    if tools.settings.resolve_binary("vivado") is not None:
        pytest.skip("Vivado est installe sur cette machine")
    with pytest.raises(FileNotFoundError) as excinfo:
        tools.vivado_run(tcl="puts hello")
    assert "FPGA_MCP_TOOL_ROOT" in str(excinfo.value)


def test_vivado_run_writes_script_before_failing(tools: FpgaTools) -> None:
    """Le script Tcl du LLM est bien ecrit dans le projet, meme si Vivado manque."""
    try:
        tools.vivado_run(tcl="puts \"bonjour vivado\"", name="llm_build.tcl")
    except FileNotFoundError:
        pass
    script = tools.settings.workspace / "scripts" / "generated" / "llm_build.tcl"
    assert script.exists()
    assert "bonjour vivado" in script.read_text()
