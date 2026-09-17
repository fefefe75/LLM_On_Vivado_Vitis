# Contraintes XDC (horloges, E/S, exceptions)

Compétence associée : `skills/xdc-constraints/SKILL.md`. Modèles :
`templates/project/constraints/`. Messages DRC réels : `docs/10-troubleshooting.md` §3.

## 1. Le minimum vital

Un design **sans contrainte d'horloge** produit un rapport de timing contenant
exactement `There are no user specified timing constraints.` et aucun WNS/TNS :
il n'a donc rien vérifié. La première ligne de tout `.xdc` :

```tcl
create_clock -period 10.000 -name sys_clk -waveform {0.000 5.000} [get_ports i_clk]
```

`-period` en ns → 10 ns = 100 MHz. `[get_ports i_clk]` doit viser un **port réel** du
top (pas un signal interne, pas un port d'un sous-module, pas un port inexistant dans
un top de simulation).

## 2. E/S : sans brochage, pas de bitstream

Vérifié : `write_bitstream` échoue avec
`[DRC NSTD-1] Unspecified I/O Standard` **et** `[DRC UCIO-1] Unconstrained Logical Port`
quand les ports n'ont ni `IOSTANDARD` ni `PACKAGE_PIN` :

```tcl
# pins.xdc — exemple Basys 3 (xc7a35tcsg324-1)
set_property PACKAGE_PIN W5  [get_ports i_clk]
set_property IOSTANDARD LVCMOS33 [get_ports i_clk]
set_property PACKAGE_PIN U16 [get_ports {o_led[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {o_led[*]}]
```
Le brochage vient de la documentation du board ou de son master XDC — jamais
d'invention. Pour un design sans board (validation de logique), utiliser
`templates/vivado/build.tcl --allow-unconstrained 1`.

## 3. Structure des fichiers

| Fichier | Contenu | Utilisé à la synthèse ? |
|---|---|---|
| `constraints/timing.xdc` | `create_clock`, I/O delay, exceptions | oui |
| `constraints/pins.xdc` | `PACKAGE_PIN`, `IOSTANDARD` | oui |
| `constraints/debug.xdc` | `mark_debug`, ILA | oui |

Un `.xdc` peut aussi être ajouté par étape (`-fileset constrs_1`) ; ne jamais mettre
un `pins.xdc` d'un board dans la simulation.

## 4. Contraintes avancées (avec discernement)

```tcl
# E/S avec horloge externe (souvent nécessaire sur un vrai board)
set_input_delay  -clock sys_clk -max 2.0 [get_ports i_data*]
set_output_delay -clock sys_clk -max 2.0 [get_ports o_data*]

# horloges réellement indépendantes (asynchrones)
set_clock_groups -asynchronous -group [get_clocks sys_clk] -group [get_clocks usb_clk]

# chemin qui ne doit jamais être analysé (justifier en commentaire !)
set_false_path -from [get_ports i_rst_async]

# horloge produite en interne (MMCM/PLL, diviseur)
create_generated_clock -name clk_div -source [get_ports i_clk] -divide_by 2 [get_pins u_div/Q]
```

Un `set_false_path` mal placé **cache** une vraie violation. Règle d'agent : ne
jamais ajouter d'exception de timing pour faire passer un design ; l'ajouter
seulement quand le protocole du design le justifie, et l'écrire en commentaire.

## 5. Vérifier ses contraintes

```tcl
report_clock_networks -file reports/clocks.rpt        # les horloges sont-elles là ?
check_timing          -file reports/check_timing.rpt  # points non contraints
report_timing_summary -file reports/timing.rpt -warn_on_violation
```
`check_timing` est la commande à lancer quand un design « passe » trop facilement :
elle liste ce que Vivado ne peut pas vérifier faute de contraintes.

## 6. Ordre de travail conseillé

1. écrire le RTL et le testbench → simuler ;
2. écrire `timing.xdc` (au minimum l'horloge) ;
3. synthèse → lire `check_timing` ;
4. `pins.xdc` avec le brochage du board ;
5. implémentation → timing → bitstream ;
6. débogage matériel (ILA) seulement après un design qui tient la fréquence.
