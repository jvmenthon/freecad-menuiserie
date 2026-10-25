# Déplacer et redimensionner à la souris avec aimantation ; définir une distance

- Issue : #65 (priorité haute, interface)
- Statut : **proposée** (architecture fonctionnelle et technique, sans code). Questions Q2 à Q8
  pour jv au § 9 ; les recommandations ★ servent de base en attendant ses réponses. Q1 tranchée
  par jv le 2026-10-25 : la pièce se **déplace à la souris à tout moment**, pas seulement panneau
  ouvert.
- Exigences de jv :
  - (2026-10-22, issue #65) « Lors de la création d'une pièce, pouvoir **déplacer la pièce et la
    redimensionner à la souris** dans la vue 3D, avec un **effet magnétique** (aimantation sur
    les faces, arêtes et sommets des pièces voisines). »
  - (2026-10-25) « Je veux pouvoir **définir une distance** : si je sélectionne 2
    faces/arêtes/points, clic droit → définir une distance. »
  - (2026-10-25) « Je veux pouvoir aussi **déplacer la pièce à la souris** » (hors du panneau).
  - (2026-10-25) jv attend cette fonction pour faire la recette de la PR #86 (épaisseurs fixes
    des ensembles) : le travail part donc de la branche de #86 (§ 5).
- ADR liés : [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](../adr/0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi par expressions natives](../adr/0009-suivi-par-expressions-natives.md),
  [0011 — Aperçu, accrochage et nom](../adr/0011-apercu-accrochage-et-nom.md),
  [0018 — Double-clic dans la vue 3D](../adr/0018-double-clic-dans-la-vue-3d.md),
  [0019 — Rangées et épaisseurs fixes](../adr/0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (PR #86),
  [0020 — Pièce en bois](../adr/0020-piece-en-bois-enveloppe-d-un-corps.md) (PR #87),
  **[0021 — Déplacement à la souris avec aimantation](../adr/0021-deplacement-a-la-souris-avec-aimantation.md)** (proposé),
  **[0022 — Distance entre deux pièces](../adr/0022-distance-entre-deux-pieces.md)** (proposé)
- Découpage : six PR, **(SM-a ∥ DI-a) → SM-b → (SM-c ∥ DI-b) → DI-c** (§ 5)

**Vocabulaire.** *Glisser* : déplacer la pièce à la souris, bouton gauche enfoncé. *Poignée* :
petit carré dessiné au milieu d'une face de bout ou de rive, qu'on tire pour changer la longueur
ou la largeur. *Guide* : plan, droite ou point d'une pièce voisine sur lequel la pièce glissée
peut s'aimanter. *Distance* : écart mesuré entre deux éléments (face, arête, sommet) de deux
pièces.

## 1. Contexte

Depuis J6, une pièce de bois se pose contre une face, une arête ou un sommet choisis **avant**
la création (accrochage ponctuel, ADR 0011), puis se règle au clavier dans le panneau (cotes,
boutons X, Y, Z). Pour la placer ailleurs, il faut taper des coordonnées dans l'éditeur de
propriétés ou passer par Std Transform, qui ne s'aimante sur rien et ne change pas les cotes.
Les ensembles (J4, #86) gardent les distances **aux bords de l'ensemble** (option « fixe / non
fixe »), mais rien ne permet de dire « cette étagère est à 320 mm du plateau ».

## 2. Objectif

Le menuisier peut :

1. **glisser** une pièce dans la vue 3D **à tout moment** quand l'atelier est actif : on la
   sélectionne d'un clic, puis on la tire ; elle suit la souris dans un plan (§ 4.3). Pendant la
   création et la modification (panneau ouvert), la pièce se glisse sans la sélectionner ;
2. panneau ouvert, **redimensionner** la pièce en tirant l'une des quatre **poignées** (deux bouts pour la
   longueur, deux rives pour la largeur) ; la face opposée ne bouge pas, l'épaisseur reste celle
   de la bibliothèque ;
3. sentir l'**aimantation** : à moins de 10 pixels d'une face, d'une arête ou d'un sommet d'une
   pièce voisine (de l'atelier ou de tout autre objet Part), la face de la pièce vient s'y coller
   ou s'y aligner, et le guide s'allume ; **Maj** enfoncée coupe l'aimantation ;
4. voir les champs du panneau (position, cotes) suivre la souris, et **annuler** tout le
   glissement par « Annuler » ou Ctrl+Z (une seule transaction, celle du panneau) ;
5. sélectionner **deux éléments** (faces, arêtes ou sommets) de deux objets, faire **clic droit →
   « Définir une distance »**, lire la distance actuelle, en saisir une autre : la pièce choisie
   se déplace pour la respecter ;
6. dans un **ensemble**, cocher « Garder cette distance » : la distance devient un objet
   **Distance** de l'arborescence, dont la valeur reste vraie quand l'ensemble change de cote ou
   qu'une épaisseur change, et se règle comme une cote (expression, tableur).

## 3. Critères d'acceptation

Unitaires (**U**, sans FreeCAD), intégration (**I**, `freecadcmd` 1.0 et 1.1), interface (**G**,
`tests/gui`) et recette manuelle (**R**).

### SM-a — Glissement et aimantation, règles pures (`core/magnet/`)

| N° | Type | Critère |
|---|---|---|
| A1 | U | `drag_plane(view_dir, frame)` : plan perpendiculaire à l'axe du repère de la pièce le plus proche de la direction de vue (vue de dessus → plan XY ; vue de face → plan XZ ; égalité → Z d'abord, puis Y). |
| A2 | U | `ray_hit(ray, plane)` : point d'intersection ; rayon parallèle au plan (à `ANGLE_TOLERANCE` près) → `None` (le glissement s'arrête, rien n'est écrit). |
| A3 | U | `magnet(box, guides, delta, tolerance, axes)` : sur chaque axe libre, la face (début ou fin) de la boîte déplacée la plus proche d'un guide à moins de `tolerance` s'y colle ; axes indépendants ; égalité → le guide le plus proche du curseur, puis le premier. Aucun guide à portée → `delta` inchangé. |
| A4 | U | Un guide **plan** n'aimante que les faces parallèles ; une droite aimante les deux axes qui lui sont perpendiculaires ; un point aimante les trois axes. Un guide hors de portée de la pièce sur les autres axes (§ 4.4, Q3) est ignoré. |
| A5 | U | Contact (normales opposées) et affleurement (normales de même sens) sont deux aimantations valables ; le résultat dit lequel (`MagnetHit.kind`) pour l'affichage. |
| A6 | U | `resize(box, handle, delta, guides, tolerance, minimum)` : seule la face tirée bouge, le long de son axe ; cote bornée à `minimum` (1 mm) ; poignée sur l'épaisseur impossible (`ValueError`). Le résultat donne la cote nouvelle et la translation de l'origine (poignée de début). |
| A7 | U | `handle_at(handles_px, cursor_px, radius=8)` : poignée la plus proche à moins de 8 pixels, sinon `None`. |
| A8 | U | `mm_per_pixel(p0, p1, px)` : tolérance en mm d'après deux points projetés ; jamais nulle ni négative. |

### SM-b — Guides et écriture (`features/magnet_guides.py`, `features/part_drag.py`)

| N° | Type | Critère |
|---|---|---|
| B1 | I | `collect_guides(part, container)` lit, une fois au début du glissement, les sommets, faces planes et arêtes droites des objets **visibles** du conteneur (tout atelier : Part, PartDesign, Draft, BIM, objets d'addons), exprimés dans le repère de la pièce ; la pièce elle-même, sa pièce usinée et ses assemblages sont exclus ; au plus `MAX_GUIDES` (5 000), les objets les plus proches d'abord. |
| B2 | I | `move_part(part, transform)` et `resize_part(part, prop, value, origin_shift)` écrivent `Placement`, `Length` ou `Width` de la **brute** (une pièce usinée glissée renvoie à sa brute, ADR 0006), sans recalcul du document. |
| B3 | I | Pièce **membre d'un ensemble** : au début du glissement, les liaisons de l'ensemble sur les propriétés touchées sont mises de côté ; au relâchement, tout l'ensemble est relié (règle de l'ADR 0019, point 6). Bureau de référence : voile glissé de 100 mm vers l'avant → ses liaisons de position sont refaites avec la nouvelle constante, la largeur du bureau ne change pas. |
| B4 | I | Propriété pilotée par une **formule de l'utilisateur** (pas une liaison de l'atelier) : l'axe correspondant n'est pas glissable (`DragLimits.fixed_axes`), aucune expression n'est retirée. |
| B5 | I | Pièce **verrouillée** (`Locked`, #86) : glissement permis, poignées refusées. Pièce en bois (#87) : glissement permis, poignées refusées (cotes du dessin). |
| B6 | I | Une pièce qui a une **Distance** gardée (DI-c) le long de l'axe glissé : la valeur de la Distance suit le glissement (Q8 ★). |
| B7 | I | Assemblage qui ne touche plus après le glissement : le glissement est gardé, avertissement dans la vue rapport (règle Q4 de J4 : toujours appliquer, prévenir). |

### SM-c — Interaction dans la vue 3D (`gui/drag/`, panneau de la pièce)

| N° | Type | Critère |
|---|---|---|
| C1 | G | Atelier actif : le filtre d'évènements d'application est posé (comme le double-clic, ADR 0018) ; atelier quitté, il est retiré. Panneau de la pièce ouvert : les poignées sont dessinées ; panneau fermé (OK, Annuler, document ou vue fermés), elles sont enlevées. |
| C2 | G | **Hors panneau** : clic gauche enfoncé sur une pièce de l'atelier **déjà sélectionnée** (seule sélection), puis mouvement de plus de 4 pixels : la pièce suit la souris dans le plan A1 ; relâchement : transaction « Déplacer la pièce », un seul recalcul. Un clic sans mouvement reste un clic (sélection inchangée). **Panneau ouvert** : même geste sur la pièce du panneau, sans sélection préalable ; les champs X, Y, Z suivent ; tout reste dans la transaction du panneau. |
| C3 | G | Clic gauche sur une pièce non sélectionnée, sur un autre objet ou dans le vide : l'évènement est rendu à FreeCAD (sélection, cadre de sélection, rotation de la vue inchangés). Molette, bouton du milieu, bouton droit : toujours rendus. Plusieurs objets sélectionnés : pas de glissement (déplacer un groupe : hors périmètre). |
| C4 | G | Poignée tirée : la cote suit, l'autre bout ne bouge pas ; le champ de la cote du panneau suit ; l'aperçu (transparence 60 %) reste posé. |
| C5 | G | Guide aimanté : il est dessiné en surbrillance (plan, droite ou point) pendant l'aimantation ; Maj enfoncée : aucune aimantation, aucun dessin. |
| C6 | G | Échap pendant le glissement : la pièce revient où elle était au début de ce glissement (le panneau, s'il est ouvert, le reste). |
| C7 | G | « Annuler » du panneau : la pièce revient à son état d'avant le panneau ; « OK » puis Ctrl+Z : idem, en une étape. Hors panneau : Ctrl+Z annule le dernier glissement en une étape. |
| C8 | R | Recette sur FreeCAD 1.0 et 1.1 (Windows, styles de navigation « Gesture », « OpenInventor », « Blender ») : déplacer une étagère entre deux joues, l'aimanter contre la joue gauche, la redimensionner jusqu'à la joue droite ; même chose dans le bureau de #86 (rangées et épaisseurs vivantes). |

### DI-a — Distance entre deux éléments, règles pures (`core/distance/`)

| N° | Type | Critère |
|---|---|---|
| D1 | U | `measure(a, b)` pour les neuf paires de cibles (`FaceTarget`, `EdgeTarget`, `VertexTarget` de `core/snap`) : face–face parallèles, face–arête parallèle, face–sommet → distance le long de la normale de la face ; arête–arête parallèles, arête–sommet → distance perpendiculaire à la droite ; sommet–sommet → distance directe. Résultat `Gap(value, direction)` : `direction` = sens dans lequel la pièce mobile s'éloigne. |
| D2 | U | Faces ou arêtes **non parallèles**, face non plane, arête courbe → `DistanceError` au message traduisible (« Les éléments ne sont pas parallèles : la distance n'est pas définie. »). |
| D3 | U | `moved_by(gap, value)` : translation qui amène la distance à `value` (≥ 0) le long de `direction`, la pièce mobile restant **de son côté** ; distance actuelle nulle → côté donné par la normale sortante de l'élément mobile. |
| D4 | U | Sommet–sommet : `axis` facultatif (X, Y, Z du conteneur) → distance et translation projetées sur cet axe seul. |
| D5 | U | `ensemble_axis(gap, frame)` : axe de l'ensemble (X, Y, Z) si `direction` lui est parallèle, sinon `None` (la distance ne peut pas être gardée, DI-c). |

### DI-b — Commande « Définir une distance » (`gui/commands/distance.py`, `gui/task_panels/distance.py`)

| N° | Type | Critère |
|---|---|---|
| E1 | G | Commande `Menuiserie_SetDistance` (menu, barre d'outils, icône générée) **et** entrée du menu contextuel de la vue 3D et de l'arborescence (`Workbench.ContextMenu`), présente seulement si la sélection compte exactement deux éléments de deux objets différents. |
| E2 | G | Panneau : ligne « Entre : … et … », distance actuelle, champ « Distance » (unités du document, expressions acceptées), case « Pièce déplacée : … » avec bouton **Inverser**, liste « Direction » pour sommet–sommet (Directe, X, Y, Z). La pièce déplacée suit la saisie en direct (règle de jv : formulaire → vue 3D en direct). |
| E3 | G | Pièce déplacée par défaut : le **second** élément sélectionné, s'il appartient à une pièce de l'atelier ; sinon le premier ; aucun des deux → commande refusée avec un message (« Choisissez au moins une pièce de l'atelier : les autres objets ne sont pas déplacés. »). |
| E4 | G | Pièce membre d'un ensemble : le déplacement relie l'ensemble (comme B3). Position pilotée par une formule de l'utilisateur sur l'axe concerné : refus expliqué. |
| E5 | G | « OK » : une transaction « Définir une distance » ; « Annuler » : rien n'a changé. |
| E6 | R | Recette : étagère à 320 mm sous le plateau (face–face), tourillon à 30 mm du bout (sommet–face), traverse alignée à 0 mm (arête–arête), sur 1.0 et 1.1. |

### DI-c — Distance gardée dans un ensemble (`features/distance.py`, `core/furniture/`)

| N° | Type | Critère |
|---|---|---|
| F1 | U | `Member` reçoit les distances gardées sous forme de `KeptGap(key, a, a_end, b, b_end, axis)` ; dans la rangée d'une des deux pièces, l'intervalle entre la face de `a` et celle de `b` est un **bloc rigide virtuel** : cellule rigide qui vaut `Name.Value` (la Distance, citée par son `Name`) quand elle est une seule cellule, constantes figées sinon (même règle que l'épaisseur coupée, ADR 0019 point 2). |
| F2 | U | Deux pièces reliées par une distance gardée sont **en vis-à-vis** sur son axe même si leurs étendues ne se recouvrent pas sur les autres axes (règle 1 bis de la rangée). |
| F3 | U | Bureau de référence, voile à 320 mm sous le plateau (gardée) : Height → 800, le voile monte avec le plateau (320 mm conservés) ; épaisseur du plateau 25 → le voile descend de 3 mm ; Distance.Value → 300 : le voile monte de 20 mm sans code de l'atelier (expression `… - Distance001.Value`). |
| F4 | U | Distance gardée qui rend la rangée sans cellule libre → rangée **bloquée** : même refus que l'ADR 0019 (`BlockedRowError`), la Distance comptée comme une pièce verrouillée ; le panneau propose « Ne plus garder et appliquer ». |
| F5 | I | Objet `Distance` (`App::FeaturePython`, sans forme, libellé « Distance : {a} – {b} ») : `PieceA`, `PieceB` (`App::PropertyLink`, lecture seule), `Axis` (X, Y, Z, lecture seule), `SideA`, `SideB` (début/fin, cachées), `Value` (`App::PropertyLength`). Placé dans le groupe de l'ensemble s'il en a un, sinon à côté de l'ensemble. |
| F6 | I | Supprimer l'une des deux pièces, la retirer de l'ensemble, ou supprimer l'ensemble supprime la Distance (sans boîte « objets référencés ») et relie l'ensemble. Supprimer la Distance relie l'ensemble ; la pièce ne bouge pas. |
| F7 | I | Copier-coller, Dupliquer : la Distance copiée suit les pièces copiées (liens réécrits par FreeCAD) ; document rouvert sans l'atelier : Distance inerte, pièces à leur place (expressions natives). |
| F8 | G | Double-clic sur une Distance (arborescence ou vue 3D, ADR 0018) : le panneau de DI-b, sur cette Distance (Valeur modifiable, case « Garder » cochée). |

## 4. Conception

### 4.1 Principe (ADR 0021, ADR 0022)

- **Glisser à tout moment, sur une pièce déjà sélectionnée** (Q1, choix de jv). Un filtre
  d'évènements d'application est posé tant que l'atelier est actif, avec celui du double-clic
  (ADR 0018), et retiré quand on le quitte. Il ne consomme un clic gauche que s'il tombe sur une
  pièce de l'atelier **déjà sélectionnée seule** (hors panneau), sur la pièce du panneau ou sur
  une de ses poignées (panneau ouvert), et seulement après 4 pixels de mouvement : un simple clic
  reste un clic. Tout le reste (navigation, cadre de sélection, rotation au clic gauche du style
  Gesture, autres ateliers) suit son cours, puisque ces gestes partent d'un endroit qui n'est
  pas une pièce sélectionnée. Std Transform n'est ni remplacé ni modifié.
- **Hors panneau**, le glissement ouvre sa propre transaction « Déplacer la pièce » (un Ctrl+Z) ;
  **panneau ouvert**, il écrit dans la transaction du panneau. Les poignées (redimensionner) ne
  sont dessinées que panneau ouvert.
- **Calcul pur, lecture et écriture séparées** (comme `core/snap`) : plan de glissement, rayon,
  aimantation, poignées et tolérance sont des fonctions pures (`core/magnet/`) ; la lecture des
  formes en guides et l'écriture des propriétés sont dans `features/` (testables dans
  `freecadcmd`) ; les évènements, le dessin des poignées et des guides sont dans `gui/`.
- **Pas de recalcul pendant le glissement** : écrire `Placement` déplace l'affichage sans
  recalcul ; une poignée recalcule la seule brute (`obj.recompute()`, au plus 30 fois par
  seconde) ; le document est recalculé une fois au relâchement (pièce usinée, assemblages,
  ensemble, liste de débit).
- **Distance = mouvement ponctuel, sauf dans un ensemble.** « Définir une distance » déplace la
  pièce une fois, sans lien (comme l'accrochage, ADR 0011). Dans un ensemble, « Garder cette
  distance » crée un objet **Distance** que les règles des rangées (ADR 0019) traitent comme un
  **bloc rigide virtuel** à valeur vivante : c'est l'extension, entre deux pièces, des distances
  fixes aux bords de J4 (Q6, Q7).

```
freecad/menuiserie/
├── core/
│   ├── magnet/
│   │   ├── __init__.py        SM-a  façade : DragPlane, Ray, Guide, GuideKind, MagnetHit, Handle, DragResult, drag_plane, ray_hit, magnet, resize, handle_at, mm_per_pixel
│   │   ├── _model.py          SM-a  objets valeur
│   │   ├── _plane.py          SM-a  plan de glissement, rayon
│   │   └── _magnet.py         SM-a  aimantation par axe, poignées
│   ├── distance/
│   │   ├── __init__.py        DI-a  façade : Gap, DistanceError, measure, moved_by, ensemble_axis
│   │   └── _measure.py        DI-a  Strategy par paire de cibles
│   └── furniture/
│       ├── _model.py          DI-c  KeptGap ; Member.gaps
│       └── _rows.py           DI-c  bloc rigide virtuel, vis-à-vis 1 bis
├── features/
│   ├── magnet_guides.py       SM-b  formes → guides (tout atelier)
│   ├── part_drag.py           SM-b  DragLimits, move_part, resize_part, liaisons mises de côté, relier
│   ├── distance.py            DI-c  proxy Distance, création, suppression liée
│   └── furniture_bindings.py  DI-c  lecture des Distances d'un ensemble, `Name.Value` dans les liaisons
├── api.py                     DI-b  set_distance(a, b, value, *, moving=None, axis=None, keep=False)
└── gui/
    ├── drag/
    │   ├── __init__.py        SM-c
    │   ├── session.py         SM-c  DragSession (State : attente, survol, glissement, poignée)
    │   ├── events.py          SM-c  filtre Qt de la zone d'affichage (pixels → FreeCAD, view_point de l'ADR 0018)
    │   └── overlay.py         SM-c  poignées et guides dessinés (pivy, SoAnnotation), posés puis retirés
    ├── task_panels/
    │   ├── wood_part_drag.py  SM-c  branche la session sur le panneau (champs qui suivent)
    │   └── distance.py        DI-b  DistanceTaskPanel
    ├── commands/distance.py   DI-b  Menuiserie_SetDistance
    ├── view_providers/distance.py  DI-c
    └── init_gui.py            DI-b  ContextMenu
```

### 4.2 Design patterns retenus

| Besoin | Pattern | Justification |
|---|---|---|
| Glissement, poignée, survol, attente | **State** (`DragSession` : `Idle`, `Hover`, `Moving`, `Resizing`), une classe par état, transitions sur évènement | pas de drapeaux croisés ; Échap et fin du panneau ramènent à `Idle` depuis tout état |
| Guides (plan, droite, point) et paires d'éléments d'une distance | **Strategy** par type (registre, comme `FRAME_BUILDERS` de `core/snap`) | neuf paires de distance, trois guides, point d'extension (axe de perçage, cylindre) |
| Retour en arrière d'un glissement (Échap) et liaisons mises de côté | **Memento** (placement, cotes et expressions du début du glissement) | rétablis tels quels, rien de persistant |
| Dessin temporaire | **Proxy d'affichage** (`Overlay` : un nœud Coin posé à l'ouverture, retiré à la fermeture) | rien dans le document, rien qui reste si FreeCAD ferme la vue |
| Création de la Distance | **Fabrique** `api.set_distance` (une seule voie : commande, console, tests) | règle du projet |
| Objet Distance | **Proxy** FeaturePython + ViewProvider séparé | règle du projet |

### 4.3 Plan et gestes (SM-a, SM-c)

- **Plan de glissement** (Q2 ★) : perpendiculaire à l'axe de la **pièce** le plus proche de la
  direction de vue, passant par le point saisi. Vue de dessus : la pièce glisse à l'horizontale ;
  vue de face : dans le plan vertical. **Ctrl** enfoncé : la pièce ne bouge que le long de cet
  axe (monter, descendre). **Maj** : pas d'aimantation. Ces touches ne servent à rien d'autre
  pendant un glissement (FreeCAD n'en reçoit pas l'évènement).
- **Rayon** : point du plan focal `view.getPoint(x, y)` et direction de vue (caméra orthogonale,
  par défaut dans FreeCAD) ; caméra en perspective : origine = position de la caméra (lue par
  `getCameraNode`). Calcul dans `core/magnet` (`ray_hit`).
- **Saisie** : `view.getObjectInfo` (déjà utilisé par le double-clic) donne l'objet sous le
  curseur ; la pièce, sa pièce usinée ou l'un de ses assemblages saisis renvoient à la brute.
  Les **poignées** sont testées avant, en pixels (`handle_at`), d'après leurs centres projetés
  (`view.getPointOnScreen`).
- **Poignées** : quatre, au milieu des faces de bout et de rive ; aucune sur les faces de
  l'épaisseur (Q4 ★ : l'épaisseur vient de la bibliothèque, ADR 0015). Tirée, la poignée bouge le
  long de la normale de sa face ; la cote vaut au moins 1 mm.
- **Champs du panneau** : la session écrit l'objet, puis demande au panneau de relire `Length`,
  `Width`, `Placement` (méthode existante de rafraîchissement des champs), sous le garde
  d'écriture du panneau pour ne pas reboucler.

### 4.4 Aimantation (SM-a, SM-b)

- **Guides** collectés une fois, au début du glissement (`collect_guides`), dans le **repère de
  la pièce** (rotation de son `Placement`) : une pièce tournée s'aimante sur les voisines
  parallèles à elle. Plans : faces planes dont la normale est parallèle à un axe de la pièce ;
  droites : arêtes droites parallèles à un axe ; points : tous les sommets. Lecture par
  `Part.getShape` (ADR 0007 : tout atelier, rien de modifié).
- **Portée** (Q3 ★ « voisines ») : un guide ne compte que s'il est à portée de la pièce sur les
  deux autres axes (recouvrement des étendues à `tolerance` près). Une étagère s'aimante sur la
  joue qu'elle longe, pas sur la joue d'un autre meuble au fond de la pièce. Les alignements à
  distance (façon SketchUp) sont l'option b de Q3.
- **Tolérance** : 10 pixels convertis en mm à la profondeur de la pièce (`mm_per_pixel`) ; zoomé
  de près, l'aimant devient fin.
- **Par axe** : sur chaque axe libre (2 en glissement, 1 avec Ctrl ou sur une poignée), la face
  de début ou de fin la plus proche d'un guide s'y colle. Contact et affleurement valent tous les
  deux (A5). Le milieu des faces n'est pas un aimant (hors périmètre).
- **Chevauchement** : l'aimant n'empêche pas une pièce d'entrer dans une autre (les assemblages
  par superposition en ont besoin, ADR 0014, 0016).

### 4.5 Pièces d'un ensemble (SM-b, Q5 ★)

Une pièce membre suit l'ensemble par des expressions (ADR 0009, 0019). Écrire sa position sans
toucher à ses liaisons serait effacé au recalcul suivant. Au début du glissement, `part_drag`
met de côté (Memento) les expressions **de l'atelier** sur les propriétés touchées
(`Placement.Base.x/y/z`, `Length`, `Width`) ; au relâchement, l'ensemble entier est relié par la
voie de #86 (`bind_members`), qui recalcule les constantes d'après la position nouvelle sans
changer les options. Une formule de l'utilisateur sur un axe le rend non glissable (B4). Une
rangée qui deviendrait bloquée (ADR 0019, point 5) : le glissement est refusé au relâchement, la
pièce revient (Memento) et la boîte « Déverrouiller et appliquer » de #86 est proposée.

### 4.6 « Définir une distance » (DI-a, DI-b)

- **Sélection** : exactement deux éléments (`Face`, `Edge`, `Vertex`) de deux objets. Les cibles
  sont lues par `features/snap_targets.py` (J6d), qui sait déjà lire tout objet Part.
- **Mesure** (`measure`) : Strategy par paire (D1) ; neuf paires ramenées à quatre calculs
  (plan–plan, plan–point, droite–droite, point–point) en prenant pour une arête parallèle à un
  plan un de ses points.
- **Pièce déplacée** : seulement une pièce de l'atelier (pièce de bois, pièce en bois de #87) ;
  les objets des autres ateliers servent de référence et ne bougent jamais (ADR 0007). Par
  défaut le second élément sélectionné (E3) ; bouton Inverser.
- **Menu contextuel** : `MenuiserieWorkbench.ContextMenu(recipient)` ajoute l'entrée quand la
  sélection convient (`recipient` = « View » ou « Tree »). Il n'existe que quand l'atelier est
  actif : aucune modification du menu des autres ateliers (ADR 0007) ; ailleurs, la commande
  reste dans le menu Menuiserie.
- **Application** : `api.set_distance` écrit le `Placement` (brute), relie l'ensemble si la pièce
  est membre (comme § 4.5), crée la Distance si `keep` (DI-c).

### 4.7 Distance gardée (DI-c, ADR 0022)

- Proposée (case « Garder cette distance », cochée par défaut ★) seulement si les deux pièces
  sont membres du **même ensemble** et que la direction est parallèle à un axe de l'ensemble
  (D5). Sinon la case est grisée, infobulle explicative (Q6).
- L'objet **Distance** ne porte aucun nom topologique (`Face3`) : il retient les deux pièces,
  l'axe de l'ensemble et le côté de chaque pièce (début/fin de son étendue sur l'axe), lus dans
  le modèle des rangées. Il survit donc aux changements de forme qui renumérotent les faces.
- **Règle des rangées** (complète l'ADR 0019) : 1 bis — deux pièces reliées par une Distance
  sont en vis-à-vis sur son axe ; 4.2 bis — l'intervalle entre les deux faces est un **bloc
  rigide virtuel**, traité comme l'épaisseur d'une pièce : une seule cellule → `Name.Value`
  vivant ; coupé par une autre face → constantes et notice `GapSplit`. Une Distance compte comme
  une pièce verrouillée pour le blocage (F4).
- Les liaisons citent la Distance par son `Name` (`Distance001.Value`), comme les épaisseurs
  (#86) : changer `Value` ne fait appel à aucun code de l'atelier (ADR 0009).
- Glisser une pièce le long de l'axe d'une Distance gardée met sa `Value` à jour au relâchement
  (Q8 ★).

### 4.8 Sécurité

Aucune entrée hors de FreeCAD. La valeur saisie passe par `Gui.ExpressionBinding` / unités de
FreeCAD ; l'atelier n'écrit dans une expression que des `Name` d'objets et des nombres formatés
(jamais un libellé saisi). Le filtre d'évènements ne garde aucune référence au-delà du panneau
(leçon J2 : pas de formulaire ni d'enveloppe PySide gardés après la fermeture) ; `MAX_GUIDES`
borne la lecture des formes d'un gros document.

### 4.9 Compatibilité avec les autres ateliers (ADR 0007)

- Le filtre n'existe que tant que l'atelier est actif et ne consomme que le glisser qui part
  d'une pièce **de l'atelier déjà sélectionnée** (ou de la pièce du panneau, de ses poignées) ;
  les styles de navigation de FreeCAD restent intacts pour tout autre geste.
- Les guides se lisent sur tout objet Part sans le modifier ; aucun objet d'un autre atelier
  n'est déplacé par une distance.
- Le menu contextuel n'est enrichi que quand l'atelier est actif.
- L'objet Distance est un `App::FeaturePython` ordinaire ; sans l'atelier, il reste inerte et
  les expressions qui le citent restent valables (FreeCAD lit `Value`).

## 5. Découpage en PR et impact

| Lot | Branche | Contenu | Diff estimé hors tests | Critères | Dépend de |
|---|---|---|---|---|---|
| **SM-a** | `feat/souris-core` | `core/magnet/` | ≈ 330 | A1–A8 | — |
| **DI-a** | `feat/distance-core` | `core/distance/` | ≈ 220 | D1–D5 | — |
| **SM-b** | `feat/souris-guides` | `features/magnet_guides.py`, `features/part_drag.py` | ≈ 280 | B1–B7 | SM-a, #86 |
| **SM-c** | `feat/souris-interface` | `gui/drag/` (filtre posé avec l'atelier, session hors panneau et panneau), `wood_part_drag.py`, `init_gui.py`, icônes de poignée, README « Glisser une pièce », recette | ≈ 460 | C1–C8 | SM-b |
| **DI-b** | `feat/distance-commande` | `api.set_distance`, commande, menu contextuel, panneau, icône, recette | ≈ 330 | E1–E6 | DI-a, SM-b |
| **DI-c** | `feat/distance-gardee` | `features/distance.py`, ViewProvider, règles 1 bis et 4.2 bis de `core/furniture`, liaisons, suppression liée | ≈ 380 | F1–F8 | DI-b, #86 |

- **Branche de jalon** `jalon/souris-distances`, partie de `feat/ensemble-epaisseurs` (#86) :
  jv recette #86 et #65 ensemble, et SM-b, DI-c touchent aux mêmes fichiers (panneau découpé,
  liaisons). Si #86 est fusionnée avant, la branche reprend `main`. Sous-lots fusionnés en
  squash dans la branche de jalon, une PR finale vers `main` (fusion par jv).
- SM-a et DI-a partent en parallèle (Python pur). SM-c et DI-b en parallèle après SM-b.
- **Impact sur l'existant** : `features/furniture_bindings.py` et `core/furniture/_rows.py`
  (DI-c, petites extensions de #86) ; `gui/task_panels/wood_part.py` (une ligne : brancher la
  session) ; `init_gui.py` (`ContextMenu`, commande). Rien ne change pour les documents sans
  Distance.
- #87 (pièce en bois) : glissement sans poignée (B5) ; si #87 arrive avant, SM-b la prend en
  compte par `is_timber`, sinon #87 ajoute une ligne à `part_drag`.

## 6. Compatibilité des documents

Aucune propriété nouvelle sur les pièces ni sur l'ensemble ; le glissement n'écrit que des
propriétés existantes. Seul DI-c ajoute un type d'objet (`Distance`, `Version` = 1). Un document
avec Distance ouvert par une version antérieure de l'atelier : objet inerte (proxy introuvable),
pièces à leur place, expressions toujours évaluées par FreeCAD.

## 7. Risques

| Risque | Parade |
|---|---|
| Un style de navigation (Gesture) commence une rotation au clic gauche avant notre filtre | filtre d'**application** posé avant celui de Quarter, comme le double-clic (ADR 0018, éprouvé sur 1.0 et 1.1) ; recette C8 sur trois styles |
| Lenteur sur un gros document (formes lues à chaque mouvement) | guides lus une fois au début du glissement, bornés à 5 000 ; pas de recalcul du document pendant le glissement |
| Pièce usinée affichée qui ne suit pas la brute pendant le glissement | la pièce usinée suit le `Placement` de sa brute (J3) ; ses découpes sont recalculées au relâchement |
| Rayon parallèle au plan (vue rasante) | `ray_hit` → `None`, la pièce reste (A2) |
| Caméra en perspective | origine du rayon lue sur la caméra ; testé en recette |
| Enveloppes PySide réutilisées sur 1.0 | aucune référence Qt gardée hors de la session ; session détruite à la fermeture du panneau |
| Cycle d'expressions avec une Distance | Distance citée comme une épaisseur : même ordre des clés et même gel en constante que #86 (ADR 0019, point 7) |

## 8. Hors périmètre (issues à ouvrir si jv le souhaite)

- Glisser plusieurs pièces sélectionnées ensemble ; redimensionner sans ouvrir le panneau.
- Aimant sur le **milieu** des faces, sur les axes de cylindres, sur la grille.
- Cote dessinée dans la vue 3D pour une Distance gardée (Q8 bis, plus tard).
- Distance entre deux éléments d'**une même pièce** (ce serait « définir une cote » : longueur
  entre ses deux bouts).
- Distance gardée hors ensemble (option b de Q6) et distance d'angle.
- Saisie d'une valeur au clavier pendant le glissement (façon SketchUp).

## 9. Questions pour jv

**Q1 — Quand peut-on glisser une pièce ?** Tranchée par jv (2026-10-25) : « je veux pouvoir
aussi déplacer la pièce à la souris » → **à tout moment** quand l'atelier est actif. Pour ne pas
gêner la navigation (rotation au clic gauche du style Gesture, cadre de sélection), le glissement
part d'une pièce **déjà sélectionnée** : un clic pour la choisir, puis on la tire. Panneau ouvert,
la pièce se tire directement et les poignées de redimensionnement apparaissent.

**Q2 — Dans quel plan la pièce glisse-t-elle ?**
1. ★ **Plan perpendiculaire à l'axe de la pièce le plus proche de la vue**, Ctrl pour bouger le
   long de cet axe seul.
2. Le plan de la face contre laquelle la pièce est posée (elle « coulisse » sur son appui),
   sinon comme 1.
3. Une poignée à trois flèches (comme Std Transform) : précis, mais plus lent pour poser une
   pièce.

**Q3 — Sur quoi la pièce s'aimante-t-elle ?**
1. ★ **Les pièces voisines** : faces, arêtes, sommets des objets qu'elle longe ou touche presque
   (10 pixels).
2. En plus, les **alignements à distance** (affleurer une face d'un autre meuble au loin) :
   plus puissant, mais l'aimant « saute » plus souvent.

**Q4 — Peut-on tirer l'épaisseur ?**
1. ★ **Non** : quatre poignées (longueur, largeur) ; l'épaisseur se choisit dans la liste de la
   bibliothèque.
2. Oui, en sautant d'une épaisseur de la bibliothèque à la suivante.

**Q5 — Glisser une pièce d'un ensemble ?**
1. ★ **Oui** : la pièce se place où on la lâche et l'ensemble entier est relié (comme une
   saisie dans le panneau avec #86). Une pièce verrouillée glisse mais garde ses cotes.
2. Non : la retirer de l'ensemble d'abord.

**Q6 — Une distance entre deux pièces hors d'un ensemble, est-elle gardée ?**
1. ★ **Non, ponctuelle** : la pièce se déplace une fois, comme l'accrochage de J6. Pour garder
   une distance, on met les pièces dans un ensemble.
2. Oui : une liaison directe entre les deux pièces (la seconde suit la première), un mécanisme
   de plus à côté des ensembles, à concevoir.

**Q7 — Dans un ensemble, comment garder la distance ?**
1. ★ **Un objet « Distance » dans l'arborescence**, valeur réglable comme une cote (expression,
   tableur), case « Garder cette distance » cochée par défaut. C'est la « distance fixe » de J4,
   mais entre deux pièces au lieu d'une pièce et un bord.
2. Une simple option sur la pièce, sans objet : moins visible, impossible à piloter par un
   tableur.

**Q8 — On glisse à la souris une pièce tenue par une Distance gardée.**
1. ★ **La valeur de la Distance suit** le glissement (ce qu'on voit est ce qu'on garde).
2. La pièce ne peut pas bouger le long de cet axe tant que la Distance existe.

(Q8 bis, sans urgence : dessiner la cote d'une Distance dans la vue 3D ? ★ plus tard, issue
séparée.)
