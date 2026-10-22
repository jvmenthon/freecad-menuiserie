# J6 — Scénarios de recette manuelle (aperçu, rotation, accrochage à la sélection)

Critères V1 à V7 (J6c) et T1 à T9 (J6d) de la [spécification J6](../specs/J6-interface.md)
(réponses de jv du 2026-10-22 : trois boutons X, Y, Z, longueur étirée modifiable, case
« Ajouter à l'ensemble » cochée), à dérouler à la main sur **FreeCAD 1.1.4** (Windows) et, si
possible, **FreeCAD 1.0**, atelier installé depuis la branche du lot.

V1 à V7 sont aussi vérifiés hors écran par `tests/gui/verifier_atelier.py`
(`verifications_apercu.py`) et, côté document, par `tests/integration/test_apercu_rotation.py` ;
T1 à T8 par `verifications_selection.py` et `tests/integration/test_accrochage_selection.py`.

## Aperçu et rotation (J6c)

Nouveau document, atelier **Menuiserie**, rien de sélectionné.

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Bouton **Pièce de bois**. | La pièce (800 × 200 × 22) apparaît **semi-transparente** (60 %), texture et couleur du chêne visibles ; panneau « Nouvelle pièce de bois ». |
| 2 | Lire l'ordre des groupes du panneau, de haut en bas. | **Identification** (le repère / nom de la pièce, premier champ du panneau), puis **Dimensions finies** (et « Surcotes de débit »), puis **Matériau**, puis **Rotation** avec trois boutons **X**, **Y**, **Z** (icônes en couleur, infobulles « Quart de tour autour de l'axe X du document… »). |
| 3 | Changer la longueur, le matériau, le sens du fil. | L'aperçu suit chaque saisie, toujours semi-transparent. |
| 4 | Cliquer **X**. | La pièce fait un quart de tour autour de l'axe X du document (elle se met sur chant) et reste posée sur le plan XY, coin à l'origine. Le sens du fil et la texture tournent avec la pièce ; `GrainDirection` est inchangé dans l'éditeur de propriétés. |
| 5 | Cliquer quatre fois sur **Y**, puis quatre fois sur **Z**. | Chaque série de quatre clics ramène la pièce à sa position de départ. Les 24 orientations sont atteignables en combinant les trois boutons. |
| 6 | Saisir le repère « E2 », **OK**. | Pièce opaque (transparence d'origine rétablie), nommée « E2 » dans l'arborescence. |
| 7 | *Édition › Annuler*. | La pièce disparaît ; une seule entrée « Créer une pièce de bois » (aucune pour la rotation ni la transparence). *Rétablir* : pièce, orientation et transparence d'origine reviennent. |
| 8 | **Pièce de bois**, cliquer **Z**, **Annuler** (bouton du panneau). | Aucune pièce dans l'arborescence ; *Édition* ne propose aucune annulation nouvelle. |
| 9 | Double-clic sur une pièce existante, cliquer **Z**. | La pièce tourne **sur place** : son centre ne bouge pas ; affichage non transparent. Si elle porte un assemblage, sa pièce usinée suit. **Annuler** : cotes, position et repère d'origine. |
| 10 | Faire de la pièce un membre d'un ensemble (**Ajouter à l'ensemble**), puis double-clic sur elle. | Boutons X, Y, Z **grisés** ; infobulle « Cette pièce suit l'ensemble « … » : tournez-la avec Std Transform après l'avoir retirée de l'ensemble. » |
| 11 | Sur une pièce libre, poser une expression sur `Placement.Base.x` (`10 mm`), double-clic. | Boutons grisés, infobulle expliquant que la position est pilotée par une expression. |
| 12 | Fermer le panneau, ouvrir *Édition › Préférences*. | Aucune rubrique ni réglage créé par l'aperçu ; la sélection de la vue 3D n'est ni filtrée ni modifiée. |

## Accrochage à la sélection (J6d)

Chaque scénario part d'un nouveau document, l'atelier **Menuiserie** étant actif. Sélectionnez
**avant** de cliquer sur **Pièce de bois**. Dans tous les cas, la ligne « Contre : … » du groupe
*Rotation* cite les éléments retenus et la sélection reste visible dans la vue 3D.

| N° | Action | Résultat attendu |
|---|---|---|
| 13 | Créer le caisson de référence de J4d (gabarit **Caisson**) puis le regrouper en ensemble « Caisson ». Sélectionner la face **intérieure du côté gauche**, puis celle du **côté droit** (Ctrl). Lancer **Pièce de bois**. | Une tablette semi-transparente apparaît **entre les deux côtés**, horizontale, à la longueur exacte de l'écart ; la longueur est écrite dans le champ ; « Contre : Face… de « Côté gauche », Face… de « Côté droit » ». La case **Ajouter à l'ensemble « Caisson »** est visible et cochée. |
| 14 | Saisir une longueur plus courte dans le champ. | L'aperçu suit aussitôt ; la saisie reste (elle n'est pas rétablie à l'écart) ; la tablette touche toujours le côté gauche. |
| 15 | Cliquer **Z** puis **X**, **Y** (quatre clics chacun pour revenir). | La pièce tourne autour des axes du document et reste contre le côté gauche, sans entrer dans la matière. |
| 16 | Saisir le repère « E2 », **OK**. | Pièce opaque nommée « E2 », entrée dans l'ensemble ; *Édition › Annuler* retire d'un coup la pièce et son entrée dans l'ensemble (une seule entrée « Créer une pièce de bois »). Redimensionner l'ensemble de +100 mm en largeur : la tablette s'allonge de 100 mm. |
| 17 | Refaire 13, décocher **Ajouter à l'ensemble**, **OK**. | La pièce n'est pas membre de l'ensemble. |
| 18 | Sélectionner **une face** d'une pièce de bois (cliquer près d'un coin), lancer la commande. | La pièce est à plat sur la face, son coin sur le coin cliqué, vers l'intérieur. Changer sa longueur, le matériau ou cliquer X, Y, Z : elle reste en contact. |
| 19 | Sélectionner **une arête**, puis **un sommet**. | Arête : une arête de la pièce est confondue avec elle, la pièce repose sur la face voisine la plus tournée vers vous. Sommet : un coin de la pièce sur le sommet, sans chevaucher l'objet. |
| 20 | Placer un **Std Part**, le tourner de 90° et le déplacer, y mettre un cube (**Part › Cube**) ; sélectionner une face du cube dans le Std Part, lancer la commande. | La pièce touche la face et est rangée **dans le Std Part** (arborescence). |
| 21 | Sélectionner une face d'un **objet d'un autre atelier** (cube Part, corps PartDesign, face cylindrique, arête d'esquisse). | La pièce touche l'élément ; pour une esquisse ou un plan sans matière, elle est du côté tourné vers vous. |
| 22 | Sélectionner une face à travers un **lien** (*App::Link*) d'un Std Part. | La pièce est créée à côté de la copie, jamais dans l'original. |
| 23 | Sélectionner une face **inclinée** (cube tourné de 30°), puis cliquer X, Y, Z. | La pièce est inclinée comme la face ; les boutons tournent autour des axes de la face (limite connue, voir le README) et la pièce reste en contact. |
| 24 | Sélectionner un objet entier (sans sous-élément), lancer la commande. | Message « l'objet entier est ignoré » dans le panneau ; la pièce est créée à l'origine, comme sans sélection. |
| 25 | Avec une sélection valide, **Annuler** (bouton du panneau), puis *Édition › Annuler*. | Aucune pièce, aucune entrée d'annulation créée ; la sélection de départ est toujours là. |
| 26 | Avec une sélection valide, changer le **sens du fil** dans le panneau. | La texture tourne aussitôt dans la vue 3D. |
| 27 | Vérifier les préférences de FreeCAD après avoir fermé le panneau. | Aucune rubrique ni réglage créé ; aucun observateur ni filtre de sélection laissé en place. |
