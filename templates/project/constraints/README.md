# `constraints/` — les contraintes .xdc

Tout ce qui dépend de la **carte** et non du design : c'est ce qui permet de
réutiliser le même `rtl/` sur un autre FPGA sans le modifier.

```
constraints/
├── pins.xdc        affectation des broches (PACKAGE_PIN, IOSTANDARD)
├── timing.xdc      horloges (create_clock, set_input_delay) et faux chemins
└── debug.xdc       ILA / VIO (optionnel, à retirer pour les builds de release)
```

## Contenu typique

```tcl
# --- horloge principale (100 MHz sur le PMOD/cristal de la carte) -----------
create_clock -period 10.000 -name sys_clk [get_ports i_clk]

# --- broches ----------------------------------------------------------------
set_property -dict {PACKAGE_PIN E3 IOSTANDARD LVCMOS33} [get_ports i_clk]
set_property -dict {PACKAGE_PIN J5 IOSTANDARD LVCMOS33} [get_ports {o_q[*]}]

# --- chemins qui ne doivent pas être contraints (horloges asynchrones) ------
set_false_path -from [get_clocks clk_aux] -to [get_clocks sys_clk]
```

## Règles

- Un fichier par préoccupation (`pins`, `timing`, `debug`) : un `.xdc` de
  500 lignes mêlant tout est introuvable en cas d'erreur de placement.
- Chaque contrainte doit nommer la carte pour laquelle elle est écrite, en
  commentaire en tête de fichier (référence + version).
- Jamais de contrainte « pour faire passer le timing » sans le dire : un faux
  chemin ajouté pour masquer une violation est un bug documenté, pas un fix.
- Les `.xdc` ne sont pas ajoutés à la main dans le GUI Vivado : le script
  `scripts/create_project.tcl` les prend en charge (`add_files -fileset constrs_1`),
  sinon la prochaine régénération les perd.
- Une contrainte non synthétisable (`set_false_path`) doit rester justifiée par
  un commentaire ou une note dans `../doc/`.
