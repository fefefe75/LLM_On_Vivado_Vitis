"""Exemple 01b - meme test, lance en Python pur (cocotb 2.x runner), sans make.

    python run_tests.py            # SIM=ghdl par defaut
    SIM=questa python run_tests.py
    WAVES=1 python run_tests.py    # -> counter.ghw

Pourquoi cette variante existe : un agent LLM gere mieux un script Python
(arguments typés, erreurs en exceptions, chemin de results.xml en retour) qu'un
Makefile. Les deux flux sont equivalents.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

HERE = Path(__file__).resolve().parent
RTL = HERE / ".." / "rtl"
SIM = os.environ.get("SIM", "ghdl").lower()

BUILD_ARGS: list[str] = []
TEST_ARGS: list[str] = []

if SIM == "ghdl":
    # --std=08 est exige a l'analyse ET a l'execution.
    # Attention : le runner GHDL ignore elab_args, il faut donc test_args.
    BUILD_ARGS += ["--std=08"]
    TEST_ARGS += ["--std=08"]


def main() -> int:
    runner = get_runner(SIM)

    runner.build(
        sources=[RTL / "counter.vhd"],
        hdl_toplevel="counter",
        build_args=BUILD_ARGS,
        # GHDL relit sa bibliotheque depuis le cwd du test : meme dossier requis.
        build_dir=HERE,
        always=True,
    )

    results = runner.test(
        hdl_toplevel="counter",
        test_module="test_counter",
        test_args=TEST_ARGS,
        test_dir=HERE,
        waves=bool(int(os.environ.get("WAVES", "0"))),
        seed=int(os.environ.get("COCOTB_RANDOM_SEED", "1234")),
    )
    print(f"results.xml -> {results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
