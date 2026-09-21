"""Analyse des rapports et logs produits par Vivado / cocotb.

Objectif : rendre au LLM du JSON exploitable au lieu de milliers de lignes de
texte, tout en gardant la sortie brute disponible.

IMPORTANT — honnêteté sur la vérification : les analyseurs ci-dessous sont testés
contre les fixtures **AUTHENTIQUES** de `tests/fixtures/` : un
`report_timing_summary` et un `report_utilization` extraits d'une exécution
réelle de Vivado v2025.2 (lin64) (compteur 24 bits + 4 LED, xc7z020clg400-1,
horloge 100 MHz ; WNS 7.087 ns), un vrai log Vivado, et un vrai `results.xml` de
cocotb 2.0.1. Conséquence : chaque fonction renvoie `{"parsed": false,
"raw": ...}` avec le texte brut quand sa mise en page ne correspond pas, afin
qu'une version future de Vivado dégrade proprement au lieu de mentir.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# --------------------------------------------------------------------------- #
# Timing : "Design Timing Summary" (UG906)
# --------------------------------------------------------------------------- #

_TIMING_HEADER = re.compile(r"Design Timing Summary", re.I)
_NUMBERS_ROW = re.compile(
    r"^\s*(?P<wns>[-\d.]+)\s+(?P<tns>[-\d.]+)\s+(?P<tns_fail>\d+)\s+(?P<tns_total>\d+)\s+"
    r"(?P<whs>[-\d.]+)\s+(?P<ths>[-\d.]+)\s+(?P<ths_fail>\d+)\s+(?P<ths_total>\d+)\s+"
    r"(?P<wpws>[-\d.]+)\s+(?P<tpws>[-\d.]+)\s+(?P<tpws_fail>\d+)\s+(?P<tpws_total>\d+)\s*$",
    re.M,
)


def parse_timing_report(text: str) -> dict:
    """Extrait WNS/TNS/WHS/THS/WPWS/TPWS d'un rapport de timing Vivado."""
    if not _TIMING_HEADER.search(text):
        return {"parsed": False, "raw": text[:4000]}

    # Cas RÉEL (verifie sur Vivado 2025.2) : un design sans contrainte d'horloge
    # affiche le titre mais AUCUN tableau, remplace par cette phrase. Renvoyer
    # "parsed: false" tout court ferait perdre la cause a l'agent.
    if re.search(r"no user specified timing constraints", text, re.I):
        return {
            "parsed": False,
            "unconstrained": True,
            "note": (
                "aucune contrainte de timing utilisateur : Vivado n'a rien a verifier. "
                "Ajouter create_clock sur le port d'horloge dans un .xdc "
                "(voir docs/06-constraints-xdc.md)."
            ),
            "raw": text[:2000],
        }

    match = _NUMBERS_ROW.search(text)
    if not match:
        return {"parsed": False, "raw": text[:4000], "note": "tableau de timing non reconnu"}

    values = {k: float(v) if "." in v else int(v) for k, v in match.groupdict().items()}
    result = {
        "parsed": True,
        "wns_ns": values["wns"],
        "tns_ns": values["tns"],
        "tns_failing_endpoints": values["tns_fail"],
        "tns_total_endpoints": values["tns_total"],
        "whs_ns": values["whs"],
        "ths_ns": values["ths"],
        "ths_failing_endpoints": values["ths_fail"],
        "ths_total_endpoints": values["ths_total"],
        "wpws_ns": values["wpws"],
        "tpws_ns": values["tpws"],
        "tpws_failing_endpoints": values["tpws_fail"],
        "tpws_total_endpoints": values["tpws_total"],
    }
    result["timing_met"] = (
        values["wns"] >= 0.0 and values["whs"] >= 0.0 and values["wpws"] >= 0.0
    )
    worst = _worst_paths(text)
    if worst:
        result["worst_paths"] = worst
    return result


def _worst_paths(text: str, limit: int = 3) -> list[dict]:
    """Résume les N chemins critiques (`report_timing -max_paths`).

    Le motif de tête est cherché partout (`finditer`) puis on lit les lignes qui
    suivent : c'est la seule façon robuste, les rapports Vivado changeant de mise
    en page entre versions.
    """
    paths: list[dict] = []
    for head in _PATH_HEAD.finditer(text):
        block = text[head.end():head.end() + 1500]
        source = re.search(r"Source:\s*(\S+)", block)
        dest = re.search(r"Destination:\s*(\S+)", block)
        logic = re.search(r"Logic Levels:\s*(\d+)", block)
        paths.append({
            "type": (head.group("kind") or "UNKNOWN").strip(),
            "slack_ns": float(head.group("slack")),
            "met": float(head.group("slack")) >= 0.0,
            "source": source.group(1) if source else None,
            "destination": dest.group(1) if dest else None,
            "logic_levels": int(logic.group(1)) if logic else None,
        })
        if len(paths) >= limit:
            break
    return paths


# --------------------------------------------------------------------------- #
# Utilisation des ressources (report_utilization)
# --------------------------------------------------------------------------- #

_PATH_HEAD = re.compile(
    r"Slack\s*\(\s*(?P<kind>MET|VIOLATED|REAL|VIRTUAL)?\s*\)\s*:\s*(?P<slack>[-\d.]+)\s*ns",
    re.I,
)

_UTIL_ROW = re.compile(
    r"^\|\s*(?P<name>[A-Za-z][^|]*?)\s*\|\s*(?P<used>\d+)\s*\|\s*(?P<fixed>\d+)\s*\|\s*"
    r"(?P<prohibited>\d+)\s*\|\s*(?P<avail>\d+)\s*\|\s*(?P<pct><?[\d.]+)\s*\|\s*$",
    re.M,
)

# Lignes de totaux en tête de fichier (format "| Slice LUTs | 1234 | 0 | 6340 | 19.46 |")
_KEEP = (
    "slice luts", "slice registers", "slice", "lut as logic", "lut as memory",
    "block ram tile", "dsp", "bonded iob", "bufgctrl", "mmcm", "pll", "bufg",
)


def parse_utilization_report(text: str) -> dict:
    """Extrait les lignes d'utilisation des ressources principales.

    Deux particularités du format RÉEL de Vivado 2025.2 (vérifiées sur un
    rapport généré) qui cassent un parseur naïf :
      - le nom peut porter une étoile : `| Slice LUTs*  |` (ressource estimée
        pendant la synthèse, affinée après implémentation) ;
      - un pourcentage peut être `<0.01` : ce n'est PAS un flottant valide.
    """
    resources: dict[str, dict] = {}
    for m in _UTIL_ROW.finditer(text):
        name = " ".join(m.group("name").split()).rstrip("*").strip()
        if name.lower() not in _KEEP:
            continue
        raw_pct = m.group("pct")
        entry = {
            "used": int(m.group("used")),
            "available": int(m.group("avail")),
            "pct": float(raw_pct.lstrip("<")),
        }
        if raw_pct.startswith("<"):
            entry["pct_note"] = f"inferieur a {raw_pct[1:]} % (sous la resolution du rapport)"
        resources[name] = entry
    if not resources:
        return {"parsed": False, "raw": text[:4000]}
    return {"parsed": True, "resources": resources}


# --------------------------------------------------------------------------- #
# DRC / messages de Vivado
# --------------------------------------------------------------------------- #

_MESSAGE = re.compile(
    r"^\s*(?P<severity>ERROR|CRITICAL WARNING|WARNING|INFO)\s*:\s*"
    r"\[(?P<code>[^\]]+)\]\s*(?P<text>.*?)\s*(?:\[(?P<file>[^:\]]+):(?P<line>\d+)\])?\s*$",
    re.I,
)


def parse_messages(text: str, kept_severities: tuple[str, ...] = ("ERROR", "CRITICAL WARNING", "WARNING")) -> dict:
    """Regroupe les messages Vivado par sévérité et par code (ex. [Synth 8-327])."""
    messages: list[dict] = []
    by_code: dict[str, int] = {}
    for line in text.splitlines():
        m = _MESSAGE.match(line)
        if not m:
            continue
        severity = m.group("severity").upper()
        if severity not in kept_severities:
            continue
        code = m.group("code")
        by_code[code] = by_code.get(code, 0) + 1
        messages.append({
            "severity": severity,
            "code": code,
            "text": m.group("text"),
            "file": m.group("file"),
            "line": int(m.group("line")) if m.group("line") else None,
        })
    return {
        "count": len(messages),
        "error_count": sum(1 for m in messages if m["severity"] == "ERROR"),
        "critical_warning_count": sum(1 for m in messages if m["severity"] == "CRITICAL WARNING"),
        "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
        "messages": messages[:200],
    }


# --------------------------------------------------------------------------- #
# Résultats cocotb
# --------------------------------------------------------------------------- #


def parse_cocotb_results(path: Path) -> dict:
    """Lit results.xml (cocotb) et renvoie un résumé exploitable."""
    path = Path(path)
    if not path.exists():
        return {"parsed": False, "note": f"results.xml absent : {path}"}

    root = ET.parse(path).getroot()
    tests: list[dict] = []
    for case in root.iter("testcase"):
        entry = {
            "name": case.get("name"),
            "module": case.get("classname"),
            "sim_time_ns": case.get("sim_time_ns"),
            "status": "passed",
        }
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if failure is not None:
            entry["status"] = "failed"
            entry["failure"] = (failure.get("message") or failure.text or "").strip()[:2000]
        elif error is not None:
            entry["status"] = "error"
            entry["failure"] = (error.get("message") or error.text or "").strip()[:2000]
        elif skipped is not None:
            entry["status"] = "skipped"
        tests.append(entry)

    # ATTENTION : cocotb 2.x n'ecrit PAS d'attributs failures=/errors= sur le
    # <testsuite> (verifie sur un results.xml reel). Les totaux sont donc deduits
    # des <testcase> : sinon un test echoue passerait pour un succes.
    totals = {
        "tests": len(tests),
        "failures": sum(1 for t in tests if t["status"] == "failed"),
        "errors": sum(1 for t in tests if t["status"] == "error"),
        "skipped": sum(1 for t in tests if t["status"] == "skipped"),
    }
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is not None and suite.get("tests") is not None:
        totals["suite_attributes"] = {
            key: suite.get(key) for key in ("tests", "failures", "errors", "skipped")
        }
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    totals["all_passed"] = totals["failures"] == 0 and totals["errors"] == 0
    # "tests" est le NOMBRE ; le détail est sous "testcases" (ne jamais mélanger
    # les deux sous la même clé : un agent lirait la liste comme un compteur).
    return {"parsed": True, **totals, "testcases": tests}


def read_text(path: Path, max_bytes: int = 200_000) -> str:
    """Lecture texte bornée, robuste aux fichiers de log partiels (UTF-8 invalide)."""
    path = Path(path)
    data = path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")


def summarize_log(path: Path) -> dict:
    """Résumé d'un log Vivado : messages, timing, utilisation, dernière ligne."""
    text = read_text(path)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "lines": text.count("\n"),
        "messages": parse_messages(text),
        "timing": parse_timing_report(text),
        "utilization": parse_utilization_report(text),
        "last_lines": [ln for ln in text.splitlines()[-15:]],
    }


def to_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)
