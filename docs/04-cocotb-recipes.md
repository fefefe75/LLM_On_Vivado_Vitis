# Recettes cocotb 2.x (vérifiées à l'exécution)

Toutes les recettes ci-dessous ont été exécutées avec **cocotb 2.0.1 + GHDL 6.0.0**.
Les valeurs et messages cités sont ceux observés.

---

## 1. Squelette d'un test qui marche du premier coup

```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge


async def demarrer(dut, cycles_reset: int = 3):
    """Horloge + reset. Les ENTREES doivent etre posees par l'appelant AVANT."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())   # 100 MHz
    dut.i_rst.value = 1
    for _ in range(cycles_reset):
        await RisingEdge(dut.i_clk)
    dut.i_rst.value = 0


@cocotb.test()
async def test_nominal(dut):
    dut.i_en.value = 1                       # 1) entrees AVANT le reset
    await demarrer(dut)                      # 2) horloge + reset

    for attendu in range(1, 6):              # 3) stimulation + 4) verification
        await RisingEdge(dut.i_clk)
        await FallingEdge(dut.i_clk)         #    sortie stabilisee
        recu = int(dut.o_count.value)
        assert recu == attendu, f"cycle {attendu}: attendu {attendu}, recu {recu}"
```
Trois règles non négociables (chacune vient d'un échec réel) :
**entrées avant reset** → sinon tout est décalé d'un cycle ;
**échantillonner sur front descendant ou via `ReadOnly()`** → sinon on lit la valeur
précédente ;
**avancer d'un événement avant d'écrire après un `ReadOnly()`** → sinon
`RuntimeError: Attempting settings a value during the ReadOnly phase.`

## 2. Helpers réutilisables

`templates/cocotb/helpers.py` (exécuté et validé) fournit :
`start_clock`, `reset`, `cycles`, `ClockReset`, `read_after_edge`, `BusDriver`,
`Scoreboard`, `bits`, `signed`, `wait_ns`. Exemple :

```python
from helpers import ClockReset, Scoreboard, cycles, read_after_edge

@cocotb.test()
async def test_avec_scoreboard(dut):
    dut.i_en.value = 1
    await ClockReset(dut).start()

    sb = Scoreboard("compteur")
    await cycles(dut, 1)
    sb.check(got=int(dut.o_count.value), expected=1, ctx="apres 1 cycle")
    sb.check(got=await read_after_edge(dut, "o_count"), expected=2, ctx="ReadOnly")
    sb.report()          # leve une AssertionError listant TOUTES les erreurs
```
`Scoreboard.report()` affiche les 10 premières erreurs et le total : un test qui
échoue dit *combien* de fois et *où*, pas seulement « ça a échoué ».

## 3. Comparer à un modèle de référence écrit en Python

C'est la technique la plus rentable pour un agent : le DUT est comparé à du Python
simple, exhaustivement ou sur des tirages aléatoires reproductibles.

```python
import random, cocotb

def modele(a: int, b: int, op: int, width: int) -> int:
    mask = (1 << width) - 1
    if op == 0: return (a + b) & mask
    if op == 1: return (a - b) & mask
    if op == 2: return a & b
    return a ^ b

@cocotb.test()
async def test_contre_modele(dut):
    rng = random.Random(1234)                       # graine FIXE
    for _ in range(2000):
        a, b, op = rng.randrange(256), rng.randrange(256), rng.randrange(4)
        dut.i_a.value, dut.i_b.value, dut.i_op.value = a, b, op
        await cocotb.triggers.Timer(1, unit="ns")   # laisser la combinatoire se stabiliser
        recu = int(dut.o_y.value)
        attendu = modele(a, b, op, 8)
        assert recu == attendu, f"a={a} b={b} op={op}: attendu {attendu}, recu {recu}"
```
Une graine fixe rend l'échec **reproductible** : le message contient les entrées, on
rejoue exactement le même cas. `COCOTB_RANDOM_SEED=1234` (ou `seed=` dans le runner)
est enregistrée dans `results.xml` (`random_seed`).

## 4. Choix des tests à exécuter

| Besoin | Commande | Vérifié |
|---|---|---|
| Tout | `make` | ✔ |
| Un seul test, par nom | `make COCOTB_TESTCASE=test_reset_synchrone` | ✔ `running ... (1/1)` |
| Sous-ensemble par expression régulière | `make COCOTB_TEST_FILTER="test_.*reset.*"` | ✔ |
| Changer de simulateur | `make SIM=questa` / `ghdl` / `icarus` / `verilator` | ✔ |
| Ondes | `WAVES=1 python3 run_tests.py` → `<top>.ghw` (avec GHDL) ; `make WAVES=1` pour Questa/Riviera | ✔ (et `make WAVES=1` **ne produit rien** avec GHDL, vérifié) |
| Un test qui boucle trop longtemps | `@cocotb.test(timeout_time=50, timeout_unit="ns")` | ✔ lève `cocotb.triggers.SimTimeoutError` |
| Déboguer au premier échec | `COCOTB_PDB_ON_EXCEPTION=1 make` | documenté cocotb |

> Note : dans un Makefile, `COCOTB_TEST_MODULES = x` **écrase** la variable
> d'environnement du même nom (comportement de make). Pour choisir le module depuis
> la ligne de commande, utiliser l'API Python (`test_module=...`) ou
> `COCOTB_TESTCASE`/`COCOTB_TEST_FILTER`.

## 5. Lire le verdict sans lire le log

Le fichier `results.xml` produit par cocotb est la source fiable (le `PASS/FAIL`
affiché peut passer inaperçu dans 200 lignes). Attention : cocotb 2.x **n'écrit pas
d'attribut `failures=`** sur le `<testsuite>` ; les échecs sont des éléments
`<failure>` dans les `<testcase>`. Compter depuis les `testcase`, sinon un test
rouge passe pour vert.

```python
from vivado_mcp.reports import parse_cocotb_results   # mcp/vivado_mcp/reports.py
print(parse_cocotb_results("tb/results.xml")["all_passed"], "...")
# ou, avec le serveur MCP : cocotb_results(tb_dir="tb")
```

## 6. Tests paramétrés / plusieurs cas

```python
CAS = [(0, 0, 0), (255, 1, 0), (128, 128, 1), (0, 255, 3)]

def make_test(a, b, op):
    @cocotb.test(name=f"cas_{a}_{b}_{op}")
    async def _t(dut):
        dut.i_a.value, dut.i_b.value, dut.i_op.value = a, b, op
        await cocotb.triggers.Timer(1, unit="ns")
        assert int(dut.o_y.value) == modele(a, b, op, 8)
    return _t

for _a, _b, _op in CAS:
    make_test(_a, _b, _op)
```
Chaque cas apparaît comme un test distinct dans `results.xml` : un agent sait lequel
a échoué sans parser de log.

## 7. Vérifier un design séquentiel : les 5 tests minimum

1. **Reset** : après reset, sorties à la valeur définie.
2. **Nominal** : un cycle normal fait ce qui est attendu.
3. **Limites** : 0, valeur max, débordement/rebouclage, valeur signée négative.
4. **Entrée ignorée** : `enable=0` ou écriture quand la FIFO est pleine ne change rien.
5. **Aléatoire à graine fixe** contre un modèle de référence.

Si un agent ne peut pas écrire ces cinq-là, ce n'est pas la peine de synthétiser.

## 8. Ce qui ne marchera pas

- Piloter XSim avec cocotb (voir `docs/03-simulation.md`).
- Simuler un design dont la bibliothèque VHDL a été compilée avec un autre standard :
  `--std=08` partout, ou `--std=93` partout, mais pas un mélange.
- Écrire dans un signal du DUT depuis le testbench pour « forcer » un résultat : cocotb
  le permet, mais le test ne vérifie alors plus le design.
