# Exemple 01 — Compteur VHDL + testbench cocotb (vérifié)

Squelette minimal mais **complet** du flux de travail : un module VHDL, un
testbench cocotb 2.x, deux façons de le lancer.

```
01-counter-cocotb/
├── rtl/counter.vhd          # module DUT (reset synchrone, générique C_WIDTH)
└── tb/
    ├── Makefile             # flux make (cocotb-config --makefiles)
    ├── test_counter.py      # 3 tests : comptage/gel, reset synchrone, débordement
    └── run_tests.py         # même chose en Python pur (cocotb_tools.runner)
```

## Lancer

Prérequis : `ghdl` dans le PATH et `cocotb` installé dans le Python courant
(voir `docs/01-toolchain.md`, section installation sans root).

```bash
cd tb
make                      # -> TESTS=3 PASS=3
WAVES=1 python3 run_tests.py   # -> counter.ghw (GTKWave, Surfer)
COCOTB_TESTCASE=test_reset_synchrone make    # un seul test
python run_tests.py       # équivalent, en Python
SIM=questa python run_tests.py               # même test, autre simulateur
```

> **Ondes : `make WAVES=1` ne marche PAS ici** (vérifié) — avec GHDL, cocotb 2.0
> n'ajoute pas `--wave` à la ligne de commande et aucun `.ghw` n'est écrit, sans
> message d'erreur. Utiliser le lanceur Python (`WAVES=1 python3 run_tests.py`,
> qui produit bien `counter.ghw`, 6558 octets mesurés).

## Ce que ce testbench enseigne (et pourquoi c'est là)

| Piège rencontré | Symptôme | Idiome correct |
|---|---|---|
| Lire une sortie juste après `RisingEdge()` | la valeur **précédente** est lue, le test échoue au cycle 1 | échantillonner sur `FallingEdge`, ou `RisingEdge()` + `await ReadOnly()` |
| Écrire un signal après `await ReadOnly()` | `RuntimeError: Attempting settings a value during the ReadOnly phase.` | avancer d'un événement (`FallingEdge`) avant toute écriture |
| Relâcher le reset sans attendre le front | tout est décalé d'un cycle | positionner **toutes** les entrées avant de relâcher le reset |
| `--std=08` uniquement à l'analyse | `cannot find entity or configuration counter` | `GHDL_ARGS += --std=08` (couvre analyse **et** exécution) |
| `MODULE = ...` dans le Makefile | avertissement de dépréciation cocotb 2.x | `COCOTB_TEST_MODULES = ...` |
| `vhdl_sources=` dans l'API runner | `DeprecationWarning` | `sources=[...]` |
| `build_args` passé à `runner.test()` | `TypeError: unexpected keyword argument 'build_args'` | utiliser `test_args=` (GHDL ignore `elab_args`) |
| `build_dir` ≠ `test_dir` avec GHDL | `cannot find entity or configuration` | même dossier pour les deux |

Tout ce tableau a été constaté en exécutant réellement ce testbench
(cocotb 2.0.1, GHDL 6.0.0, VHDL-2008).

## Adapter à un autre simulateur

| Simulateur | Ligne de commande | Remarque |
|---|---|---|
| GHDL (libre) | `make SIM=ghdl` | référence de ce dépôt, VHDL uniquement |
| Verilator (libre, Verilog) | `make SIM=verilator` | très rapide, Verilog/SystemVerilog seulement |
| Icarus (libre, Verilog) | `make SIM=icarus` | Verilog/SV, pas de VHDL |
| Questa / ModelSim (licence) | `make SIM=questa GUI=1` | VHDL + Verilog, GUI |
| **XSim (Vivado)** | *non supporté par cocotb* | utiliser un testbench VHDL pur : voir `examples/04-vhdl-testbench-xsim` |

La dernière ligne est importante : **cocotb ne pilote pas XSim**. Vérifié dans
cocotb 2.0.1 — la liste des simulateurs supportés est
`activehdl cvc dsim ghdl icarus ius modelsim nvc questa riviera vcs verilator xcelium`.
Avec Vivado seul, on écrit donc un testbench VHDL (exemple 04) ou on simule le
même RTL avec GHDL + cocotb (exemples 01 à 03) avant de lancer Vivado.
