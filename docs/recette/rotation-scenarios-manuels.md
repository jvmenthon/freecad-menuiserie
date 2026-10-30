# Rotation d'une pièce : scénarios de recette manuelle

Recette de l'issue #117 ([spécification](../specs/rotation-d-une-piece.md),
[ADR 0025](../adr/0025-rotation-libre-d-une-piece.md) et
[ADR 0026](../adr/0026-assemblage-defait-par-un-deplacement.md)), à dérouler à la main par jv sur
**FreeCAD 1.1.4 (Windows)**, atelier installé depuis la branche du lot, avec les trois styles de
navigation **Gesture**, **OpenInventor** et **Blender** (Édition > Préférences > Affichage >
Navigation). Les règles de calcul (A1 à A5) et l'écriture (B1 à B5) sont vérifiées par les tests
unitaires et d'intégration, l'interface (C1 à C6, D1 à D7) hors écran par
`tests/gui/verifier_atelier.py` (`verifications_panneau_rotation.py`,
`verifications_souris_rotation.py`), **sans vrais évènements de souris** ; cette recette sert à
**sentir** le geste et à **voir** ce que voit jv. Les résultats et les captures sont reportés
dans la PR.

## Préparation

Nouveau document, atelier **Menuiserie**. Par **Pièce de bois** : une planche de chêne
800 × 200 × 22 en (100, 50, 0), sans rotation. Cadrer la vue (**V, F**).

Pour R5 à R7, voir leur propre préparation. Pour R9 : une petite pièce de chêne 100 × 60 × 20.

### Scénario R1 : champs d'angle en direct (C1, C2, C3, C6)

1. Double-clic sur la planche : le panneau s'ouvre. Le groupe **Rotation** montre les trois
   boutons de quart de tour X, Y, Z puis, dessous, trois champs **Autour de X**, **Autour de Y**,
   **Autour de Z**, en degrés, tous à 0.
2. Taper 30 dans **Autour de Z** (sans valider) : la planche tourne **aussitôt** dans la vue 3D,
   autour de son centre (le centre ne bouge pas). Taper 45, puis 12,5 : la vue suit chaque saisie,
   sans à-coup.
3. Les bornes : **Autour de X** et **Autour de Z** acceptent de −180 à 180 ; **Autour de Y**
   de −90 à 90 (un 120 est ramené à 90). Une décimale seulement ; la molette et les flèches du
   champ avancent de 1°.
4. Valider (Tab ou Entrée) : l'angle reste ; aucun message dans la vue rapport.
5. Cliquer le bouton de quart de tour **X** : la pièce fait un quart de tour autour de l'axe X du
   document à partir de l'angle saisi, et les trois champs relisent les nouveaux angles.
6. **Ctrl+Z** dans le panneau (ou **Annuler** du panneau) : tout revient à l'état d'avant
   l'ouverture. Rouvrir, **OK** après une saisie : l'angle est gardé et **Ctrl+Z** l'annule en une
   étape.
7. Tangage à 90° (**Autour de Y** = 90) : **Autour de X** passe à 0 et **Autour de Z** porte le
   reste, sans saut ni valeur absurde.

### Scénario R2 : anneaux, survol, aimant, Maj, angle affiché (D1 à D5)

1. Cliquer la planche (panneau fermé) : trois flèches **et** trois anneaux apparaissent autour
   d'elle, X rouge, Y vert, Z bleu. Sélectionner deux pièces ou rien : plus d'anneau.
2. Approcher la souris d'un anneau : il **s'épaissit**. Sur une flèche qui croise un anneau, la
   flèche l'emporte. Vu de dessus, les anneaux X et Y sont de chant : ils ne s'épaississent pas
   et un clic dessus est rendu à FreeCAD (sélection ou navigation habituelle).
3. Tirer l'anneau **Z** : la planche tourne autour de la verticale ; l'angle s'affiche près de la
   souris (« 15° », « -30° », virgule décimale) et un secteur transparent montre le chemin
   parcouru. L'angle **obtenu** de la planche autour de l'axe saute de 15° en 15° (aimant) : une planche
   déjà à 7° (champ « Autour de Z ») revient d'équerre (0°) en la tirant par l'anneau, sans passer
   par 7° + 15°.
4. Même geste en maintenant **Maj** : l'angle varie librement, au dixième (« 37,5° ») ; relâcher
   Maj pendant le geste : l'aimant revient aussitôt.
5. Faire plus d'un tour : l'angle continue de s'additionner (« 400° »), il ne revient pas à 40°.
6. Relâcher : la pièce reste tournée ; **Ctrl+Z** la ramène en une étape (« Tourner la pièce »
   dans le menu Édition).
7. Anneau **X**, puis anneau **Y** (orienter la vue de biais pour les voir) : la pièce tourne
   autour des axes **fixes du document**, pas autour de ses propres axes.
8. Panneau ouvert : tirer un anneau écrit dans la transaction du panneau, et les trois champs
   d'angle sont relus à chaque mouvement.

### Scénario R3 : Échap et Ctrl+Z (B3, D4)

1. Tirer un anneau, puis **Échap** en plein geste : la pièce revient à son orientation de départ ;
   relâcher le bouton ne fait rien d'autre. Un seul **Ctrl+Z** n'a alors rien à défaire pour ce
   geste.
2. Tirer un anneau jusqu'à 45°, relâcher, tirer un autre anneau, relâcher : deux **Ctrl+Z**
   défont les deux gestes, un par un, dans l'ordre inverse. **Ctrl+Y** les rétablit.
3. Dans le panneau, saisir un angle puis tirer un anneau : **Annuler** du panneau remet l'angle
   d'avant l'ouverture.

### Scénario R4 : pièce de bois (B1, B5)

1. Sur la planche posée, tourner de 20° par le champ, de 15° par l'anneau : la pièce reste sur
   place, son **Placement** (éditeur de propriétés) montre l'axe et l'angle correspondants.
2. Dans l'arbre, la planche est dans un **App::Part** lui-même tourné de 90° : les champs
   donnent les angles du **Placement local** (ceux de l'éditeur de propriétés), les anneaux
   suivent les axes du conteneur.
3. Dans la liste de débit, la planche garde ses cotes 800 × 200 × 22.

### Scénario R5 : pièce en bois, ShapedPart (B2)

Préparation : un corps **PartDesign** « Pied » (esquisse 45 × 95, protrusion de 720), converti par
**Convertir en pièce en bois**.

1. Double-clic sur la pièce en bois : le groupe Rotation montre les champs d'angle. Saisir
   30° autour de Z : la pièce tourne autour de son centre.
2. Dans l'arbre, le corps « Pied » sous la pièce n'a pas bougé (son **Placement** est inchangé) ;
   seule la pièce en bois porte la rotation.
3. Tirer un anneau, puis **Échap** : retour à l'angle d'avant le geste. Relâcher, **Ctrl+Z** :
   retour à l'angle d'avant.
4. Modifier le dessin (allonger la protrusion) : la pièce reste tournée et ses cotes suivent.

### Scénario R6 : membre d'ensemble (C4, D6)

Préparation : un ensemble de deux ou trois pièces (**Ensemble**), les membres reliés à
l'ensemble.

1. Sélectionner un membre : **pas d'anneau**, seulement les flèches des axes libres.
2. Double-clic sur le membre : les boutons de quart de tour **et** les trois champs d'angle sont
   **grisés** ; l'infobulle d'un champ dit « Position pilotée par l'ensemble ».
3. Poser une formule sur le **Placement** d'une pièce hors ensemble (éditeur de propriétés,
   « Placement.Base.x = 50 mm ») : mêmes constats, infobulle « Position pilotée par une formule ».

### Scénario R7 : pièce assemblée, fenêtre d'ADR 0026 (B4, C2)

Préparation : deux pièces assemblées par un **Tenon-mortaise**, la traverse bout contre le montant.

1. Sélectionner la traverse et tirer un anneau de 40° : pendant le geste, rien ne s'affiche
   (aucune trace dans la vue rapport).
2. Au relâchement, la fenêtre **Menuiserie : assemblage défait** cite l'assemblage et propose
   **Annuler le déplacement** (choix par défaut) et **Supprimer l'assemblage**. **Échap** ou la
   fermeture de la fenêtre valent « Annuler ».
3. **Annuler le déplacement** : la traverse revient à son orientation de départ, l'assemblage est
   gardé. Recommencer et **Supprimer l'assemblage** : la rotation est gardée, l'assemblage et les
   pièces usinées sans autre assemblage disparaissent ; **Ctrl+Z** rend tout, rotation comprise.
4. Dans le panneau de la traverse : saisir 40° dans **Autour de Z** ; la fenêtre ne s'ouvre qu'à
   la **fin de saisie** (Tab ou Entrée), pas à chaque chiffre. « Annuler » remet l'angle d'avant
   la saisie dans le champ.
5. Saisir un angle sans valider, puis tirer une **flèche** : la fenêtre s'ouvre à ce moment-là
   (la saisie n'est pas abandonnée en silence).
6. Un quart de tour par un bouton, qui défait lui aussi l'assemblage : même fenêtre.
7. Tourner une pièce de 20°, puis essayer **Tenon-mortaise** avec une autre pièce : le refus
   « Les deux pièces doivent être d'équerre » est un message simple, sans trace (assemblages en
   biais prévus par #114).

### Scénario R8 : les trois styles de navigation (D2)

Pour **chaque** style (**Gesture**, **OpenInventor**, **Blender**), planche sélectionnée :

1. Tirer un anneau avec le clic gauche : la pièce tourne, la vue ne bouge pas.
2. Clic gauche hors anneau et hors flèche, tourner la vue, panoramique, molette, cadre de
   sélection : tout se comporte comme d'habitude (en **Gesture**, le clic gauche glissé hors
   anneau tourne la vue).
3. Clic droit sur un anneau : le menu contextuel habituel s'ouvre ; aucune rotation ne démarre.
4. Zoomer et dézoomer pendant la sélection : les anneaux gardent leur forme autour de la pièce.
5. Changer d'atelier (Part Design…) : flèches et anneaux disparaissent ; revenir à **Menuiserie** :
   ils reviennent avec la sélection.

### Scénario R9 : petite pièce dézoomée (revue #117)

1. Sélectionner la petite pièce 100 × 60 × 20 et zoomer à la molette jusqu'à ce qu'elle ne
   mesure plus qu'une dizaine de pixels : les anneaux restent dessinés mais **un clic sur la pièce
   ou à côté d'elle ne lance jamais de rotation** (le clic est rendu à FreeCAD : sélection,
   flèches).
2. Zoomer peu à peu : dès que le rayon d'un anneau dépasse environ 16 pixels à l'écran, il se
   survole et se tire de nouveau, uniquement **sur** sa ligne (à 8 pixels près), pas au centre.
3. Faire pivoter la vue pour voir un anneau de biais (ellipse très aplatie) : la bande saisissable
   reste large de 8 pixels de part et d'autre de la ligne dessinée ; vu par la tranche, l'anneau
   n'est plus proposé.
4. Planche de 800 mm, vue normale : les anneaux se saisissent comme au scénario R2.
