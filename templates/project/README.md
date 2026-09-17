# Squelette de projet FPGA (VHDL) — `templates/project/`

Copiez ce dossier comme racine de votre projet, puis remplissez `rtl/` et `tb/`.
Tout le reste (Makefile, `.gitignore`, arborescence, conventions) est déjà en place.

```bash
cp -r /chemin/vers/LLM_On_Vivado_Vitis/templates/project/ ~/mon_projet
cd ~/mon_projet
make help
```

## Arborescence

```
mon_projet/
├── Makefile          boîte à outils : sim, lint, tcl-check, vivado-*, vitis-build
├── README.md         ce fichier
├── CONTRIBUTING.md   conventions de nommage et règles de qualité
├── .gitignore        tout ce qui est généré est exclu de git
├── rtl/              le code VHDL synthétisable (un module = un fichier)
├── tb/<mon_test>/    un dossier par testbench cocotb
├── constraints/      les contraintes .xdc (broches, horloges, faux chemins)
├── scripts/          les scripts d'automatisation (.tcl Vivado/Vitis, .sh, .py)
├── software/         le code embarqué (C pour MicroBlaze/Zynq, BSP, boot)
├── sim/              les sorties de simulation (traces, logs) — non versionné
└── doc/              la documentation de conception (schémas, rapports, notes)
```

| Dossier | Versionné ? | Rôle | Ce qu'on n'y met **jamais** |
|---|---|---|---|
| `rtl/` | oui | code VHDL synthétisable, un module par fichier | des `assert` de simulation, des `wait for`, des testbenches |
| `tb/<nom>/` | oui | un testbench cocotb par module ou par fonction | du code qui doit être synthétisé |
| `constraints/` | oui | `.xdc` : broches, horloges, I/O standards | des chemins en dur d'une seule carte sans le dire |
| `scripts/` | oui | Tcl/Python/shell d'automatisation (Vivado, Vitis, outils) | des scripts propres à une machine (`/home/…`) |
| `software/` | oui | sources C/assembleur, BSP, `BOOT.bif` | des `.elf`, `Debug/`, `Release/` générés |
| `sim/` | **non** | traces (`.ghw`, `.vcd`, `.fst`), `results.xml`, logs | des sources |
| `doc/` | oui | notes de conception, schémas, rapports de timing archivés | des captures non commentées |

## Pourquoi cette séparation

- **`rtl/` n'est que du synthétisable.** Un outil de synthèse lit tout ce qu'on lui
  donne : mélanger testbench et RTL oblige à filtrer les fichiers à la main dans
  chaque script Tcl, et c'est là qu'on ajoute un `assert` par erreur.
- **`tb/<nom>/` = un dossier par test.** cocotb exige un top et un module de test :
  un dossier par test garde le `Makefile`, le script Python et les traces ensemble,
  et le Makefile racine peut les lancer tous en boucle (`make sim`).
- **`constraints/` séparé du RTL.** Les `.xdc` dépendent de la *carte*, pas du
  design : le même `rtl/` doit pouvoir être contraint pour une autre carte sans
  être modifié. C'est la base du portage.
- **`scripts/` hors de `rtl/`.** Vivado ajoute des fichiers par motif (`[glob rtl/*.vhd]`) :
  un `.tcl` posé dans `rtl/` finit un jour dans la synthèse.
- **`software/` séparé.** Le logiciel embarqué se compile avec une autre chaîne
  d'outils (Vitis, GCC croisé) et suit son propre cycle de vie : séparer évite de
  relancer une synthèse FPGA pour corriger une ligne de C.
- **`sim/` et les artefacts générés sont jetables.** Traces, `results.xml`,
  `sim_build/`, `.Xil/`, `*.xpr` : tout cela se régénère et n'a rien à faire dans
  git (bruit dans les diffs, conflits de binaire). C'est le rôle du `.gitignore`.
- **`doc/` garde les traces humaines.** Un rapport de timing archivé avec sa date
  et sa version d'outil vaut mieux qu'une capture d'écran dans une conversation.

## Prise en main

```bash
make help                       # liste des cibles et variables
make check-tools                # quels outils sont présents, quels scripts EDA sont détectés
```

### Ajouter un module VHDL

```bash
# rtl/compteur.vhd : une entité = un fichier, nom du fichier = nom de l'entité
make lint                       # GHDL analyse tout rtl/** en VHDL-2008, dans l'ordre des dépendances
```

### Ajouter un testbench cocotb

Voir `tb/README.md` (modèle complet). En résumé :

```bash
mkdir -p tb/compteur
# y placer soit un Makefile cocotb, soit un run_tests.py (et test_compteur.py)
make sim                        # lance TOUS les tb/*/ et agrège les résultats
make sim-one TEST=compteur      # un seul test
make waves TEST=compteur        # idem, en enregistrant les traces
```

### Aller jusqu'au FPGA (Vivado / Vitis installés)

```bash
make vivado-create              # créer le projet Vivado (scripts/create_project.tcl)
make vivado-build               # synthèse + implémentation + bitstream (build.tcl)
make vivado-program             # programmer la carte (program.tcl)
make vitis-build                # compiler le logiciel embarqué (create_app.py / .tcl)
```

Si `vivado` n'est pas dans le `PATH`, la cible s'arrête en l'expliquant (elle
n'affiche jamais un faux succès) :

```
make vivado-create VIVADO=/outils/Xilinx/2024.1/Vivado/bin/vivado
source /outils/Xilinx/2024.1/Vivado/settings64.sh   # ou sourcer l'environnement
```

### Vérifier les scripts Tcl

```bash
make tcl-check                  # syntaxe de tous les *.tcl, via tclsh, sans exécution
```

## Ce que la boîte à outils garantit (et ne garantit pas)

- `make lint` **n'est pas** une preuve de fonctionnement : il prouve seulement que
  le VHDL est syntaxiquement et sémantiquement analysable. La preuve, c'est `make sim`.
- `make sim` retourne un code non nul si un test échoue, et affiche un résumé
  (`N tests, X OK, Y en échec`). Sans testbench, il le dit et sort en 0.
- Les cibles EDA (`vivado-*`, `vitis-build`) ne fabriquent pas de résultat : sans
  l'outil, elles l'annoncent et ne font rien.
- Les tests doivent être **reproductibles à graine fixe** (`SEED=1234` par défaut,
  exporté en `COCOTB_RANDOM_SEED`). Voir `CONTRIBUTING.md`.
