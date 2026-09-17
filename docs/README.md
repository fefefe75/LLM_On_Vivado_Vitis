# Documentation — index

Tout est en anglais, sauf indication contraire. Chaque affirmation technique sur
Vivado/Vitis est sourcée (docs AMD) ou **mesurée** sur Vivado 2025.2 — les faits
mesurés sont signalés comme tels, et ce qui n'a pas pu être vérifié est dit
explicitement.

| Fichier | Contenu | Statut de vérification |
|---|---|---|
| [`01-toolchain.md`](01-toolchain.md) | installation Linux, chemins, `settings64.sh`, licences, udev, outillage libre | outils détectés et versions réelles sur la machine de référence |
| [`02-vivado-tcl.md`](02-vivado-tcl.md) | project mode / non-project mode, scripts complets, logs, pièges | flux exécuté jusqu'au **bitstream** (2025.2) |
| [`03-simulation.md`](03-simulation.md) | XSim vs GHDL vs cocotb : commandes et limites | XSim et GHDL exécutés sur le même testbench, verdicts identiques |
| [`04-cocotb-recipes.md`](04-cocotb-recipes.md) | recettes de testbench, scoreboard, modèles de référence | exécutées (cocotb 2.0.1 + GHDL 6.0.0) |
| [`06-constraints-xdc.md`](06-constraints-xdc.md) | horloges, E/S, contraintes minimales | commandes vérifiées ; brochage dépendant du board |
| [`07-timing-closure.md`](07-timing-closure.md) | lire WNS/TNS/WHS/THS, fermer le timing | rapports réels analysés |
| [`08-vitis.md`](08-vitis.md) | Vitis classique (xsct) vs unifié (`vitis -s`), XSA, boot | `vitis -s`/`xsct` présents et testés en `--version` ; flux complet non exécuté (pas de carte Zynq) |
| [`10-troubleshooting.md`](10-troubleshooting.md) | **catalogue d'erreurs réelles** avec correctif | messages copiés depuis Vivado 2025.2 |
| [`11-agent-workflow.md`](11-agent-workflow.md) | comment un agent doit travailler (boucle, vérifications, rapports) | — |
| `_research/` | notes de recherche brutes (sources AMD/cocotb/MCP), matière première | sources citées, non intégralement relues |

Deux autres ensembles de documents :

- `../AGENTS.md` : contrat pour un agent qui travaille **dans ce dépôt**.
- `../mcp/README.md` : le serveur MCP (outils, sécurité, configuration client).

## Ce qui est prouvé, et comment

| Affirmation | Preuve |
|---|---|
| Le flux Vivado complet marche | `top.bit` de 4 Mo généré, `STATUS=write_bitstream Complete!`, WNS 7.317 ns |
| Les scripts Tcl sont valides | `tclsh … check_tcl_syntax.tcl` (8/8) + `scripts/check_tcl.py` (procédures exécutées) |
| Les testbenches passent | `make` sur les exemples : `tests/test_reports.py` et sorties citées |
| Le serveur MCP pilote un vrai Vivado | synthèse réelle via `vivado_run` (rc=0, 28,6 s), `job_log`, `report_summary` |
| Les analyseurs de rapports sont justes | fixtures **authentiques** dans `mcp/tests/fixtures/` (Vivado 2025.2) |

## Ce qui n'est pas prouvé

- La **programmation JTAG** (`program_hw_devices`) : aucune carte branchée.
- Le flux **Vitis complet** (plateforme + application + boot) : pas de cible Zynq.
- Un **timing en violation** (WNS < 0) : seule une fixture synthétique le couvre.
- Les **gros composants** (UltraScale+, Versal) : aucune licence de ce type ici.
