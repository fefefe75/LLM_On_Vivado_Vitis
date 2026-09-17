#!/usr/bin/env python3
"""Verification des scripts Tcl du depot, sans Vivado.

Deux niveaux, tous deux reellement executes :

1. `info complete` (tclsh) : le fichier est-il un script Tcl syntaxiquement
   complet (accolades, guillemets, continuations equilibres) ? Cela attrape les
   erreurs de structure les plus courantes des scripts generes par un LLM.

2. Extraction et EXECUTION des procedures utilitaires (`get_arg`,
   `collect_sources`) dans un bac a sable tclsh, sur une arborescence bidon :
   on verifie le comportement reel, pas seulement la syntaxe.

Ce que cela NE fait PAS : valider les commandes Vivado elles-memes
(`create_project`, `launch_runs`...) — il faut Vivado pour cela. Les scripts
restent donc a executer une premiere fois par un humain.

Usage :
    python3 scripts/check_tcl.py                 # tout le depot
    python3 scripts/check_tcl.py templates/vivado  # un dossier
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Procedures que l'on sait tester en isolation, avec un cas de test.
TESTABLE_PROCS = ("get_arg", "collect_sources")


def tcl_available() -> bool:
    return shutil.which("tclsh") is not None


def run_tcl(script: str, cwd: Path | None = None) -> tuple[int, str]:
    """Execute un script Tcl (via fichier temporaire : tclsh ne prend pas stdin)."""
    with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as handle:
        handle.write(script)
        script_file = Path(handle.name)
    try:
        proc = subprocess.run(
            ["tclsh", str(script_file)],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=60,
        )
    finally:
        script_file.unlink(missing_ok=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def check_complete(path: Path) -> tuple[bool, str]:
    """Verifie avec tclsh que le fichier est un script Tcl complet.

    tclsh ne lit pas stdin avec l'argument "-" : le controle est donc ecrit dans
    un fichier temporaire, puis le script a examiner est passe en argument.
    """
    script = (
        "set fh [open [lindex $argv 0] r]\n"
        "set data [read $fh]\n"
        "close $fh\n"
        "if {[info complete $data]} { puts COMPLETE } else { puts INCOMPLETE }\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as handle:
        handle.write(script)
        wrapper = Path(handle.name)
    try:
        proc = subprocess.run(["tclsh", str(wrapper), str(path)],
                              capture_output=True, text=True, timeout=60)
    finally:
        wrapper.unlink(missing_ok=True)
    out = (proc.stdout + proc.stderr).strip()
    return out.startswith("COMPLETE"), out


def _skip_balanced(text: str, start: int) -> int | None:
    """Index juste apres le bloc d'accolades ouvert en `start`, ou None."""
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def extract_proc(text: str, name: str) -> str | None:
    """Extrait `proc <name> ... {corps}` (liste d'arguments puis corps).

    Piege : le premier bloc d'accolades rencontres est la LISTE D'ARGUMENTS, pas
    le corps. Un compteur naif s'arrete dessus et renvoie un proc tronque.
    """
    header = re.search(rf"^proc\s+{re.escape(name)}\s", text, re.M)
    if not header:
        return None

    i = header.end()
    while i < len(text) and text[i] in " \t":
        i += 1
    if i < len(text) and text[i] == "{":
        after_args = _skip_balanced(text, i)
        if after_args is None:
            return None
        i = after_args
    else:                                      # argument unique, non entoure
        while i < len(text) and not text[i].isspace():
            i += 1
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i >= len(text) or text[i] != "{":
        return None
    end = _skip_balanced(text, i)
    return text[header.start():end] if end else None


def test_procs(paths: list[Path]) -> list[str]:
    """Execute get_arg/collect_sources extraits, sur une arborescence temporaire."""
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "rtl" / "alu").mkdir(parents=True)
        (root / "rtl" / "top.vhd").write_text("-- top\n")
        (root / "rtl" / "alu" / "alu.vhd").write_text("-- alu\n")
        (root / "rtl" / "alu" / "note.txt").write_text("ignore\n")

        procs: dict[str, str] = {}
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            for name in TESTABLE_PROCS:
                if name not in procs:
                    body = extract_proc(text, name)
                    if body:
                        procs[name] = body

        if "get_arg" not in procs or "collect_sources" not in procs:
            errors.append("procedures get_arg/collect_sources introuvables : rien teste")
            return errors

        harness = procs["get_arg"] + "\n" + procs["collect_sources"] + "\n" + f"""
set fails 0

# --- get_arg ---------------------------------------------------------------
set argv {{--name prj --part xc7a35tcsg324-1 --jobs 8}}
if {{[get_arg $argv --name defaut] ne "prj"}} {{ puts "FAIL get_arg --name"; incr fails }}
if {{[get_arg $argv --part defaut] ne "xc7a35tcsg324-1"}} {{ puts "FAIL get_arg --part"; incr fails }}
if {{[get_arg $argv --absent defaut] ne "defaut"}} {{ puts "FAIL get_arg --absent"; incr fails }}
if {{[get_arg {{}} --name defaut] ne "defaut"}} {{ puts "FAIL get_arg vide"; incr fails }}
# option en derniere position (pas de valeur) : doit renvoyer la valeur par defaut
if {{[get_arg {{--name}} --name defaut] ne "defaut"}} {{ puts "FAIL get_arg sans valeur"; incr fails }}

# --- collect_sources -------------------------------------------------------
set found [collect_sources {{{root}/rtl}} vhd]
if {{[llength $found] != 2}} {{ puts "FAIL collect_sources count=[llength $found] (attendu 2)"; incr fails }}
foreach f $found {{
    if {{![string match "*.vhd" $f]}} {{ puts "FAIL extension: $f"; incr fails }}
}}
if {{[llength [collect_sources {{{root}/rtl}} txt]] != 1}} {{ puts "FAIL collect_sources txt"; incr fails }}
if {{[llength [collect_sources {{{root}/absent}} vhd]] != 0}} {{ puts "FAIL dossier absent"; incr fails }}

if {{$fails == 0}} {{ puts "PROCS OK" }} else {{ puts "PROCS FAIL=$fails" }}
"""
        code, out = run_tcl(harness, cwd=root)
        if "PROCS OK" not in out:
            errors.append(f"test fonctionnel des procedures : {out}")
        else:
            print("  procedures get_arg/collect_sources : OK (executees sur une arborescence reelle)")

    return errors


def main(argv: list[str]) -> int:
    if not tcl_available():
        print("tclsh absent : impossible de verifier les scripts Tcl")
        return 2

    target = Path(argv[1]) if len(argv) > 1 else REPO
    if not target.is_absolute():
        target = REPO / target
    files = sorted(p for p in target.rglob("*.tcl") if ".git" not in p.parts)
    if not files:
        print(f"aucun .tcl trouve sous {target}")
        return 0

    print(f"== verification de {len(files)} script(s) Tcl sous {target}")

    failures: list[str] = []
    for path in files:
        ok, out = check_complete(path)
        mark = "OK  " if ok else "KO  "
        print(f"{mark}{path.relative_to(REPO)}")
        if not ok:
            failures.append(f"{path}: script Tcl incomplet -> {out}")

    errors = test_procs(files)
    failures.extend(errors)

    if failures:
        print("\n== ECHECS ==")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("\n== tout est coherent (syntaxe Tcl + procedures executees)")
    print("   rappel : les commandes Vivado elles-memes ne sont PAS validees ici.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
