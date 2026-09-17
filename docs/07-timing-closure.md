# Fermeture du timing (lire un rapport, agir)

## 1. Lire le résumé

Rapport réel (Vivado 2025.2, compteur 24 bits, xc7z020clg400-1, horloge 100 MHz) :

```
    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  ...
    -------      -------  ---------------------  -------------------      -------      -------  ...
      7.087        0.000                      0                   24        0.213        0.000  ...
```
| Champ | Signification | Seuil |
|---|---|---|
| **WNS** (Worst Negative Slack) | marge du pire chemin *setup* | doit être **≥ 0** |
| **TNS** | somme des violations setup | doit être **0** |
| **TNS Failing Endpoints** | nombre de bascules en violation setup | doit être **0** |
| **WHS / THS** | équivalent *hold* | WHS ≥ 0, THS = 0 |
| **WPWS / TPWS** | marge sur la largeur d'impulsion (horloges) | ≥ 0 |

Un rapport sans tableau mais avec `There are no user specified timing constraints.`
signifie : **aucune horloge contrainte** (voir `docs/06-constraints-xdc.md`).

Chemin critique (morceau réel du même rapport) :
```
Slack (MET) :             7.087ns  (required time - arrival time)
  Source:                 s_count_reg[1]/C
  Destination:            s_count_reg[21]/D
  Data Path Delay:        2.809ns  (logic 1.940ns (69%)  route 0.869ns (31%))
  Logic Levels:           6  (CARRY4=6)
```
À regarder dans cet ordre : slack, **Logic Levels** (profondeur), répartition
logic/route, source et destination.

## 2. Les actions, de la plus efficace à la moins

| # | Action | Effet typique |
|---|---|---|
| 1 | **Pipeliner** le chemin (insérer un registre au milieu) | le plus fort : divise la profondeur logique |
| 2 | Réduire la logique combinatoire (comparateur en cascade, arbre d'addition équilibré, `unsigned` plutôt que `integer`) | moyen à fort |
| 3 | Laisser Vivado réessayer : `launch_runs impl_1 -to_step route_design -directive Explore` (ou `AggressiveExplore`) | variable |
| 4 | `phys_opt_design` (activé par défaut dans les runs ; utile en flux non-project) | faible à moyen |
| 5 | `set_max_delay` / `set_multicycle_path` **avec un protocole multi-cycle documenté** | fort mais dangereux : masque la réalité si mal utilisé |
| 6 | Baisser la fréquence annoncée (`-period` plus grand) | fort — mais c'est un **aveu** : le dire explicitement à l'utilisateur |
| 7 | Changer de famille de FPGA / de vitesse (grade -2, -3) | hors périmètre logiciel |

Règle : ne jamais « fermer » le timing en ajoutant une exception sans le dire.
Un design qui ne tient pas 100 MHz se pipeline ou s'annonce à 50 MHz.

## 3. Où agir : le tableau d'utilisation

```
| Slice LUTs*             |    1 |     0 |          0 |     53200 | <0.01 |
| Slice Registers         |   24 |     0 |          0 |    106400 |  0.02 |
| Bonded IOB              |    5 |     0 |          0 |       125 |  4.00 |
```
L'étoile (`Slice LUTs*`) et `<0.01` sont normaux **après synthèse** : le compte est
estimé, et le pourcentage peut être sous la résolution du rapport. Après
implémentation, ces marques disparaissent (le script `build.tcl` génère les deux
états : `post_synth_*` et `*` finaux).

Saturation typique : > 80 % de LUTs ou de BRAM → il faut revoir l'architecture avant
de parler de timing.

## 4. Méthode d'agent

1. Lancer l'implémentation, puis lire **WNS/TNS/THS** (jamais affirmer sans ces nombres).
2. Si WNS < 0 : ouvrir `report_timing_summary`, lire la source/destination du pire
   chemin et le nombre de niveaux logiques.
3. Corriger **le RTL** (pipeline, factorisation) ; ne pas toucher aux contraintes
   sauf protocole explicite.
4. Relancer **l'implémentation seule** (pas la synthèse) pour itérer vite.
5. Rapporter : `WNS avant → WNS après`, et ce qui a été changé.
