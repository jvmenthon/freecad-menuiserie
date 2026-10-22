# ADR 0015 — Épaisseurs standards de brut dans la bibliothèque de matériaux

- Statut : **accepté** (demande de jv, recette J2, 2026-10-22)
- Date : 2026-10-22
- Spécification : [docs/specs/J2-liste-de-debit.md](../specs/J2-liste-de-debit.md), § 10.4
- ADR liés : [0002 — Bibliothèque de matériaux](0002-bibliotheque-de-materiaux.md),
  [0013 — Liste de débit vivante](0013-liste-de-debit-vivante.md)

## Contexte

La liste de débit donnait une épaisseur de débit égale à l'épaisseur finie plus la surcote
(0 mm par défaut pour le massif) : 18 mm de débit pour une pièce finie de 18 mm. Le menuisier
achète pourtant du massif en épaisseurs de brut du commerce (plots de 27, 34, 41 mm…) et rabote :
la liste, son volume et sa masse ne correspondaient pas à ce qui est acheté. Le champ
`thicknesses` existant donne les épaisseurs **finies** courantes (aide à la saisie), pas le brut.

## Décision

1. Champ **facultatif** `rough_thicknesses` d'une entrée de la bibliothèque (format 1 inchangé) :
   liste d'épaisseurs de brut en mm, mêmes bornes que `thicknesses`. Absent = aucune.
2. La liste de débit arrondit l'épaisseur de débit d'une pièce **massive** à la plus petite
   épaisseur de brut ≥ finie + max(surcote + ajouts d'épaisseur, `MIN_PLANING_MM` = 3 mm).
   Au-delà de la plus grande : pas d'arrondi et un avertissement.
3. Seul `core/cutlist` applique la règle (via `CutEntry`) ; `PartRecord.rough` et la géométrie
   des pièces ne changent pas. La collecte passe les épaisseurs de brut du matériau de la pièce.

## Conséquences

- Les totaux par matériau et épaisseur deviennent des totaux par épaisseur de plot.
- Une bibliothèque personnelle sans le champ garde l'ancien calcul ; une version plus ancienne
  de l'atelier qui lit une bibliothèque avec le champ le signale comme clé inconnue
  (avertissement) et l'ignore.
- La marge de rabotage de 3 mm est une constante du cœur ; la rendre réglable sera un autre lot
  si jv le demande.
