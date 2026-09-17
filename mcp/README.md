# Serveur MCP Vivado / Vitis — le pont entre un LLM et les outils FPGA

Un LLM ne peut pas piloter Vivado : il ne sait pas lancer un batch, suivre un run de
synthèse de 40 minutes, ni retrouver la seule ligne `ERROR:` utile dans un log de
30 000 lignes. Ce serveur MCP lui donne exactement ça, en 18 outils.

Il est **générique** : aucun projet particulier en dur, tout se configure par le
`--workspace`.

## Installation

```bash
cd LLM_On_Vivado_Vitis/mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # ou : .venv/bin/pip install -e .
.venv/bin/python -m vivado_mcp --workspace ~/mon_projet --selftest   # verification
```

`--selftest` affiche ce qui est réellement installé (Vivado, Vitis, xsct, GHDL, cocotb…)
sans ouvrir de transport. **Toujours commencer par là** quand quelque chose ne marche pas.

## Lancement

```bash
# Mode standard (stdio) : c'est le client MCP qui lance le serveur
.venv/bin/python -m vivado_mcp --workspace ~/mon_projet

# Mode HTTP (serveur partagé) — A NE JAMAIS EXPOSER sans authentification
.venv/bin/python -m vivado_mcp --workspace ~/mon_projet --transport http --port 8000
```

| Option | Effet |
|---|---|
| `--workspace` | racine du projet ; **toute** écriture y est confinée |
| `--tool-root` | racine AMD (`/tools/Xilinx`) si Vivado/Vitis n'est pas dans le `PATH` |
| `--transport` | `stdio` (défaut), `http`, `sse` |
| `--selftest` | n'ouvre rien, affiche l'environnement détecté |

Variables d'environnement : `FPGA_MCP_WORKSPACE`, `FPGA_MCP_RUNS_DIR`, `FPGA_MCP_TOOL_ROOT`,
`FPGA_MCP_TIMEOUT` (délai max par job, défaut 3600 s).

## Outils exposés

| Outil | Quand l'utiliser |
|---|---|
| `project_tree` | **en premier** : comprendre la structure du projet |
| `read_text_file` / `write_text_file` | lire un `.vhd`/`.xdc`, écrire un module ou un testbench |
| `grep` | retrouver une entité, un port, un signal, une erreur |
| `env_info` | savoir ce qui est réellement installé avant de prescrire un flux |
| `vivado_run` | lancer un script Tcl Vivado en batch (synthèse, impl., bitstream, rapports) |
| `vitis_run` | lancer `xsct` (≤ 2023.1) ou `vitis -s` (≥ 2023.2) |
| `cocotb_run` | lancer un testbench cocotb (`make`) — la vérification avant synthèse |
| `job_status` / `wait_for_job` / `job_list` | suivre un job (asynchrone, ne bloque jamais) |
| `job_log` | **diagnostic** : erreurs et avertissements extraits, lignes filtrées |
| `job_cancel` | arrêter un run parti en vrille |
| `report_summary` | analyser un rapport : messages par code, WNS/TNS/WHS/THS, ressources |
| `cocotb_results` | verdict PASS/FAIL par test (lecture de `results.xml`) |
| `project_status` | état d'un projet : runs, timing, bitstreams (ne lance rien) |
| `list_hw_targets` | cibles JTAG visibles |
| `program_fpga` | programmer la carte — **action matérielle, `confirm=True` obligatoire** |

## Boucle de travail attendue

```
env_info()                    -> quels outils sont là
project_tree()                -> structure
write_text_file("rtl/x.vhd")  -> RTL
cocotb_run("tb/x")            -> SIMULATION (obligatoire avant toute synthèse)
cocotb_results("tb/x")        -> PASS/FAIL
vivado_run(script_path="scripts/build.tcl")
job_status(id, wait_s=30)     -> en cours / fini
job_log(id)                   -> erreurs seulement
report_summary(".../timing_summary.rpt") -> WNS/TNS
```

Un run Vivado dure de quelques secondes à plusieurs heures : les outils ne bloquent
jamais plus longtemps que demandé (`wait_s` borné). Le LLM sonde l'avancement.

## Sécurité — ce qui est appliqué dans le code

| Barrière | Où | Comportement testé |
|---|---|---|
| Confinement au workspace | `safety.resolve_in_workspace` | `../secret`, `/etc/passwd`, `~/x` et les liens symboliques sortants sont refusés (`tests/test_safety.py`) |
| Liste blanche de binaires | `config.EDA_BINARIES` | `rm`, `curl`, ou un chemin absolu sont refusés ; jamais de `shell=True` |
| Scripts Tcl générés | `safety.write_tcl` | nom nettoyé, écriture atomique dans `scripts/generated/` |
| Sortie bornée | `jobs.JobManager` | log tronqué à 50 Mo, `tail` glissant de 400 lignes, 40 erreurs max remontées |
| Arrêt propre | `jobs._kill` | `SIGTERM` sur le **groupe** de processus, puis `SIGKILL` après 8 s |
| Actions matérielles | `tools.program_fpga` | refus explicite tant que `confirm=True` n'est pas fourni (et l'accord de l'utilisateur) |
| Batch forcé | `config.base_env` | `DISPLAY=""` : aucune IHM ne s'ouvre derrière le dos de l'agent |

Le serveur ne donne **aucun** accès shell générique : c'est la seule façon d'être
utilisable par un LLM sans transformer chaque prompt en exécution arbitraire.

## Configuration des clients

`configs/` contient des exemples prêts à copier :

| Client | Fichier |
|---|---|
| Claude Desktop | `configs/claude_desktop_config.json` |
| Hermes Agent | `configs/hermes-config-snippet.yaml` (`mcp_servers:` dans `~/.hermes/config.yaml`) |
| VS Code / Copilot | `configs/vscode-mcp.json` |
| Cline | `configs/cline_mcp_settings.json` |

Remplacez les chemins (`/chemin/vers/venv/bin/python`, `PYTHONPATH`, `--workspace`).
Un LLM **sans** client MCP peut quand même travailler : les scripts Tcl des
`templates/vivado/` sont faits pour être exécutés à la main.

## Tests

```bash
cd mcp
python -m pytest -q          # 51 tests
```

Ce qui est réellement vérifié (pas des mocks) : lancement de vrais processus (`make`,
`python3`), détection de succès/échec, extraction d'erreurs dans les logs, **timeout qui
tue le processus**, annulation, persistance des `runs/*.json`, parsing d'un
`results.xml` authentique de cocotb 2.0.1, sérialisation des chemins, et démarrage du
serveur en **sous-processus stdio** avec un vrai client MCP (liste des outils + appel).

## Limites assumées

- **Aucun Vivado sur la machine d'écriture de ce dépôt** : les commandes Tcl ont été
  validées sur la documentation AMD et par analyse syntaxique `tclsh`, pas par un run
  réel. Les analyseurs de rapports Vivado dégradent proprement (`"parsed": false` +
  texte brut) si la mise en page change : ils ne mentiront pas.
- **cocotb ne supporte pas XSim** (vérifié dans cocotb 2.0.1) : en environnement
  Vivado seul, utiliser un testbench VHDL (`examples/04-vhdl-testbench-xsim`) ou
  simuler le même RTL avec GHDL.
- Les jobs vivent en mémoire du serveur (les logs et un JSON par job restent sur
  disque dans `.mcp_runs/`) : après un redémarrage, `job_list` repart de zéro.
- Le serveur est **batch-only** : pas de session Vivado interactive, pas de GUI.
