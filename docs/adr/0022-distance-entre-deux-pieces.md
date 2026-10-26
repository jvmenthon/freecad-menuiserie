# ADR 0022 — Distance entre deux pièces : mouvement ponctuel, objet Distance dans un ensemble

- Statut : **accepté** (demande de jv du 2026-10-25 ; Q6 à Q8 de la spécification : recommandations
  validées par jv le 2026-10-25)
- Date : 2026-10-25
- Spécification : [docs/specs/souris-et-distances.md](../specs/souris-et-distances.md), § 4.6 et 4.7
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi par expressions natives](0009-suivi-par-expressions-natives.md),
  [0011 — Aperçu, accrochage et nom](0011-apercu-accrochage-et-nom.md),
  [0019 — Rangées et épaisseurs fixes](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (PR #86),
  [0021 — Déplacement à la souris](0021-deplacement-a-la-souris-avec-aimantation.md)

## Contexte

jv veut sélectionner deux faces, arêtes ou sommets, faire clic droit → « Définir une distance »
et obtenir cette distance. Les ensembles de J4 gardent déjà des distances **aux bords** de
l'ensemble (option « fixe / non fixe ») ; #86 range les membres par rangées où chaque écart est
une cellule rigide ou libre. Il faut choisir si la distance est gardée, et par quel mécanisme.

## Options

1. **Contrainte géométrique** (atelier Assembly de FreeCAD 1.0, solveur) : puissante, mais
   impose un conteneur Assembly, un solveur et des références topologiques (`Face3`) fragiles ;
   conflit avec les liaisons de l'ensemble (deux pilotes pour un même `Placement`). Rejetée.
2. **Attachement natif** (`AttachExtension`, décalage) : une seule référence, noms topologiques,
   conflit avec les liaisons de l'ensemble (déjà rejeté par l'ADR 0011). Rejetée.
3. **Expression directe** entre les deux pièces hors ensemble (`B.Placement.Base.x =
   A.Placement.Base.x + …`) : un second mécanisme de suivi à côté des ensembles, à maintenir
   (cycles, rotation des pièces, retrait). Rejetée en attendant Q6.
4. **Mouvement ponctuel partout ; dans un ensemble, objet `Distance` lu par les règles des
   rangées comme un bloc rigide virtuel à valeur vivante.** Retenue.

## Décision

1. « Définir une distance » mesure la distance des deux éléments (règles pures
   `core/distance/`, une Strategy par paire face/arête/sommet ; éléments non parallèles refusés)
   et **déplace une pièce de l'atelier** une fois (la seconde sélectionnée par défaut, bouton
   Inverser). Un objet d'un autre atelier n'est jamais déplacé (ADR 0007).
2. Si les deux pièces sont membres du même ensemble et que la direction est parallèle à un axe
   de l'ensemble, la case « Garder cette distance » (cochée par défaut) crée un objet
   **`Distance`** (`App::FeaturePython` sans forme) : deux liens vers les pièces, l'axe, le côté
   de chaque pièce (début ou fin de son étendue), `Value` (`App::PropertyLength`). Aucun nom
   topologique n'est retenu.
3. Règles des rangées (complètent l'ADR 0019) : **1 bis** deux pièces reliées par une Distance
   sont en vis-à-vis sur son axe ; **4.2 bis** l'intervalle entre leurs faces est un bloc rigide
   virtuel : une seule cellule → `Name.Value` dans l'expression (Distance citée par son `Name`,
   comme une épaisseur), coupé par une autre face → constantes figées et notice. Une Distance
   compte comme une pièce verrouillée pour le blocage.
4. Changer `Value` ne fait appel à aucun code de l'atelier (ADR 0009). Supprimer une des pièces,
   la retirer de l'ensemble ou supprimer l'ensemble supprime la Distance ; créer ou supprimer une
   Distance relie tout l'ensemble (ADR 0019, point 6).

## Conséquences

- Un seul mécanisme de suivi (l'ensemble) ; la « distance fixe » de J4 s'étend naturellement
  d'un bord à une autre pièce.
- Un nouveau type d'objet (`Distance`, `Version` = 1) ; sans l'atelier il reste inerte et les
  expressions qui le citent restent valables.
- Une distance hors ensemble n'est pas gardée : le menuisier est invité à mettre les pièces dans
  un ensemble (limite documentée, option 3 possible plus tard).
- La distance entre deux éléments d'une même pièce n'est pas traitée (ce serait une cote).
