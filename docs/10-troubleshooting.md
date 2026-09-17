# Troubleshooting — catalogue d'erreurs réelles

Toutes les erreurs de la colonne « message » ont été **produites pour de vrai** sur
Vivado v2025.2 (lin64) pendant l'écriture de ce dépôt : elles sont copiées telles
quelles. Utilise ce fichier comme table de diagnostic : cherche le code de message
entre crochets (`[Synth 8-36]`, `[Common 17-69]`…) dans le log, puis applique la
correction.

Rappel de lecture des logs :
```bash
grep -nE "^(ERROR|CRITICAL WARNING):" vivado.log                       # console
grep -nE "^(ERROR|CRITICAL WARNING):" <prj>.runs/impl_1/runme.log       # un run
```
Le serveur MCP fait ce filtrage tout seul (`job_log`, `report_summary`).

---

## 1. Avant le build

| Message (authentique) | Cause | Correctif |
|---|---|---|
| `ERROR: [Coretcl 2-106] Specified part could not be found.` | nom de partie inexistant ou famille non installée | `get_parts xc7z020*` liste ce qui est installé ; vérifier la casse et le suffixe de vitesse (`xc7z020clg400-1`) |
| `ERROR: [Vivado 12-172] File or Directory '/chemin/x.vhd' does not exist` | `add_files` sur un chemin faux ou relatif au mauvais dossier | `pwd` dans le script, puis `file normalize` ; lister avec `glob -nocomplain rtl/*.vhd` avant d'ajouter |
| `ERROR: [Common 17-69] Command failed: Run 'synth_1' needs to be reset before launching. The run can be reset using the Tcl command 'reset_run synth_1'.` | on relance un run déjà terminé | `reset_run synth_1` puis `launch_runs` — ou réutiliser le run existant (voir `templates/vivado/build.tcl`, procédure `run_or_reuse`) |
| `ERROR: [Common 17-161] Invalid option value '' specified for 'object'.` | commande appelée sans design ouvert (ex. `get_property ... [current_project]` avant `create_project`) | ordonner les commandes : projet → sources → contraintes → top → runs |
| `ERROR: [Common 17-53] User Exception: No open design. Please open an elaborated, synthesized or implemented design before executing this command.` | `report_*` sans `open_run`/`open_design` | `open_run impl_1` (ou `synth_1`) avant tout rapport |
| `ERROR: [Common 17-37] Directory in which file timing.rpt is to be written does not exist [/chemin/reports]` | Vivado **ne crée pas** le dossier de destination | `file mkdir reports` avant `report_timing_summary -file ...` |
| `set_property top entite_qui_nexiste_pas` ne renvoie **aucune** erreur | le nom du top n'est pas validé à ce moment | l'erreur n'arrive qu'à la synthèse : toujours lancer une synthèse avant de dire qu'un projet est bon |

## 2. Synthèse (VHDL)

| Message | Cause | Correctif |
|---|---|---|
| `ERROR: [Synth 8-36] 'o_q' is not declared` | signal/port utilisé mais non déclaré (souvent oublié dans la liste `port`) | déclarer le port ou le signal, ou corriger la faute de frappe |
| `ERROR: [Synth 8-2716] syntax error near 'process'` | `end if;`/`end loop;` manquant, ou bloc non fermé dans le process précédent | vérifier l'imbrication `if ... end if;` et `process ... end process;` |
| `ERROR: [Synth 8-5826] no such design unit 'bloc_inexistant' in library 'work'` | entité instanciée absente du projet ou non compilée (mauvais ordre) | ajouter le fichier (`add_files`) ; l'ordre de compilation est calculé par `update_compile_order -fileset sources_1` |
| `ERROR: [Synth 8-12189] Failed to read vhdl '/chemin/fichier.vhd'` | erreur de lecture : syntaxe VHDL 2008 alors que le projet est en VHDL-93, ou encodage | `set_property target_language VHDL` + `read_vhdl -vhdl2008`, ou passer au std attendu |
| `ERROR: [Synth 8-285] failed synthesizing module 'wrapper'` | message de synthèse : c'est un **agrégat**, le vrai détail est dans la ligne d'erreur précédente | remonter le log de quelques lignes |
| `ERROR: [Common 17-69] Command failed: Vivado Synthesis failed` | idem : échec du run, cause détaillée dans `runme.log` | lire `grep -n "ERROR" <prj>.runs/synth_1/runme.log` |
| `WARNING: [Synth 8-327] inferring latch for variable ...` | branche non couverte dans un process combinatoire | affecter une valeur par défaut en tête de process |

## 3. Implémentation et bitstream

| Message | Cause | Correctif |
|---|---|---|
| `ERROR: [DRC NSTD-1] Unspecified I/O Standard: N out of N logical ports use I/O standard (IOSTANDARD) value 'DEFAULT'` | aucun `IOSTANDARD` sur les ports | contraindre les E/S : `set_property IOSTANDARD LVCMOS33 [get_ports ...]` |
| `ERROR: [DRC UCIO-1] Unconstrained Logical Port: N out of N logical ports have no user assigned specific location constraint (LOC)` | aucun `PACKAGE_PIN` | donner les broches du board réel, ou valider la logique sans carte (voir juste en dessous) |
| `ERROR: [Vivado 12-1345] Error(s) found during DRC. Bitgen not run.` | conséquence des DRC ci-dessus | corriger les DRC, ou abaisser leur sévérité |
| `ERROR: [Common 17-39] 'write_bitstream' failed due to earlier errors.` | idem | idem |
| `ERROR: [Vivado 12-13638] Failed runs(s) : 'impl_1'` | le run est marqué en échec après coup | `get_property STATUS [get_runs impl_1]` pour le détail |
| `ERROR: [Common 17-39] 'wait_on_runs' failed due to earlier errors.` | l'échec remonte via `wait_on_run` | traiter la cause réelle (DRC ou timing) |

### Valider la logique sans carte

Deux options, dans cet ordre de préférence :

1. **Contraindre les E/S** avec le brochage d'un vrai board (recommandé : c'est ce
   qui produira un bitstream utile).
2. **Abaisser la sévérité des deux DRC**, uniquement pour vérifier que la logique
   se place et se route. Vivado l'indique lui-même dans le message d'erreur, et
   précise que pour un run il faut un **pre-hook** Tcl :

```tcl
# fichier abaisse_drc.tcl
set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
set_property SEVERITY {Warning} [get_drc_checks UCIO-1]
```
```tcl
set_property STEPS.WRITE_BITSTREAM.TCL.PRE abaisse_drc.tcl [get_runs impl_1]
```

Vérifié : avec ce pre-hook, un compteur 24 bits sans brochage a produit
`impl_1 : PROGRESS=100% STATUS=write_bitstream Complete!` et un `top.bit` de 4 Mo
(référence : WNS = 7.317 ns à 100 MHz sur xc7z020clg400-1).
`templates/vivado/build.tcl --allow-unconstrained 1` applique exactement ceci.

## 4. Timing

| Constat dans le rapport | Cause | Correctif |
|---|---|---|
| `There are no user specified timing constraints.` et aucun tableau WNS/TNS | aucune horloge déclarée : rien n'est vérifié | `create_clock -period 10.000 [get_ports i_clk]` dans un `.xdc` — sans cela, un design « passe » sans rien prouver |
| `WNS(ns)` négatif, `TNS Failing Endpoints` > 0 | chemins trop longs | pipeline, réduire la logique combinatoire, ou baisser la fréquence annoncée (voir `docs/07-timing-closure.md`) |
| `report_timing_summary` vide mais design implémenté | design ouvert avec `open_run` sur le mauvais run | relire le bon run (`open_run impl_1`) ou vérifier `get_property STATUS [get_runs impl_1]` |

## 5. Simulation

| Message | Cause | Correctif |
|---|---|---|
| cocotb : `Couldn't find makefile for simulator: "xsim"! Available simulators: activehdl cvc dsim ghdl icarus ius modelsim nvc questa riviera vcs verilator xcelium` | **cocotb ne supporte pas XSim** (vérifié dans cocotb 2.0.1) | simuler avec GHDL/Icarus/Verilator/Questa, ou écrire un testbench VHDL pur pour XSim (`examples/04-vhdl-testbench-xsim`) |
| GHDL : `cannot find entity or configuration mon_module` | `--std=08` manquant à l'**exécution**, top mal orthographié, ou bibliothèque dans un autre dossier que le cwd du test | `GHDL_ARGS += --std=08` (analyse **et** run) ; avec l'API Python, `test_args=["--std=08"]` (GHDL ignore `elab_args`) ; `build_dir` = `test_dir` |
| cocotb : `RuntimeError: Attempting settings a value during the ReadOnly phase.` | écriture d'un signal juste après `await ReadOnly()` | avancer d'un événement (`await FallingEdge(...)`) avant d'écrire |
| cocotb : valeur lue décalée d'un cycle | lecture juste après `RisingEdge()` (les sorties du DUT changent après le front) ou entrées posées après la sortie de reset | échantillonner sur front descendant ou avec `ReadOnly()` ; **poser les entrées avant de relâcher le reset** |
| cocotb : `MODULE is deprecated, please use COCOTB_TEST_MODULES` | nom de variable cocotb 1.x | `COCOTB_TEST_MODULES = ...` (idem `COCOTB_TOPLEVEL`) |
| Questa : `Failure to obtain a Verilog simulation license. Unable to checkout 'intelqsimstarter' license` + `Invalid host. (<chemin>/license.dat)` | licence gratuite liée à une autre machine (`HOSTID=` dans le fichier ≠ MAC du PC) | re-hoster la licence (site Intel, MAC de cette machine), ou passer à XSim/GHDL. `vsim -version` répond malgré tout : seul le checkout échoue |
| cocotb 2.x : `DeprecationWarning: logic_array.integer getter is deprecated. Use logic_array.to_unsigned() instead` | accès `sig.value.integer` / `sig.value.binstr` (API 1.x conservée en 2.x mais dépréciée) | `sig.value.to_unsigned()` / `to_signed()` / `str(sig.value)` ; `int(sig.value)` reste correct |
| cocotb+GHDL : `make WAVES=1` ne produit **aucun** fichier d'ondes, et sans erreur | le Makefile GHDL de cocotb 2.0 n'ajoute jamais `--wave` à la commande | utiliser le lanceur Python : `WAVES=1 python3 run_tests.py` → `<top>.ghw` (vérifié : 6558 octets) ; `make WAVES=1` reste valable avec Questa/Riviera |
| Testbench VHDL : valeur lue systématiquement un cycle trop tôt | lecture dans les cycles **delta** du front (`wait until rising_edge(clk)` puis lecture : on lit encore l'ancienne valeur, même avec `wait for 0 ns`) | échantillonner au milieu de la période : `wait until rising_edge(clk); wait for C_PERIODE/4;` — mesuré sur GHDL **et** XSim, voir `templates/vhdl/README.md` |
| Testbench VHDL : `type of a shared variable must be a protected type` | `shared variable` en VHDL-2008 | variables locales au process + procédure imbriquée |
| Testbench VHDL : `unexpected token 'procedure' in a concurrent statement list` | procédure déclarée après le `begin` de l'architecture | la placer dans la partie déclarative (architecture ou process) |
| Testbench VHDL : `'others' choice not allowed for an aggregate in this context` | `return (others => '0');` dans une fonction | passer par une variable locale |
| xsim : `ERROR: [Common 17-206]` / simulation qui ne se termine jamais | testbench sans condition d'arrêt | terminer par `std.env.finish` (VHDL-2008) ou un `stop-time` explicite |

## 6. Tcl lui-même

| Message | Cause | Correctif |
|---|---|---|
| `missing close-brace: possible unbalanced brace in comment` | **à l'intérieur d'un bloc `{...}`, Tcl compte les accolades même dans un commentaire ou une chaîne** | échapper toute accolade littérale : `"\{ "`, `"\}"` — ou l'éviter dans les commentaires |
| `can't read "to_step:+, jusqu'a $to_step": no such variable` | syntaxe shell `${var:+alt}` utilisée dans un script Tcl : elle n'existe pas en Tcl | `if {$to_step ne ""} { ... } else { ... }` |
| `wrong # args: should be "proc name args body"` | extraction/écriture d'un `proc` mal formé (liste d'arguments et corps confondus) | vérifier `proc nom {args} {corps}` |
| doute sur la validité d'un script | — | `tclsh templates/project/scripts/check_tcl_syntax.tcl fichier.tcl` (ou `python3 scripts/check_tcl.py`) : contrôle `info complete` + refus par le compilateur Tcl |

## 7. Vitis

| Message / symptôme | Cause | Correctif |
|---|---|---|
| `xsct` introuvable | Vitis ≤ 2023.1 → `xsct` ; depuis 2023.2 la voie recommandée est `vitis -s script.py` | vérifier la version : `vitis --version` (2025.2 : `vitis -s <python_script>`, `xsct` existe encore mais est déprécié) |
| le `.xsa` manque au moment de créer la plateforme | export non fait côté Vivado | `write_hw_platform -fixed -include_bit -force -file export/design.xsa` (voir `templates/vivado/export_xsa.tcl`) ; `write_hw_def` **n'existe plus** en 2025.2 |
| adresses de registres inconnues | adresses tapées à la main | les lire dans `xparameters.h` du BSP, généré depuis l'XSA |
| carte non vue en JTAG | câble/udev/licence | `lsusb | grep -i xilinx` ; installer les règles udev du câble ; `hw_server` lancé ? |

## 8. Réflexes d'agent

1. Lire **le code du message** (`[Cat NNNN]`), pas seulement « ERROR ».
2. Aller au log du **run** concerné (`<prj>.runs/<run>/runme.log`) : la console est tronquée.
3. Corriger **une** cause, relancer l'étape la plus précoce possible (synthèse avant implémentation).
4. Après une implémentation, lire WNS/TNS **avant** de dire que ça passe.
