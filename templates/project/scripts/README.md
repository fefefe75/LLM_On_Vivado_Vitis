# `scripts/` — l'automatisation

Tout ce qui n'est ni du HDL ni du logiciel embarqué : les scripts qui pilotent
les outils. Rien ici n'est synthétisé ; rien dans `../rtl/` ne doit contenir de
script (Vivado ajoute des fichiers par motif `[glob rtl/*.vhd]`).

```
scripts/
├── create_project.tcl     create_project + add_files + set_property top
├── build.tcl              synthèse, implémentation, bitstream, rapports
├── program.tcl            programmation FPGA / flash
├── create_app.py          logiciel embarque, Vitis unifie (>= 2023.2, vitis -s)
├── create_app.tcl         logiciel embarque, XSCT classique (<= 2023.1, xsct)
├── ghdl_lint.sh           analyse VHDL (appelé par `make lint`)
├── run_testbench.sh       lance un tb/ et vérifie results.xml (appelé par `make sim`)
└── check_tcl_syntax.tcl   vérification de syntaxe Tcl (appelé par `make tcl-check`)
```

## Règles

- **Mode batch uniquement** : `vivado -mode batch -nojournal -nolog -source script.tcl`.
  Un script qui attend un clic de souris n'est pas reproductible.
- **Non interactif** : toutes les valeurs variables (part, top, chemins)
  arrivent par `-tclargs` ou par variable d'environnement. Le Makefile racine
  les transmet via `VIVADO_ARGS` :
  ```bash
  make vivado-build VIVADO_ARGS="-tclargs --part xc7a35tcsg324-1"
  ```
- **Chemins relatifs au projet**, jamais de `/home/…` en dur.
- **Vérifier le résultat, pas le retour du lancement** : `launch_runs` retourne
  avant la fin ; il faut `wait_on_run` puis tester
  `get_property PROGRESS [get_runs impl_1]` et `get_property STATUS`.
  Un `ERROR` dans `vivado.log` doit faire sortir le script en erreur.
- **Vérifier la syntaxe avant de lancer Vivado** (30 secondes économisées à
  chaque itération) :
  ```bash
  make tcl-check
  ```
  Le contrôle compile le Tcl sans l'exécuter : les commandes Vivado n'ont pas
  besoin d'exister.

## Rappel : deux générations d'outils, deux syntaxes

| Outil | Version | Lancement |
|---|---|---|
| Vivado | toutes | `vivado -mode batch -source script.tcl` |
| Vitis (unifié) | ≥ 2023.2 | `vitis -s script.py` |
| XSCT (classique) | ≤ 2023.1 | `xsct script.tcl` |

`make vitis-build` choisit automatiquement selon l'extension du script trouvé
(`.py` → `vitis -s`, `.tcl` → `xsct`).
