# `rtl/` — le code VHDL synthétisable

**Un module = un fichier**, nom du fichier = nom de l'entité :

```
rtl/
├── compteur.vhd        entity compteur        (le module)
├── pkg_utilitaires.vhd package utilitaires    (les types, fonctions, constantes)
└── top.vhd             entity top            (l'instanciation des modules)
```

## Règles

- **Que du synthétisable** : pas de `wait for`, pas de `after`, pas d'`assert`
  de simulation, pas d'initialisation de signal dans la déclaration.
  Un testbench posé ici finirait dans la synthèse : il va dans `tb/`.
- Bibliothèques autorisées : `ieee.std_logic_1164`, `ieee.numeric_std`.
  Jamais `std_logic_arith` ni `std_logic_unsigned` (non standard, sources de
  bugs silencieux entre outils).
- Un `process(i_clk)` par bloc séquentiel, un seul style de reset
  (actif haut, synchrone) dans tout le design — voir `../CONTRIBUTING.md`.
- Ports : `i_` entrée, `o_` sortie, `s_` signal, `C_` constante, `p_` process.
- Pas de chemin de fichier absolu, pas de dépendance à une carte dans le RTL :
  les broches sont dans `../constraints/`.

## Vérifier

```bash
make lint     # GHDL analyse tout rtl/**/*.vhd en VHDL-2008, dans l'ordre des dépendances
```

`make lint` prouve que le code est *analysable*. Il ne prouve pas qu'il
*fonctionne* : c'est le rôle de `make sim` (dossier `../tb/`).
