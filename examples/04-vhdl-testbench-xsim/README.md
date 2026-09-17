# Exemple 04 — Valider un design avec un testbench VHDL pur sous XSim

> **But** : montrer qu'on peut vérifier un design *sans cocotb*, avec un
> testbench **VHDL auto-vérifiant** qui ne dépend d'aucune bibliothèque de
> vérification propriétaire (pas d'OSVVM, pas d'UVVM, pas de VIP) et qui
> s'exécute aussi bien sous **XSim** (Vivado Simulator) que sous **GHDL**.

Le même fichier `tb/tb_word_parity_counter.vhd` tourne sur les deux outils sans
modification : `std_logic_1164`, `numeric_std` et `math_real` suffisent.

---

## 1. Arborescence

```
examples/04-vhdl-testbench-xsim/
├── README.md                          <- ce fichier
├── rtl/
│   └── word_parity_counter.vhd        <- le DUT (générique, reset synchrone)
└── tb/
    ├── tb_word_parity_counter.vhd     <- testbench VHDL pur, auto-vérifiant
    ├── run_sim.sh                     <- 4 commandes XSim en ligne de commande
    ├── xsim_sources.prj               <- liste de sources pour xvhdl/xelab -prj
    └── xsim_wave.tcl                  <- add_wave / run all / quit (facultatif)

templates/vivado/
└── simulate.tcl                       <- équivalent "projet" : launch_simulation
                                          / run all / close_simulation
```

---

## 2. Le DUT : `word_parity_counter`

Générateur de parité + compteur de mots, pipeline à 1 étage.

| Port | Sens | Description |
|---|---|---|
| `i_clk` | in | horloge unique |
| `i_rst` | in | **reset synchrone actif haut** |
| `i_valid` | in | qualifie `i_data` |
| `i_data` | in | mot de `C_DATA_WIDTH` bits |
| `o_valid` | out | `i_valid` retardé d'un cycle |
| `o_parity` | out | parité du mot mémorisé (paire ou impaire) |
| `o_words` | out | nombre de mots déjà présentés (16 bits) |

| Génératique | Défaut | Rôle |
|---|---|---|
| `C_DATA_WIDTH` | 8 | largeur des mots d'entrée |
| `C_ODD_PARITY` | `false` | `false` = parité paire, `true` = parité impaire |

Chronogramme (latence = 1 cycle) :

```
              __    __    __    __    __    __
i_clk      __|  |__|  |__|  |__|  |__|  |__|  |__
i_valid    ___/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\_________________
i_data     ===<  mot A  ><  mot B  >=============
                     ______________________
o_valid    ________/                      \______
o_parity   ========<  par(A) ><  par(B)  >=======
o_words    ====== 0 <    1    ><    2    >=======
```

`o_words` est incrémenté à chaque front où `o_valid` était actif au cycle
précédent : il compte les mots **déjà** présentés, donc un cycle après la
pulsion `o_valid` correspondante.

---

## 3. Le testbench : ce qui est vérifié

| # | Test | Détail |
|---|---|---|
| 1 | Reset synchrone | sorties à zéro pendant `i_rst='1'` ; **`i_rst` armé entre deux fronts ne change rien** (preuve que le reset est bien synchrone) |
| 1b | Latence | aucune sortie ne bouge avant le front ; `o_valid='1'` un cycle après `i_valid` ; `o_words` décalé d'un cycle |
| 3 | **Exhaustif** | les `2**C_DATA_WIDTH` (= 256) mots sont balayés, parité vérifiée pour les deux génératiques (paire et impaire) |
| 4 | Trous dans `i_valid` | le compteur ne compte que les mots réellement valides, puis repart |
| 4.5 | Table de référence figée | la fonction de parité du modèle est elle-même validée par la constante `C_REF_PARITY_LOW = "0110100110010110"` (parité paire de 0 à 15) |
| 5 | **Aléatoire reproductible** | 500 cycles avec `i_valid` et `i_data` aléatoires, via `uniform(seed1, seed2, r)` de `ieee.math_real` et **graines fixes** (`C_SEED_VALID=12345`, `C_SEED_DATA=6789`) |
| 6 | Reset en plein trafic | remise à zéro du compteur et de la parité, puis reprise propre |

Mécanismes utilisés :

* **modèle de référence** tenu dans la procédure `cycle()` (état mémorisé,
  latence, compteur) et comparé aux sorties des **deux** instances du DUT à
  chaque cycle ;
* **procédure d'assertion** `check(cond, msg, err, nb)` : incrémente un
  compteur d'erreurs et émet `report "ECHEC : ..." severity error` ;
* **garde-fou** `p_watchdog` : erreur fatale si plus de `C_MAX_CYCLES` cycles ;
* fin de test : `report "ALL TESTS PASSED" severity note` **si et seulement si**
  `v_errors = 0`, sinon `report "TESTS FAILED : N erreur(s)" severity failure` ;
* **aucun fichier de sortie optionnel** : pas de VCD/FST/GHW, pas de fichier de
  référence externe — le testbench est auto-verifiant et ne lit rien sur
  disque. Le chronogramme est laissé au simulateur (`xsim_wave.tcl` sous XSim,
  `--wave=` en option sous GHDL) ;
* l'horloge est **coupée en fin de test** (`s_clk_en`) : plus aucun événement
  programmé, donc `xsim -R` (*run all*) et GHDL se terminent d'eux-mêmes, sans
  `--stop-time` ni `std.env.finish`.

---

## 4. Lancer la simulation sous XSim (Vivado)

XSim s'utilise en trois étapes : **analyse → élaboration → exécution**.

### 4.1 Flux explicite (4 commandes) — c'est ce que fait `tb/run_sim.sh`

```bash
cd examples/04-vhdl-testbench-xsim/tb

# 1) analyse VHDL du design
xvhdl -2008 -work work ../rtl/word_parity_counter.vhd

# 2) analyse VHDL du testbench
xvhdl -2008 -work work tb_word_parity_counter.vhd

# 3) élaboration du snapshot de simulation (debug indispensable pour les ondes)
xelab -debug typical -s tb_sim work.tb_word_parity_counter

# 4) exécution : -R = run all puis quit (le testbench coupe son horloge)
xsim tb_sim -R
```

### 4.2 Flux par fichier de projet (3 commandes) — `tb/xsim_sources.prj`

```bash
cd examples/04-vhdl-testbench-xsim/tb

xvhdl -prj xsim_sources.prj
xelab -prj xsim_sources.prj -debug typical -s tb_sim work.tb_word_parity_counter
xsim tb_sim -R
```

`xsim_sources.prj` (syntaxe UG900 « Project File (.prj) Syntax ») :

```
vhdl2008 work ../rtl/word_parity_counter.vhd
vhdl2008 work tb_word_parity_counter.vhd
```

### 4.3 Script fourni

```bash
./run_sim.sh              # flux explicite (4 commandes) + vérification du PASS
./run_sim.sh --prj        # flux par fichier de projet
./run_sim.sh --dry-run    # affiche les commandes sans les exécuter
./run_sim.sh clean        # supprime xsim.dir/, *.log, *.jou, *.cf, *.vcd, ...
```

`run_sim.sh` surcharge les outils par variable d'environnement, ce qui permet de
pointer une installation Vivado précise :

```bash
XVHDL=/tools/Xilinx/Vivado/2023.2/bin/xvhdl \
XELAB=/tools/Xilinx/Vivado/2023.2/bin/xelab \
XSIM=/tools/Xilinx/Vivado/2023.2/bin/xsim ./run_sim.sh
```

À la fin, le script refuse de conclure « OK » sans avoir trouvé `ALL TESTS PASSED`
dans la sortie de `xsim` (code de retour 0 si succès, 1 sinon).

### 4.4 Ondes (facultatif)

```bash
xelab -debug typical -s tb_sim work.tb_word_parity_counter   # -debug obligatoire
xsim tb_sim -gui -t xsim_wave.tcl                            # GUI + ondes
xsim tb_sim -t xsim_wave.tcl                                 # batch : génère le .wdb
```

### 4.5 Depuis un projet Vivado : `templates/vivado/simulate.tcl`

```bash
vivado -mode batch -source templates/vivado/simulate.tcl
vivado -mode batch -source templates/vivado/simulate.tcl -tclargs chemin/mon_projet.xpr
```

Le script enchaîne `launch_simulation` → `run all` → `close_simulation`, lit le
compteur `s_errors` du testbench avec `get_value`, puis vérifie la présence de
`ALL TESTS PASSED` dans `<projet>.sim/<fileset>/<mode>/xsim/simulate.log`
(code de retour 1 si absent — `exit 1` dans un script batch Vivado est bien
propagé au shell).

> ✅ **MISE À JOUR (vérification ultérieure, pendant l'écriture du dépôt)** :
> Vivado 2025.2 **était** installé sur la machine (`~/vivado/2025.2/Vivado`), mais
> pas dans le `PATH` au moment où cet exemple a été écrit. Le flux XSim a été
> **réellement exécuté** depuis, avec les résultats suivants :
> ```
> ./run_sim.sh          -> [1/4]..[4/4] OK, "ALL TESTS PASSED" trouvé, exit 0
> ./run_sim.sh --prj    -> flux 3 commandes OK, "ALL TESTS PASSED", exit 0
> ```
> Verdict XSim : `*** 4695 verifications effectuees, 0 erreur(s) *** / ALL TESTS
> PASSED` — identique au verdict GHDL, au même instant de simulation (7796 ns).
> `templates/vivado/simulate.tcl` n'a en revanche toujours pas été lancé dans un
> projet Vivado réel (il faudrait un projet avec un testbench déclaré) : sa
> logique a seulement été testée avec des commandes simulées.
> Les commandes XSim ci-dessus sont cohérentes avec UG900 (`xvhdl -2008/-work/-prj`,
> `xelab -debug/-s/-prj`, `xsim -R/-t/-gui`) et ont donc été validées à l'exécution
> pour les options utilisées par `run_sim.sh`.
> Le testbench a également été exécuté sous **GHDL** (§5) — deux simulateurs
> indépendants, même verdict.

---

## 5. Vérification réellement effectuée : GHDL 6.0.0

XSim n'étant pas disponible, le testbench a été compilé et exécuté avec GHDL
6.0.0 (backend mcode) — mêmes sources, aucune modification.

```bash
/tmp/ghdl_tool/bin/ghdl -a --std=08 ../rtl/word_parity_counter.vhd
/tmp/ghdl_tool/bin/ghdl -a --std=08 tb_word_parity_counter.vhd
/tmp/ghdl_tool/bin/ghdl -m --std=08 tb_word_parity_counter
/tmp/ghdl_tool/bin/ghdl -r --std=08 tb_word_parity_counter --assert-level=error --stop-time=100us
```

Résultat (dernières lignes réelles) :

```
tb_word_parity_counter.vhd:398:5:@2716ns:(report note): -- (5) 500 cycles aleatoires (graines 12345/6789) --
tb_word_parity_counter.vhd:419:5:@7716ns:(report note): -- (6) reset en plein trafic --
tb_word_parity_counter.vhd:439:5:@7746ns:(report note): -- (6b) reprise apres reset --
tb_word_parity_counter.vhd:451:5:@7796ns:(report note): *** 4695 verifications effectuees, 0 erreur(s) ***
tb_word_parity_counter.vhd:455:7:@7796ns:(report note): ALL TESTS PASSED
```

Contrôles complémentaires :

* **terminaison naturelle** : `ghdl -r --std=08 tb_word_parity_counter`
  (sans `--stop-time`) s'arrête tout seul à `7796 ns`, ce qui valide la
  stratégie « horloge coupée » utilisée pour que `xsim -R` termine ;
* **VHDL-93** : les deux fichiers compilent aussi avec `--std=93`
  (`vhdl` ou `vhdl2008` dans le `.prj` sont donc équivalents) ;
* **le testbench détecte bien les erreurs** : en mutant le DUT (bit de poids
  faible ignoré dans l'arbre XOR), GHDL remonte **828 messages
  `(report error): ECHEC : ...`**, la simulation échoue
  (`ghdl:error: simulation failed`) et `ALL TESTS PASSED` **n'est pas** émis.

Exécution sous GHDL (équivalent libre, sans Vivado) :

```bash
cd examples/04-vhdl-testbench-xsim/tb
ghdl -a --std=08 ../rtl/word_parity_counter.vhd
ghdl -a --std=08 tb_word_parity_counter.vhd
ghdl -m --std=08 tb_word_parity_counter
ghdl -r --std=08 tb_word_parity_counter --assert-level=error --stop-time=100us
```

---

## 6. XSim vs cocotb + GHDL : quand utiliser l'un ou l'autre

| Critère | **XSim + testbench VHDL pur** (cet exemple) | **cocotb + GHDL** (flux Python) |
|---|---|---|
| Langage du stimulus | VHDL (IEEE 1076) | Python (coroutines `async/await`) |
| Bibliothèques requises | aucune : `std_logic_1164`, `numeric_std`, `math_real` | `cocotb`, `pytest`, plus Python + GHDL |
| Licence / installation | Vivado (licence gratuite WebPACK pour les petits FPGA, sinon licence payante) | 100 % libre (GPL pour GHDL, cocotb en BSD) |
| Fonctionne sans Vivado | non (c'est le simulateur de Vivado) | oui — utile en CI et sur machine sans licence |
| Temps de mise en place | quelques minutes : un fichier `.vhd` + 4 commandes | `pip install cocotb`, `Makefile`, structure de projet |
| Simulation post-synthèse / post-implémentation | **oui** (`launch_simulation -mode post-synthesis/post-implementation`, timing, SDF, .xdc) | non (RTL uniquement) |
| Signaux Xilinx (UNISIM, IP, BRAM, MIG) | **oui** (bibliothèques compilées avec Vivado) | nécessite des stubs ou une compilation des libs Xilinx |
| Debug / ondes | GUI intégré, `.wdb`, `add_wave`, configs `.wcfg` | GTKWave / Surfer sur un `.vcd`/`.fst` |
| Assertions dans le design | PSL (`--psl`), `report ... severity failure` | idem + coroutines Python |
| Contraintes aléatoires avancées, coverage functional | limité (à la main, `math_real`) | **fort** : `random`, `cocotb-coverage`, crv, scoreboards Python |
| Réutilisation / factorisation | génériques, procédures, packages VHDL, `for ... generate` | classes Python, réutilisable hors HDL, parallélisme facile |
| Reproductibilité | graines fixées dans les génériques du TB | `RANDOM_SEED` + `PYTHONHASHSEED` |
| Qui peut le relire | un concepteur HDL (tout est dans le langage du design) | un profil mixte logiciel/HDL |
| Convient pour | équipe HDL pure, validation fine du timing, design Xilinx (IP/BRAM/MMCM), simulation post-synthèse | CI rapide, gros environnements de vérification, génération automatique de vecteurs, reprise d'un flux logiciel |
| Limite | verbosité VHDL, pas de coverage automatique | RTL seulement, environnement Python à maintenir, plus lent à démarrer |

Règle pratique retenue dans ce dépôt :

* **testbench VHDL pur** quand le test est petit, qu'il doit être livré *avec*
  le design et rejoué par un concepteur HDL ou par Vivado (post-synthèse,
  timing, IP Xilinx) ;
* **cocotb + GHDL** quand le test est gros, piloté par des données, qu'il doit
  tourner en CI sans licence, ou quand on veut du coverage et des contraintes
  aléatoires évoluées ;
* les deux cohabitent très bien sur le même design : le DUT n'a aucune
  dépendance de simulation, et les deux environnements le pilotent par le même
  protocole d'entrée/sortie.

---

## 7. Pièges rencontrés / bonnes pratiques

* **Reset synchrone** : ne jamais tester un reset synchrone en le relâchant
  juste avant un front sans vérifier l'absence d'effet *entre* deux fronts —
  c'est ce que fait le test 1b.
* **Latence** : ne pas vérifier une sortie registrée dans le même delta que le
  front. Le testbench échantillonne `C_SETTLE` (1 ns) après le front montant.
* **`xelab -debug typical`** est obligatoire si vous voulez voir les signaux
  internes du testbench et du DUT dans les ondes ; sans lui, seuls les ports du
  top sont visibles.
* **`xsim -R` (run all)** ne termine que s'il n'y a plus d'événement : une
  horloge librement oscillante ferait tourner la simulation indéfiniment. D'où
  la coupure d'horloge en fin de test (ou, à défaut, `xsim.simulate.runtime`
  fixé à une durée).
* **Un testbench « sans assertion » ne vaut rien** : ici tout échec passe par
  `report ... severity error` et le code de sortie du simulateur (ou
  `--assert-level=error` sous GHDL) fait échouer la CI.
* Les fichiers générés (`xsim.dir/`, `*.log`, `*.jou`, `*.cf`, `*.vcd`,
  `work-obj*.cf`) sont ignorés par le `.gitignore` du dépôt et supprimés par
  `./run_sim.sh clean`.
