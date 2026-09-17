---
name: vivado-build-timing
description: Use when running synthesis/implementation/bitstream and reading the results (WNS/TNS, timing closure, resource usage), or when a build must be iterated to meet timing.
---

# Build Vivado et fermeture du timing

Référence : `docs/02-vivado-tcl.md` (flux) et `docs/07-timing-closure.md` (timing).

## Lancer

```bash
vivado -mode batch -source templates/vivado/build.tcl -nolog -nojournal \
       -tclargs --xpr prj/prj.xpr --to synthesis|implementation|bitstream --jobs 4
```
`--reset 1` pour relancer de zéro ; `--allow-unconstrained 1` pour un design sans
brochage (validation de logique). Le script est idempotent et renvoie un code retour
non nul en cas d'échec.

## Critères de réussite (à exiger, pas à supposer)

| Étape | Ce qu'on doit lire |
|---|---|
| synthèse | `PROGRESS=100% STATUS=synth_design Complete!` |
| implémentation | `PROGRESS=100% STATUS=route_design Complete!` ou `write_bitstream Complete!` |
| timing | un tableau avec **WNS ≥ 0** et **TNS = 0** (`timing_summary.rpt`) |
| DRC | pas d'`ERROR: [DRC …]` (`drc.rpt`) |
| bitstream | fichier `<prj>.runs/impl_1/<top>.bit` existant |

Si le rapport contient `There are no user specified timing constraints.` : **aucune
horloge contrainte**, le design n'a rien prouvé (`docs/06-constraints-xdc.md`).

## Itérer vite

- Après une correction **RTL uniquement**, relancer l'implémentation, pas la synthèse.
- Pour explorer les directives de placement/routage :
  `launch_runs impl_1 -to_step route_design -directive Explore`.
- Le pire chemin se lit dans `timing_summary.rpt` : slack, `Logic Levels`,
  `Source`/`Destination`. Plus de 10 niveaux logiques à 100 MHz = à pipeliner.

## Dans quel ordre corriger

1. pipeline (insérer un registre) ;
2. simplifier la logique combinatoire ;
3. réessayer avec une autre directive ;
4. exception de timing **seulement** avec un protocole multi-cycle documenté ;
5. baisser la fréquence annoncée — et le **dire** dans le compte rendu.

## Rapporter

`WNS avant → WNS après`, utilisation (`Slice LUTs %`, `Slice Registers %`), chemin
critique avant/après, et ce qui a été changé. Jamais « le timing est bon » sans les
chiffres.
