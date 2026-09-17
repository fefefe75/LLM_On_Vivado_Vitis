---
name: vitis-embedded
description: Use when building embedded software for a Zynq/MicroBlaze target (Vitis platform, BSP, application, BOOT.bin) or when connecting Vivado hardware to Vitis.
---

# Vitis — logiciel embarqué

Référence complète : `docs/08-vitis.md`. Scripts modèles : `templates/vitis/`.

## Première question : quelle génération ?

```bash
vitis --version        # >= 2023.2 -> flux unifie : vitis -s script.py  (PYTHON)
command -v xsct        # <= 2023.1 -> flux classique : xsct script.tcl  (TCL)
```
Vérifié en 2025.2 : `vitis -s <python_script>` et `xsct` coexistent,
mais `xsct` est le flux hérité. Ne jamais mélanger les deux.

## Prérequis : l'XSA

```tcl
# côté Vivado, après implémentation
write_hw_platform -fixed -include_bit -force -file export/design.xsa
```
`write_hw_def` **n'existe plus** (supprimée après 2020.x). Sans `impl_1` lancé,
l'export échoue.

## Flux classique (xsct)

```tcl
setws ./vitis_ws
platform create -name plat -hw ./export/design.xsa -proc ps7_cortexa9_0 -os standalone
platform active plat
domain create -name dom -os standalone -proc ps7_cortexa9_0
app create -name hello -platform plat -domain dom -template "Hello World"
app build -name hello
```

## Règles de code baremetal

- Toute adresse vient de `xparameters.h` (généré depuis l'XSA) — jamais en dur.
- `xil_printf` + `\r\n` pour un terminal série ; les pilotes viennent du BSP
  (`XGpio_*`, `XUartPs_*`, …).
- Un `main()` qui termine en baremetal doit décider quoi faire ensuite (boucle ou
  retour) ; sinon comportement indéfini.

## Déploiement

| Cible | Commande |
|---|---|
| JTAG | `xsct` : `connect` → `targets` → `dow hello.elf` → `con` |
| Carte SD | `BOOT.bin` en FAT32 (bootgen + `.bif` : FSBL, bitstream, application) |
| QSPI | `program_flash -f BOOT.bin` |

## Honnêteté obligatoire

Sans carte branchée : « compile et produit un `.elf` » n'est **pas** « ça démarre ».
Rapporter séparément : ce qui compile, ce qui est vérifiable sur cible, ce qui reste
à tester. C'est la limite la plus fréquente des réponses d'IA sur ce sujet.
