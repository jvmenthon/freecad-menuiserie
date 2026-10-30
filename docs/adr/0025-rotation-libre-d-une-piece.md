# ADR 0025 — Rotation libre d'une pièce : angles du `Placement` et anneaux de la session de glissement

- Statut : **accepté** (issue #117 ; Q1 tranchée par jv le 2026-10-28 : angle libre ; Q2 à Q6
  validées par jv le 2026-10-29 : « c'est ok »)
- Date : 2026-10-28
- Spécification : [docs/specs/rotation-d-une-piece.md](../specs/rotation-d-une-piece.md)
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0011 — Aperçu, accrochage et nom](0011-apercu-accrochage-et-nom.md),
  [0021 — Déplacement à la souris](0021-deplacement-a-la-souris-avec-aimantation.md),
  [0024 — Assemblages entre pièces en biais](0024-assemblages-entre-pieces-en-biais.md),
  [0026 — Assemblage défait par un déplacement](0026-assemblage-defait-par-un-deplacement.md)

## Contexte

jv veut choisir la rotation d'une pièce dans le panneau et dans la vue 3D, à un angle quelconque
(Q1). Deux choix sont difficiles à défaire : ce que représentent les nombres du panneau, et le
mécanisme du geste dans la vue.

## Options

### Nombres du panneau

1. **Axe et angle** (comme l'onglet « Rotation axiale » de FreeCAD) : exact, mais un menuisier ne
   pense pas en vecteur d'axe. Rejetée.
2. **Incrément** (« tourner de N° autour de X », bouton Appliquer) : simple, mais l'état n'est pas
   lisible et l'aperçu en direct (règle de jv du 2026-10-22) n'a pas de sens. Rejetée.
3. **Trois angles absolus du `Placement`** (roulis X, tangage Y, lacet Z de FreeCAD, autour des
   axes fixes du document) : mêmes nombres que l'éditeur de propriétés, aperçu en direct
   naturel. Limite : blocage de cardan à ±90° de tangage. Retenue.

### Geste dans la vue

1. **Std Transform** (`SoFCCSysDragger`) : tourne, mais sans aimant à nos pas, sans fenêtre
   d'assemblage défait, sans lien avec le panneau. Rejetée (comme dans l'ADR 0021).
2. **`SoRotateDiscDragger` de Coin** : le geste est fourni, mais sa saisie dépend du style de
   navigation et il faut corriger sa valeur à chaque mouvement. Rejetée.
3. **État `Rotating` de la session de l'atelier** (ADR 0021) : même filtre d'évènements, même
   Memento, même transaction, même fenêtre d'ADR 0026 ; anneaux dessinés par l'incrustation
   existante ; géométrie pure dans `core/rotation/`. Retenue.

## Décision

1. Les champs du panneau sont les trois angles du `Placement` (convention `getYawPitchRoll`),
   en degrés au dixième, de −180 à 180 (Y, le tangage, de −90 à 90) ; à ±90° de tangage, X vaut 0
   et Z porte tout.
2. Toute rotation (champ, anneau, quart de tour) se fait autour du centre de la brute.
3. Un anneau tourne à partir de l'orientation courante, autour d'un axe fixe du document,
   aimanté tous les 15° sur l'angle **obtenu** et non sur le seul angle parcouru (jv, 2026-10-30) (libre avec Maj) ; c'est un état de la session de glissement, qui ne
   consomme que le clic sur un anneau.
4. Seul `Placement` est écrit ; une expression sur le `Placement` interdit la rotation (pas de
   rotation d'un membre d'ensemble avant #114).
5. En création, une rotation libre arrête l'accrochage ; un quart de tour le garde.

## Conséquences

- Aucune propriété ni migration ; documents lisibles sans l'atelier.
- Une pièce tournée hors d'équerre ne reçoit pas de nouvel assemblage avant #114 (refus propre
  existant) ; la liste de débit n'est pas touchée (L, l, e inchangées).
- Les règles d'angle et d'anneau se testent sans FreeCAD ; le geste par `tests/gui` et la recette.
