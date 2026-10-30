# Rotation d'une pièce : angle saisi dans le panneau, anneaux dans la vue 3D

- Issue : #117
- Statut : **acceptée** (Q1 tranchée par jv le 2026-10-28 : angle libre ; Q2 à Q6 validées par jv le
  2026-10-29 : « c'est ok », voir § 9).
- Demande de jv (2026-10-28) : « ajoute la possibilité de choisir la rotation d'une pièce dans le
  formulaire et dans la vue ».
- ADR : **[0025 — Rotation libre d'une pièce](../adr/0025-rotation-libre-d-une-piece.md)** (accepté) ;
  ADR liés 0011 (aperçu et accrochage), 0021 (glissement à la souris), 0026 (assemblage défait par
  un déplacement, PR #111).
- Découpage : quatre PR, **RO-a → RO-b → (RO-c ∥ RO-d)** (§ 5), branche de jalon `jalon/rotation`
  partie de `main` **après la fusion de #111**.

**Vocabulaire.**

- *Angles de la pièce* : trois angles X, Y, Z en degrés qui décrivent la rotation de son
  `Placement` (dans le repère du document ou de son conteneur). Ce sont les angles du
  `Placement` de FreeCAD (roulis X, tangage Y, lacet Z), affichés dans l'ordre X, Y, Z.
- *Anneau* : cercle dessiné autour de la pièce sélectionnée, perpendiculaire à un axe du
  document ; le tirer fait tourner la pièce autour de cet axe.
- *Centre* : centre de la boîte de la brute (L × l × e). Il ne bouge pas pendant une rotation.

## 1. Contexte

Aujourd'hui (J6, Q1 de jv) le groupe « Rotation » du panneau de la pièce n'a que trois boutons de
quart de tour X, Y, Z (`features/placement.rotate_part`, `core/snap.Turn`). Après #111, ils passent
par `rotate_checked`, qui propose d'annuler ou de supprimer les assemblages défaits (ADR 0026). Dans la vue 3D, la pièce sélectionnée porte trois flèches de
déplacement et, panneau
ouvert, des poignées de taille (ADR 0021, `gui/drag/`, `core/magnet/`). Rien ne permet un autre
angle que le quart de tour, sauf l'éditeur de `Placement` de FreeCAD.

Ce qui sert déjà :

- une pièce en biais est tolérée partout : `squared_rotation` laisse passer une rotation oblique,
  l'accrochage sait s'appuyer sur une face inclinée (`support_rotation`), la liste de débit ne
  lit que L, l, e ;
- les assemblages d'une pièce hors d'équerre sont refusés proprement jusqu'à #114 (angles
  composés, 70° max), qui les rendra possibles ;
- la session de glissement (pattern State, Memento, transaction, Échap, fenêtre d'ADR 0026) est le
  bon endroit pour un état « Rotating ».

## 2. Objectif

1. **Panneau** : trois champs d'angle (X, Y, Z, en degrés, au dixième) dans le groupe
   « Rotation », sous les trois boutons de quart de tour qui restent. Une saisie s'affiche en
   direct dans la vue 3D (règle de jv du 2026-10-22). Les boutons mettent les champs à jour.
2. **Vue 3D** : trois anneaux (X rouge, Y vert, Z bleu, couleurs des axes de FreeCAD) autour de
   la pièce sélectionnée seule, avec ses flèches. Tirer un anneau fait tourner la pièce autour de
   l'axe du document qui passe par son centre ; l'angle parcouru s'affiche près de la souris ;
   l'anneau s'aimante tous les 15° ; Maj enfoncée, il tourne librement (au dixième de degré).
3. Un Ctrl+Z défait une rotation ; Échap pendant le geste ramène la pièce à son début.
4. Une rotation qui défait un assemblage passe par la fenêtre « Annuler / Supprimer » (ADR 0026).

## 3. Critères d'acceptation

### RO-a — Règles pures (`core/rotation/`)

- A1 `angles_of(matrix)` et `matrix_of(angles)` font l'aller-retour à 1e-9 près, y compris pour
  les 24 rotations d'équerre ; tangage à ±90° (blocage de cardan) : X est ramené à 0 et Z porte
  tout, sans `nan`.
- A2 `turned_about(transform, dimensions, axis, angle)` tourne autour du centre : le centre ne
  bouge pas à 1e-9 près ; 4 × 90° autour d'un axe redonne la rotation de départ.
- A3 `snapped_angle(angle, step=15, free=False)` : arrondi au multiple de 15° le plus proche ;
  `free=True` : arrondi au dixième. Entrées non finies refusées (`ValueError`).
- A4 `ring_of(box, rotation, axis)` donne centre, normale et rayon (1,15 × demi-diagonale de la
  boîte, au moins 20 mm) ; `ring_hit(ray, ring, tolerance)` dit si un rayon touche l'anneau (à
  `tolerance` mm près) ; `ring_angle(ray, ring, start)` donne l'angle signé parcouru, `None` si le
  rayon est parallèle au plan de l'anneau (moins de 5°).
- A5 Aucun import de FreeCAD, Qt ou pivy (test d'import existant étendu).

### RO-b — Écriture (`features/part_rotate.py`)

- B1 `rotate_to(obj, angles)` écrit la rotation absolue autour du centre, sans recalcul du
  document ; renvoie faux sans rien écrire si une expression pilote le `Placement` (liaison
  d'ensemble ou formule), comme `rotate_part`.
- B2 Une pièce usinée ou un assemblage renvoie à sa brute (`raw_part`) ; une pièce en bois
  (`ShapedPart`) tourne par son propre `Placement`, sa source n'est jamais écrite.
- B3 Le geste à la souris réutilise `DragMemento` : écritures absolues par rapport au début, rien
  ne s'accumule ; Échap rétablit le `Placement` et les `Distance` touchées.
- B4 Fin de rotation : même chemin que `end_drag` (Distances gardées mises à jour, fenêtre
  d'ADR 0026 si un assemblage est défait, un recalcul).
- B5 Dans un conteneur (`App::Part`, Body), les angles sont ceux du `Placement` local ; les
  anneaux suivent les axes globaux du conteneur.

### RO-c — Panneau (`gui/task_panels/wood_part.*`)

- C1 Trois `Gui::QuantitySpinBox` en degrés (−360 à 360 pour les trois axes, demande de jv du 2026-10-30 ;
  la saisie tourne la pièce comme demandé, puis les champs sont recalculés à la fin de la saisie
  en la forme canonique de `angles_of` : X et Z dans [−180, 180], Y dans [−90, 90] ; pas de 1, une
  décimale), étiquettes
  « Autour de X », « Autour de Y », « Autour de Z », sous les boutons.
- C2 `valueChanged` : `rotate_to` puis aperçu de la seule brute (comme une poignée, au plus
  30 fois par seconde) ; `editingFinished` : recalcul et contrôle des assemblages (fenêtre
  d'ADR 0026 ; « Annuler » remet l'angle d'avant la saisie).
- C3 Les boutons de quart de tour, un glissement et un anneau relisent les champs (signaux
  bloqués pendant l'écriture : pas de boucle).
- C4 Placement piloté par une expression : champs et boutons grisés, infobulle « Position
  pilotée par l'ensemble » (ou « par une formule »).
- C5 En création, une saisie d'angle arrête l'accrochage (la pièce n'est plus reposée), comme un
  glissement (`after_drag`) ; les boutons de quart de tour gardent l'accrochage.
- C6 Tout texte visible traduisible (`QT_TRANSLATE_NOOP`), en français.

### RO-d — Anneaux dans la vue 3D (`gui/drag/`)

- D1 Une pièce de l'atelier sélectionnée seule porte trois anneaux en plus de ses flèches,
  dessinés par l'incrustation existante (`Overlay`), invisibles pour la sélection de FreeCAD.
- D2 Survol d'un anneau : il s'épaissit (état `Hover`). Clic gauche sur un anneau : état
  `Rotating` ; seul ce clic est consommé, tout autre évènement est rendu à FreeCAD.
- D3 Pendant le geste : angle **obtenu** (angle de départ + angle parcouru, `snapped_turn`) aimanté à 15°, libre avec Maj, affiché près de la souris
  (« 37,5° ») ; secteur parcouru dessiné en transparence.
- D4 Hors panneau, le geste ouvre la transaction « Tourner la pièce » (un Ctrl+Z) ; panneau
  ouvert, il écrit dans la sienne et le panneau relit ses champs (C3).
- D5 Anneau vu par la tranche (A4 renvoie `None`) : il n'est pas proposé au survol. Il n'est pas
  non plus proposé quand son rayon à l'écran est inférieur à 16 pixels (pièce dézoomée) ; la
  tolérance de saisie (8 pixels) se mesure à l'écran, sur l'ellipse projetée, pas en mm au centre
  (revue #117).
- D6 Pièce pilotée par une expression : pas d'anneau (comme les flèches d'un axe bloqué).
- D7 Vérification hors écran (`tests/gui`) : dessin des anneaux, geste simulé par la session
  (pas de clic Qt réel, cf. leçons de l'interface hors écran), Ctrl+Z, Échap.

## 4. Conception

### 4.1 Angles (ADR 0025)

Les champs montrent les angles du `Placement` (convention de FreeCAD : `getYawPitchRoll`, rotation
= Rz · Ry · Rx, chaque angle autour d'un axe **fixe** du document, X d'abord). C'est ce que montre
l'éditeur de propriétés de FreeCAD : un menuisier qui passe de l'un à l'autre lit les mêmes
nombres. Une pièce posée debout par l'accrochage affiche donc déjà, par exemple, X = 90.

Un anneau, lui, tourne **à partir de l'orientation courante** autour de l'axe fixe choisi
(R' = R(axe, Δ) · R) ; les champs relisent ensuite les trois angles. Quand une seule rotation est
en jeu, anneau et champ disent la même chose ; avec plusieurs, l'anneau suit le geste et les
champs restent exacts.

### 4.2 Centre et accrochage

La rotation se fait autour du centre de la brute, comme le quart de tour en modification
(`turned_in_place`). En création, l'accrochage (J6d) ne sait reposer qu'une pièce d'équerre par
rapport à son appui : un angle saisi ou un anneau arrête la session d'accrochage (C5), comme le
fait déjà un glissement. Les boutons de quart de tour gardent leur comportement.

### 4.3 Session de la vue 3D

Nouvel état `Rotating` de `DragSession` (pattern State, ADR 0021), à côté de `Moving` et
`Resizing`. `geometry.build_layout` ajoute les anneaux (polylignes de 96 segments) ; le test de
survol et l'angle viennent de `core/rotation` (A4). Pendant le geste, seul `Placement` est écrit,
sans recalcul ; la brute est recalculée au plus 30 fois par seconde (`Throttle`), le document une
fois au relâchement. Les guides d'aimantation de position ne servent pas : seul l'angle s'aimante.

### 4.4 Assemblages et ensembles

- Assemblages : la fin d'une rotation passe par le même contrôle que la fin d'un glissement
  (ADR 0026). Une pièce tournée hors d'équerre ne peut pas recevoir de **nouvel** assemblage
  avant #114 : le refus existant (« Les deux pièces doivent être d'équerre ») reste.
- Ensembles (Q5 ★) : un membre dont le `Placement` est piloté ne tourne pas (champs grisés, pas
  d'anneau), comme les boutons aujourd'hui. Le suivi d'un membre en biais par translation est
  prévu par #114 ; la rotation d'un membre pourra être rouverte ensuite.

### 4.5 Design patterns

- State : `Rotating` dans `DragSession`.
- Memento : `DragMemento` repris tel quel (B3).
- Fonctions pures dans `core/rotation/` (A1 à A4), comme `core/magnet/`.

### 4.6 Sécurité

Angles finis (A3) et compris entre −360° et 360° avant écriture (`rotate_to`) ; rayon d'anneau
borné (pièce démesurée : rayon plafonné à 10 m) ; aucune lecture de fichier, aucune évaluation de texte.

### 4.7 Compatibilité avec les autres ateliers (ADR 0007)

Rien de nouveau dans le document : seule la propriété `Placement` existante est écrite. Les
anneaux ne sont dessinés que sur les pièces de l'atelier, atelier actif, et retirés en le
quittant, avec les flèches. Std Transform et l'éditeur de `Placement` restent utilisables.

## 5. Découpage en PR et impact

| Lot | Contenu | Dépend de |
|-----|---------|-----------|
| RO-a | `core/rotation/` (A1 à A5) + tests unitaires | — |
| RO-b | `features/part_rotate.py`, `rotate_part` réécrit sur `turned_about` (B1 à B5) | RO-a |
| RO-c | champs du panneau (C1 à C6) + vérifications hors écran | RO-b |
| RO-d | anneaux, état `Rotating` (D1 à D7) | RO-b |

Fichiers touchés hors création : `gui/drag/session.py`, `gui/drag/geometry.py`,
`gui/drag/overlay.py` (secteur transparent), `gui/task_panels/wood_part.py` et `.ui`,
`features/placement.py`, `tools/captures_interface.py` (une pièce tournée de 15° dans la
scène), `CHANGELOG.md`. Recette manuelle : `docs/recette/rotation-scenarios-manuels.md`
(trois styles de navigation, pièce de bois, pièce en bois, membre d'ensemble, Ctrl+Z, Échap).

## 6. Compatibilité des documents

Aucune propriété ni migration : un document enregistré avec une pièce tournée s'ouvre sans
l'atelier (seul `Placement` change).

## 7. Risques

- Blocage de cardan : à tangage ±90°, X et Z décrivent le même tour ; A1 fixe la règle (X = 0) pour
  que les champs ne sautent pas.
- Anneaux et flèches se gênent sur une petite pièce : rayon d'au moins 20 mm, flèches dessinées
  par-dessus, priorité au survol à la flèche.
- **Numéro d'ADR** : `main` a déjà une ADR 0024 (assemblages en biais) ; celle de #111 (assemblage
  défait par un déplacement) est l'ADR 0026, et cette spécification prend 0025.

## 8. Hors périmètre

- Aimantation de l'angle sur les faces des pièces voisines (aligner sur une pièce en biais).
- Rotation autour d'un autre point que le centre (un coin, une arête).
- Rotation autour des axes propres de la pièce (L, l, e) : voir Q2.
- Rotation d'un membre d'ensemble (après #114).

## 9. Questions pour jv

Q2 à Q6 : choix ★ validés par jv le 2026-10-29 (« c'est ok »).

- Q1 Angles autorisés : **angle libre** (jv, 2026-10-28).
- Q2 Axes des champs et des anneaux : ★ **ceux du document**, comme les boutons actuels ; sinon
  ceux de la pièce (L, l, e), qui tournent avec elle.
- Q3 Souris : ★ **aimant tous les 15°, Maj pour tourner librement** ; sinon 5° ou 45°.
- Q4 Ordre : ★ **dev après la fusion de #111** (mêmes fichiers) et **avant #114**.
- Q5 Membre d'ensemble : ★ **pas de rotation** tant que #114 n'est pas fait (comme les boutons).
- Q6 Anneaux : ★ **visibles dès qu'une pièce est sélectionnée**, comme les flèches ; sinon
  seulement panneau ouvert, comme les poignées de taille.
