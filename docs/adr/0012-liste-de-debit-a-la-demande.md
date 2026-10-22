# ADR 0012 — Liste de débit calculée à la demande dans une feuille standard

- Statut : **proposé** (spécification J2, question Q3 posée à jv)
- Date : 2026-10-22
- Spécification : [docs/specs/J2-liste-de-debit.md](../specs/J2-liste-de-debit.md), § 4
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

La liste de débit lit toutes les pièces d'un document (ou d'une sélection), les liens qui les
répètent, les ensembles et les assemblages, puis l'affiche dans une feuille de calcul FreeCAD et
l'exporte en CSV. Deux façons de la tenir à jour :

1. **Objet vivant** : un `FeaturePython` (ou une feuille à proxy) qui dépend de toutes les pièces
   et réécrit la feuille à chaque recalcul.
2. **Calcul à la demande** : une commande lit le document et réécrit une feuille ordinaire.

L'objet vivant devrait déclarer un lien vers chaque pièce (sinon FreeCAD ne le recalcule pas), ce
qui l'insère dans le graphe de dépendances de tout le meuble, ralentit chaque recalcul, crée des
risques de cycle avec les ensembles (constat de J4 : un conteneur lu par expression par ses
enfants donne une « cyclic reference ») et laisse un proxy de plus dans le document.

## Décision

1. La liste se calcule **à la demande** (commande « Liste de débit », fonction
   `make_cut_list`) : collecte en lecture seule → calcul pur dans `core/cutlist/` → rendu.
2. Elle est écrite dans un **`Spreadsheet::Sheet` standard, sans proxy**, marqué par une
   propriété booléenne masquée `MenuiserieCutList`, retrouvé par cette marque et réécrit à chaque
   mise à jour (colonnes de l'atelier A–O ; colonnes suivantes laissées à l'utilisateur). La
   feuille porte la date et la portée du calcul.
3. Les cellules ne reçoivent que des valeurs littérales, jamais une formule construite à partir
   d'un repère ou d'un libellé.
4. Les longueurs de débit incluent les ajouts des assemblages, lus de façon générique sur la
   boîte englobante de la pièce usinée dans le repère de sa brute (ADR 0006).

## Conséquences

- Aucun impact sur le recalcul ni sur le graphe de dépendances ; aucune migration ; un document
  ouvert sans l'atelier garde une feuille lisible (ADR 0007).
- La feuille peut être périmée : la date affichée et l'infobulle le disent ; une mise à jour
  coûte un clic.
- Si jv préfère une liste vivante (Q3 b), cet ADR est remplacé : la collecte et le calcul pur
  restent valables, seul le déclencheur change.
