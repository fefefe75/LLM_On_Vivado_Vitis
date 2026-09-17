---
name: cocotb-testbench
description: Use when writing, running or debugging a cocotb testbench for a VHDL/Verilog module, or when a simulation must prove a design works.
---

# Testbench cocotb 2.x (GHDL, Icarus, Verilator, Questa)

Recettes complètes et vérifiées : `docs/04-cocotb-recipes.md`.
Helpers prêts à copier : `templates/cocotb/helpers.py`. Makefiles modèles :
`templates/cocotb/Makefile.ghdl` (et `.icarus`, `.verilator`, `.questa`).
Exemples qui passent : `examples/01-counter-cocotb`, `02-alu`, `03-fifo`.

## Ce qui ne marche pas, et qu'il ne faut pas essayer

**cocotb ne supporte pas XSim** (Vivado Simulator) — vérifié dans cocotb 2.0.1 :
`make SIM=xsim` → `Couldn't find makefile for simulator: "xsim"`.
Si l'environnement est Vivado-only : écrire un testbench VHDL pur
(`examples/04-vhdl-testbench-xsim`) ou simuler avec GHDL.

Liste réellement supportée : `ghdl icarus verilator nvc questa modelsim rivista…`
→ en pratique : `ghdl` (VHDL), `icarus`/`verilator` (Verilog), `questa` (licence).

## Makefile minimal

```make
SIM ?= ghdl
TOPLEVEL_LANG ?= vhdl
VHDL_SOURCES += $(PWD)/../rtl/mon_module.vhd
COCOTB_TOPLEVEL = mon_module          # (MODULE/TOPLEVEL = dépréciés en 2.x)
COCOTB_TEST_MODULES = test_mon_module
GHDL_ARGS += --std=08                 # analyse ET exécution
include $(shell cocotb-config --makefiles)/Makefile.sim
```

## Les trois pièges qui font échouer un test correct

1. **Entrées posées après le reset** → tout est décalé d'un cycle. Poser les
   entrées **avant** de relâcher le reset.
2. **Lecture juste après `await RisingEdge()`** → on lit la valeur *précédente*.
   Échantillonner sur `FallingEdge`, ou `RisingEdge()` puis `await ReadOnly()`.
3. **Écriture juste après `await ReadOnly()`** →
   `RuntimeError: Attempting settings a value during the ReadOnly phase.`
   Avancer d'un événement avant d'écrire.

Autres : `--std=08` oublié à l'exécution → `cannot find entity or configuration` ;
`vhdl_sources=` dans l'API Python → déprécié, utiliser `sources=` ; GHDL ignore
`elab_args` → utiliser `test_args=["--std=08"]`.

## Structure d'un test qui prouve quelque chose

1. reset → sortie à l'état défini ;
2. cas nominal ;
3. valeurs limites (0, max, débordement, signé négatif) ;
4. opération interdite/ignorée (write quand full, enable=0) ;
5. tirage aléatoire à **graine fixe** comparé à un modèle Python.

```python
@cocotb.test(timeout_time=100, timeout_unit="us")   # un test qui boucle est tué
async def test_x(dut):
    dut.i_en.value = 1                       # entrées AVANT
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    dut.i_rst.value = 1
    for _ in range(3):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0
    await RisingEdge(dut.i_clk)              # prise en compte du reset
    await ReadOnly()
    assert int(dut.o_count.value) == 0, "compteur non nul après reset"
```

## Lancer, cibler, diagnostiquer

```bash
make                                     # tout
make COCOTB_TESTCASE=test_reset          # un test
make COCOTB_TEST_FILTER="test_.*reset.*" # filtre regex
make WAVES=1                             # <top>.ghw (GTKWave / Surfer)
COCOTB_PDB_ON_EXCEPTION=1 make           # debugger au premier échec
```
Verdict fiable : `results.xml` (compter les `<testcase>`, **pas** un attribut
`failures=` qui n'existe pas dans cocotb 2.x).
