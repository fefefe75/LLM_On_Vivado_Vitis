"""Tests des analyseurs de rapports et de logs.

Jeu de données, et sa provenance est explicite :

  * `fixtures/real_timing_2025.2.rpt`, `fixtures/real_utilization_2025.2.rpt`,
    `fixtures/real_log_2025.2.log` : extraits **AUTHENTIQUES** de rapports et du
    log produits par Vivado v2025.2 (lin64) sur un compteur 24 bits, partie
    xc7z020clg400-1, horloge 100 MHz. En-tête (date, hôte, chemins) retirée.
  * `REAL_COCOTB_RESULTS` / `REAL_COCOTB_FAILURE` : copies d'un results.xml
    authentique de cocotb 2.0.1.
  * Les fixtures de **timing en échec** et de messages multi-sévérités sont
    SYNTHÉTIQUES : aucun design en violation de timing n'a été produit. Elles
    testent le chemin négatif et sont nommées `*_synthetic` — c'est un trou
    assumé, pas une vérification déguisée.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vivado_mcp.reports import (
    parse_cocotb_results,
    parse_messages,
    parse_timing_report,
    parse_utilization_report,
    summarize_log,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# --------------------------------------------------------------------------- #
# Vivado 2025.2 : rapports reels
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def real_timing() -> str:
    return (FIXTURES / "real_timing_2025.2.rpt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def real_utilization() -> str:
    return (FIXTURES / "real_utilization_2025.2.rpt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def real_log() -> str:
    return (FIXTURES / "real_log_2025.2.log").read_text(encoding="utf-8")


def test_real_timing_2025_2(real_timing: str) -> None:
    payload = parse_timing_report(real_timing)

    assert payload["parsed"] is True
    assert payload["wns_ns"] == pytest.approx(7.087)
    assert payload["whs_ns"] == pytest.approx(0.213)
    assert payload["tns_failing_endpoints"] == 0
    assert payload["tns_total_endpoints"] == 24
    assert payload["timing_met"] is True

    worst = payload["worst_paths"][0]
    assert worst["type"] == "MET"
    assert worst["slack_ns"] == pytest.approx(7.087)
    assert worst["source"] == "s_count_reg[1]/C"
    assert worst["destination"] == "s_count_reg[21]/D"
    assert worst["logic_levels"] == 6


def test_real_utilization_2025_2(real_utilization: str) -> None:
    """Deux pieges du format reel : 'Slice LUTs*' (etoile) et un '<0.01'."""
    payload = parse_utilization_report(real_utilization)

    assert payload["parsed"] is True
    res = payload["resources"]
    assert res["Slice LUTs"]["used"] == 1
    assert res["Slice LUTs"]["available"] == 53200
    assert res["Slice LUTs"]["pct"] == pytest.approx(0.01)
    assert "pct_note" in res["Slice LUTs"]           # '<0.01' n'est pas un 0.01 exact
    assert res["Slice Registers"]["used"] == 24
    assert res["LUT as Memory"]["used"] == 0


def test_real_log_messages(real_log: str) -> None:
    payload = parse_messages(real_log)

    assert payload["count"] >= 20
    assert payload["error_count"] == 0
    assert payload["by_code"]["Board 49-26"] > 1     # avertissements board reels
    first = payload["messages"][0]
    assert first["severity"] == "WARNING"
    assert first["text"]


def test_log_is_not_mistaken_for_a_timing_report(real_log: str) -> None:
    """Un log ne contient pas de tableau de timing : pas de faux positif."""
    assert parse_timing_report(real_log)["parsed"] is False
    assert parse_utilization_report(real_log)["parsed"] is False


# --------------------------------------------------------------------------- #
# cocotb : sortie reelle
# --------------------------------------------------------------------------- #

REAL_COCOTB_RESULTS = """<testsuites name="results">
  <testsuite name="all" package="all">
    <property name="random_seed" value="1234" />
    <testcase name="test_comptage_et_gel" classname="test_counter" file="/tmp/tb/test_counter.py" lineno="34" time="0.00048" sim_time_ns="105.0" ratio_time="218236.8" />
    <testcase name="test_reset_synchrone" classname="test_counter" file="/tmp/tb/test_counter.py" lineno="54" time="0.00031" sim_time_ns="85.0" ratio_time="270292.5" />
    <testcase name="test_debordement" classname="test_counter" file="/tmp/tb/test_counter.py" lineno="78" time="0.00438" sim_time_ns="2585.0" ratio_time="589030.0" />
  </testsuite>
</testsuites>
"""

REAL_COCOTB_FAILURE = """<testsuites name="results">
  <testsuite name="all" package="all">
    <testcase name="test_ok" classname="test_alu" file="/tmp/tb/test_alu.py" lineno="10" time="0.001" sim_time_ns="50.0" ratio_time="1.0" />
    <testcase name="test_ko" classname="test_alu" file="/tmp/tb/test_alu.py" lineno="20" time="0.001" sim_time_ns="60.0" ratio_time="1.0">
      <failure message="AssertionError: op=3 attendu 7, recu 6">Traceback (most recent call last):
  File "/tmp/tb/test_alu.py", line 22, in test_ko
AssertionError: op=3 attendu 7, recu 6
</failure>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_cocotb_all_passed(tmp_path: Path) -> None:
    path = tmp_path / "results.xml"
    path.write_text(REAL_COCOTB_RESULTS, encoding="utf-8")
    payload = parse_cocotb_results(path)

    assert payload["parsed"] is True
    assert payload["tests"] == 3
    assert payload["passed"] == 3
    assert payload["all_passed"] is True
    assert [t["name"] for t in payload["testcases"]] == [
        "test_comptage_et_gel", "test_reset_synchrone", "test_debordement",
    ]
    assert all(t["status"] == "passed" for t in payload["testcases"])


def test_cocotb_failure_is_counted_not_missed(tmp_path: Path) -> None:
    """Regression : cocotb n'ecrit pas d'attribut failures= sur le testsuite."""
    path = tmp_path / "results.xml"
    path.write_text(REAL_COCOTB_FAILURE, encoding="utf-8")
    payload = parse_cocotb_results(path)

    assert payload["failures"] == 1
    assert payload["passed"] == 1
    assert payload["all_passed"] is False
    failed = [t for t in payload["testcases"] if t["status"] == "failed"]
    assert failed and "attendu 7, recu 6" in failed[0]["failure"]


def test_cocotb_missing_file(tmp_path: Path) -> None:
    payload = parse_cocotb_results(tmp_path / "absent.xml")
    assert payload["parsed"] is False
    assert "absent" in payload["note"]


# --------------------------------------------------------------------------- #
# Chemins negatifs (fixtures SYNTHETIQUES, voir docstring)
# --------------------------------------------------------------------------- #

TIMING_FAIL_SYNTHETIC = """Design Timing Summary
---------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  THS Failing Endpoints  THS Total Endpoints     WPWS(ns)     TPWS(ns)  TPWS Failing Endpoints  TPWS Total Endpoints
    -------      -------  ---------------------  -------------------      -------      -------  ---------------------  -------------------     --------     --------  ----------------------  --------------------
     -0.512      -12.400                     23                  742        0.020        0.000                      0                   742        4.000        0.000                       0                     212

Slack (VIOLATED) :        -0.512ns  (required time - arrival time)
  Source:                 u_mult/p_reg[7]/C
    Destination:            u_acc/sum_reg[3]/D
  Logic Levels:           19
"""

MESSAGES_SYNTHETIC = """ERROR: [Synth 8-327] inferring latch for variable 's_state_reg'
WARNING: [Synth 8-3331] design top has unconnected port led[3]
INFO: [Common 17-83] Releasing license: Synthesis
ERROR: [Place 30-681] Sub-optimal placement for a clock-capable IO pin
CRITICAL WARNING: [Vivado 12-1411] Cannot set LOC property of port
"""


def test_timing_violation_synthetic() -> None:
    """WNS < 0 doit etre traite comme un echec, jamais comme un succes."""
    payload = parse_timing_report(TIMING_FAIL_SYNTHETIC)
    assert payload["timing_met"] is False
    assert payload["wns_ns"] < 0
    assert payload["tns_failing_endpoints"] == 23
    assert payload["worst_paths"][0]["slack_ns"] < 0


def test_timing_unknown_layout_degrades_cleanly() -> None:
    payload = parse_timing_report("ceci n'est pas un rapport de timing\n")
    assert payload["parsed"] is False
    assert "raw" in payload


def test_messages_severity_grouping_synthetic() -> None:
    payload = parse_messages(MESSAGES_SYNTHETIC)
    assert payload["count"] == 4                       # INFO exclu
    assert payload["error_count"] == 2
    assert payload["critical_warning_count"] == 1
    assert payload["by_code"]["Synth 8-327"] == 1


def test_summarize_log_tolerates_binary_noise(tmp_path: Path) -> None:
    """Un log tronque au milieu d'un caractere UTF-8 ne doit pas lever."""
    log = tmp_path / "vivado.log"
    log.write_bytes(b"ERROR: [Synth 8-327] inferring latch\n" + b"\xc3\xa9\xff\xfe" + b"fin")
    payload = summarize_log(log)
    assert payload["messages"]["error_count"] == 1
    assert payload["lines"] >= 1
