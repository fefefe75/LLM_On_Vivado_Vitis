# `doc/` — la documentation de conception

Ce dossier garde ce qu'un humain (ou un agent) doit lire pour comprendre le
projet **sans** reconstruire l'historique des conversations.

```
doc/
├── 01-cahier-des-charges.md    ce que le design doit faire, et à quelle fréquence
├── 02-architecture.md          blocs, flux de données, horloges, resets
├── 03-timing.md                contraintes, WNS/TNS constatés, version d'outil
├── reports/                    rapports exportés (timing.rpt, utilization.rpt)
└── img/                        schémas, chronogrammes, captures annotées
```

## Règles

- **Un rapport de timing archivé porte sa date et sa version d'outil** :
  « WNS = 0,123 ns, Vivado 2024.1, run impl_1 du 2026-09-17 ». Un `timing.rpt`
  sans version ne vaut rien six mois plus tard.
- **Les diagrammes sont du texte quand c'est possible** (Mermaid, PlantUML) :
  ils se relisent en diff. Les images vont dans `doc/img/`.
- **Chaque affirmation sur Vivado/Vitis cite sa source** : lien
  `docs.amd.com` / numéro d'UG, ou la sortie réelle de l'outil. C'est ce qui
  distingue une note de conception d'une supposition.
- **Les fichiers générés n'y entrent pas** : un `.rpt` se copie ici depuis
  `.runs/` *volontairement*, avec sa date, jamais par un `cp -r` de dossier.
- Le glossaire et le mode d'emploi du projet appartiennent au `README.md`
  racine ; `doc/` contient ce qui est trop long pour lui.
