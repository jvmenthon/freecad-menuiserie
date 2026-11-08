# ADR 0038 — Taille et orientation d'un ensemble à la souris

- Statut : **accepté** (jv, 2026-11-07)
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

## Décision

1. Chaque ensemble est rangé, **dès sa création**, dans un Std Part qui contient l'ensemble, ses
   pièces, leurs assemblages et ses Distances. Tourner ou déplacer l'ensemble, c'est écrire le
   `Placement` de ce Std Part (outil natif de FreeCAD, utilisable aussi par les autres ateliers).
2. **Un sous-ensemble a son propre Std Part**, rangé dans celui de son parent. Les liaisons du
   parent portent sur le `Placement.Base` de ce Std Part au lieu de l'`Origin` du sous-ensemble.
   Cela amende le point 3 de l'ADR 0008 (« même conteneur ») pour les sous-ensembles.
3. Taille par six poignées de face (`resize_furniture`, étirement), déplacement par trois flèches,
   orientation par trois anneaux, dessinés par la session de glissement (`gui/drag`) pour une
   cible « ensemble ».
4. Pas de reprise des documents existants pour l'instant (jv).

## Conséquences

- La session de glissement a deux cibles (pièce, ensemble) : une abstraction `Target` à introduire
  sans toucher au comportement des pièces.
- Un Std Part apparaît dans l'arbre à la création de chaque ensemble.
- Le glissement recalcule beaucoup plus que pour une pièce : brutes seules pendant le geste.

## Essai sur FreeCAD 1.1

Essai du 2026-11-07 sur FreeCAD 1.1.3 (conda-forge, `freecadcmd`), avec le bureau de référence des
tests et son caisson. Résultats :

- Un `App::Part` qui contient l'ensemble, ses pièces (brutes et usinées), ses assemblages et ses
  Distances garde toutes les expressions `<<Ensemble>>.Width`… valides : aucun « cyclic
  reference », aucune erreur de portée, géométrie inchangée, y compris après un changement de cote,
  une rotation du Std Part, un enregistrement et une réouverture.
- Un sous-ensemble dans son propre `App::Part`, imbriqué dans celui du parent, fonctionne : ses
  cotes et le `Placement.Base` de son Std Part sont liés par expression à l'ensemble parent (portée
  d'un enfant vers son ancêtre acceptée), ses pièces citent `<<Caisson>>` sans erreur.
- `addObject` / `removeObject` d'un Std Part déplacent aussi la **fermeture des liens** de l'objet
  (assemblages, pièces usinées, pièces assemblées, ensemble cité par une expression) et renvoient la
  liste des objets déplacés. Conséquences : l'ensemble et ses membres se rangent d'un coup, mais un
  sous-ensemble déjà lié à son parent par des expressions ne peut plus être séparé de lui ; il faut
  le ranger **avant** de poser ses liaisons, et défaire ses liaisons avant de le sortir. Une pièce
  assemblée à une autre qui reste dans l'ensemble ne peut pas en sortir seule : elle reste alors dans
  le Std Part (le retrait ne touche que ses propriétés de membre et ses liaisons).
- FreeCAD impose des libellés uniques : le Std Part ne peut pas porter le libellé exact de
  l'ensemble (`<<Bureau>>` viserait un objet ambigu). Le Std Part s'appelle « Bureau (Std Part) ».
