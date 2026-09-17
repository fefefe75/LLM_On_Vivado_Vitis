---
name: vivado-tcl-project
description: Use when creating or building a Vivado project from the command line (create_project, add_files, launch_runs, bitstream, XSA export) or when a Vivado build must be run/fixed in batch.
---

# Vivado en Tcl (mode batch, Linux)

Référence complète : `docs/02-vivado-tcl.md`. Scripts prêts : `templates/vivado/`.
Messages d'erreur réels et correctifs : `docs/10-troubleshooting.md`.

## Règle de base

Jamais d'IHM, jamais d'édition manuelle d'un `.xpr`. On écrit un script Tcl, on le
lance, on lit la sortie et le code retour.

```bash
source ~/vivado/2025.2/Vivado/settings64.sh
vivado -mode batch -source scripts/build.tcl -nolog -nojournal -tclargs --xpr prj/prj.xpr
```

## Les cinq pièges qui coûtent une heure chacun

1. Un run déjà terminé **ne peut pas** être relancé sans `reset_run` →
   `ERROR: [Common 17-69] ... needs to be reset before launching`. Tester
   `get_property PROGRESS [get_runs <run>]` : `100%` = réutiliser.
2. Vivado **ne crée pas** le dossier de rapport → `file mkdir reports` avant tout
   `report_*  -file` (`ERROR: [Common 17-37]`).
3. `get_timing_paths` ne renvoie rien après `close_design` : lire le WNS design ouvert.
4. Sans `IOSTANDARD` ni `PACKAGE_PIN`, `write_bitstream` échoue (`DRC NSTD-1`,
   `DRC UCIO-1`). Pour valider la logique sans carte :
   `templates/vivado/build.tcl --allow-unconstrained 1`.
5. `set_property top <nom>` ne valide rien : l'erreur n'apparaît qu'à la synthèse.
   Toujours lancer une synthèse avant de conclure.

## Séquence minimale (project mode)

```tcl
create_project $name $dir/$name -part $part -force
set_property target_language VHDL [current_project]
add_files -fileset sources_1 [glob rtl/*.vhd]
add_files -fileset constrs_1 [glob constraints/*.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 4        ; wait_on_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 4 ; wait_on_run impl_1
```
Flux non-project (sans `.xpr`, pour un design jetable) :
`templates/vivado/nonproject_build.tcl`.

## Vérifier au lieu de deviner

```tcl
get_parts xc7z020*          ;# parties réellement installées
info commands write_hw_def  ;# vide en 2025.2 : commande supprimée
get_property STATUS [get_runs impl_1]
```
Avant d'utiliser une option inconnue : la lancer dans un script de sonde, ou lire
`docs/02-vivado-tcl.md` §3.

## Après le build

```tcl
open_run impl_1
report_timing_summary -file reports/timing_summary.rpt -max_paths 10 -warn_on_violation
report_utilization    -file reports/utilization.rpt
report_drc            -file reports/drc.rpt
write_hw_platform -fixed -include_bit -force -file export/design.xsa   ;# pour Vitis
```
Le bitstream est dans `<prj>.runs/impl_1/<top>.bit`. Ne jamais committer les
artefacts (le `.gitignore` racine s'en charge).
