# ADR 0043 — Répétition : un objet de cotes et des pièces ordinaires liées par expressions

- Statut : **accepté** (jv, 2026-11-08 ; Q4 et Q5 : cases « Recopier les assemblages » et
  « Suivre le redimensionnement », autres questions selon les ★)
- Date : 2026-11-07
- Spécification : [docs/specs/repetition.md](../specs/repetition.md), issue #180
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi des pièces par expressions natives](0009-suivi-par-expressions-natives.md)

## Contexte

jv veut une répétition modifiable après coup, dont les copies suivent l'original, dissociables,
extensible au cercle et au trajet. Options :

1. **Tableau Draft ou `App::Link`** : un seul objet à éléments virtuels. Les copies ne peuvent pas
   être usinées ni assemblées une à une et n'ont pas de ligne de débit propre. Rejetée.
2. **Copies indépendantes, créées par une commande** (esprit des gabarits, ADR 0010) : pas de
   suivi de l'original, pas modifiable après coup. Ne répond pas à la demande. Rejetée.
3. **Objet de cotes `Repeat` + copies réelles liées par expressions natives** : retenue. FreeCAD
   interdit de créer ou supprimer des objets pendant un recalcul, donc le nombre de copies change
   par une commande (transaction), tandis que le pas, les cotes et le placement suivent par
   expressions.

## Décision

1. `Repeat` est un objet de données sans forme (comme l'Ensemble) : `Source` (pièces ou ensembles ; un ensemble copié devient un sous-ensemble copie dont les cotes sont liées à la source), `Mode`
   (`Linear`, `Circular` et `Path` réservés, valeurs stables), `Count`, `Step`, `Axis`, `Reverse`.
2. Chaque copie est une pièce ordinaire portant `Repeat` et `RepeatIndex` (lecture seule) ; ses
   cotes et son placement sont des expressions sur la source et sur `Repeat`, écrites par l'API
   dans la transaction en cours, jamais pendant un recalcul.
3. Les assemblages de la source sont recréés pour chaque copie, liés à ceux de l'origine tant que
   la copie est liée.
4. « Dissocier » retire les expressions et le lien `Repeat` : la copie devient libre.
5. `core/repeat/` (Python pur) calcule les décalages ; Draft n'est utilisé que pour le mode
   trajet (placements le long d'une arête), importé tardivement dans `features/`.
6. Le geste de copie à la souris s'appuie sur la même fabrique (répétition d'une copie).

## Conséquences

- Nouveau type persistant : son chemin, son nom de classe et ses propriétés entrent dans le
  contrat de persistance (ADR 0003) dès la première version, d'où les valeurs de `Mode` réservées.
- Les copies gardent tous les avantages des pièces (usinage, assemblages, liste de débit).
- Le nombre de copies ne change que par la commande « Modifier la répétition », pas en tapant
  `Count` dans l'éditeur de propriétés (champ en lecture seule).
- 100 copies liées par expressions : coût de recalcul à mesurer au lot R-a.
