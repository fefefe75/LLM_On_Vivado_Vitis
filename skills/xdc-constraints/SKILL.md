---
name: xdc-constraints
description: Use when adding or fixing FPGA constraints (create_clock, IOSTANDARD, PACKAGE_PIN, false paths) or when a build fails with DRC NSTD-1 / UCIO-1 / unconstrained paths.
---

# Contraintes XDC

Modèles : `templates/project/constraints/`. Erreurs DRC réelles et correctifs :
`docs/10-troubleshooting.md` §3. Fermeture du timing : `docs/07-timing-closure.md`.

## Sans contraintes, un design ne prouve rien

Sans `create_clock`, le rapport de timing contient littéralement
`There are no user specified timing constraints.` et aucun WNS/TNS : le build
« passe » mais rien n'a été vérifié.

```tcl
# constraints/timing.xdc — le minimum absolu pour un design à une horloge
create_clock -period 10.000 -name sys_clk -waveform {0.000 5.000} [get_ports i_clk]
```

## E/S : les deux DRC qui bloquent le bitstream

`ERROR: [DRC NSTD-1] Unspecified I/O Standard` et
`ERROR: [DRC UCIO-1] Unconstrained Logical Port` : chaque port doit avoir un
`IOSTANDARD` et une `PACKAGE_PIN` (donc connaître le board).

```tcl
set_property PACKAGE_PIN W5  [get_ports i_clk]
set_property IOSTANDARD LVCMOS33 [get_ports i_clk]
set_property PACKAGE_PIN U16 [get_ports {o_led[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {o_led[*]}]
```

Deux voies possibles :

| Situation | Solution |
|---|---|
| Vrai board | contraintes de brochage du board (voir sa doc / son master XDC) |
| Validation de logique **sans** board | `templates/vivado/build.tcl --allow-unconstrained 1` : abaisse la sévérité de NSTD-1/UCIO-1 via un pre-hook `write_bitstream` (méthode indiquée par Vivado lui-même) |

## Conventions à respecter

- Deux fichiers XDC : `timing.xdc` (horloges, I/O delay, exceptions) et
  `pins.xdc` (broches/IOSTANDARD). Un top de simulation n'a pas besoin de `pins.xdc`.
- **Ne pas contraindre un top sans ports** (ex. testbench) : Vivado refuse
  `get_ports` sur un port inexistant.
- Exceptions seulement si justifiées : `set_false_path` (chemin jamais actif),
  `set_clock_groups -asynchronous` (horloges indépendantes), `set_max_delay`.
  Un `set_false_path` mal placé masque une vraie violation de timing.
- Une horloge générée en interne : `create_generated_clock`, pas un second
  `create_clock`.

## Vérifier

```tcl
report_clock_networks -file reports/clocks.rpt     # les horloges attendues ?
check_timing          -file reports/check_timing.rpt  # ce qui n'est pas contraint
report_timing_summary -file reports/timing.rpt -warn_on_violation
```
`check_timing` liste les points non contraints : c'est la première chose à lire quand
un design « passe » trop facilement.
