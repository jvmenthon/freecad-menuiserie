# ADR 0049 — Cotes du parent recalées sur l'enveloppe de ses membres

- Statut : **accepté** (jv, 2026-11-11 : « Agrandir les cotes du parent », précisé le même jour :
  « la boîte doit toujours être de la taille de l'ensemble »)
- Date : 2026-11-11
- ADR liés : [0008](0008-ensemble-objet-de-cotes.md), [0019](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md),
  [0038](0038-ensemble-a-la-souris.md), [0048](0048-selection-par-ensemble-dans-la-vue-3d.md) (abandonné le 2026-11-13, sans effet sur cet ADR)

## Contexte

La boîte bleue d'un ensemble, ce sont ses cotes (`Origin` + largeur, profondeur, hauteur). Quand
jv déplace ou tourne un sous-ensemble hors de son parent, les cotes du parent ne changent pas : la
boîte ne l'englobe plus (constaté le 2026-11-11).

## Options

1. **Recaler les cotes du parent sur l'enveloppe de ses membres** après le geste. Retenue (jv).
2. Afficher l'enveloppe réelle sans changer les cotes : poignées et boîte ne coïncident plus.
3. Garder les cotes et avertir.

## Décision

1. À la fin d'un déplacement ou d'une rotation d'un sous-ensemble (souris ou `api.move_furniture`),
   l'`Origin` et les cotes du parent deviennent la boîte qui enveloppe ses membres directs : pièces
   et sous-ensembles, rotation comprise. La boîte est **exactement** celle de l'ensemble, sans
   marge : elle grandit ou rétrécit (ramener un sous-ensemble la rétrécit).
2. **Rien ne bouge** : les cotes sont écrites sans recalcul, puis les liaisons du parent sont
   recalculées d'après la géométrie actuelle (comme « Relier les pièces »). Les pièces liées aux
   cotes du parent ne suivront ces nouvelles cotes qu'au prochain changement de taille.
3. Seul un ensemble **de plus haut niveau** est recalé : la position d'un sous-ensemble est portée
   par son Std Part avec un `Origin` nul (ADR 0038), qu'un recalage casserait. Un parent n'est pas
   recalé non plus quand une formule autre qu'une liaison de l'atelier pilote son `Origin` ou une
   cote, **ou les lit** : répétition « Suivre le redimensionnement » (ADR 0043), formule de
   l'utilisateur sur un membre. Le recaler redistribuerait ces copies ou déplacerait ces pièces,
   contraire au point 2.
5. Le document est recalculé **avant** le calcul de l'enveloppe : les copies d'une répétition du
   sous-ensemble (membres du parent) suivent leur source par expression et seraient sinon lues à
   leur ancienne place.
4. Liaison refusée : cotes du parent et sous-ensemble reviennent à leur état du début.

## Conséquences

- Code : `features/furniture_envelope.py`, appelé par `furniture_drag._relink`.
- Un sous-ensemble d'un sous-ensemble déplacé hors de son parent garde l'ancien comportement : à
  traiter plus tard si jv le demande (normaliser `Origin` en décalant le Std Part).
- Un recalcul complet du document de plus à la fin d'un geste sur un sous-ensemble.
- Tests d'intégration : `tests/integration/test_enveloppe_du_parent.py` (déplacement à droite
  et à gauche, rotation, rétrécissement quand on ramène le sous-ensemble, répétition qui suit le parent, copies d'un
  sous-ensemble répété, création autour d'un ensemble tourné).
