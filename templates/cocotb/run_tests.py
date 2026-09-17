"""Lancement programmatique de cocotb 2.x, sans make (cocotb_tools.runner).

Avantage pour un agent LLM : pas de Makefile a parser, tout est Python, les
erreurs de build remontent comme exceptions, et le retour de test() donne le
chemin de results.xml.

Usage :
    SIM=ghdl  python run_tests.py
    SIM=questa python run_tests.py

PIEGES VERIFIES SUR cocotb 2.0.1 :
  * `sources=` est le parametre language-agnostic de build() ;
    `vhdl_sources=` / `verilog_sources=` sont declasses (DeprecationWarning).
  * test() n'accepte PAS build_args : ce sont test_args / elab_args / plusargs.
  * GHDL ignore elab_args : --std=08 doit etre passe a build_args ET test_args.
  * GHDL ecrit sa bibliotheque (top-obj08.cf) dans le cwd du build et la relit
    depuis le cwd du test -> build_dir et test_dir doivent viser le meme dossier,
    sinon : "cannot find entity or configuration <top>".
"""

from __future__ import annotations

import os
from pathlib import Path

from cocotb_tools.runner import get_runner

HERE = Path(__file__).resolve().parent          # dossier du testbench
RTL = (HERE / ".." / ".." / "rtl").resolve()    # sources HDL du projet
SIM = os.environ.get("SIM", "ghdl").lower()

# --- sources : a adapter au projet -------------------------------------------
SOURCES = [
    RTL / "mon_module.vhd",
]
HDL_TOPLEVEL = "mon_module"
TEST_MODULE = "test_mon_module"
SEED = int(os.environ.get("COCOTB_RANDOM_SEED", "1234"))

# --- arguments par simulateur -------------------------------------------------
BUILD_ARGS: list[str] = []
TEST_ARGS: list[str] = []
ELAB_ARGS: list[str] = []

if SIM == "ghdl":
    BUILD_ARGS += ["--std=08"]
    TEST_ARGS += ["--std=08"]        # indispensable, elab_args est ignore
elif SIM == "questa":
    TEST_ARGS += []                  # ex: ["-voptargs=+acc"]
elif SIM in ("icarus", "verilator"):
    BUILD_ARGS += ["-g2012"]


def main() -> int:
    runner = get_runner(SIM)

    runner.build(
        sources=SOURCES,
        hdl_toplevel=HDL_TOPLEVEL,
        build_args=BUILD_ARGS,
        build_dir=HERE,              # cf. piege GHDL : meme dossier que test_dir
        always=True,
        waves=False,
    )

    results = runner.test(
        hdl_toplevel=HDL_TOPLEVEL,
        test_module=TEST_MODULE,
        elab_args=ELAB_ARGS,
        test_args=TEST_ARGS,
        test_dir=HERE,
        waves=bool(int(os.environ.get("WAVES", "0"))),
        seed=SEED,
    )
    print(f"results.xml -> {results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
