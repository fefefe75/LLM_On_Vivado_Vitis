# Contribuer à ce projet — règles courtes, non négociables

Ce projet est destiné à être lu et modifié autant par des humains que par des
agents LLM : les règles ci-dessous existent pour qu'une relecture ou une
vérification automatique soit possible.

## 1. Conventions de nommage

| Élément | Préfixe | Exemple |
|---|---|---|
| Port d'entrée | `i_` | `i_clk`, `i_rst`, `i_data` |
| Port de sortie | `o_` | `o_q`, `o_valid` |
| Signal interne | `s_` | `s_compteur` |
| Constante générique | `C_` | `C_LARGEUR` |
| Label de process | `p_` | `p_comptage` |
| Entité / fichier | minuscules, `_` | `compteur.vhd` → `entity compteur` |
| Générics | `g_` | `g_INCREMENT` |

Horloge `i_clk`, reset `i_rst` (actif haut, synchrone). Un seul style de reset
par design : jamais un module en reset asynchrone et son voisin en synchrone.

## 2. Un module = un fichier

Un fichier contient **une** entité et son architecture, ou **un** package.
Le nom du fichier est celui de l'entité (`rtl/compteur.vhd` → `entity compteur`).
Pas de `entity`/`architecture` secondaire « au cas où » dans le même fichier.

## 3. Reset synchrone unique

```vhdl
process (i_clk) is
begin
  if rising_edge(i_clk) then
    if i_rst = '1' then
      s_q <= (others => '0');
    else
      s_q <= ...;
    end if;
  end if;
end process;
```

Un seul signal de reset, commun à tout le design, actif au même niveau partout.
Si un cas impose l'asynchrone, il est documenté dans le fichier et isolé.

## 4. Tout test doit être reproductible à graine fixe

- La graine vient de `COCOTB_RANDOM_SEED` (défaut `SEED=1234` du Makefile) :
  dans un test, n'appelez jamais `random` sans `seed=...`.
- Un test qui passe une fois sur deux est un test cassé, pas un test « instable ».
- Un test doit être auto-vérifiant : il échoue tout seul (`assert`), il ne se
  contente pas d'afficher des valeurs.
- Toute affirmation de bon fonctionnement doit être accompagnée de la sortie
  réelle de l'outil (`make sim`, `make lint`, log de build).

## 5. Aucun fichier généré dans git

`sim_build/`, `results.xml`, `*.ghw`, `*.vcd`, `*.fst`, `*.xpr`, `.Xil/`,
`.runs/`, `*.bit`, `*.elf`, `build/`, `__pycache__/` : jamais commités (voir
`.gitignore`). Un fichier généré commité devient une source de vérité fausse :
on régénère à partir du script, on ne versionne pas le résultat.

## 6. Une source AMD par affirmation sur Vivado/Vitis

Toute affirmation de comportement de Vivado, Vitis, XSCT ou d'une IP doit être
adossée à une source officielle (`docs.amd.com`, UG835, UG973, UG1400, ou la
sortie réelle de l'outil). Deux pièges à ne pas oublier :

- les deux générations de Vitis sont incompatibles : classique/XSCT `<= 2023.1`
  (`xsct script.tcl`) et unifiée `>= 2023.2` (`vitis -s script.py`) ;
- ne jamais inventer une option Tcl : en cas de doute, `<outil> -help` et on
  cite la sortie réelle, ou on cherche dans `docs/`.

## 7. Avant de proposer une modification

```bash
make lint        # le VHDL s'analyse (GHDL, VHDL-2008)
make sim         # les tests passent, à graine fixe
make tcl-check   # les scripts .tcl sont syntaxiquement valides
git status       # aucun artefact généré dans le diff
```

Rapport attendu : *ce qui a changé* → *la commande lancée* → *la sortie réelle*
(PASS/FAIL, WNS, erreurs) → *l'étape suivante*. Pas d'adjectif sans log derrière.
