---
name: fpga-agent-mcp
description: Use when an agent must actually run Vivado/Vitis/simulations itself, when setting up the FPGA MCP server, or when deciding between MCP tools, terminal and generated scripts.
---

# Piloter les outils FPGA depuis un agent (MCP)

Instructions détaillées : `mcp/README.md`. Configs prêtes : `mcp/configs/`.

## Le serveur en une phrase

`mcp/vivado_mcp` est un serveur MCP (paquet `fastmcp`, Python ≥ 3.10) qui expose
18 outils : lecture/écriture de fichiers confinée au projet, lancement de Vivado en
batch, de Vitis (`xsct` ou `vitis -s`) et de cocotb, suivi de job, filtrage de log,
analyse de rapports, programmation FPGA (avec confirmation).

```bash
pip install -r mcp/requirements.txt
python -m vivado_mcp --workspace ~/mon_projet --tool-root ~/vivado/2025.2 --selftest
python -m vivado_mcp --workspace ~/mon_projet --tool-root ~/vivado/2025.2   # stdio
```

## Boucle d'utilisation recommandée

```
env_info()                    -> ce qui est réellement installé (jamais prescrire à l'aveugle)
project_tree()                -> structure
write_text_file("rtl/x.vhd")  -> RTL
cocotb_run("tb/x")            -> simulation (obligatoire avant synthèse)
cocotb_results("tb/x")        -> PASS/FAIL par test
vivado_run(tcl=... ou script_path="scripts/build.tcl")
job_status(id, wait_s=30)     -> en cours / fini (jamais bloquant)
job_log(id)                   -> erreurs + avertissements extraits
report_summary("<...>.rpt")   -> WNS/TNS, ressources, messages par code
```

## Ce que le serveur refuse, et pourquoi

| Refus | Raison |
|---|---|
| chemin hors du `--workspace` (dont `..`, `~`, lien symbolique sortant) | un LLM ne doit pas pouvoir écrire n'importe où |
| binaire hors liste blanche (`rm`, `curl`, chemin absolu) | pas de shell dégénéré ; `shell=True` jamais utilisé |
| `program_fpga` sans `confirm=True` | action matérielle : accord explicite de l'utilisateur |
| sortie non bornée | log tronqué (50 Mo), 40 erreurs max, `tail` glissant |

## Sans MCP

Le serveur n'est pas obligatoire : un agent sans MCP génère les scripts
(`templates/vivado/*.tcl`, `templates/cocotb/`) et les fait exécuter, en annonçant
qu'ils ne sont pas encore vérifiés. La boucle reste la même ; seule l'exécution change.

## Avant de conclure

Un job MCP « ok » signifie que la commande a réussi (code retour 0), pas que le
design est bon : lire le rapport (`report_summary`) et le verdict de simulation
(`cocotb_results`) avant d'annoncer quoi que ce soit.
