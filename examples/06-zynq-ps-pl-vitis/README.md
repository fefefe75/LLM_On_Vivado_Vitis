# Exemple 06 — Zynq PS + PL, puis application Vitis

Cet exemple est **documentaire** : il montre le flux complet Vivado → Vitis pour une
carte Zynq-7000, mais il n'a **pas été exécuté** (aucune carte Zynq branchée sur la
machine de référence). Les fichiers sont fournis pour être copiés et adaptés ; les
commandes viennent de la documentation AMD et du comportement vérifié de Vivado
2025.2 (`write_hw_platform` existe, `write_hw_def` a disparu, `vitis -s` prend un
script Python).

## Le problème que ça résout

Un LLM sait écrire du VHDL, mais pas forcément brancher ce VHDL sur le PS (processeur
ARM) d'un Zynq, ni produire l'application C qui parle aux registres. Voici la chaîne
minimale, dans l'ordre.

```
1. Vivado : block design (Zynq PS + IP AXI GPIO ou ton VHDL emballé en IP)
2. Vivado : make_wrapper + synthèse + implémentation + bitstream
3. Vivado : write_hw_platform -fixed -include_bit -file design.xsa
4. Vitis  : plateforme depuis l'XSA -> BSP -> application C -> build
5. Cible  : JTAG (dow/con) ou carte SD (BOOT.bin via bootgen)
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `scripts/create_bd.tcl` | crée le projet, le block design (PS7 + AXI GPIO), le wrapper, puis lance le build |
| `scripts/export_xsa.tcl` | export du `.xsa` (à utiliser après l'implémentation) |
| `software/hello_gpio.c` | application baremetal : écrit un motif sur le GPIO du PL et l'affiche |
| `software/hello_gpio.bif` | fichier bootgen pour fabriquer `BOOT.bin` |

## Ce qui est vérifié, et ce qui ne l'est pas

| Affirmation | Statut |
|---|---|
| `write_hw_platform -fixed -include_bit -force -file x.xsa` existe en 2025.2 | **vérifié** (commande présente, utilisée dans `templates/vivado/export_xsa.tcl`) |
| `write_hw_def` n'existe plus | **vérifié** (`info commands write_hw_def` → vide) |
| `vitis -s <script.py>` attend un **script Python** | **vérifié** (texte d'aide de Vitis 2025.2) |
| `xsct` existe encore en 2025.2 (flux hérité Tcl) | **vérifié** |
| Les noms d'IP du block design (`processing_system7_0`, `axi_gpio_0`) et les commandes `create_bd_cell`/`apply_bd_automation` | **non exécuté** : à valider au premier lancement, les noms exacts dépendent de la version du catalogue d'IP |
| L'application C s'exécute sur la carte | **non exécuté** (pas de cible) |

Conséquence pour un agent : présenter ce flux comme « à exécuter et à corriger »,
jamais comme « validé ».

## Ordre de lancement

```bash
source ~/vivado/2025.2/Vivado/settings64.sh

# 1) projet + block design (adapter la partie a votre carte)
vivado -mode batch -source scripts/create_bd.tcl -nolog -nojournal \
       -tclargs --part xc7z020clg400-1 --name zynq_prj

# 2) implémentation + bitstream (script générique du dépôt)
vivado -mode batch -source ../templates/vivado/build.tcl -nolog -nojournal \
       -tclargs --xpr zynq_prj/zynq_prj.xpr --to bitstream --jobs 4

# 3) export XSA (le point de jonction avec Vitis)
vivado -mode batch -source scripts/export_xsa.tcl -nolog -nojournal \
       -tclargs --xpr zynq_prj/zynq_prj.xpr --out export/zynq.xsa

# 4) application Vitis (flux unifie >= 2023.2 : script PYTHON)
vitis -s scripts/create_app.py           # a ecrire/valider sur place (voir docs/08-vitis.md)
```

## Pièges connus de ce flux (voir `docs/10-troubleshooting.md`)

- Un block design **sans `make_wrapper`** : le top reste le BD, et `write_hw_platform`
  produit un XSA inutilisable côté logiciel.
- Une horloge non contrainte sur le PL : le PS fonctionne, mais rien ne garantit le
  timing du PL (et le rapport de timing sera vide).
- Un `bitstream` absent de l'XSA (`-include_bit` oublié) : impossible de faire un
  `BOOT.bin` autonome.
- Des adresses de registres écrites à la main dans le C : elles changent à chaque
  modification du block design — toujours passer par `xparameters.h`.
