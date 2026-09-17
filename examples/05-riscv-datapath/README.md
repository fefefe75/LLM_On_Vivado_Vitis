# Exemple 05 : mini-datapath RISC-V RV32I (ALU, décodeur, banc de registres)

Un début de cœur RISC-V RV32I écrit en VHDL, avec deux testbenches cocotb 2.x :
l'ALU seule (`tb/alu/`) et le chemin de données complet (`tb/riscv/`). Aucun
outil propriétaire n'est nécessaire : GHDL et cocotb suffisent.

Cet exemple vient d'un projet personnel de l'auteur
(`risv_v_basique`), repris ici **tel quel** comme **exemple de structure de
référence** pour le dépôt.

## Pourquoi cet exemple est dans ce dépôt

Les exemples 01 à 04 montrent chacun un module isolé, dans un dossier plat :

```
examples/02-alu/
├── README.md
├── rtl/alu.vhd
└── tb/{Makefile, test_alu.py}
```

L'exemple 05 montre l'organisation à adopter dès que le projet grossit :

- **`rtl/` hiérarchisé** : `rtl/alu/`, `rtl/decoder/`, `rtl/registre/` et le
  fichier qui assemble le tout, `rtl/datapath.vhd` ;
- **`tb/` avec un dossier par banc d'essai** : `tb/alu/` et `tb/riscv/`,
  chacun avec son propre `Makefile` cocotb 2.x et son `waveform.do` pour
  Questa/ModelSim ;
- **`software/`** : le firmware exécuté par le matériel pendant la simulation,
  séparé du RTL et du banc d'essai.

C'est la disposition que reprennent les exemples suivants du dépôt, et celle
à utiliser pour un projet Vivado/Vitis complet.

## Arborescence

```
examples/05-riscv-datapath/
├── README.md
├── rtl/
│   ├── alu/
│   │   ├── alu.vhd             ALU 32 bits, multiplexeur des 4 opérations
│   │   ├── et_logique.vhd      ET bit à bit
│   │   ├── ou_logique.vhd      OU bit à bit
│   │   ├── somme.vhd           addition + retenue
│   │   └── soustraction.vhd    soustraction + drapeau
│   ├── decoder/
│   │   └── decoder.vhd         décodage des instructions RV32I
│   ├── registre/
│   │   └── banc_registre.vhd   banc de 32 registres de 32 bits, x0 câblé à 0
│   └── datapath.vhd            assemblage ALU + décodeur + banc de registres
├── tb/
│   ├── alu/
│   │   ├── Makefile            cocotb 2.x, SIM ?= ghdl
│   │   ├── testbench_alu.py    test de l'addition de l'ALU
│   │   └── waveform.do         visualisation Questa/ModelSim (non testé ici)
│   └── riscv/
│       ├── Makefile            cocotb 2.x, SIM ?= ghdl
│       ├── testbench_datapath.py  exécute software/main.bin instruction par instruction
│       └── waveform.do         visualisation Questa/ModelSim (non testé ici)
└── software/
    ├── Makefile                génère main.elf et main.bin (chaîne croisée RISC-V)
    └── main.c                  programme C joué par le datapath
```

## Liens entre les blocs

```
        i_instruction ──► ┌──────────┐
                          │ decoder  │──► adresses rs1/rs2/rd, write_en,
                          │          │    commande ALU, immédiat étendu,
                          └──────────┘    mem_read, mem_write, branch
                                             │
        ┌───────────────────┐  rs1/rs2 data  │
        │  banc_registre    │◄───────────────┘
        │  (32 x 32 bits)   │──► s_rs1_data, s_rs2_data ──┐
        └───────────────────┘                              │
                 ▲  i_rd_data                           ┌──▼───┐
                 │                                      │ MUX  │ ◄─ immédiat
                 │                                      └──┬───┘
                 │                                     ┌───▼───┐
                 │                                     │  ALU  │──► s_alu_result
                 │                                     └───────┘     │
                 └──────────── MUX écriture ◄── mem_read, PC+4 ─────┘
```

Sorties du `datapath` : `o_next_pc`, `o_ram_addr`, `o_ram_data`, `o_mem_read`,
`o_mem_write`, `o_branch`. Le registre de PC et la mémoire de programme sont
**hors** du bloc : c'est le banc d'essai qui les joue (voir plus bas).

### Instructions reconnues par `decoder.vhd`

| `opcode`  | Type | Instructions                          | `o_alu_cmd`        |
|-----------|------|---------------------------------------|--------------------|
| `0110011` | R    | `add`, `sub`, `or`, `and`             | selon `funct3/funct7` |
| `0010011` | I    | `addi`, `li`, `mv`                    | addition           |
| `0000011` | I    | `lw` (chargement mémoire)             | addition (base+offset) |
| `0100011` | S    | `sw` (écriture mémoire)               | addition           |
| `1100011` | B    | `beq` / `bne`                         | soustraction       |
| `1101111` | J    | `jal` (appel de fonction, `j`)        | addition           |
| `1100111` | I    | `jalr` (`ret`)                        | addition           |
| `0010111` | U    | `auipc`                               | addition           |

Les immédiats des types I, S, B, J et U sont reconstruits et étendus sur
32 bits dans le décodeur.

### Opcodes de l'ALU

| `i_opcode` | Opération        | Latence observée (front d'horloge) |
|------------|------------------|------------------------------------|
| `000000`   | ET bit à bit     | 2 cycles                           |
| `000001`   | OU bit à bit     | 2 cycles                           |
| `000010`   | Addition         | 4 cycles                           |
| `000011`   | Soustraction     | 4 cycles                           |
| autres     | aucun cas prévu  | `o_data` conserve sa valeur        |

Les latences ci-dessus sont mesurées, pas déduites : `et_logique` et
`ou_logique` mémorisent une fois, `somme` et `soustraction` deux fois
(ils enregistrent d'abord les opérandes), et le multiplexeur de sortie de
`alu.vhd` ajoute un cycle. Le `case` de `alu.vhd` n'a pas de branche
`when others` qui pilote `o_data` : un opcode inconnu laisse donc la sortie
inchangée.

## Le programme RISC-V (`software/main.c`)

`main.c` est un programme volontairement minimal qui parcourt les quatre
formats d'instruction intéressants :

```c
int main() {
    int a = 10;       // Type I (addi)
    int b = 20;       // Type I (addi)
    int c = 0;
    c = a + b;        // Type R (add)
    if (c == 30) {    // Type B (beq/bne)
        c = 1;
    } else {
        c = 2;
    }
    return 0;
}
```

`tb/riscv/testbench_datapath.py` charge le **code machine** de ce programme
(`main.bin`) et l'injecte dans le datapath, exactement comme le ferait une
mémoire de programme. L'adresse de chargement est `0x100f8` (constante
`START_ADDRESS` du banc d'essai), qui correspond à l'index 0 du tableau
d'instructions.

### Note importante : les binaires ne sont pas committés

`main.bin` et `main.elf` sont des **artefacts dérivés** : ils dépendent du
compilateur croisé et de ses options. Ils ne sont **pas** dans le dépôt (et
`*.bin` / `*.elf` sont déjà couverts par le `.gitignore`). Sans `main.bin`, le
test du datapath **échoue** avec un message explicite qui rappelle les
commandes de génération — il ne simule jamais un programme inexistant.

Pour le produire :

```
cd examples/05-riscv-datapath/software
make            # détecte la chaîne croisée et génère main.elf + main.bin
```

`software/Makefile` essaie, dans cet ordre : `riscv-none-embed-gcc` (xPack,
bare-metal, la chaîne d'origine), puis `riscv64-unknown-elf-gcc`, puis
`riscv64-linux-gnu-gcc` (chaîne Linux, présente sur Fedora). Les commandes
équivalentes à la main :

```
# 1. chaîne croisée bare-metal xPack
riscv-none-embed-gcc -march=rv32i -mabi=ilp32 -O0 -nostdlib -nostartfiles \
    -e main -Wl,-Ttext=0x100f8 -o main.elf main.c
riscv-none-embed-objcopy -O binary main.elf main.bin

# 2. chaîne croisée GNU
riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 -mno-relax -O0 \
    -nostdlib -nostartfiles -e main -Wl,-Ttext=0x100f8 -o main.elf main.c
riscv64-unknown-elf-objcopy -O binary main.elf main.bin

# 3. chaîne Linux (celle utilisée pour valider cet exemple)
riscv64-linux-gnu-gcc -march=rv32i -mabi=ilp32 -mno-relax -O0 -nostdlib \
    -nostartfiles -e main -Wl,--build-id=none -Wl,-Ttext=0x100f8 \
    -o main.elf main.c
riscv64-linux-gnu-objcopy -O binary main.elf main.bin
```

Trois points à respecter :

- `-Ttext=0x100f8` doit correspondre à `START_ADDRESS` du banc d'essai,
  sinon le testbench injecte des NOP ;
- `-e main` : sans `crt0`, c'est `main` qui sert de point d'entrée ;
- `-Wl,--build-id=none` est obligatoire avec la chaîne Linux, sinon `ld`
  refuse la place de `.note.gnu.build-id` sous `0x100f8`.

`make RISCV_BIN=/autre/chemin/main.bin` permet de pointer vers un autre
binaire sans toucher au fichier.

## Lancer les tests

Prérequis : GHDL 6.0.0 (testé) et cocotb 2.0.1 (testé), `cocotb-config` sur le
`PATH`. Si les outils sont dans un environnement dédié :

```
export PATH=/chemin/vers/ghdl/bin:/chemin/vers/venv/bin:$PATH
```

### Test de l'ALU

```
cd examples/05-riscv-datapath/tb/alu
make                      # SIM ?= ghdl par défaut
```

### Test du datapath

Il faut d'abord le binaire (voir plus haut), puis :

```
cd examples/05-riscv-datapath/software && make
cd ../tb/riscv && make
```

Options utiles (les deux bancs d'essai) :

```
make clean                              # supprime sim_build/ et results.xml
make SIM=questa                         # Questa/ModelSim (voir plus bas)
make SIM=modelsim
```

## Sortie réellement obtenue

Machine de référence, 2026-09-17 : GHDL 6.0.0 (backend mcode) + cocotb 2.0.1,
Python 3.12.4.

`cd examples/05-riscv-datapath/tb/alu && PATH=/tmp/ghdl_tool/bin:$PATH make SIM=ghdl`
— **exit 0** :

```
     0.00ns INFO     cocotb.regression   running testbench_alu.alu_basic_test (1/1)
    20.00ns INFO     cocotb.alu          --- Début Test 1 : Addition standard ---
    70.00ns INFO     cocotb.alu          Sortie Data lue en Hexa : 0x2d
    70.00ns INFO     cocotb.alu          TEST 1 REUSSI ! 🚀
    70.00ns INFO     cocotb.regression   testbench_alu.alu_basic_test passed
** testbench_alu.alu_basic_test   PASS          70.00           0.00     100893.91  **
** TESTS=1 PASS=1 FAIL=0 SKIP=0                 70.00           0.00      52730.11  **
```

`cd examples/05-riscv-datapath/tb/riscv && make SIM=ghdl` **avec** un
`software/main.bin` généré localement — **exit 0** :

```
     0.00ns INFO     cocotb.datapath   Programme RISC-V charge depuis : .../software/main.bin
   160.00ns INFO     cocotb.datapath   [RAM WRITE] Ecriture de 0 a 0xffffffc0
                                       [...] lignes [RAM WRITE] omises : 210, 510 et 710 ns
   360.00ns INFO     cocotb.datapath   [RAM WRITE] Ecriture de 10 a 0xa
   460.00ns INFO     cocotb.datapath   [RAM WRITE] Ecriture de 20 a 0x14
   960.00ns INFO     cocotb.datapath   [RAM WRITE] Ecriture de 1 a 0x1
  2441.00ns INFO     cocotb.datapath   Fin de la simulation Cocotb !
** TESTS=1 PASS=1 FAIL=0 SKIP=0         2441.00           0.01     206304.96  **
```

Sans `software/main.bin`, le même `make` échoue **proprement** (exit 2) :

```
FileNotFoundError:
================================================================================
PROGRAMME RISC-V ABSENT : .../examples/05-riscv-datapath/software/main.bin

Ce testbench charge le code machine produit a partir de software/main.c
(adresse de chargement 0x100f8). Le fichier .bin n'est pas committe
(fichier derive) : il doit etre genere localement.
[... commandes de generation ...]
================================================================================
** TESTS=1 PASS=0 FAIL=1 SKIP=0      0.00   0.00    0.00  **
```

## Ce qui est vérifié, ce qui ne l'est pas

### Vérifié sur cette machine (GHDL 6.0.0 + cocotb 2.0.1)

| Point                                        | Résultat |
|----------------------------------------------|----------|
| Les 5 fichiers de `rtl/alu/` s'analysent en VHDL-2008 et `alu` s'élabore | OK |
| Les 8 fichiers de `rtl/` s'analysent et `datapath` s'élabore | OK |
| `alu` : `15 + 30 = 45` (`0x2d`) lu sur `o_data` | PASS |
| `alu` : ET, OU, ADD, SUB donnent le bon résultat (mesure indépendante, 4 opcodes) | OK |
| `datapath` : 50 itérations d'injection d'instructions sans erreur de simulation | PASS |
| Absence de `main.bin` → échec explicite, pas de simulation à vide | PASS |

### Non vérifié, ou fragile

- **`testbench_alu.py` ne teste presque rien.** Il ne joue qu'**une** addition
  (opcode `000010`) et n'a **qu'une seule assertion**. Les opcodes ET, OU et
  soustraction, l'extension de signe, les cas limites et `o_flag` ne sont
  **pas** testés par le testbench fourni. Le fichier a été conservé tel quel
  (c'est le testbench d'origine), mais il ne faut pas le prendre comme modèle
  de couverture : voir `examples/02-alu/tb/test_alu.py` pour un banc d'essai
  complet avec modèle de référence Python.
- **`testbench_datapath.py` n'a aucune assertion.** Il journalise le PC et
  l'instruction à chaque cycle, mais ne vérifie ni le résultat du programme ni
  les sorties RAM. « PASS » signifie uniquement « la simulation s'est déroulée
  sans erreur », pas « le programme C a produit le bon résultat ».
- **La mémoire de données n'est pas modélisée.** `i_ram_data` reste à 0 :
  tous les `lw` renvoient donc 0, et le résultat du `if (c == 30)` du programme
  C n'est pas celui qu'on obtiendrait sur un vrai cœur. Le testbench journalise
  les écritures (`sw`) mais ne les relit jamais.
- **`o_flag` n'est pas un indicateur fiable.** `somme.vhd` et
  `soustraction.vhd` utilisent le **même** test d'anticipation de retenue
  `(0xFFFFFFFF - a) < b` : pour l'addition c'est un débordement non signé
  correct, pour la soustraction ce n'est pas un emprunt. `o_flag` n'est testé
  nulle part.
- **La condition de branchement est approximative.** `datapath.vhd` prend le
  saut quand `o_branch = '1'` **et** `o_flag = '0'`, c'est-à-dire quand la
  soustraction `rs1 - rs2` ne déborde pas — et non quand `rs1 = rs2`. `beq` et
  `bne` ne sont d'ailleurs pas distingués par le décodeur (même `opcode`,
  `funct3` ignoré). Le `if/else` du programme C ne fonctionne donc pas
  correctement sur ce cœur.
- **Le PC n'est pas dans le datapath.** `i_pc` est piloté par le banc d'essai
  et `o_next_pc` recalculé à chaque itération : ce n'est pas encore un
  processeur autonome, seulement un chemin de données avec injection

### Non vérifié car l'outil est absent de cette machine

- **Questa/ModelSim** : le `.do` de génération des vagues, `GUI=1`, les
  fichiers `tb/*/waveform.do` et les sorties SDF / `vsim.wlf` n'ont **pas** pu
  être exécutés. Aucun test n'a été fait avec `SIM=questa` ou `SIM=modelsim`.
- **Chaîne croisée d'origine** : le `main.bin` du projet source a été produit
  par un toolchain bare-metal qui n'est pas installé ici
  (`riscv-none-embed-gcc` / `riscv64-unknown-elf-gcc` absents). Le binaire
  utilisé pour valider le second test a donc été **régénéré localement** avec
  `riscv64-linux-gnu-gcc` : le chemin est validé de bout en bout, mais ce
  n'est **pas** la même image mémoire que celle du projet d'origine (même
  programme C, code machine possiblement différent).

## Autres simulateurs

Le `Makefile` ne fait que choisir un backend cocotb ; les testbenches Python ne
parlent qu'aux ports du DUT et sont donc indépendants du simulateur.

| `SIM=`                 | VHDL | État dans cet exemple |
|------------------------|------|-----------------------|
| `ghdl`                 | oui  | vérifié, les deux bancs d'essai PASS |
| `questa`, `modelsim`   | oui  | non vérifié, aucune licence sur cette machine |
| `nvc`                  | oui  | backend fourni par cocotb, non vérifié |
| `icarus`, `verilator`  | non  | ne compilent pas le VHDL |

## Pièges rencontrés, et mesures prises

1. **cocotb 2.x renomme les variables du Makefile.** Les deux `Makefile`
   d'origine utilisaient `TOPLEVEL` / `MODULE` (cocotb 1.x) : remplacés par
   `COCOTB_TOPLEVEL` et `COCOTB_TEST_MODULES`. Les anciens noms sont ignorés.
2. **`SIM ?= modelsim` par défaut** dans les deux `Makefile` d'origine : passé
   à `SIM ?= ghdl`, pour que `make` fonctionne sans licence. Questa/ModelSim
   restent disponibles via `make SIM=questa`.
3. **GHDL exige `--std=08`** à l'analyse **et** à l'exécution.
   `GHDL_ARGS += --std=08` couvre les deux phases ; sinon GHDL s'arrête sur
   `cannot find entity or configuration datapath`.
4. **Les chemins de sources étaient relatifs à l'ancienne arborescence**
   (`VHDL_SOURCES += et_logique.vhd` dans `tb/alu/`, où les `.vhd` étaient
   copiés à côté du Makefile). Ils pointent maintenant vers `../../rtl/...`.
5. **Le testbench du datapath lisait `../../src/software/main.bin`** en dur,
   avec un chemin relatif au dossier de lancement — or cocotb exécute le test
   depuis `sim_build/`. Le chemin est désormais **exporté en absolu** par le
   Makefile (`RISCV_BIN`), avec replis dans le testbench.
6. **`logic_array.binstr` est déprécié** en cocotb 2.x : remplacé par
   `str(logic_array)` dans `testbench_datapath.py`.
7. **Le `Makefile` de `tb/alu/` générait un `waveform.do`** et enchaînait
   `all: purge waveform.do sim`, ce qui écrivait des fichiers à chaque `make`.
   Remplacé par un `waveform.do` statique, à usage Questa/ModelSim uniquement.
8. **Le `waveform.do` d'origine était incohérent** : placé dans `tb/riscv/`, il
   compilait les sources de l'ALU et chargeait `work.alu`. Corrigé pour
   `work.datapath` et pour tous les fichiers de `rtl/`.

## Fichiers générés

`sim_build/`, `results.xml`, `__pycache__/`, `main.elf` et `main.bin` sont des
artefacts. Ils sont déjà couverts par le `.gitignore` du dépôt et ne doivent
jamais être committés. `make clean` (dans `tb/alu/`, `tb/riscv/`) et
`make -C software clean` les suppriment.

## Origine

Projet personnel `risv_v_basique` de l'auteur, importé ici sans modification du
RTL. Seuls les `Makefile`, les chemins et le chargement du binaire ont été
adaptés à cocotb 2.x et à GHDL ; les points non couverts par les testbenches
d'origine sont listés ci-dessus plutôt que maquillés.
