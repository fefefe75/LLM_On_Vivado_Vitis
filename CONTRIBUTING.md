# Contributing

Merci de vouloir améliorer ce dépôt. Il sert à des **agents IA** autant qu'à des
humains : la précision passe avant le style.

## Règles non négociables

1. **Pas d'affirmation sans preuve.** Toute affirmation sur le comportement de
   Vivado/Vitis doit venir soit d'une source AMD (lien `docs.amd.com`), soit d'une
   exécution réelle dont la sortie est citée. « Ça devrait marcher » n'est pas une
   contribution.
2. **Version explicite.** Vitis a deux générations incompatibles (classique `xsct`
   ≤ 2023.1, unifié `vitis -s script.py` ≥ 2023.2) ; des commandes Vivado
   disparaissent (`write_hw_def`, supprimée après 2020.x). Indique la version
   concernée.
3. **Commandes copiables.** Une commande par ligne, pas d'`...`, pas de variable non
   définie. Si un chemin dépend de l'installation, dis-le et donne la commande de
   détection (`find … -name settings64.sh`).
4. **Rien de propriétaire dans le dépôt.** Pas de bitstream, pas de `.dcp`, pas de
   capture d'écran d'outil sous licence. Les exemples doivent tourner avec GHDL
   (ou Icarus/Verilator) quand c'est techniquement possible.
5. **Honnêteté sur les trous.** Une doc qui dit « non vérifié : pas de carte
   branchée » vaut mieux qu'une doc qui invente une sortie.

## Conventions

- Un module HDL par fichier, nom de fichier = nom d'entité.
- Ports : `i_` entrées, `o_` sorties, `s_` signaux internes, `C_` constantes,
  `p_` labels de process. Reset **synchrone actif haut** par défaut, un seul style
  par design.
- Tout testbench s'exécute avec une **graine fixe** et doit être reproductible.
- Aucun fichier généré en git (`sim_build/`, `*.xpr`, `.Xil/`, `xsim.dir/`,
  `results.xml`, `*.bit`, `*.xsa`, `__pycache__/`) : le `.gitignore` racine couvre
  ces cas.
- Langues : `docs/` et le README principal en anglais ; `examples/` et les
  commentaires de code en français ; `README.fr.md` et `prompts/quickref.fr.md`
  maintenus en parité avec l'anglais.

## Ajouter un exemple

```
examples/NN-nom/
├── README.md        ce que ça montre, comment le lancer, ce qui est vérifié
├── rtl/             sources HDL
├── tb/              Makefile + test_<module>.py (cocotb 2.x)
└── constraints/     .xdc si nécessaire
```
Puis, dans le README de l'exemple, la **preuve** : commande lancée et ligne de
résultat réelle (`TESTS=… PASS=… FAIL=…`).

## Ajouter un skill

`skills/<nom>/SKILL.md` avec un frontmatter YAML :

```yaml
---
name: nom-du-skill
description: Use when <déclencheur précis>. <ce que ça fait en une ligne>.
---
```
Le corps reste court ; le détail va dans `references/` et est référencé depuis le
`SKILL.md`. La `description` est la seule chose que l'agent lit s'il ne charge pas le
skill : elle doit dire **quand** l'utiliser.

## Vérifier avant de proposer une modification

```bash
bash scripts/verify_all.sh                           # tout : exemples, templates, MCP, Tcl, Vivado
python3 scripts/check_tcl.py .                       # scripts Tcl seulement (syntaxe + procs)
python3 scripts/verify_vivado.py                     # flux Vivado réel (après settings64.sh)
cd mcp && python -m pytest -q                        # serveur MCP (52 tests)
cd examples/01-counter-cocotb/tb && make             # un testbench qui doit rester vert
```
`scripts/verify_all.sh` est la référence : il n'affiche `OK` que sur un code retour
nul, et `IGNORE` pour ce qu'il n'a pas pu exécuter (par exemple XSim si Vivado n'est
pas sourcé). Un script Tcl qui ne passe pas `check_tcl.py` ne sera pas accepté :
c'est le seul garde-fou automatique contre le piège du comptage d'accolades (Tcl
compte les accolades même dans un commentaire, à l'intérieur d'un bloc).
