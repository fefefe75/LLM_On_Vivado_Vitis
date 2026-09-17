# `software/` — le logiciel embarqué

Le code qui tourne sur le **processeur** (MicroBlaze, ARM Cortex-A9/A53 des
Zynq, RISC-V selon la plateforme), pas sur le FPGA. Il se compile avec une autre
chaîne d'outils (Vitis, GCC croisé) et suit son propre cycle de vie : on corrige
souvent le C sans retoucher une seule ligne de VHDL.

```
software/
├── src/            sources C/assembleur de l'application
├── platform/       BSP, plateforme matérielle (généré ou scripté)
├── boot/           FSBL, .bif, BOOT.bin (fichiers de configuration, pas binaires)
└── README.md       ce fichier
```

## Règles

- **Jamais de binaire versionné** : `.elf`, `.map`, `*.o`, `Debug/`, `Release/`,
  `BOOT.bin` se régénèrent (`make clean` les enlève, `.gitignore` les exclut).
  Ce qui est versionné, c'est le *script* qui les produit.
- **Adresses par `xparameters.h`**, jamais en dur : les adresses de base
  viennent du `.xsa` exporté par Vivado (`xparameters.h`), pas d'un `#define`
  recopié d'un ancien projet.
- **Le matériel d'abord** : un logiciel ne se compile pas sans plateforme
  exportée :
  ```tcl
  write_hw_platform -fixed -include_bit -force -file export/mon_projet.xsa
  ```
- **Version d'outil explicite** dans le README du sous-dossier concerné : les
  deux générations de Vitis sont incompatibles (classique/XSCT ≤ 2023.1,
  unifiée ≥ 2023.2). Un script `create_app.tcl` ne fonctionne pas avec `vitis -s`.
- **Compilation** :
  ```bash
  make vitis-build          # choisit vitis -s (.py) ou xsct (.tcl)
  make check-tools          # vérifie ce qui est disponible sur la machine
  ```
- Une affirmation sur une API Xilinx (`XGpio_*`, `xil_printf`, bootgen) se
  justifie par une source AMD : UG1400 (Vitis), UG1137 (Zynq FSBL), ou l'en-tête
  réellement installé.
