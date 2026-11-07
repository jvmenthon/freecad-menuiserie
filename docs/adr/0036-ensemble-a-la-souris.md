# ADR 0036 — Taille et orientation d'un ensemble à la souris

- Statut : **proposé** (en attente de jv : questions Q1 à Q5 de la spécification)
- Date : 2026-11-07
- Spécification : [docs/specs/ensemble-a-la-souris.md](../specs/ensemble-a-la-souris.md)
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008](0008-ensemble-objet-de-cotes.md), [0019](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md),
  [0021](0021-deplacement-a-la-souris-avec-aimantation.md), [0025](0025-rotation-libre-d-une-piece.md)

## Contexte

jv veut changer la taille et l'orientation d'un ensemble à la souris, comme pour une pièce. Or
l'ensemble n'a ni forme ni `Placement` (ADR 0008) : ses pièces le suivent par expressions dans le
repère de leur conteneur commun, et supposent qu'elles sont d'équerre avec lui.

## Options pour l'orientation

1. **Tourner chaque pièce** autour du centre : les pièces sortent des liaisons (plus d'équerre),
   l'ensemble ne répond plus à ses cotes. Rejetée.
2. **Donner un `Placement` à l'ensemble** : tout le calcul des liaisons passe dans un repère
   propre, les pièces ne sont plus dans le repère de leur conteneur ; refonte d'ADR 0008, risque
   pour les autres ateliers. Rejetée.
3. **Std Part** (`App::Part` natif, ADR 0008 point 4) : au premier geste, l'ensemble et tous ses
   membres sont rangés dans un Std Part dont le `Placement` est écrit. Rien de neuf dans le
   modèle, compatible Assembly, TechDraw, STEP (ADR 0007). Retenue, sous réserve de l'essai sur
   FreeCAD 1.1 de la portée des expressions (risque R1).

## Taille

Le geste appelle `resize_furniture` (comme le panneau) : cotes en étirement, pas de mise à
l'échelle (épaisseurs fixes, rangées de l'ADR 0019). Retenue.

## Décision (provisoire)

Taille par six poignées de face et orientation par trois anneaux, dessinés par la session de
glissement existante (`gui/drag`) pour une cible « ensemble » ; rotation par un Std Part créé au
besoin. Les points Q1 à Q5 de la spécification peuvent la modifier.

## Conséquences

- La session de glissement a deux cibles (pièce, ensemble) : une abstraction `Target` à introduire
  sans toucher au comportement des pièces.
- Un Std Part apparaît dans l'arbre au premier geste de rotation : à signaler dans l'interface.
- Le glissement recalcule beaucoup plus que pour une pièce : brutes seules pendant le geste.
