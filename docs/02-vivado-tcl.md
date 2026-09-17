# Piloter Vivado en Tcl (mode batch)

Doc de référence pour un agent : tout ce qui suit a été exécuté sur **Vivado 2025.2
(lin64)**. Les sorties citées sont recopiées telles quelles.

Ne jamais éditer un `.xpr` à la main : on régénère depuis un script (`-force`).

---

## 1. Les deux flux, et lequel choisir

| | Project mode | Non-project mode |
|---|---|---|
| Entrée | `create_project` → `.xpr` | `read_vhdl`/`read_verilog` |
| Runs | `launch_runs` / `wait_on_run` (processus séparés) | commandes en séquence dans la même session |
| Reprise après plantage | oui (par run) | non (à relancer) |
| Rapport | projet explorable dans l'IDE | plus léger, scriptable en CI |
| Recommandé pour | projet réel, bitstream, Vitis | vérification rapide, design jetable |

Les deux scripts sont fournis : `templates/vivado/create_project.tcl`,
`templates/vivado/build.tcl` (project mode) et
`templates/vivado/nonproject_build.tcl` (non-project mode).

## 2. Project mode — le flux complet (et vérifié)

```bash
source ~/vivado/2025.2/Vivado/settings64.sh
vivado -mode batch -source templates/vivado/create_project.tcl -nolog -nojournal \
       -tclargs --name prj --part xc7z020clg400-1 --top top
vivado -mode batch -source templates/vivado/build.tcl -nolog -nojournal \
       -tclargs --xpr prj/prj.xpr --to bitstream --jobs 4
```
Sortie réelle de `create_project.tcl` :
```
== create_project : prj (xc7z020clg400-1, top=top, VHDL)
== 1 fichier(s) HDL ajoute(s)
== 1 contrainte(s) XDC ajoutee(s)
== projet cree : /tmp/vivado_real/prj/prj.xpr
```
Sortie réelle de `build.tcl` (fin de course, avec brochage volontairement absent) :
```
== synth_1 : PROGRESS=100% STATUS=synth_design Complete!
== impl_1 : PROGRESS=100% STATUS=write_bitstream Complete!
== TIMING: WNS = 7.317 ns
== BITSTREAM: /tmp/vivado_real/prj/prj.runs/impl_1/top.bit
== termine
```

Le squelette minimal, si tu écris ton propre script :

```tcl
create_project $name $dir/$name -part $part -force
set_property target_language VHDL [current_project]
add_files -fileset sources_1 [glob rtl/*.vhd]
add_files -fileset constrs_1 [glob constraints/*.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 4      ; wait_on_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 4 ; wait_on_run impl_1
open_run impl_1
report_timing_summary -file reports/timing_summary.rpt
write_bitstream est deja fait ; le .bit est dans <prj>.runs/impl_1/<top>.bit
```

### Cinq pièges vérifiés (chacun a coûté une erreur réelle)

1. **Relancer un run terminé échoue** —
   `ERROR: [Common 17-69] Command failed: Run 'synth_1' needs to be reset before launching.`
   → tester `get_property PROGRESS [get_runs synth_1]` : si `100%`, réutiliser ;
   sinon `reset_run synth_1` avant `launch_runs`. `build.tcl` implémente
   `run_or_reuse` pour être idempotent.
2. **Vivado ne crée pas les dossiers de rapport** —
   `ERROR: [Common 17-37] Directory in which file timing.rpt is to be written does not exist`
   → `file mkdir reports` **avant** `report_*  -file`.
3. **WNS doit être lu design ouvert** — `get_timing_paths` après `close_design`
   ne renvoie plus de chemin. Lire le slack avant de fermer :
   ```tcl
   open_run impl_1
   set paths [get_timing_paths -delay_type max -max_paths 1]
   set wns [expr {[llength $paths] ? [get_property SLACK [lindex $paths 0]] : 0.0}]
   ```
4. **Un design sans IOSTANDARD/LOC n'a pas de bitstream** — les DRC `NSTD-1` et
   `UCIO-1` bloquent `write_bitstream` (voir `docs/10-troubleshooting.md`, §3, et
   `--allow-unconstrained 1` pour le cas « validation sans carte »).
5. **Le nom du top n'est pas validé** par `set_property top …` : l'erreur
   n'apparaît qu'à la synthèse. Toujours lancer la synthèse avant de conclure.

## 3. Vérifier plutôt que deviner

Un agent ne doit pas inventer d'options. Trois introspection fiables :

```tcl
get_parts xc7z020*                    ;# les parties REELLEMENT installees
info commands write_hw_def            ;# existe ? (vide en 2025.2)
set_property STATUS [get_runs impl_1] ;# etat reel d'un run
```
En ligne de commande : `vivado -mode batch -source <(echo 'puts [get_parts xc7z020*]')`
ou plus simplement un petit `.tcl` de sonde (`/tmp/probe.tcl` dans ce dépôt).

Vérifié en 2025.2 : `write_hw_platform` existe, **`write_hw_def` n'existe plus**
(remplacée depuis 2020.x). Les commentaires de version comptent : une commande qui
existait dans un tutoriel de 2019 peut avoir disparu.

## 4. Lire les logs et les messages

Formats authentiques (Vivado 2025.2) :
```
WARNING: [Board 49-26] cannot add Board Part ... 
ERROR: [Synth 8-36] 'o_q' is not declared [/chemin/casse.vhd:8]
ERROR: [Synth 8-5826] no such design unit 'bloc_inexistant' in library 'work' [/chemin/wrapper.vhd:6]
ERROR: [Coretcl 2-106] Specified part could not be found.
ERROR: [Vivado 12-172] File or Directory '/chemin/nexistepas.vhd' does not exist
ERROR: [DRC NSTD-1] Unspecified I/O Standard: 5 out of 5 logical ports ...
ERROR: [Vivado 12-1345] Error(s) found during DRC. Bitgen not run.
```
Structure : `SEVERITE: [Categorie Numero] texte [fichier:ligne]`. Le numéro
`[Cat NNNN]` est l'identifiant à chercher (support AMD, `docs/10-troubleshooting.md`).

Où chercher :
```bash
grep -nE "^(ERROR|CRITICAL WARNING):" vivado.log                       # console globale
grep -nE "^(ERROR|CRITICAL WARNING):" prj.runs/synth_1/runme.log        # un run precis
grep -nE "^(ERROR|CRITICAL WARNING):" prj.runs/impl_1/runme.log
```
Le serveur MCP (`job_log`) fait exactement ce filtrage et renvoie les 40 dernières
erreurs + les compteurs, sans rapatrier 30 000 lignes.

**Important** : une `ERROR:` dans un script batch **interrompt** le script et le
code retour de `vivado` est non nul. C'est ce qu'il faut tester, pas la sortie
standard.

## 5. Contraintes et rapports utiles

```tcl
# avant implémentation : les chemins E/S et les horloges doivent exister
report_clock_networks   -file reports/clocks.rpt
check_timing            -file reports/check_timing.rpt
# après implémentation
report_timing_summary   -file reports/timing_summary.rpt -max_paths 10 -warn_on_violation
report_utilization      -file reports/utilization.rpt
report_drc              -file reports/drc.rpt
report_clock_utilization -file reports/clock_utilization.rpt
report_power            -file reports/power.rpt
```
Sans `create_clock`, le rapport de timing contient exactement
`There are no user specified timing constraints.` et **aucun** tableau WNS/TNS :
le design « passe » sans rien prouver. C'est le piège n°1 du débutant.

## 6. Export vers Vitis et programmation

```tcl
write_hw_platform -fixed -include_bit -force -file export/design.xsa   ;# 2020.2+
```
`-include_bit` embarque le bitstream dans l'XSA (nécessaire pour un `BOOT.bin`
autonome). C'est le point de jonction avec Vitis (`docs/08-vitis.md`).

Programmation (script fourni : `templates/vivado/program.tcl`) :
```tcl
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
set dev [lindex [get_hw_devices] 0]
set_property PROGRAM.FILE /chemin/top.bit $dev
program_hw_devices $dev
close_hw_manager
```

> Statut de vérification : le flux complet jusqu'au **bitstream** a été exécuté et
> vérifié sur cette machine. La **programmation JTAG** (`program_hw_devices`) n'a
> PAS été exécutée (aucune carte branchée) : les commandes viennent de la
> documentation AMD et du message d'erreur de Vivado, pas d'un essai matériel.
> C'est une action matérielle : elle exige l'accord explicite de l'utilisateur.

## 7. Ce qu'on ne met PAS dans git

`.gitignore` fourni à la racine couvre : `*.xpr`, `*.jou`, `*.log`, `.Xil/`,
`*.runs/`, `*.cache/`, `.ip_user_files/`, `*.dcp`, `*.bit`, `*.xsa`, `sim_build/`,
`xsim.dir/`, `*.wdb`, `results.xml`. Un agent doit écrire dans `rtl/`, `tb/`,
`constraints/`, `scripts/`, `software/` — pas dans les dossiers du projet.
