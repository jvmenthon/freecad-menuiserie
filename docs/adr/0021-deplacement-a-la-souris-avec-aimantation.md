# ADR 0021 — Déplacement et redimensionnement à la souris, avec aimantation

- Statut : **proposé** (issue #65 ; questions Q1 à Q5 de la spécification en attente de jv)
- Date : 2026-10-25
- Spécification : [docs/specs/souris-et-distances.md](../specs/souris-et-distances.md), § 4.1 à 4.5
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0009 — Suivi par expressions natives](0009-suivi-par-expressions-natives.md),
  [0011 — Aperçu, accrochage et nom](0011-apercu-accrochage-et-nom.md),
  [0018 — Double-clic dans la vue 3D](0018-double-clic-dans-la-vue-3d.md),
  [0019 — Rangées et épaisseurs fixes](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (PR #86)

## Contexte

jv veut, pendant la création d'une pièce, la déplacer et la redimensionner à la souris dans la
vue 3D, avec une aimantation sur les faces, arêtes et sommets des pièces voisines. Trois choix
sont difficiles à défaire : quel mécanisme d'interaction, quand il est actif, et comment il
cohabite avec les liaisons des ensembles.

## Options

### Mécanisme

1. **Std Transform** (manipulateur natif `SoFCCSysDragger`) : déplace et tourne, mais ne
   s'aimante sur rien, ne change pas les cotes et ne se programme pas depuis Python. Rejetée.
2. **Draggers Coin** (`SoTranslate1Dragger`, `SoTranslate2Dragger`) posés sur la pièce : le
   glisser est fourni, mais il faut corriger leur valeur à chaque mouvement pour l'aimant, et
   leur saisie dépend du style de navigation. Rejetée.
3. **Session d'interaction de l'atelier** : un filtre d'évènements Qt sur la zone d'affichage
   (technique éprouvée du double-clic, ADR 0018), un rayon calculé à chaque mouvement, les règles
   d'aimantation pures dans `core/magnet/`, les poignées et guides dessinés par un nœud Coin
   temporaire. Retenue.

### Quand

1. **Seulement pendant le panneau de la pièce** (création et modification). Retenue (Q1 ★).
2. Tout le temps quand l'atelier est actif : entre en conflit avec les styles de navigation où le
   clic gauche glissé tourne la vue ou trace un cadre. Rejetée en attendant jv.

### Pièces d'un ensemble

1. Refuser le glissement d'un membre. Simple, mais la recette de #86 a justement besoin de
   bouger les pièces d'un bureau.
2. **Mettre de côté les liaisons touchées pendant le glissement, puis relier tout l'ensemble au
   relâchement** (voie de l'ADR 0019, point 6). Retenue (Q5 ★).

## Décision

1. Le glissement est une **session** (`gui/drag/`, pattern State) créée à l'ouverture du panneau
   de la pièce et détruite à sa fermeture. Son filtre d'évènements ne consomme que le clic gauche
   qui tombe sur la pièce (brute, usinée ou assemblage, qui renvoient à la brute) ou sur une de
   ses quatre poignées (longueur, largeur ; jamais l'épaisseur) ; tout autre évènement est rendu
   à FreeCAD.
2. Plan de glissement, rayon, aimantation par axe, poignées et tolérance (10 pixels convertis en
   mm) sont des fonctions pures de `core/magnet/`, sans FreeCAD ni Qt.
3. Les **guides** (plans, droites, sommets des objets visibles du conteneur, tout atelier) sont
   lus une fois au début du glissement, dans le repère de la pièce, bornés à 5 000, et ne
   comptent que s'ils sont à portée de la pièce (« voisines »). Aucun objet n'est modifié.
4. Pendant le glissement, seules les propriétés de la brute sont écrites (`Placement`, `Length`,
   `Width`), sans recalcul du document ; un seul recalcul au relâchement. Le tout reste dans la
   transaction du panneau (un seul Ctrl+Z) ; Échap ramène la pièce au début du glissement
   (Memento).
5. Pour un membre d'ensemble, les expressions **de l'atelier** sur les propriétés touchées sont
   mises de côté au début du glissement et l'ensemble est relié au relâchement ; une formule de
   l'utilisateur rend l'axe non glissable ; une rangée bloquée refuse le relâchement et propose
   « Déverrouiller et appliquer » (ADR 0019).

## Conséquences

- Aucune propriété ni migration nouvelles : le glissement n'écrit que des propriétés existantes.
- La géométrie est testée sans FreeCAD ; la lecture des guides dans `freecadcmd` ; l'interaction
  par `tests/gui` et par une recette sur trois styles de navigation, FreeCAD 1.0 et 1.1.
- Le menuisier ouvre le panneau (double-clic) pour glisser une pièce existante ; glisser sans
  panneau reste possible plus tard sans changer `core/magnet`.
- Une pièce posée à la souris ne suit pas sa voisine si celle-ci bouge (comme l'accrochage de
  l'ADR 0011) ; le suivi reste le rôle de l'ensemble et des Distances gardées (ADR 0022).
- `pivy` n'est utilisé que dans `gui/drag/overlay.py` (dessin), comme dans `gui/textures.py`.
