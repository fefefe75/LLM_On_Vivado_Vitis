# Exemple 02 : ALU generique verifiee par cocotb

Une ALU combinatoire a largeur parametrable, et un testbench cocotb 2.x qui la
compare a un modele de reference ecrit en Python. L'exemple ne depend d'aucun
outil proprietaire : GHDL et cocotb suffisent.

## Arborescence

```
examples/02-alu/
├── README.md
├── rtl/
│   ├── alu_pkg.vhd   codes d'operation, dans un paquet partage
│   └── alu.vhd       entite alu, architecture rtl, un seul processus
└── tb/
    ├── Makefile      cocotb 2.x (COCOTB_TEST_MODULES, COCOTB_TOPLEVEL)
    └── test_alu.py   modele de reference Python et quatre campagnes de test
```

## Interface de l'ALU

| Port      | Sens | Largeur            | Role                                                 |
|-----------|------|--------------------|------------------------------------------------------|
| `C_WIDTH` | gene | 1 a n              | largeur des operandes et du resultat, 8 par defaut    |
| `i_op`    | in   | `C_OP_WIDTH` = 4   | code d'operation, voir `rtl/alu_pkg.vhd`              |
| `i_a`     | in   | `C_WIDTH`          | operande A                                            |
| `i_b`     | in   | `C_WIDTH`          | operande B, sert aussi de nombre de bits de decalage  |
| `o_y`     | out  | `C_WIDTH`          | resultat                                              |
| `o_zero`  | out  | 1                  | `'1'` quand `o_y` vaut zero                           |
| `o_carry` | out  | 1                  | retenue ou emprunt, voir plus bas                     |

Le module est purement combinatoire : pas d'horloge, pas de reset. Le
multiplexeur d'operation appartient au chemin de donnees, le sequentiel reste
dans le registre d'instruction du design appelant. Pour l'inserer dans un
chemin cadence, enregistrer `o_y`, `o_zero` et `o_carry` en sortie.

### Table des operations

| `i_op` | Constante     | Operation                          | `o_y`                            |
|--------|---------------|------------------------------------|----------------------------------|
| `0000` | `C_OP_ADD`    | addition                           | `i_a + i_b` modulo 2\*\*C_WIDTH  |
| `0001` | `C_OP_SUB`    | soustraction                       | `i_a - i_b` modulo 2\*\*C_WIDTH  |
| `0010` | `C_OP_AND`    | ET bit a bit                       | `i_a and i_b`                    |
| `0011` | `C_OP_OR`     | OU bit a bit                       | `i_a or i_b`                     |
| `0100` | `C_OP_XOR`    | OU exclusif bit a bit              | `i_a xor i_b`                    |
| `0101` | `C_OP_NOT`    | complement                         | `not i_a`                        |
| `0110` | `C_OP_EQ`     | egalite                            | 1 si `i_a = i_b`, 0 sinon        |
| `0111` | `C_OP_LT_U`   | inferieur non signe                | 1 si `i_a < i_b`, 0 sinon        |
| `1000` | `C_OP_LT_S`   | inferieur signe, complement a deux | 1 si `i_a < i_b`, 0 sinon        |
| `1001` | `C_OP_SLL`    | decalage logique a gauche          | `i_a << i_b`                     |
| `1010` | `C_OP_SRL`    | decalage logique a droite          | `i_a >> i_b`                     |
| `1011` | `C_OP_PASS_B` | recopie de l'operande B            | `i_b`                            |

Les codes `1100` a `1111` sont reserves. L'ALU renvoie zero sur `o_y` et
`o_carry`, donc `o_zero` vaut `'1'`. Une operation inconnue ne produit jamais
un resultat fantaisiste, et la table de verite reste complete : le testbench
peut donc balayer les seize codes d'opcode.

### Conventions de drapeaux

- addition : `o_carry` est la retenue sortante, `'1'` quand le resultat depasse
  `C_WIDTH` bits ;
- soustraction : le calcul est `i_a + (not i_b) + 1`, donc `o_carry` vaut `'1'`
  quand `i_a >= i_b`. C'est l'inverse de l'emprunt, comme sur ARM et MIPS ;
- toutes les autres operations : `o_carry` vaut `'0'` ;
- `o_zero` ne depend que de `o_y`.

Pour un nombre de decalage superieur ou egal a `C_WIDTH`, le resultat est zero.
La fonction `f_shift_amount` sature le compte a `C_WIDTH`, ce qui evite le
debordement de conversion sur les grandes largeurs.

## Modele de reference et campagnes de test

`tb/test_alu.py` contient une fonction Python par operation, une table
d'operations `REFERENCE` et la fonction `alu_reference(op, a, b, width)`. Ce
modele est ecrit d'apres la specification du RTL, il ne lit jamais le VHDL.

| Test                            | Ce qu'il couvre                                                       | Vecteurs |
|---------------------------------|-----------------------------------------------------------------------|----------|
| `test_golden_vectors`           | cas calcules a la main, hors modele : retenues, emprunts, bornes      | 35       |
| `test_all_opcodes_corner_values`| les 16 opcodes sur les 13 valeurs limites deux a deux                 | 2704     |
| `test_operand_sweep_all_opcodes`| balayage de `i_a` sur les 256 valeurs, 3 valeurs de `i_b`, par opcode | 12288    |
| `test_random_vectors`           | vecteurs aleatoires reproductibles, moitie a petits `i_b`             | 2000     |

Avec `C_WIDTH = 8`, cela fait 17027 vecteurs. Chaque vecteur verifie les trois
sorties et controle en plus que `o_y` ne contient ni `X` ni `Z`. Les valeurs
limites sont zero, un, deux, le maximum, le maximum moins un, le bit de poids
fort seul, les extremums signes, les motifs a bits alternes et les bornes de
decalage `C_WIDTH - 1`, `C_WIDTH`, `C_WIDTH + 1`.

## Lancer les tests

Prerequis : GHDL 6.0.0 (teste) et cocotb 2.0.1 (teste), avec `cocotb-config`
sur le `PATH`.

```
cd examples/02-alu/tb
make
```

Si les outils sont installes dans un environnement dedie :

```
PATH=/chemin/vers/ghdl/bin:/chemin/vers/venv/bin:$PATH make
```

Fin de sortie attendue, les temps varient d'une machine a l'autre. Sortie
reellement obtenue sur la machine de reference (2026-09-17, GHDL 6.0.0 +
cocotb 2.0.1) :

```
** test_alu.test_golden_vectors              PASS          35.00           0.00      25913.62  **
** test_alu.test_all_opcodes_corner_values   PASS        2704.00           0.07      37774.82  **
** test_alu.test_operand_sweep_all_opcodes   PASS       12288.00           0.32      38065.46  **
** test_alu.test_random_vectors              PASS        2000.00           0.06      32786.31  **
** TESTS=4 PASS=4 FAIL=0 SKIP=0                         17027.00           0.46      37091.45  **
```

Options utiles :

```
make COCOTB_TESTCASE=test_golden_vectors    # un seul test
make ALU_RANDOM_VECTORS=20000               # campagne aleatoire plus longue
make COCOTB_RANDOM_SEED=999                 # autre graine, meme longueur
make clean                                  # supprime sim_build/ et results.xml
```

Les traces de signaux ne sont pas disponibles avec **le flux Makefile** sous GHDL :
le backend GHDL de cocotb n'implémente pas `WAVES=1`, et le binaire mcode 6.0.0
utilisé ici refuse l'option `--wave=FILE` ajoutée à la main (`unknown command
option`). Vérifié pendant l'écriture du dépôt : `make WAVES=1` ne produit aucun
fichier **et ne signale rien**.

Deux façons d'obtenir quand même une trace :

```bash
# 1) lanceur Python de cocotb, qui ajoute lui-meme --wave=<top>.ghw
WAVES=1 python3 run_tests.py          # -> tb/*.ghw (GTKWave / Surfer)
# 2) autre simulateur qui gere WAVES=1 (Questa, Riviera) ou XSim
make SIM=questa WAVES=1
```
Le testbench joue donc le role d'oracle automatise, sans fichier de traces, ce qui
suffit pour valider une ALU combinatoire. Pour observer les signaux, passer
par un simulateur qui gère les traces avec le même
`test_alu.py`, ou par un GHDL compile avec le support des vagues.

## Reproductibilite

Le Makefile exporte `COCOTB_RANDOM_SEED` (1234 par defaut). Le test tire ses
vecteurs d'un `random.Random` initialise avec `cocotb.RANDOM_SEED`, lui-meme
derive de cette graine et du nom du test. Deux executions avec la meme graine
rejouent exactement les memes vecteurs, et la graine utilisee est ecrite dans
le journal de `test_random_vectors`.

## Changer la largeur

Le testbench lit la largeur sur les ports du DUT, il ne la code pas en dur. Le
generic se surcharge donc a l'elaboration :

```
make SIM_ARGS="-gC_WIDTH=16"
```

Verifie : `C_WIDTH=16` passe avec 24576 vecteurs en balayage, `C_WIDTH=5` et
`C_WIDTH=1` passent aussi. En dessous de 4 bits, `test_golden_vectors` se
retire et l'annonce dans le journal, car ses cas n'ont plus assez d'etats pour
etre pertinents. Les trois autres campagnes gardent la couverture.

## Autres simulateurs

Le Makefile se contente de choisir un backend cocotb. Le testbench Python est
independant du simulateur, il ne parle qu'aux ports du DUT.

| `SIM=`              | VHDL | Etat dans cet exemple                                                 |
|---------------------|------|-----------------------------------------------------------------------|
| `ghdl`              | oui  | verifie, quatre tests PASS                                            |
| `questa`, `modelsim`| oui  | RTL compile par vcom 2023.3 sans option de revision (0 erreur) ; la simulation demande une licence, non disponible ici |
| `nvc`               | oui  | backend fourni par cocotb, non verifie ici                            |
| `icarus`, `verilator` | non | cocotb s'arrete sur `Skipping simulation as only Verilog is supported` |

```
make SIM=questa
make SIM=modelsim
make SIM=nvc
```

Icarus et Verilator ne compilent que Verilog et SystemVerilog. Pour les
utiliser, il faut un portage Verilog de l'ALU (`rtl/alu.v`) et deux lignes du
Makefile a changer :

```make
TOPLEVEL_LANG = verilog
VERILOG_SOURCES += $(PWD)/../rtl/alu.v
```

Le fichier `test_alu.py` reste identique, y compris le modele de reference.

## Pieges rencontres, et mesures prises

1. cocotb 2.x renomme les variables du Makefile : `COCOTB_TEST_MODULES`
   remplace `MODULE` et `COCOTB_TOPLEVEL` remplace `TOPLEVEL`. Les anciens noms
   sont declasses et ignores.
2. GHDL exige `--std=08` a l'analyse et a l'execution. `GHDL_ARGS += --std=08`
   couvre les deux phases.
3. Sur un DUT combinatoire, il faut attendre un `Timer` apres chaque ecriture
   d'entree. Sans cette attente, on lit les sorties du vecteur precedent.
4. `o_zero` est derive de la variable interne et non du signal `o_y`. Comparer
   `o_y` a zero des le premier delta ferait sortir un avertissement
   `NUMERIC_STD."=": metavalue detected` a chaque simulation.
5. Les affectations conditionnelles de signal restent hors des processus.
   GHDL les accepte dans un processus, vcom les refuse avec
   `Illegal sequential statement`. Le RTL s'analyse d'ailleurs en VHDL-93 comme
   en VHDL-2008, ce qui evite d'imposer une revision aux autres outils.
6. Le test de la ligne `TESTS=...` est le seul juge : `make` doit finir avec
   `PASS=4 FAIL=0`. Un test qui ne compare rien passe sans rien verifier.

## Fichiers generes

`sim_build/`, `results.xml`, `work/`, `transcript` et `modelsim.ini` sont des
artefacts de simulation. Ils sont deja couverts par le `.gitignore` du depot et
ne doivent jamais etre committes. `make clean` supprime les deux principaux.
