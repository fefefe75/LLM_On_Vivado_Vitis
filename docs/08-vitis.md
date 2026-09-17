# Vitis — logiciel embarqué (Zynq / MicroBlaze)

Compétence associée : `skills/vitis-embedded/SKILL.md`. Scripts modèles :
`templates/vitis/`.

**Statut de vérification** : sur la machine de référence, Vitis **2025.2** est
installé et répond (`vitis --version`, `xsct -version`), le flux de bout en bout
n'a **pas** été exécuté (aucune cible Zynq branchée). Les commandes de chaque flux
viennent de la documentation AMD et sont signalées comme telles.

---

## 1. Deux générations incompatibles

| | Vitis classique (≤ 2023.1) | Vitis unifié (≥ 2023.2) |
|---|---|---|
| Entrée en ligne de commande | `xsct script.tcl` | `vitis -s script.py` |
| Langage de script | **Tcl** | **Python** |
| Notion centrale | workspace → platform → application | workspace → platform component → application component |
| Vérifié en 2025.2 | `xsct` **existe encore** mais est déprécié | `vitis -s <python_script>` (texte d'aide réel : « Runs the given python script ») |

Autres options réelles de `vitis` 2025.2 : `-i` (shell Python interactif),
`-w <workspace>` (IDE sur un workspace), `-a` (ouvrir un rapport dans l'analyse),
`-j` (interface Jupyter).

Un agent **doit** vérifier laquelle des deux il a sous la main avant d'écrire un script :
```bash
vitis --version        # -> Vitis v2025.2 (64-bit)  => flux unifie (python)
command -v xsct        # présent aussi en 2025.2, mais flux classique (tcl)
```

## 2. Le point de jonction : le `.xsa`

Vivado exporte le matériel, Vitis le consomme. Rien de plus, rien de moins.

```tcl
# côté Vivado (templates/vivado/export_xsa.tcl)
write_hw_platform -fixed -include_bit -force -file export/design.xsa
```
- `-fixed` : design figé (non extensible dans Vitis).
- `-include_bit` : embarque le bitstream dans l'XSA — nécessaire pour produire un
  `BOOT.bin` autonome.
- Vérifié en 2025.2 : `write_hw_platform` existe, **`write_hw_def` a disparu**
  (remplacée depuis 2020.x — les tutoriels plus anciens sont faux sur ce point).
- L'implémentation doit avoir été lancée avant : sinon erreur (« impl_1 non lancé »).

## 3. Flux classique (xsct, ≤ 2023.1)

```tcl
# scripts/create_app.tcl
setws ./vitis_ws
platform create -name plat -hw ./export/design.xsa -proc ps7_cortexa9_0 -os standalone
platform active plat
domain create -name dom_standalone -os standalone -proc ps7_cortexa9_0
app create -name hello -platform plat -domain dom_standalone -template "Hello World"
app build -name hello
```
```bash
xsct scripts/create_app.tcl
```
Artefacts : `vitis_ws/hello/Debug/hello.elf`, BSP sous `vitis_ws/plat/…`,
`xparameters.h` dans le BSP.

## 4. Flux unifié (≥ 2023.2, Python)

```python
# scripts/create_app.py   ->   vitis -s scripts/create_app.py
# (API Python du composant Vitis ; les noms de classes exacts dependant de la
#  version, verifier avec `vitis -i` puis help() dans le shell interactif)
```
Conseil d'agent : dans un environnement 2023.2+, ouvrir `vitis -i` et vérifier l'API
réelle avant d'écrire un script — c'est plus fiable que de recopier un exemple.

## 5. Application baremetal : ce qui compte

```c
#include <stdio.h>
#include "xparameters.h"     /* adresses de base generees depuis l'XSA */
#include "xgpio.h"
#include "xil_printf.h"

int main(void) {
    XGpio gpio;
    XGpio_Initialize(&gpio, XPAR_GPIO_0_DEVICE_ID);   /* jamais d'adresse en dur */
    XGpio_SetDataDirection(&gpio, 1, 0x0);            /* canal 1 = sortie */
    XGpio_DiscreteWrite(&gpio, 1, 0x1);
    xil_printf("hello from PS\r\n");
    return 0;
}
```
- Toute adresse vient de `xparameters.h` (généré depuis l'XSA), jamais du code.
- `xil_printf` (pas `printf`) en baremetal sans stdio, et `\r\n` sur un terminal série.
- Les pilotes (`xgpiо.h`, `xuartps.h`, …) sont fournis par le BSP de la plateforme.

## 6. Déploiement

| Méthode | Comment | Remarques |
|---|---|---|
| JTAG | `xsct` : `connect`, `targets`, `dow hello.elf`, `con`, `rst` | le plus rapide pour tester |
| Carte SD | `BOOT.bin` en FAT32 + partition Linux éventuelle | mode de boot = SD |
| QSPI | `program_flash -f BOOT.bin` (xsct) | persistant |

`BOOT.bin` se fabrique avec **bootgen** et un fichier `.bif` :
```
// boot.bif  (Zynq-7000)
the_ROM_image:
{
  [bootloader] fsbl.elf
  design.bit
  hello.elf
}
```
```bash
bootgen -image boot.bif -arch zynq -o BOOT.bin -w on
```
Rôles : le **FSBL** (First Stage Boot Loader, généré par Vitis depuis l'XSA) configure
le PS/PL ; l'ordre (FSBL → bitstream → application) et les offsets dépendent de la
famille — à vérifier dans la doc AMD de la carte visée avant d'écrire une partition.

## 7. Erreurs fréquentes (Vitis)

| Symptôme | Cause probable | Piste |
|---|---|---|
| `xsct: command not found` | environnement non sourcé, ou flux unifié utilisé à la place | `source <Vitis>/settings64.sh` ; sinon `vitis -s` |
| plateforme impossible à créer | `.xsa` absent ou corrompu | refaire `write_hw_platform` après `impl_1` |
| `xparameters.h` introuvable | BSP non généré / mauvais include path | recompiler la plateforme, vérifier le BSP associé |
| `undefined reference to XGpio_…` | pilote non inclus dans le BSP | activer le pilote dans la configuration de la plateforme |
| build qui « ne trouve pas » un fichier | chemins relatifs au workspace, pas au script | raisonner depuis le workspace (`setws`), pas depuis le cwd du shell |
| carte absente en JTAG | câble/udev | `lsusb \| grep -i xilinx`, installer les règles udev du câble |

## 8. Ce qu'un agent doit dire honnêtement

Une application Vitis **ne se valide pas sans cible** : « ça compile » ne veut pas
dire « ça démarre ». Tant qu'aucune carte n'est branchée, l'agent doit :
1. compiler et vérifier le code retour ;
2. vérifier l'existence des artefacts (`.elf`, BSP, `xparameters.h`) ;
3. dire explicitement que l'exécution sur cible reste à faire.
