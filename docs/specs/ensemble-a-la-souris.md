# Taille et orientation d'un ensemble à la souris

- Statut : **proposée**, en attente des réponses de jv (§ 8).
- Demande de jv (2026-11-07) : « quand je suis sur un ensemble je veux pouvoir aussi modifier la
  taille et l'orientation avec la souris ».
- ADR : **[0038 — Taille et orientation d'un ensemble à la souris](../adr/0038-ensemble-a-la-souris.md)**
  (proposé). ADR liés : 0008 (Ensemble, objet de cotes), 0019 (rangées), 0021 (glissement),
  0025 (rotation), 0007 (compatibilité).
- Reprend pour l'**ensemble** (`Furniture`, issue #86) les poignées de taille de la pièce (#65,
  PR #98) et les anneaux de rotation (#117, PR #128).

## 1. Contexte

- Un ensemble n'a **ni forme ni `Placement`** : il porte `Width`, `Depth`, `Height` et `Origin`
  (coin avant gauche bas) dans le repère de son conteneur ; ses pièces le suivent par des
  expressions (ADR 0008, 0009, 0019). Aujourd'hui ses cotes se changent dans son panneau
  (`resize_furniture`) ; il n'y a rien à saisir dans la vue 3D, et sélectionné il n'est pas
  dessiné.
- Une pièce sélectionnée seule porte des flèches de déplacement, des poignées de taille (panneau
  ouvert) et trois anneaux de rotation (`gui/drag/`, `core/magnet`, `core/rotation`).
- Tourner un ensemble se fait aujourd'hui par un Std Part (ADR 0008, point 4) : les liaisons
  des pièces supposent que les pièces sont d'équerre avec l'ensemble ; les pièces tournées une à
  une sortent des liaisons (notice « pas d'équerre »).

## 2. Objectif

Un ensemble sélectionné (dans l'arbre, ou une de ses pièces avec le raccourci du § 4.1) :

1. **Boîte** : sa boîte englobante (`Origin`, `Width`, `Depth`, `Height`) est dessinée en
   transparence dans la vue 3D.
2. **Taille** : une double flèche au milieu de chacune des six faces ; la tirer change la cote
   correspondante, la face opposée reste en place (`Origin` suit si on tire la face avant,
   gauche ou basse). Les pièces suivent selon leurs options « fixe », leur mode et leurs rangées
   (étirement, **pas** une mise à l'échelle : les épaisseurs ne changent pas). Aimant comme
   celui des pièces (10 px, Maj coupe) sur les faces voisines ; cote affichée près de la souris.
3. **Orientation** : trois anneaux autour du centre de la boîte (X rouge, Y vert, Z bleu), aimantés
   tous les 15°, Maj libre, angle affiché. Tout l'ensemble tourne, ses pièces avec lui et ses
   liaisons restent intactes (ADR 0038 : par un Std Part).
4. Un Ctrl+Z défait le geste ; Échap pendant le geste le ramène au début ; refus expliqué si une
   cote est bloquée (pièces verrouillées, cote minimale) comme dans le panneau.

## 3. Critères d'acceptation

### EN-a — Règles pures (`core/`)

- A1 `furniture_layout(box, frame, size_mm)` : poignées (6 faces) et anneaux d'une boîte, en
  réutilisant `core/magnet` et `core/rotation` sans les dupliquer.
- A2 `resized_box(box, face, delta)` : la face opposée ne bouge pas ; cote minimale 0,1 mm ; une
  entrée non finie est refusée.
- A3 Aucun import de FreeCAD, Qt ou pivy.

### EN-b — Écriture (`features/furniture_drag.py`)

- B1 `begin_furniture_drag` / `resize_furniture_to` (par `Memento`) : écritures absolues de
  `Width`, `Depth`, `Height`, `Origin` ; aucune écriture cumulée.
- B2 Pendant le glissement, seules les pièces **brutes** sont recalculées (pas les usinages), au
  plus 10 fois par seconde ; au relâchement : un recalcul complet et les avertissements d'ADR 0017.
- B3 Cote refusée (`LockedPiecesError`, pièce trop petite) : le geste s'arrête à la dernière
  valeur permise, message près de la souris ; jamais d'écriture perdue en silence.
- B4 Rotation : `ensure_container(furniture)` renvoie le Std Part (`App::Part`) qui contient
  l'ensemble et tous ses membres, le crée au premier geste (ADR 0038) ; le geste écrit son
  `Placement`. Ensemble déjà dans un Std Part : on tourne ce Std Part (refus expliqué s'il
  contient autre chose que l'ensemble, Q2).
- B5 Sous-ensemble : taille, déplacement et rotation permis, par son propre Std Part (Q2).

### EN-c — Vue 3D (`gui/drag/`)

- C1 Ensemble sélectionné seul dans l'arbre : boîte, six poignées, trois anneaux ; la session de
  glissement (`DragSession`) accepte une cible « ensemble » en plus de la cible « pièce ».
- C2 Mêmes règles d'évènements que les pièces : seul le clic sur une poignée ou un anneau est
  consommé ; survol épaissi ; Échap ; transaction « Redimensionner l'ensemble » / « Tourner
  l'ensemble » (un Ctrl+Z).
- C3 Pièce membre sélectionnée seule : ses propres poignées (inchangé) ; Ctrl+clic sur la
  boîte de l'ensemble n'existe pas (Q4).
- C4 Vérification hors écran (`tests/gui`) : dessin, geste simulé par la session, Ctrl+Z, Échap,
  ensemble dans un Std Part tourné.

### EN-d — Panneau de l'ensemble

- D1 Trois champs d'angle (−360 à 360, comme la pièce) dans le panneau de l'ensemble, qui
  relisent le Std Part ; grisés avec une infobulle si l'ensemble est un sous-ensemble.
- D2 Les champs `Width`, `Depth`, `Height` du panneau relisent la valeur après un glissement.

## 4. Conception (voir ADR 0038)

### 4.1 Sélection

`_target_part` renvoie aujourd'hui la brute de la pièce sélectionnée. Elle devient `_target()` :
un `Target` (pièce ou ensemble) qui porte son repère (`frame`), sa boîte et ses poignées. Une
pièce membre n'ouvre pas l'ensemble (Q4).

### 4.2 Taille

Une poignée de face écrit la cote et, pour les faces avant, gauche et basse, `Origin` du même
delta (face opposée fixe). Les liaisons sont des expressions (`<<Ensemble>>.Width`…) : un recalcul
fait suivre les pièces. Aucun code de rangée n'est touché : on appelle `resize_furniture`
(`features/furniture_members.resize`) comme le panneau.

### 4.3 Orientation

Voir ADR 0038. Le Std Part est le mécanisme natif de FreeCAD (ADR 0008, point 4) ; l'ensemble, ses
membres et leurs assemblages sont rangés dedans, aucune propriété nouvelle sur l'ensemble.

## 5. Découpage

| Lot | Branche | Contenu |
|-----|---------|---------|
| EN-a | `feat/ensemble-souris-core` | `core/` : disposition, `resized_box` |
| EN-b | `feat/ensemble-souris-write` | `features/furniture_drag.py`, Std Part |
| EN-c ∥ EN-d | `feat/ensemble-souris-vue`, `feat/ensemble-souris-panneau` | session, dessin ; champs |

Branche de jalon `jalon/ensemble-souris`, depuis `main`. Revue complète à la fin (testeur +
sécurité + reviewer), PR unique vers `main`.

## 6. Risques

| N° | Risque | Parade |
|----|--------|--------|
| R1 | Ranger des objets existants dans un Std Part casse des expressions (portée) ou des liens. | Essai sur FreeCAD 1.1 avant EN-b (spike) ; refus expliqué sinon. |
| R2 | Recalcul des pièces trop lent pendant le geste. | Brutes seules, 10 Hz ; sinon aperçu par boîte seule (Q3). |
| R3 | Ensemble sans pièce ou à cotes illisibles : pas de boîte. | Aucune poignée, aucun message. |

## 7. Hors périmètre

Mise à l'échelle homogène, plusieurs ensembles
sélectionnés, gabarits.

## 8. Questions pour jv (★ recommandé)

- **Q1 — Taille.** a) étirer l'ensemble comme dans le panneau : les pièces suivent leurs options
  « fixe » (épaisseurs inchangées) ★ ; b) mise à l'échelle de toutes les pièces, épaisseurs
  comprises.
- **Q2 — Orientation.** **Tranchée par jv (2026-11-07) : a) Std Part, créé dès la création de
  l'ensemble.** Pas de reprise des anciens documents pour l'instant (jv). Une pièce ajoutée à
  l'ensemble est rangée dans son Std Part, une pièce retirée en sort à la même position.
  **Un sous-ensemble a son propre Std Part** (jv), rangé dans celui de son parent : l'objet
  sous-ensemble et ses membres sont dedans, son `Origin` y vaut (0, 0, 0) ; les liaisons du parent
  pilotent la position (`Placement.Base`) du Std Part du sous-ensemble au lieu de son `Origin`, et
  ses cotes comme avant. Cela amende l'ADR 0008 (point 3) et la règle F11 de J4 : à vérifier par
  l'essai sur FreeCAD 1.1 (expressions entre Std Part imbriqués). Un sous-ensemble tourné n'est plus
  d'équerre avec son parent : il le suit alors par translation seulement (règle des pièces en biais).
- **Q3 — Aperçu pendant le geste.** a) les pièces bougent en direct (brutes seules) ★ ; b) seule
  la boîte bouge, les pièces suivent au relâchement.
- **Q4 — Comment sélectionner ?** a) l'ensemble dans l'arbre ★ ; b) aussi un bouton « Sélectionner
  l'ensemble » dans le panneau d'une pièce membre.
- **Q5 — Flèches de déplacement** : **tranchée par jv (2026-11-07) : oui, dans ce jalon.** Trois
  flèches au centre de la boîte ; le geste décale `Origin` et les positions des pièces qui ne
  suivent pas `Origin` (pas de liaison sur cet axe), dans une transaction « Déplacer
  l'ensemble ». Aimant sur les objets voisins comme pour une pièce.
