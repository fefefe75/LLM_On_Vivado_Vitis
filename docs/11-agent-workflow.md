# Comment un agent doit travailler (boucle, preuves, comptes rendus)

## 1. La boucle

```
1. LIRE    état du projet (arborescence, .xdc, entités existantes, logs)
2. ÉCRIRE  un module à la fois, un fichier par entité
3. SIMULER testbench AVANT toute synthèse
4. CORRIGER sur la base de la sortie réelle de l'outil
5. SYNTHÉTISER puis implémenter
6. VÉRIFIER timing (WNS/TNS) et DRC
7. RAPPORTER ce qui a été lancé, la sortie obtenue, ce qui reste
```

Interdits :
- affirmer qu'un design fonctionne **sans** log de simulation ou de build ;
- sauter la simulation « pour gagner du temps » ;
- modifier une contrainte de timing pour faire passer un design sans le dire ;
- éditer un `.xpr`/`.xsa`/netlist à la main ;
- inventer une option de commande (Tcl/Vivado/Vitis) : vérifier ou le dire.

## 2. Choisir son niveau d'outillage

| Ce dont dispose l'agent | Ce qu'il doit faire |
|---|---|
| Serveur MCP (`mcp/`) | utiliser les outils : `env_info` → `project_tree` → `write_text_file` → `cocotb_run` → `vivado_run` → `job_log` → `report_summary` |
| Accès terminal | générer les scripts `templates/` et les exécuter lui-même ; vérifier le code retour |
| Ni l'un ni l'autre | écrire les scripts Tcl/shell **exacts** et les confier à l'utilisateur, en annonçant qu'ils ne sont pas encore vérifiés |

Dans tous les cas : lire d'abord la sortie de `env_info` (ou son équivalent
`command -v vivado / ghdl / vitis`) avant de proposer un flux. Prescrire Vivado à
quelqu'un qui ne l'a pas, ou cocotb+XSim qui n'existe pas, c'est une erreur.

## 3. Preuves attendues

| Étape | Preuve minimale |
|---|---|
| VHDL écrit | fichier créé, entité/architecture cohérentes, compilation sans erreur |
| Testbench | `TESTS=n PASS=n FAIL=0` (cocotb) ou `ALL TESTS PASSED` (VHDL) |
| Synthèse | `PROGRESS=100% STATUS=synth_design Complete!` |
| Implémentation | `PROGRESS=100% STATUS=write_bitstream Complete!` ou `route_design Complete!` |
| Timing | WNS/TNS chiffrés, et un tableau de timing **présent** (sinon : non contraint) |
| Vitis | compilation OK + artefacts présents ; exécution sur cible = à faire |

## 4. Format de compte rendu

```
Changé :      <fichiers, une ligne chacun>
Lancé :       <commande exacte>
Résultat :    <PASS/FAIL + chiffres : TESTS=, WNS=, % LUT>
Non vérifié : <ce qui n'a pas pu être exécuté, et pourquoi>
Suivant :     <une étape concrète>
```
Aucun adjectif sans log derrière. « Ça devrait marcher » n'est pas un résultat.

## 5. Gérer un gros projet sans se noyer

- **Ne pas lire tout le dépôt** : arborescence (`project_tree`), puis seulement les
  fichiers en rapport avec la tâche.
- Charger **un** `SKILL.md` (ils sont courts) et la référence qu'il pointe, pas toute
  la doc.
- Travailler par incréments vérifiables : un module → son testbench → vert → suivant.
- Garder une trace écrite (fichier de suivi) plutôt que de la mémoire de contexte.
- Sur un modèle à petit contexte (< 16k), utiliser `prompts/quickref.fr.md` et
  éviter `docs/_research/`.

## 6. Dépannage : par où commencer

1. Le **code de message** (`[Synth 8-36]`, `[Common 17-69]`, `[DRC UCIO-1]`) :
   `docs/10-troubleshooting.md`.
2. Le log **du run** concerné (`<prj>.runs/<run>/runme.log`), pas seulement la console.
3. Corriger une cause, relancer l'étape la plus précoce possible.
4. Si le comportement de l'outil est incertain : `info commands`, `get_parts`,
   `--help`, ou un petit script de sonde — **jamais** une supposition.

## 7. Rapport à l'être humain

Un agent qui travaille pour quelqu'un doit distinguer trois choses :
ce qu'il a **fait et vérifié**, ce qu'il a **fait sans pouvoir vérifier**, et ce
qu'il **n'a pas fait**. Un rapport qui mélange les trois est inutilisable, même
s'il est joli.
