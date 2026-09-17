---
name: eda-troubleshooting
description: Use when a Vivado, XSim, cocotb or Vitis command fails and the error message must be turned into a fix.
---

# Dépanner un échec d'outil EDA

Catalogue complet, **messages authentiques** : `docs/10-troubleshooting.md`.
Chercher d'abord le code entre crochets (`[Synth 8-36]`, `[Common 17-69]`, `[DRC UCIO-1]`).

## Méthode (dans cet ordre)

1. Lire **le code de message**, pas seulement « ERROR ».
2. Aller au log du **run** concerné, pas la console tronquée :
   ```bash
   grep -nE "^(ERROR|CRITICAL WARNING):" vivado.log
   grep -nE "^(ERROR|CRITICAL WARNING):" <prj>.runs/impl_1/runme.log
   ```
3. Corriger **une** cause, relancer l'étape la plus précoce possible.
4. Vérifier le code retour de la commande, pas la sortie standard.

## Les plus fréquents (réels, Vivado 2025.2)

| Message | Correctif |
|---|---|
| `[Common 17-69] Run 'synth_1' needs to be reset before launching` | `reset_run synth_1` (ou réutiliser le run à 100 %) |
| `[Common 17-37] Directory in which file timing.rpt is to be written does not exist` | `file mkdir reports` avant `report_* -file` |
| `[Common 17-53] No open design` | `open_run <run>` avant un rapport |
| `[Vivado 12-172] File or Directory 'x.vhd' does not exist` | chemin relatif erroné : `file normalize`, `glob -nocomplain` |
| `[Coretcl 2-106] Specified part could not be found` | `get_parts xc7z020*` pour voir ce qui est installé |
| `[Synth 8-36] 'x' is not declared` | port/signal non déclaré |
| `[Synth 8-5826] no such design unit 'x' in library 'work'` | fichier manquant ou ordre de compilation (`update_compile_order`) |
| `[Synth 8-2716] syntax error near 'process'` | `end if;`/`end process;` manquant |
| `[DRC NSTD-1]` / `[DRC UCIO-1]` | contraindre IOSTANDARD et PACKAGE_PIN (ou `--allow-unconstrained 1` pour tester la logique) |
| `[Vivado 12-1345] Error(s) found during DRC. Bitgen not run.` | conséquence des DRC ci-dessus |
| cocotb : `Couldn't find makefile for simulator: "xsim"` | cocotb **ne supporte pas** XSim → GHDL/Icarus/Verilator/Questa, ou testbench VHDL |
| GHDL : `cannot find entity or configuration x` | `--std=08` absent à l'exécution, top mal nommé, ou `build_dir` ≠ `test_dir` |
| cocotb : `RuntimeError: Attempting settings a value during the ReadOnly phase` | avancer d'un événement avant d'écrire après un `ReadOnly()` |
| Tcl : `missing close-brace: possible unbalanced brace in comment` | accolade littérale dans un commentaire/chaîne à l'intérieur d'un bloc `{...}` → échapper (`\{`) |

## Réflexe anti-devinette

Quand le comportement d'une commande est incertain : `info commands <cmd>`,
`<cmd> -help`, `get_parts`, ou un petit script de sonde. Une supposition plausible
coûte plus cher qu'une vérification de 30 secondes.
