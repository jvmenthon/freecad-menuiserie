# ADR 0055 — Quincaillerie : charnières à cuvette et vis

- Statut : **proposé** (issue #156, à valider par jv ; aucun code avant son accord)
- Date : 2026-11-12
- ADR liés : [0033 — Catalogue de quincaillerie](0033-quincaillerie-catalogue-et-modeles-generiques.md),
  [0006 — Brute et usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

Le catalogue local (ADR 0033) pose déjà tourillons, faux tenons, biscuits, pieds, taquets LR32 et
coulisses. Restent deux besoins de l'issue #156 : les **charnières à cuvette** (perçage Ø35 dans la
porte, platine sur le côté) et les **vis** (trou de passage, avant-trou, fraisage). Les jeux de
références de base sont livrés hors ligne ; d'autres viendront de paquets SaaS (issue #161), au même
format JSON, sans changement de l'addon.

## Décision proposée

1. **Charnière** : un assemblage porte → caisson (deux pièces), comme la coulisse. Cuvette Ø `cup_diameter`
   et profondeur `cup_depth` percées dans la porte à `edge_distance` du bord ; deux vis de platine
   sur le côté du caisson à l'entraxe de 32 mm (`screw_pitch`). Nombre automatique selon la hauteur
   (2 jusqu'à 900 mm, puis 3, 4…), positions à 100 mm des angles, réglables.
2. **Vis** : assemblage à une pièce traversant deux pièces, trou de passage dans la première,
   avant-trou dans la seconde, fraisage facultatif ; diamètre et longueur pris dans le catalogue
   (`wood-screw`). Longueur proposée selon l'épaisseur traversée.
3. **Nouvelles cotes** de famille : charnière `edge_distance`, `screw_pitch`, `screw_diameter` ;
   famille inconnue inchangée (la référence reste dans la liste d'achat, sans forme).
4. **Liste d'achat** : déjà livrée (propriété `HardwareReference`, colonnes fabricant et référence).
5. **Références de marque** (Blum, Hettich, Salice) : saisies à la main depuis les fiches
   publiques, chacune avec sa source (ADR 0033 §3) ; les marques réellement utilisées par jv
   (question Q6) priment.

## Conséquences

- Deux nouveaux types d'assemblage dans `JointKind`, rangés sous « Quincaillerie » (ADR 0046).
- Les cotes de marque exigent une relecture sur fiche avant fusion.
- Découpage prévu : lot 1 charnières, lot 2 vis.

## Questions pour jv

- Q1. Quelles charnières utilises-tu (marque, recouvrement, angle) ?
- Q2. Vis : seulement les assemblages visibles (fraisées) ou aussi les fixations cachées ?
