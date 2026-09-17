# `_research/` — notes de recherche brutes (non vérifiées ligne à ligne)

Ces fichiers sont des **notes de recherche produites par des agents IA** pendant la
construction de ce dépôt, à partir de sources officielles (docs.amd.com, cocotb,
spec MCP, dépôts GitHub cités dans le texte). Elles ont été conservées parce
qu'elles contiennent les **sources** et le raisonnement qui ont mené à la
documentation finale.

## Statut — à lire avant de s'en servir

| | |
|---|---|
| **Vérifié ligne à ligne ?** | **Non.** Chaque affirmation n'a pas été rejouée sur une machine avec Vivado. |
| **Source de vérité** | Les documents `docs/01…11` et les scripts `templates/` — eux-mêmes vérifiés par exécution (`scripts/verify_all.sh`, 11 contrôles). |
| **En cas de contradiction** | C'est la documentation mesurée qui gagne, jamais ces notes. |
| **Usage recommandé** | s'en servir pour retrouver une URL, un nom de commande, une piste ; pas pour conclure. |

Trois exemples de points où ces notes sont alignées avec ce qui a été mesuré
(elles ne sont donc pas à jeter) :

- sur `SIM=xsim` : elles concluent qu'une tentative avec XSim doit **échouer avec un
  message clair**, ce qui correspond au comportement réel constaté dans cocotb 2.0.1
  (le Makefile XSim n'existe pas) ;
- sur l'export Vivado → Vitis : elles signalent que `write_hw_def` **n'est pas** la
  commande AMD attendue (c'est `write_hw_platform`) ;
- elles recensent des serveurs MCP Vivado déjà publiés (par exemple
  `coreyhahn/vivado_mcp`, qui maintient une session Tcl persistante via pexpect) —
  utile pour comparer les approches.

## Inventaire

| Fichier | Sujet |
|---|---|
| `01-vivado-tcl.md` | flux Tcl Vivado, batch, logs, versions, récupération après échec |
| `02-vitis.md` | Vitis classique (XSCT) vs unifié, XSA, boot, BSP |
| `03-simulation-cocotb.md` | simulateurs, XSim vs GHDL vs cocotb, pièges d'API 1.x → 2.x |
| `04-mcp-server-design.md` | protocole MCP, serveurs existants, architecture et sécurité |
| `05-agent-integration.md` | skills, prompts compacts, consommation par un LLM local |
| `06-vhdl-and-constraints.md` | VHDL synthétisable, XDC, timing, IP |

## Ce qui a été repris dans la documentation finale

`docs/02`, `docs/03`, `docs/04`, `docs/06`, `docs/07`, `docs/08`, `docs/10` et
`docs/11` reprennent la matière utile, **en la confrontant aux essais réels** : ce
qui était faux ou invérifiable a été corrigé ou explicitement marqué comme non
vérifié. Les notes restent ici pour la traçabilité des sources.
