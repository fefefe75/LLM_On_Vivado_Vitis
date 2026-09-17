# `sim/` — les sorties de simulation (non versionnées)

Ce dossier reçoit ce que la simulation **produit** : traces, résultats, logs.
Il est presque vide dans un dépôt propre, et c'est normal : tout ce qu'il
contient se régénère avec `make sim`.

```
sim/
├── README.md           ce fichier (le seul fichier versionné de sim/)
├── compteur.ghw        trace GTKWave/Surfer (généré)
├── results.xml         résultats cocotb du dernier run (généré)
└── transcript          log du simulateur (généré)
```

## Ce qui va ici

| Fichier | Format | Ouvert avec |
|---|---|---|
| `*.ghw` | GHDL (natif) | GTKWave, Surfer |
| `*.vcd` | VCD (universel) | GTKWave, PulseView |
| `*.fst` | FST (compact) | GTKWave |
| `*.wlf` | Questa/ModelSim | vsim |
| `results.xml` | cocotb (JUnit XML) | tout outil qui lit du JUnit |

## Règles

- **Rien de généré n'est commité** : `.gitignore` exclut `*.ghw`, `*.vcd`,
  `*.fst`, `results.xml`. Une trace de 200 Mo dans git n'est pas une
  documentation.
- **Une trace sans son `results.xml` ne prouve rien** : la trace aide à
  comprendre un échec, elle ne l'établit pas. La preuve, c'est la sortie de
  `make sim`.
- **Les scripts qui post-traitent les traces** (extraction de mesures,
  conversion, calculs) sont, eux, versionnés — dans `../scripts/`.
- `make clean` vide les artefacts ici présents sans toucher à ce README.
- Une trace ou un rapport qu'on veut conserver durablement se copie dans
  `../doc/` avec sa date et sa version d'outil, pas laissé ici en vrac.
