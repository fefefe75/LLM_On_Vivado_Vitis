# 03 — FIFO synchrone générique (VHDL + cocotb 2.x)

Exemple de référence : une FIFO synchrone VHDL générique, simulée et vérifiée
par un testbench cocotb **avant** toute synthèse (règle du dépôt : aucun design
n'est déclaré fonctionnel sans journal de simulation).

Arborescence (même disposition que `examples/01-counter-cocotb`,
`examples/02-alu` et `examples/04-vhdl-testbench-xsim`) :

```
examples/03-fifo/
├── README.md
├── rtl/
│   └── fifo_sync.vhd   DUT : FIFO synchrone générique, un processus horlogé
└── tb/
    ├── Makefile        analyse GHDL + simulation cocotb (SIM=ghdl, VHDL-2008)
    └── test_fifo.py    testbench cocotb 2.x (pilote + 7 tests)
```

| Fichier              | Rôle                                                     |
|----------------------|----------------------------------------------------------|
| `rtl/fifo_sync.vhd`  | DUT : FIFO synchrone générique, un seul processus horlogé |
| `tb/test_fifo.py`    | Testbench cocotb 2.x (pilote + 7 tests)                  |
| `tb/Makefile`        | Analyse GHDL + simulation cocotb (`SIM=ghdl`, VHDL-2008)  |

Pour un DUT **Verilog**, voir les modèles réutilisables
`templates/cocotb/Makefile.icarus` et `templates/cocotb/Makefile.verilator`.

## Exécution

```bash
cd examples/03-fifo/tb
make          # analyse GHDL (--std=08) + simulation cocotb
make clean    # supprime sim_build/ et results.xml
```

Prérequis : GHDL (testé avec 6.0.0, backend mcode) et cocotb 2.0.1 dans le
`PATH`. Résultat réellement obtenu sur la machine de référence
(2026-09-17, GHDL 6.0.0 + cocotb 2.0.1) :

```
** TESTS=7 PASS=7 FAIL=0 SKIP=0                                21025.01           0.05    400180.01  **
```

## Interface

```vhdl
generic (
  C_WDATA   : positive := 8;                    -- largeur d'un mot (bits)
  C_LEVEL_W : positive := 4;                    -- largeur binaire de o_level
  C_DEPTH   : positive := 2 ** (C_LEVEL_W - 1)  -- profondeur, puissance de 2
);
port (
  i_clk, i_rst, i_wr_en, i_rd_en : in  std_logic;
  i_data  : in  std_logic_vector(C_WDATA-1 downto 0);
  o_data  : out std_logic_vector(C_WDATA-1 downto 0);
  o_full  : out std_logic;
  o_empty : out std_logic;
  o_level : out std_logic_vector(C_LEVEL_W-1 downto 0)
);
```

- **Horloge unique**, toutes les sorties enregistrées ou dérivées du compteur
  de remplissage : aucun domaine d'horloge croisé, aucune logique asynchrone.
- **Reset synchrone actif haut** (`i_rst` échantillonné sur front montant),
  conformément à la convention du dépôt : un seul style de reset par design.
- **`o_level`** est le nombre de mots stockés, sur `C_LEVEL_W` bits.
  La VHDL standard n'a pas de fonction `log2` ; la largeur du port ne peut donc
  pas être calculée dans la clause de ports et doit être fournie par un
  générique. `C_LEVEL_W` et `C_DEPTH` sont vérifiés à l'élaboration : une
  profondeur non puissance de 2, ou un `C_LEVEL_W` trop petit, provoque une
  erreur explicite au lieu d'une troncature silencieuse :

  ```
  fifo_sync : C_LEVEL_W=4 est trop petit pour C_DEPTH=16 ; utilisez C_LEVEL_W >= 5
  ```

  Règle : `C_LEVEL_W >= log2(C_DEPTH) + 1`. Pour une profondeur de 8 mots, le
  défaut `C_LEVEL_W=4` convient.

## Comportement

| Situation                                   | Effet                                                    |
|---------------------------------------------|----------------------------------------------------------|
| `i_wr_en` et FIFO non pleine                | mot écrit, `o_level` +1, pointeur d'écriture +1          |
| `i_wr_en` et `o_full=1`                     | **écriture ignorée** (verrou dur, rien n'est écrasé)     |
| `i_rd_en` et FIFO non vide                  | `o_data` reçoit le mot, `o_level` -1, pointeur lecture +1|
| `i_rd_en` et `o_empty=1`                    | **lecture ignorée** (pointeur intact, `o_data` conservé)|
| `i_wr_en` et `i_rd_en`, FIFO ni pleine ni vide | les deux acceptées, `o_level` inchangé                |
| `i_wr_en` et `i_rd_en`, FIFO pleine         | seule la lecture est acceptée, l'écriture est refusée    |
| `i_rst=1`                                   | pointeurs, compteur et `o_data` remis à zéro, `o_empty=1`|

`o_full` et `o_empty` sont des **verrous durs** : ils bloquent respectivement
l'écriture et la lecture. C'est le comportement des FIFO « standard » Xilinx
(le drapeau `FULL` refuse l'écriture), donc celui qui se transpose le plus
directement vers une IP de FIFO de la bibliothèque du fabricant.

## Choix de lecture : pas de *first word fall through*

La FIFO fonctionne en mode **standard** (`FIFO_FIRST_WORD_FALL_THROUGH = false`) :

- `o_data` est un **registre chargé lors d'une lecture réussie** ; il n'est mis
  à jour qu'au front où `i_rd_en` est accepté, et conserve ensuite le dernier mot
  lu. Le premier mot ne « tombe » donc pas sur la sortie avant la lecture ;
- la latence lecture → donnée valide est de ce fait de un cycle ;
- ce qui a motivé le choix : en mode *first word fall through*, `o_data` devrait
  être piloté de façon combinatoire par `mem(rd_ptr)`, ce qui sort la mémoire du
  chemin enregistré (lecture asynchrone, RAM distribuée, chemin combinatoire plus
  long, fermeture temporelle plus délicate) et rend la sortie sensible aux
  glitches. Le mode enregistré garde une seule logique séquentielle, un chemin
  mémoire → registre, et correspond au mode « Standard » de l'IP FIFO Xilinx.

Conséquence pratique : `o_data` n'est **significatif qu'après une lecture
acceptée**. Un test qui lit sur `i_rd_en` sans vérifier `o_empty=0` comparera des
données périmées — c'est pourquoi le testbench ne compare `o_data` que lorsque la
lecture a été acceptée.

## Protocole du testbench (VHDL / VHPI)

```
front descendant ...  entrées appliquées  →  front montant (enregistrement)
   →  front descendant suivant : sorties échantillonnées
```

- les entrées sont posées juste **après un front descendant** et maintenues
  jusqu'au front descendant suivant ;
- les sorties sont lues **au front descendant** qui suit le front montant ayant
  enregistré ces entrées : une demi-période plus tard, tous les cycles delta sont
  terminés et les sorties (registres + `o_full`/`o_empty`/`o_level` dérivés du
  compteur) sont stables ;
- le reset est asservi à la même règle : les entrées sont positionnées **avant**
  le relâchement de `i_rst`, et l'état vide est échantillonné pendant que le
  reset est encore actif ;
- `ReadOnly` n'est pas utilisé : après un réveil sur `ReadOnly`, toute écriture
  exige d'avancer d'un événement (phase ReadOnly non écrivable). L'échantillonnage
  au front descendant évite cette contrainte et lit des valeurs déjà stabilisées.

## Tests (`test_fifo.py`, 7 tests)

| Test | Ce qui est vérifié |
|------|--------------------|
| `test_reset_etat_vide` | après reset : `o_empty=1`, `o_full=0`, `o_level=0` |
| `test_remplissage_jusqu_a_full` | `o_level` suit chaque écriture, `o_full` monte au dernier mot |
| `test_debordement_ignore` | 3 écritures sur FIFO pleine non acceptées : niveau inchangé, le mot refusé n'apparaît jamais à la lecture |
| `test_vidage_et_ordre_fifo` | les mots ressortent dans l'ordre d'entrée, `o_level` décroît, `o_empty` monte au dernier mot, `o_data` conserve le dernier mot lu |
| `test_lecture_quand_vide` | 4 lectures à vide ignorées, puis l'ordre reste intact (pointeur de lecture non déplacé) |
| `test_ecriture_et_lecture_simultanees` | cas 1 : une entrée + une sortie, niveau inchangé ; cas 2 : pleine, écriture refusée |
| `test_aleatoire_modele_deque` | 2000 cycles aléatoires à **graine fixe** (20260917), modèle de référence `collections.deque`, comparaison de **chaque** valeur lue + `o_level`/`o_full`/`o_empty` à chaque cycle, puis vidage final |

Le test aléatoire tire `i_wr_en` et `i_rd_en` indépendamment (50 % chacun), ce qui
couvre les écritures sur FIFO pleine et les lectures à vide ; les compteurs de
fin de test affichent la couverture réellement obtenue :

```
graine=20260917 cycles=2000 ecritures=914 lectures=907 debordements_ignores=24 lectures_a_vide_ignorees=118
```

Reproductibilité : la graine du test est une constante du module
(`RANDOM_SEED = 20260917`) et un `random.Random` dédié est utilisé, donc le
résultat ne dépend pas de la graine globale de cocotb. En complément, le
Makefile exporte `COCOTB_RANDOM_SEED ?= 1234` (convention du dépôt, cf.
`AGENTS.md`), ce qui fixe aussi la graine de cocotb lui-même. Le test déduit
`C_WDATA`/`C_DEPTH` des largeurs de ports du DUT, il suit donc automatiquement
un changement de génériques.

## Valeur du test (vérifié par mutation)

Le testbench a été confronté à des DUT volontairement erronés (copies de travail,
hors dépôt) pour vérifier qu'il n'est pas complaisant :

| Mutation du DUT | Résultat |
|-----------------|----------|
| `v_wr_ok := (i_wr_en = '1')` (écriture acceptée même pleine) | 5 tests sur 7 échouent |
| pointeur de lecture qui n'avance pas | 5 tests sur 7 échouent |
| `C_DEPTH := 12` (non puissance de 2) | erreur d'élaboration : `fifo_sync : C_DEPTH doit etre une puissance de 2 (C_DEPTH=12)` |
| `C_DEPTH := 16` avec `C_LEVEL_W := 4` | erreur d'élaboration : `fifo_sync : C_LEVEL_W=4 est trop petit pour C_DEPTH=16 ; utilisez C_LEVEL_W >= 5` |

Les deux premières lignes et la troisième ont été rejouées le 2026-09-17 sur
GHDL 6.0.0 : la mutation de l'écriture donne bien `TESTS=7 PASS=2 FAIL=5`, et
`C_DEPTH := 12` provoque `(assertion failure): fifo_sync : C_DEPTH doit etre
une puissance de 2 (C_DEPTH=12)` avec un code de retour `make` non nul (2) : la
commande `make` est donc un juge fiable, pas un simple rapport.

## Note sur la synthèse

L'exemple n'a pas été synthétisé (Vivado n'est pas disponible sur la machine de
référence) : seul le comportement simulé est garanti ici. Le code est écrit de
façon synthétisable : un seul processus horlogé, pas de `wait`, mémoire décrite
par un tableau inféré en RAM simple port (un port écriture, un port lecture),
sorties enregistrées ou sorties de comparateurs.
