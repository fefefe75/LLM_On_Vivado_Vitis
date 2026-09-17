# 07 — Mini-GPU : un accélérateur SIMT qui calcule la fractale de Mandelbrot

Cet exemple construit un **petit GPU en VHDL** : un moteur SIMT à `C_LANES` voies qui
calcule une image de Mandelbrot en parallèle, avec répartiteur de travail, divergence de
voies et file de résultats. Il est **synthesizable sur la puce de ce dépôt**
(`xc7z020clg400-1`) et **vérifié par simulation** contre un modèle de référence.

L'objectif n'est pas de battre un CPU (la comparaison honnête est plus bas, et le CPU
gagne en débit brut) : c'est de montrer, avec des chiffres mesurés, **comment on
parallélise vraiment** et ce que coûte cette parallélisation.

---

## 1. Pourquoi Mandelbrot est le bon « kernel »

| Propriété | Conséquence pour le matériel |
|---|---|
| Chaque pixel est indépendant | aucun verrou, aucun partage de données entre voies |
| Le travail par pixel est **variable** (1 à `C_MAX_ITER` itérations) | divergence : certaines voies finissent très vite, d'autres bloquent |
| Le calcul est itératif et arithmétique (`z ← z² + c`) | se prête à un automate + multiplicateurs dédiés |
| Le résultat est **vérifiable visuellement** | une seule image fausse se voit immédiatement |

## 2. Architecture (l'analogie GPU, terme par terme)

```
                        ┌──────────────── repartiteur ────────────────┐
   pixel suivant ──────►│ balayage ligne par ligne, 1 point/cycle     │
   (x, y)               │ gate : (voie libre) ET (creneau libre)      │
                        └──────┬─────┬─────┬─────────┬────────────────┘
                               │     │     │         │     c = x0 + x*dx + i*(y0 + y*dy)
                     ┌─────────▼─┐ ┌─▼───────┐ ┌───────▼─┐      (2 multiplicateurs PARTAGES)
                     │  lane 0   │ │ lane 1  │ │ ... 15  │      1 automate z←z²+c par voie
                     │ 3 mult.   │ │ 3 mult. │ │         │      3 cycles par iteration
                     └─────┬─────┘ └────┬────┘ └────┬────┘
                           │            │           │  o_done + iterations
                        ┌──▼────────────▼───────────▼──┐
                        │  file de resultats (2 slots  │  contre-pression : un résultat
                        │  par voie, pointeurs)        │  ne peut jamais être écrasé
                        └──────────────┬───────────────┘
                                       │  valid / ready
                              o_px_x, o_px_y, o_px_iter, o_px_escaped
```

| Le vocabulaire GPU | Ici | Fichier |
|---|---|---|
| thread / CUDA core | une voie (`lane`) : un automate qui itère `z ← z² + c` | `rtl/mandelbrot_lane.vhd` |
| distributeur de blocs | le répartiteur : donne un pixel à la première voie libre (balayage circulaire) | `rtl/mandelbrot_gpu.vhd` |
| warp divergence | une voie dont le point reste dans l'ensemble tourne `C_MAX_ITER` fois et bloque sa place | mesurée, §4 |
| unités partagées du SM | le générateur de `c` (2 multiplications pour **toutes** les voies) | `rtl/mandelbrot_gpu.vhd` |
| file de sortie | 2 créneaux par voie avec contre-pression | `rtl/mandelbrot_gpu.vhd` |
| registres de configuration | ports `o_cfg_*` : le design **déclare** ses paramètres | `rtl/mandelbrot_gpu.vhd` |

L'arithmétique est en **virgule fixe Q26 sur 32 bits** (plage ±32, précision ~2·10⁻⁹,
soit ~10⁷ fois plus fin que le pas d'un pixel dans la vue classique).

## 3. Ce qui est vérifié, et comment

Tout est reproductible avec les commandes données en §6.

| Ce qui est prouvé | Résultat mesuré |
|---|---|
| Correction : 96×64 pixels comparés **exactement** au modèle Python | **6144 / 6144 pixels identiques**, 0 divergence |
| Correction : 320×240 pixels (image pleine), 16 voies, 128 itérations | **76800 / 76800 pixels identiques** |
| Débit réel du moteur (8 voies, 96×64, 64 itérations) | **50528 cycles** pour 6144 pixels = **8,22 cycles/pixel** |
| Débit réel du moteur (16 voies, 320×240, 128 itérations) | **572057 cycles** pour 76800 pixels = **7,45 cycles/pixel** |
| Efficacité parallèle (travail utile / voies × cycles) | **90,2 %** (8 voies) et **86,8 %** (16 voies) |
| Contrôle croisé VHDL ↔ Python ↔ C | total d'itérations **233 737** dans les trois implémentations (image 128×96) |
| Synthèse + placement-routage réels (Vivado 2025.2, `xc7z020clg400-1`) | voir §5 |
| Image produite **par le RTL** (pas par un modèle logiciel) | `tb/images/mandelbrot_petite.png` |

> Transparence sur l'état des mesures : la mesure 320×240 a été interrompue *juste
> après* la comparaison des pixels et l'affichage des métriques, mais *avant* l'écriture
> de son image PNG et la ligne `passed` (arrêt volontaire de la machine pour libérer la
> place à l'IHM Vivado). Aucune ligne d'écart de pixel n'a été produite. Le détail est
> reproductible en une commande (§6). Les chiffres de synthèse du §5, eux, ont été obtenus
> avant un recâblage purement structurel des sorties (signaux internes au lieu d'une
> lecture de ports `out`, §8), mais **ce recâblage a été validé depuis** : compilation
> Vivado réussie dans le projet de l'IHM (`synth_design completed successfully`, 32 s) et
> re-simulation complète du banc (48×32, les deux tests `passed`).

Le modèle de référence Python refait le **même** calcul entièrement en entier, opération
par opération, débordements 32 bits compris — la comparaison est une égalité, pas une
tolérance. Et le test lit la fenêtre du plan complexe et le format Q **sur les ports de
configuration du design** : il vérifie donc l'arithmétique du RTL, pas une constante
recopiée à la main.

![image calculée par le RTL](tb/images/mandelbrot_petite.png)

*(image 96×64 obtenue en simulation, écrite par le banc de test — voir §6)*

## 4. Débit mesuré (et non espéré)

Deux configurations mesurées sur la même vue classique, en comparant à chaque fois
**tous** les pixels au modèle Python :

| Image | Voies | Itérations max | Cycles du rendu | Cycles / pixel | Efficacité parallèle | Perte par divergence |
|---|---|---|---|---|---|---|
| 48 × 32 (1536 px) | 8 | 32 | **8 271** | **5,38** | **85,2 %** | 14,8 % |
| 96 × 64 (6144 px) | 8 | 64 | **50 528** | **8,22** | **90,2 %** | 9,8 % |
| 320 × 240 (76800 px) | 16 | 128 | **572 057** | **7,45** | **86,8 %** | 13,2 % |

Les trois lignes sont des mesures réelles. La première (48×32) est celle qui a été
rejouée **après** le recâblage des sorties décrit au §8 : ses **deux tests passent**
(`test_petite_image_egale_le_modele` et `test_image_complete_et_image_png`), donc le RTL
tel qu'il est livré dans ce dépôt est bien vérifié par simulation, pas seulement analysé.

L'efficacité est calculée **uniquement à partir de la sortie du design** :
`travail utile = Σ(3 × itérations + 2)` sur tous les pixels, comparé à
`voies × cycles`. Elle mesure donc directement ce que coûte la divergence — sur cette
image, **13 % du temps de calcul de 16 voies est perdu** parce que des points de
l'ensemble immobilisent leur voie pendant que d'autres sont libérées. C'est le phénomène
central d'un GPU, ici chiffré.

### Mise à l'échelle : ce que coûte vraiment d'ajouter des voies

Balayage complet **mesuré** (image 48×32, 32 itérations) : chaque configuration est
élaborée, simulée, ses cycles sont lus dans le compteur matériel `o_cycles`, et ses
1536 pixels sont comparés au modèle Python.

| Voies | Cycles du rendu | Cycles / pixel | Gain vs 1 voie | Efficacité parallèle |
|---|---|---|---|---|
| 1 | 60 977 | 39,70 | 1,00× | **92,4 %** |
| 2 | 30 915 | 20,13 | **1,97×** | 91,2 % |
| 4 | 15 982 | 10,41 | **3,82×** | 88,2 % |
| 8 | 8 270 | 5,38 | **7,37×** | 85,2 % |
| 16 | 4 895 | 3,19 | **12,46×** | 72,0 % |

Ce que ce tableau enseigne, et qu'aucune formule ne remplace :

- jusqu'à 8 voies le gain suit presque le nombre de voies (7,37× pour 8) ;
- **à 16 voies il décroche** (12,46× pour 16) et l'efficacité tombe à 72 % : c'est la
  divergence (des pixels de l'ensemble immobilisent leur voie jusqu'à 32 itérations)
  aggravée par la petite image (1536 pixels ÷ 16 voies = 96 pixels par voie, donc la
  fin du rendu s'exécute à quelques voies seulement) ;
- l'efficacité est **maximale à 1 voie** (92,4 %) : par construction, aucune divergence
  entre voies. Ajouter des voies ne donne pas « ×N » gratuitement — c'est la leçon
  centrale d'un GPU.

Reproductible en une commande : `cd tb && make bench`.

> Correction d'une estimation que j'avais écrite ici : j'avais annoncé « GHDL simule ce
> design à ~500 cycles/s, donc le balayage est long ». **C'était faux** — c'était mon
> banc de test qui coûtait 0,6 ms de Python par cycle d'horloge. GHDL est en réalité
> rapide (~120 000 cycles/s sur ce design : les 60 978 cycles de la configuration à
> 1 voie se simulent en ~5 s). Le balayage complet a donc été exécuté, et la leçon
> utile est celle-là : **mesurer l'outil, pas le supposer** — même quand on se trompe
> soi-même (voir `skills/cocotb-testbench`, section « mesurer au lieu de poller »).

## 5. Coût matériel et fréquence (synthèse Vivado 2025.2)

Synthèse **et** placement-routage réels, Vivado v2025.2, `xc7z020clg400-1`, image
640×480, `max_iter=128`, horloge contrainte à 100 MHz (`constraints/timing.xdc`) :

| Voies | LUT | Basc. | DSP48E1 | DSP / voie | WNS après P&R | F max estimée | Tient 100 MHz ? |
|---|---|---|---|---|---|---|---|
| 8 | 3604 (6,8 %) | 2745 (2,6 %) | 99 (45 %) | 12,4 | **+0,244 ns** | **102,5 MHz** | ✅ oui |
| 16 | 7186 (13,5 %) | 5937 (5,6 %) | 195 (88,6 %) | 12,2 | **−1,583 ns** | **86,3 MHz** | ❌ non |

Trois enseignements tirés de ces chiffres, pas de la théorie :

1. **~12 DSP48 par voie** : trois multiplications 32×32 par voie, chacune répartie sur
   plusieurs DSP48E1. La puce n'en a que 220 → **18 voies maximum**. Le plafond n'est pas
   la logique (13 % de LUT à 16 voies) mais les multiplicateurs.
2. **Ajouter des voies coûte de la fréquence** : 8 voies tiennent 100 MHz, 16 voies non
   (86 MHz). Le chemin critique est le multiplieur 32×32 non pipeliné, et le
   répartiteur qui dessert 16 voies en allonge le fanout.
3. **La comparaison avec une implémentation publiée sur la même puce** : `delhatch/Zedboard_Mandel`
   place 9 moteurs en saturant les 220 DSP (≈ 24 DSP par moteur) ; ici 16 voies en
   consomment 195 (≈ 12 par voie), soit **~2× plus économe par voie**. La contrepartie
   est la fréquence (86 MHz contre 90 MHz annoncés là-bas) et un pipeline moins profond.

Débit qui en découle : à 3 cycles par itération, une voie fait **0,33 itération par
cycle**. 8 voies à 100 MHz → **267 Miter/s** ; 16 voies à 86 MHz → **458 Miter/s**.

> Piste d'optimisation chiffrée, **non implémentée** : pipeliner les trois
> multiplications (1 itération par cycle au lieu de 3) triplerait le débit par voie, soit
> ~1,4 Giter/s à 16 voies — au prix de 3× plus de DSP, donc de moins de voies par puce.
> C'est exactement l'arbitrage que fait un vrai GPU entre profondeur de pipeline et
> nombre de cœurs.

## 6. Comment lancer

```bash
export PATH=/tmp/ghdl_tool/bin:$HOME/Documents/mon_env/mon_env/bin:$PATH   # GHDL + cocotb

cd tb
make                                   # 96x64, 8 voies : test complet + image
make bench                             # tableau d'accélération 1/2/4/8/16 voies

# variantes (l'API cocotb runner passe les génériques VHDL) :
python3 run_tests.py --lanes 16 -w 320 -H 240 --max-iter 128   # grande image
python3 run_tests.py --testcase test_petite_image_egale_le_modele
python3 run_tests.py --waves                                   # traces .ghw

# référence CPU (même algorithme, même format, un cœur) :
gcc -O2 -o baseline ../software/baseline_c.c && ./baseline 128 96 64

# synthèse + placement-routage réels :
source ~/vivado/2025.2/Vivado/settings64.sh
vivado -mode batch -source ../scripts/synth_vivado.tcl \
       -tclargs --part xc7z020clg400-1 --lanes 16
```

## 7. Comparaison honnête avec un CPU

Le même algorithme, en C, optimisé `-O2`, **sur un seul cœur** de cette machine
(i7-1360P) :

```
image            : 128 x 96 (12288 pixels), max_iter=64
iterations       : 233737
debit CPU        : 22.929 Mpixels/s      (436 Miter/s)
```

Le FPGA, à 3 cycles par itération, fait **0,33 itération par cycle et par voie**. D'après
les mesures de §5 :

| | Itérations/s |
|---|---|
| 1 cœur CPU (C, `-O2`) | **436 Miter/s** |
| FPGA 8 voies @ 100 MHz | 267 Miter/s |
| FPGA 16 voies @ 86 MHz | 458 Miter/s |

Autrement dit : **il faut 16 voies pour égaler à peine un seul cœur de ce CPU**, qui en a
douze. Sur ce noyau-là, le FPGA ne gagne pas — et le dire fait partie du travail.

**Conclusion, sans enjolivure** : pour ce noyau arithmétique lourd et sans dépendances,
un CPU moderne est un adversaire redoutable, et un petit FPGA ne le bat pas en débit
brut. Ce que cet exemple démontre vraiment :

1. la **structure SIMT** (voies, répartiteur, divergence) se construit proprement en VHDL ;
2. on sait **mesurer** ce qu'elle donne (cycles/pixel, efficacité parallèle, coût par voie)
   au lieu de l'espérer ;
3. le plafond de la puce est identifié (220 DSP → 18 voies) et la piste d'optimisation
   est chiffrée (pipeline → ×3 par voie) ;
4. le FPGA reste gagnant là où il gagne toujours : latence déterministe, pas d'OS,
   quelques watts, et le calcul peut être intégré au flux de données (ici la sortie est
   déjà un flux `valid/ready` prêt à alimenter un affichage ou une DDR).

## 8. Pièges rencontrés — tous mesurés, pas théoriques

| Piège | Symptôme exact | Correction |
|---|---|---|
| Format Q trop juste | `bound check failure` sous GHDL : Q28 sur 32 bits porte ±8,0 et l'intermédiaire `2·zr·zi` atteint **pile** 8,0 au bord de la fuite | Q26 (±32) ; le format est passé en générique et **déclaré** par le design |
| Lecture d'un port `out` dans l'architecture | `ERROR: [Synth 8-10557] cannot read from 'out' object 'o_px_valid'; use 'buffer' or 'inout' instead` — GHDL le refuse en `--std=93` mais l'accepte en `--std=08`, et **un projet Vivado lit les sources en VHDL-93 par défaut** : le fichier est rejeté à la synthèse | signaux internes (`s_px_valid`, `s_cycles`) + câblage concurrent des ports : le design s'analyse alors en **VHDL-93 comme en VHDL-2008** (vérifié sur les deux) |
| Entier signé multiplié par un littéral | `bound check failure` sur `resize(zr*zi, 64) * 2` même pour de petites valeurs (reproduit en 10 lignes) | `shift_left(zr*zi, 1)` |
| Addition avec un entier signé | `bound check failure` sur `unsigned + v_delta` : l'opérateur numeric_std attend un **NATURAL**, un delta négatif violé le sous-type | branches explicites (`+1`, `-1`, inchangé) |
| Un seul créneau de résultat par voie | **351 pixels sur 6144 jamais émis**, simulation bloquée, `o_done` jamais armé : la voie repartait avant la collecte et écrasait le résultat (coordonnées fausses en prime) | 2 créneaux par voie + contre-pression sur l'émission |
| Double distribution à une même voie (`C_LANES=1`) | **1536 pixels émis pour 768 calculés** : le répartiteur balaie la même voie à chaque cycle et lui confie un second pixel alors que la voie est encore `IDLE` — le pulse de départ, étant enregistré, n'agit qu'au front suivant, et ce second pixel n'est **jamais calculé** (simulation qui ne se termine plus, gel à exactement la moitié) | demande **maintenue** par voie (`s_req`) au lieu d'un pulse, effacée dès que la voie quitte `IDLE` : la distribution devient idempotente. Ne se manifeste qu'à 1 voie (le balayage revient sur une voie déjà occupée dès 2 voies) |
| Lire un signal juste après le front | `Attempting settings a value during the ReadOnly phase` (écrire après `ReadOnly()`), et lecture décalée d'un cycle | testbench : lire sur le front **descendant** ; init : terminer sur un front, pas sur `ReadOnly` |
| `to_integer` sur un `std_logic` | `no overloaded function found matching "to_integer"` | fonction de conversion explicite `f_bit_vers_int` |
| Plage de port non localement statique | `unsigned(f_bits(C_IMG_W-1)-1 downto 0)` refusé (appel de fonction dans une plage) | largeurs passées en génériques (`C_XW`, `C_YW`) |
| Runner cocotb + GHDL | `cannot find entity or configuration mandelbrot_gpu` : l'élaboration va dans `build_dir` mais la simulation s'exécute dans `test_dir` | `test_args=["--std=08", "--workdir=<build>", "-P<build>"]` |
| Banc trop lent (0,6 ms/cycle) | 1 million de cycles simulés en 48 s : inutilisable | attendre `o_done.value_change` au lieu de poller chaque front (×1000) |

## 9. Ce qui n'est PAS vérifié

- **Aucune carte réelle** : le bitstream n'est pas généré (le top n'a pas de contraintes
  de broches) ; seul le flux synthèse → placement-routage → timing est exécuté.
- La fréquence annoncée en §5 vient du **pire chemin** après placement-routage, sans
  contrainte d'horloge imposée : c'est une estimation d'implémentation, pas une mesure
  sur silicium.
- Un seul point de conception : 3 cycles par itération. Un pipeline plus profond
  (1 itération/cycle par voie) n'a pas été tenté ; c'est la piste d'optimisation
  évidente et elle coûterait plus de multiplicateurs.
- La comparaison avec le CPU porte sur **un cœur** ; la version multi-thread du même C
  n'a pas été mesurée (elle serait ~10× plus rapide sur cette machine).

## 10. Sources

- Architecture d'un GPU réel (voies, blocs, divergence) : `tiny-gpu`
  (github.com/adam-maj/tiny-gpu), FGPU, « An SIMT-Architecture for FPGAs » (ACM TRETS).
- Implémentations Mandelbrot sur FPGA comparables, dont une sur **la même puce**
  (`xc7z020`) : `delhatch/Zedboard_Mandel` (9 moteurs @ 90 MHz → 12,8 images/s en
  640×480, 220 DSP saturés), `shapoco/accelbrot` (paramétrable en nombre de cœurs),
  `davemuscle/fpga_mandlebrot_fractal` (analyse de coût par « tranche »).
- Arithmétique virgule fixe et seuil de fuite : littérature classique sur l'ensemble de
  Mandelbrot ; le format et le seuil sont ici des génériques mesurés, pas des choix
  recopiés.
