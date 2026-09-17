# `tb/` — les testbenches cocotb

**Un dossier par test**, nommé comme le module ou la fonction testés :

```
tb/
├── compteur/
│   ├── test_compteur.py     le test (Python, cocotb)
│   └── run_tests.py         le lanceur  (ou un Makefile, au choix)
└── compteur_makefile/       autre exemple : lancement par le Makefile cocotb
```

Le Makefile racine découvre tout seul les dossiers de `tb/` :

```bash
make sim                       # lance TOUS les tb/*/ et agrège les résultats
make sim-one TEST=compteur     # un seul dossier
make waves TEST=compteur       # idem, en gardant les traces (.ghw / .vcd / .fst)
make sim WAVES=1               # traces pour tous les tests
make sim SIM=questa            # autre simulateur (icarus, questa, ...)
make sim SEED=42               # graine explicite (défaut : 1234)
```

Le nom du dossier est aussi le répertoire de travail du test : `cd tb/compteur`
puis `make SIM=ghdl` fonctionne à l'identique.

> ⚠️ **Piège de chemin, rencontré pour de vrai** : le dossier étant `tb/<nom>/`,
> les sources se référencent avec **deux** niveaux : `$(PWD)/../../rtl/mon_module.vhd`.
> Un chemin écrit pour un `tb/` à plat (`$(PWD)/../rtl/...`) donne une erreur
> trompeuse :
> ```
> make[2]: *** Aucune règle pour fabriquer la cible « .../tb/rtl/counter.vhd »
> ```
> (Vivado n'est pas en cause : c'est make qui ne trouve pas le fichier.)

## Modèle 1 — `run_tests.py` (cocotb 2.x, `cocotb_tools.runner`)

Recommandé : tout est Python, les erreurs remontent comme exceptions, aucun
Makefile à parser. `tb/compteur/run_tests.py` :

```python
"""Lancement programmatique de cocotb 2.x (cocotb_tools.runner), sans make."""
import os
from pathlib import Path
from cocotb_tools.runner import get_results, get_runner

HERE = Path(__file__).resolve().parent          # dossier du testbench
RTL = (HERE / ".." / ".." / "rtl").resolve()    # sources HDL du projet
SIM = os.environ.get("SIM", "ghdl").lower()
SEED = int(os.environ.get("COCOTB_RANDOM_SEED", "1234"))

SOURCES = [RTL / "pkg_utilitaires.vhd", RTL / "compteur.vhd"]   # ORDRE de compilation
HDL_TOPLEVEL = "compteur"
TEST_MODULE = "test_compteur"

BUILD_ARGS, TEST_ARGS = ([], [])
if SIM == "ghdl":
    BUILD_ARGS += ["--std=08"]
    TEST_ARGS += ["--std=08"]       # GHDL ignore elab_args : --std=08 des deux cotes

def main() -> int:
    runner = get_runner(SIM)
    runner.build(sources=SOURCES, hdl_toplevel=HDL_TOPLEVEL,
                 build_args=BUILD_ARGS, build_dir=HERE, always=True, waves=False)
    results = runner.test(hdl_toplevel=HDL_TOPLEVEL, test_module=TEST_MODULE,
                          test_args=TEST_ARGS, test_dir=HERE,
                          waves=bool(int(os.environ.get("WAVES", "0"))), seed=SEED)
    print(f"results.xml -> {results}")

    # PIEGE : en cocotb 2.x, test() ne fait pas echouer le processus quand un
    # test echoue (sortie 0 avec des tests rouges). On relit donc results.xml.
    nb_tests, nb_echecs = get_results(results)
    if nb_echecs:
        print(f"{nb_echecs}/{nb_tests} test(s) en echec")
        return 1
    print(f"{nb_tests} test(s) OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`make sim` relit **aussi** `results.xml` de son côté
(`scripts/run_testbench.sh`) : même si un `run_tests.py` oublie de propager
l'échec, un test rouge ne peut pas être annoncé vert. Une autre voie, en ligne
de commande :

```bash
python -m cocotb_tools.check_results tb/compteur/results.xml   # code non nul si echec
```

Et `tb/compteur/test_compteur.py` :

```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

async def reset(dut):
    dut.i_rst.value = 1
    for _ in range(2):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0        # le compteur repart de 0 au prochain coup d'horloge

@cocotb.test()
async def test_compte(dut):
    """Le compteur s'incremente une fois par coup d'horloge."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    await reset(dut)
    valeurs = []
    for _ in range(3):
        await RisingEdge(dut.i_clk)      # 1er coup apres le reset : 1, puis 2, 3
        await ReadOnly()
        valeurs.append(int(dut.o_q.value))
    assert valeurs == [1, 2, 3], f"attendu [1, 2, 3], obtenu {valeurs}"

@cocotb.test()
async def test_reset(dut):
    """Le reset ramene la sortie a zero."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    await reset(dut)
    for _ in range(3):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 1
    await RisingEdge(dut.i_clk)
    await ReadOnly()
    assert int(dut.o_q.value) == 0, f"reset inoperant : {int(dut.o_q.value)}"
```

## Modèle 2 — `Makefile` cocotb

Le dossier contient un `Makefile` (copie de `templates/cocotb/Makefile.ghdl`) :

```make
SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl
VHDL_SOURCES += $(PWD)/../../rtl/pkg_utilitaires.vhd
VHDL_SOURCES += $(PWD)/../../rtl/compteur.vhd
COCOTB_TOPLEVEL = compteur
COCOTB_TEST_MODULES = test_compteur
GHDL_ARGS += --std=08
export COCOTB_RANDOM_SEED ?= 1234
include $(shell cocotb-config --makefiles)/Makefile.sim
```

Dans ce cas, `make waves` ajoute `SIM_ARGS=--wave=…ghw` (les makefiles de
cocotb 2.x ne gèrent pas `WAVES` pour GHDL, et GHDL n'accepte `--wave=` qu'après
l'unité de tête : `GHDL_RUN_ARGS` est placé avant, donc inutilisable ici).

## Règles

- Un test est **auto-vérifiant** : il échoue tout seul (`assert`), il n'affiche
  pas des valeurs en espérant qu'un humain les lise.
- **Graine fixe** : `COCOTB_RANDOM_SEED` (défaut `1234`) est fourni par le
  Makefile racine. Pas de test « qui passe une fois sur deux ».
- Pas de fichier généré commité : `sim_build/`, `results.xml`, `*.ghw` sont dans
  `.gitignore`.
- cocotb ne pilote pas XSim : le chemin libre est GHDL + cocotb (VHDL) ou
  Icarus/Verilator (Verilog). Pour un poste qui n'a que Vivado, écrire un
  testbench VHDL auto-vérifiant et le lancer avec `xvlog`/`xelab`/`xsim`.
