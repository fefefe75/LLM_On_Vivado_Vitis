# Simulation : XSim, GHDL, cocotb — quoi utiliser, et comment

Tout ce qui suit a été **exécuté** sur cette machine (Vivado 2025.2 / XSim 2025.2,
GHDL 6.0.0, cocotb 2.0.1). Les chiffres sont réels.

---

## 1. Choisir son simulateur

| Simulateur | Langages | Licence | cocotb ? | Verdict |
|---|---|---|---|---|
| **GHDL** | VHDL | GPL, libre | **oui** (`SIM=ghdl`) | référence de ce dépôt : installation en 30 s, aucun compte |
| Icarus Verilog | Verilog/SV | libre | oui (`SIM=icarus`) | pour du Verilog |
| Verilator | Verilog/SV | libre | oui (`SIM=verilator`) | le plus rapide, mais exige du code « verilatable » |
| **XSim** (Vivado) | VHDL/Verilog/SV | inclus Vivado | **non** | obligatoire si l'environnement est Vivado-only, mais testbench en VHDL/Verilog pur |
| Questa / ModelSim | les deux | licence payante | oui (`SIM=questa`) | ce que le tutoriel de cours utilise souvent |
| NVC | VHDL | libre | oui (`SIM=nvc`) | alternative à GHDL |

**Fait vérifié** (à ne pas répéter de travers) : cocotb **ne pilote pas XSim**.
Dans cocotb 2.0.1, la liste des simulateurs supportés est :
```
activehdl cvc dsim ghdl icarus ius modelsim nvc questa riviera vcs verilator xcelium
```
```
$ make SIM=xsim
Couldn't find makefile for simulator: "xsim"! Available simulators: activehdl cvc dsim ...
```
Conséquence pratique pour un projet Vivado : **soit** on écrit un testbench VHDL
auto-vérifiant (exécutable par XSim), **soit** on simule le même RTL avec
GHDL + cocotb (beaucoup plus rapide à écrire et à relire pour un agent), **soit**
on a une licence Questa.

## 2. XSim en ligne de commande

Flux en 4 commandes (script complet : `examples/04-vhdl-testbench-xsim/tb/run_sim.sh`) :

```bash
source ~/vivado/2025.2/Vivado/settings64.sh
cd tb
xvhdl -2008 -work work ../rtl/mon_module.vhd          # analyse VHDL-2008
xvhdl -2008 -work work tb_mon_module.vhd              # analyse du testbench
xelab -debug typical -s tb_sim work.tb_mon_module     # elaboration (snapshot)
xsim tb_sim -R                                        # execution : run all puis quit
```

Ou en 3 commandes avec un fichier de projet (`.prj`) :
```bash
xvhdl -prj xsim_sources.prj
xelab -prj xsim_sources.prj -debug typical -s tb_sim work.tb_mon_module
xsim tb_sim -R
```
Syntaxe du `.prj` (une source VHDL par ligne) :
```
vhdl2008 work ../rtl/mon_module.vhd
vhdl2008 work tb_mon_module.vhd
```

Détails utiles :
- `-R` = « run all puis quitte ». Un testbench qui ne se termine jamais (compteur
  d'horloge infini) fera tourner la simulation sans fin : terminer par
  `std.env.finish` (VHDL-2008) ou utiliser `-t`/`--stop-time`.
- Traces d'ondes : `xsim tb_sim -gui -t xsim_wave.tcl` (script `add_wave`/`run all`),
  ou en batch `xsim tb_sim -R -wdb on`.
- Sortie : `xsim.dir/` (snapshot), `xsim.log`, `*.wdb` — à ignorer en git.
- Le code retour de `xsim` est 0 quand la simulation se termine normalement ; un
  `report ... severity failure` non capturé fait échouer la simulation (attendu).

Résultat réel obtenu sur `examples/04-vhdl-testbench-xsim` (testbench VHDL pur,
4695 vérifications) :
```
Note: *** 4695 verifications effectuees, 0 erreur(s) ***
Note: ALL TESTS PASSED
INFO: xsimkernel Simulation Memory Usage: 511076 KB (Peak: 560408 KB)
```

## 3. Le même testbench sous GHDL (vérification croisée)

```bash
ghdl -a --std=08 rtl/word_parity_counter.vhd tb/tb_word_parity_counter.vhd
ghdl -m --std=08 tb_word_parity_counter
ghdl -r --std=08 tb_word_parity_counter --stop-time=100us --assert-level=error
```
Résultat réel : `*** 4695 verifications effectuees, 0 erreur(s) *** ALL TESTS PASSED`
au même instant de simulation (7796 ns) qu'avec XSim. Deux simulateurs indépendants
qui donnent le même verdict, c'est une vraie vérification ; un seul, c'est une
présomption.

## 4. cocotb 2.x + GHDL (la voie la plus rapide à écrire)

```bash
cd tb
PATH=/tmp/ghdl_tool/bin:$PATH make            # SIM=ghdl par défaut dans nos Makefiles
WAVES=1 python3 run_tests.py                  # -> <top>.ghw (GTKWave / Surfer)
COCOTB_TESTCASE=test_reset make               # un seul test
python run_tests.py                           # variante API Python (cocotb_tools.runner)
```

> **Piège vérifié** : `make WAVES=1` ne produit **aucune** trace avec GHDL (le
> Makefile GHDL de cocotb 2.0 n'ajoute jamais `--wave`), et cela sans erreur.
> Les traces s'obtiennent avec le lanceur Python (`waves=True` /
> `WAVES=1 python3 run_tests.py`, qui écrit `counter.ghw`) ou avec
> Questa/Riviera/XSim qui gèrent `WAVES=1`.

Makefile minimal (`templates/cocotb/Makefile.ghdl`) :
```make
SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl
VHDL_SOURCES += $(PWD)/../rtl/mon_module.vhd
COCOTB_TOPLEVEL = mon_module
COCOTB_TEST_MODULES = test_mon_module
GHDL_ARGS += --std=08
include $(shell cocotb-config --makefiles)/Makefile.sim
```

### Pièges vérifiés (cocotb 2.0.1 + GHDL 6.0.0)

| Piège | Symptôme | Correctif |
|---|---|---|
| Lecture juste après `RisingEdge()` | valeur **précédente** lue, échec au cycle 1 | `await FallingEdge()` ou `await ReadOnly()` |
| Écriture après `ReadOnly()` | `RuntimeError: Attempting settings a value during the ReadOnly phase.` | avancer d'un événement avant d'écrire |
| Entrées posées après le reset | tout décalé d'un cycle | poser les entrées **avant** de relâcher le reset |
| `--std=08` à l'analyse seulement | `cannot find entity or configuration <top>` | `GHDL_ARGS += --std=08` (analyse + run) |
| `MODULE`/`TOPLEVEL` | avertissement de dépréciation | `COCOTB_TEST_MODULES` / `COCOTB_TOPLEVEL` |
| API runner : `vhdl_sources=` | `DeprecationWarning` | `sources=[...]` |
| API runner : `build_args` dans `test()` | `TypeError: unexpected keyword argument` | `test_args=[...]` (GHDL **ignore** `elab_args`) |
| `build_dir` ≠ `test_dir` (GHDL) | `cannot find entity or configuration` | même dossier pour les deux |
| `results.xml` : attribut `failures=` | absent du fichier réel de cocotb 2.x | compter les `<testcase status="failed">`, pas l'attribut du `<testsuite>` |

Recettes de testbench (reset, scoreboard, modèles de référence) :
`docs/04-cocotb-recipes.md`, helpers prêts à copier : `templates/cocotb/helpers.py`
(vérifiés à l'exécution).

## 5. Ce qu'il faut avoir vérifié avant de synthétiser

Un agent ne synthétise **jamais** un design sans au moins un test de simulation qui
passe, sauf raison explicite (design purement structurel, IP fournie). La boucle
attendue :

```
écrire le RTL -> écrire/adapter le testbench -> make (simulation) -> corriger
             -> seulement alors : synthèse -> implémentation -> timing
```

## 6. Ondes : quoi regarder

- GHDL/cocotb : `--wave=...` → `.ghw` (lisible par GTKWave et Surfer).
- Icarus/Verilator : `.vcd` / `.fst`.
- XSim : `.wdb` (lisible uniquement par l'IHM Vivado) — pour un agent, préférer
  `xsim -R -wdb off` plus une impression texte, ou exporter un VCD.
- Un agent ne lit pas une onde : il lit des **assertions** et des messages. Les
  ondes servent à l'humain qui relit après coup.
