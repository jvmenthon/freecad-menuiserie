# ADR 0021 — Déplacement et redimensionnement à la souris, avec aimantation

- Statut : **accepté** (issue #65 ; Q1 à Q5 de la spécification tranchées par jv le 2026-10-25 :
  à tout moment, flèches, voisines, pas d'épaisseur, membres d'ensemble reliés)
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
3. **Session d'interaction de l'atelier** : un filtre d'évènements d'application (technique
   éprouvée du double-clic, ADR 0018), un rayon calculé à chaque mouvement, les règles
   d'aimantation pures dans `core/magnet/`, trois flèches (choix de jv, Q2), les poignées et les
   guides dessinés par un nœud Coin temporaire. Retenue.

### Quand

1. Seulement pendant le panneau de la pièce. Sûr, mais jv veut aussi déplacer une pièce sans
   ouvrir son panneau. Rejetée par jv.
2. Tout le temps, dès qu'on tire une pièce : entre en conflit avec les styles de navigation où
   le clic gauche glissé tourne la vue (Gesture) ou trace un cadre de sélection. Rejetée.
3. **Tout le temps quand l'atelier est actif, par les flèches de la pièce sélectionnée seule**
   (panneau ouvert : la pièce du panneau). Seul un clic sur une flèche ou une poignée est pris :
   aucun conflit avec la navigation. Retenue.

### Pièces d'un ensemble

1. Refuser le glissement d'un membre. Simple, mais la recette de #86 a justement besoin de
   bouger les pièces d'un bureau.
2. **Mettre de côté les liaisons touchées pendant le glissement, puis relier tout l'ensemble au
   relâchement** (voie de l'ADR 0019, point 6). Retenue (Q5 ★).

## Décision

1. Le glissement est une **session** (`gui/drag/`, pattern State). Son filtre d'évènements
   d'application et un observateur de sélection sont posés quand l'atelier est activé et retirés
   quand on le quitte, avec le filtre du double-clic (ADR 0018). Une pièce de l'atelier
   sélectionnée seule (brute, usinée ou assemblage, qui renvoient à la brute) reçoit trois
   flèches selon ses axes ; panneau ouvert, la pièce du panneau reçoit en plus quatre poignées
   (longueur, largeur) et, pour le massif seulement, deux poignées d'épaisseur (note du
   2026-10-26). Le filtre ne consomme que le clic gauche qui tombe
   sur une flèche ou une poignée ; tout autre évènement est rendu à FreeCAD.
2. Flèches, rayon, déplacement sur l'axe, aimantation, poignées et tolérance (10 pixels convertis en
   mm) sont des fonctions pures de `core/magnet/`, sans FreeCAD ni Qt.
3. Les **guides** (plans, droites, sommets des objets visibles du conteneur, tout atelier) sont
   lus une fois au début du glissement, dans le repère de la pièce, bornés à 5 000, et ne
   comptent que s'ils sont à portée de la pièce (« voisines »). Aucun objet n'est modifié.
4. Pendant le glissement, seules les propriétés de la brute sont écrites (`Placement`, `Length`,
   `Width`), sans recalcul du document ; un seul recalcul au relâchement. Panneau ouvert, le tout
   reste dans sa transaction ; hors panneau, le glissement ouvre sa transaction « Déplacer la
   pièce ». Un Ctrl+Z dans les deux cas ; Échap ramène la pièce au début du glissement (Memento).
5. Pour un membre d'ensemble, les expressions **de l'atelier** sur les propriétés touchées sont
   mises de côté au début du glissement et l'ensemble est relié au relâchement ; une formule de
   l'utilisateur rend l'axe non glissable (voir la note du 2026-10-25 pour le refus d'une rangée
   bloquée, retiré).

## Conséquences

- Aucune propriété ni migration nouvelles : le glissement n'écrit que des propriétés existantes.
- La géométrie est testée sans FreeCAD ; la lecture des guides dans `freecadcmd` ; l'interaction
  par `tests/gui` et par une recette sur trois styles de navigation, FreeCAD 1.0 et 1.1.
- Un clic pour sélectionner, puis on tire une flèche : un axe à la fois, précis, sans conflit
  avec la navigation. Redimensionner demande le panneau (double-clic).
- L'observateur de sélection est le premier observateur permanent de l'atelier : il ne fait que
  dessiner ou enlever les flèches, et n'existe que tant que l'atelier est actif (ADR 0007).
- Une pièce posée à la souris ne suit pas sa voisine si celle-ci bouge (comme l'accrochage de
  l'ADR 0011) ; le suivi reste le rôle de l'ensemble et des Distances gardées (ADR 0022).
- L'observateur de sélection est accompagné d'un second observateur, celui des documents : il
  oublie les flèches d'un document qui se ferme.
- `pivy` n'est utilisé que dans `gui/drag/overlay.py` (dessin), comme dans `gui/textures.py`.

## Note (2026-10-25, relecture du jalon)

Le refus prévu au point 5 (« une rangée bloquée refuse le relâchement et propose
« Déverrouiller et appliquer ») ne peut pas se produire et il est **retiré**. Un glissement ne
change ni la cote de l'ensemble ni une épaisseur : `bind_members` peut toujours écrire la nouvelle
position, et `BlockedRowError` ou `LockedPiecesError` ne sont jamais levées au relâchement. Le
code et les tests qui les attendaient (boîte « Déverrouiller et appliquer » du glissement,
reprise du glissement après déverrouillage) sont supprimés. Le refus reste réservé aux réglages
qui changent une cote ou une épaisseur (panneaux de l'ensemble et de la pièce, ADR 0019).

Les formules de l'utilisateur rendent toujours l'axe non glissable (point 5) : une formule sur la
position de la pièce, et aussi une formule sur la `Value` d'une Distance gardée de la pièce (le
suivi ne réécrit pas une valeur pilotée par une formule ; l'axe de cette Distance est refusé avec
le même message). Le statut reste **accepté**.

## Note (2026-10-26, décision de jv : épaisseur du massif)

jv : « Si c'est du massif l'épaisseur est modifiable. » La décision Q4 de la spécification
(« pas de poignée sur l'épaisseur », point 1 ci-dessus) est amendée : une pièce dont la famille est
le **massif** (`MaterialKind.SOLID`, d'après `part_kind`) reçoit aussi **deux poignées
d'épaisseur** (faces du dessus et du dessous, axe Z de la pièce) quand son panneau est ouvert, soit
six poignées ; un panneau (contreplaqué, MDF, mélaminé) garde l'épaisseur de la bibliothèque
(ADR 0015) et quatre poignées. La structure ne change pas : `core/magnet.resize` accepte les trois
axes (borne de 1 mm inchangée) et `drag_limits` décide, comme pour la longueur et la largeur (pièce
verrouillée, pièce en bois #87, formule de l'utilisateur sur `Thickness` ou sur la position en Z :
pas de poignée).

Dans un ensemble, une épaisseur tirée se comporte comme une épaisseur saisie dans le panneau
(ADR 0019, points 5 et 6) : pendant le glissement, la liaison de l'atelier sur `Thickness` est
mise de côté comme celles de `Length` et `Width` ; au relâchement la pièce reprend son placement
du début, l'épaisseur est contrôlée (`thickness_notices`) puis tout l'ensemble est relié sur la
géométrie d'avant (`relink_thickness`) : l'épaisseur est **gardée**, la rangée des autres membres
est recalculée. Contrairement au déplacement (note du 2026-10-25), cette modification peut donc
être **refusée** quand une rangée est bloquée par des pièces verrouillées : la pièce revient et le
message, qui cite les pièces, va dans la vue rapport. Échap rétablit l'épaisseur du début. La face
du dessus ou du dessous tirée n'est pas forcément celle qui bouge à l'arrivée : la position d'un
membre d'ensemble est refaite par ses liaisons (une épaisseur saisie dans le panneau fait de
même). Le statut reste **accepté**.

## Note (2026-10-27, B7 modifié par l'ADR 0026)

Le critère B7 (assemblage qui ne touche plus : déplacement gardé, avertissement) est **modifié**
par l'[ADR 0026](0026-assemblage-defait-par-un-deplacement.md) : au relâchement, une fenêtre
propose d'annuler le déplacement ou de supprimer les assemblages défaits, sans trace Python. Le
statut reste **accepté**.
