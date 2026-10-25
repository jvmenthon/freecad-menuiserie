# Souris et distances : scénarios de recette manuelle

Recette de l'issue #65 ([spécification](../specs/souris-et-distances.md),
[ADR 0022](../adr/0022-distance-entre-deux-pieces.md)), à dérouler à la main sur **FreeCAD 1.0** et
**FreeCAD 1.1**, atelier installé depuis la branche du lot. Les résultats et les captures sont
reportés dans la PR. Les règles de calcul et le déplacement sont vérifiés par les tests unitaires
et d'intégration ; l'interface hors écran par `tests/gui/verifier_atelier.py`
(`verifications_distance.py`) ; cette recette sert à **voir** ce que voit jv : la pièce déplacée
suit chaque saisie dans la vue 3D.

Les scénarios de glisser à la souris (SM-c) sont dans la dernière section.

## Définir une distance (DI-b, critère E6)

### Préparation

Nouveau document, atelier **Menuiserie**, trois pièces de chêne par **Pièce de bois**, cotes et
`Placement` réglés dans l'éditeur de propriétés :

| Libellé | L × l × e | Position (x, y, z) |
|---|---|---|
| Plateau | 800 × 200 × 22 | (0, 0, 700) |
| Étagère | 600 × 200 × 22 | (0, 0, 100) |
| Tourillon | 100 × 20 × 20 | (500, 50, 30) |

### Scénario D1 : étagère à 320 mm sous le plateau (face-face)

1. Dans la vue 3D, cliquer le **dessous du plateau**, puis (Ctrl) le **dessus de l'étagère**.
2. Clic droit, **Définir une distance** (le même ordre est aussi dans le menu et la barre
   d'outils *Menuiserie*, et dans le menu contextuel de l'arborescence).
3. Le panneau affiche « Entre : … et … », « Distance actuelle : 578 mm », « Pièce déplacée :
   Étagère » et le champ **Distance** à 578 mm.
4. Saisir `320 mm` (ou `300 mm + 20 mm`) : l'étagère monte tout de suite, le plateau ne bouge pas.
5. **Inverser** : le plateau devient la pièce déplacée, l'étagère revient en place.
   **Inverser** de nouveau, puis **OK**.
6. Attendu : le dessus de l'étagère est à 320 mm sous le dessous du plateau (z = 380) ;
   **Édition > Annuler** annule tout d'un coup (« Définir une distance »).

### Scénario D2 : tourillon à 30 mm du bout (sommet-face)

1. Sélectionner le **bout** de la planche (face x = 800 du plateau), puis un **sommet** du bout du
   tourillon (x = 500).
2. **Définir une distance**, saisir `30`.
3. Attendu : le tourillon recule jusqu'à 30 mm du bout, sans changer de hauteur ni de côté.

### Scénario D3 : traverse alignée à 0 mm (arête-arête)

1. Sélectionner deux **arêtes parallèles** de deux pièces (par exemple le haut de l'arête avant du
   plateau, puis l'arête de l'étagère).
2. **Définir une distance**, saisir `0`.
3. Attendu : les deux arêtes sont confondues.

### Scénario D4 : deux sommets, direction

1. Sélectionner un sommet de chaque pièce. La liste **Direction** apparaît (Directe, X, Y, Z) ;
   elle est absente pour les autres paires.
2. Choisir **X** : la distance affichée est celle sur X seul ; la saisir ne déplace la pièce que
   sur X.

### Scénario D5 : refus expliqués et annulation

1. Sélectionner deux faces **non parallèles** : message « Les éléments ne sont pas parallèles… »,
   aucun panneau, aucune entrée d'annulation.
2. Sélectionner des éléments de deux objets d'un **autre atelier** (Part, par exemple deux
   cubes) : « Choisissez au moins une pièce de l'atelier : les autres objets ne sont pas
   déplacés. » Avec une pièce de l'atelier et un cube, seule la pièce bouge, quel que soit
   l'ordre.
3. Sélectionner une arête **courbe** : refus (une arête courbe n'a pas de distance).
4. Donner à l'étagère une formule sur `Placement.Base.z` (`=100 mm`) : saisir une distance en
   hauteur affiche en rouge « l'axe Z est piloté par une formule », **OK** ne ferme pas le
   panneau.
5. **Annuler** dans le panneau, après avoir saisi une valeur : la pièce revient, l'historique
   d'annulation est inchangé.

### Scénario D6 : pièce d'un ensemble

1. Mettre Plateau et Étagère dans un **Ensemble**, puis définir une distance avec un cube de
   référence : la pièce déplacée garde sa nouvelle position après un recalcul
   (**Relier les pièces** n'est pas nécessaire : l'ensemble est relié par la commande).
2. **Édition > Annuler** rétablit la position et les liaisons d'origine.

### Scénario D7 : garder la distance dans l'ensemble (DI-c)

1. Bureau regroupé en **Ensemble** (plateau, deux joues, voile). Sélectionner le **dessous de la
   joue gauche** puis le **dessous du voile**, **Définir une distance** : la case **Garder cette
   distance** est cochée et active. Saisir `320 mm`, **OK**.
2. Attendu : un objet **Distance : Joue gauche – Voile** dans le groupe de l'ensemble ; une
   seule entrée d'annulation. Passer la hauteur de l'ensemble à 800 mm : le voile garde ses
   320 mm sous la joue, le plateau suit.
3. Avec deux pièces hors ensemble : la case est grisée, l'infobulle donne la raison.
4. **Double-clic** sur la Distance dans l'arbre : panneau « Entre … et … », champ à 320 mm,
   case cochée. Saisir `340 mm` : le voile suit ; **OK** valide, **Annuler** rétablit.
5. Rouvrir le panneau, décocher la case, **OK** : la Distance disparaît, le voile reste en place.
6. Supprimer une des deux pièces : la Distance disparaît avec elle ; **Annuler** les rend.
7. Copier-coller le meuble : la copie a sa propre Distance, liée aux pièces copiées.
8. Verrouiller le voile (case « fixe »), puis changer la hauteur : refus nommant la Distance,
   avec **Ne plus garder et appliquer**. Idem en créant la Distance avec le voile verrouillé :
   message et bouton **Ne plus garder et appliquer**.
9. Glisser le voile vers le bas à la souris, le long de l'axe de la Distance : au relâchement,
   sa valeur est mise à jour ; **Échap** pendant le glissement la rétablit.

## Déplacer une pièce à la souris (SM-c, critère C8)

Critère C8 de la [spécification](../specs/souris-et-distances.md) et
[ADR 0021](../adr/0021-deplacement-a-la-souris-avec-aimantation.md) (choix de jv du 2026-10-25 :
déplacer à tout moment, par trois flèches). À dérouler à la main sur **FreeCAD 1.0** et
**FreeCAD 1.1** (Windows), avec les trois styles de navigation **Gesture**, **OpenInventor** et
**Blender** (Édition > Préférences > Affichage > Navigation), atelier installé depuis la branche
du lot. Les résultats et les captures sont reportés dans la PR.

Les règles de calcul (A1 à A8), la lecture des guides et l'écriture (B1 à B7) sont vérifiées par
les tests unitaires et d'intégration ; l'interface (C1 à C7) l'est hors écran par
`tests/gui/verifier_atelier.py` (`verifications_souris.py`), **sans vrais évènements de souris**.
Cette recette sert à **sentir** le geste, ce qu'aucun test hors écran ne voit.

### Préparation A : étagère entre deux joues

Nouveau document, atelier **Menuiserie**. Trois pièces de chêne par **Pièce de bois** :

| Libellé | L × l × e | Position (x, y, z) | Rotation |
|---|---|---|---|
| Joue gauche | 700 × 300 × 22 | (22, 0, 0) | −90° autour de Y |
| Joue droite | 700 × 300 × 22 | (1062, 0, 0) | −90° autour de Y |
| Étagère | 500 × 300 × 18 | (300, 0, 300) | aucune |

Cadrer la vue (**V, F**) pour voir les trois pièces.

### Scénarios SM-c

### S1. Flèches (C1, C3)

1. Cliquer l'étagère : trois flèches (rouge, verte, bleue) partent de son centre, de 80 pixels
   quel que soit le zoom ; zoomer à la molette, elles gardent leur taille.
2. Cliquer une joue (tournée) : ses flèches sont tournées avec elle.
3. Sélectionner deux pièces (Ctrl+clic) : aucune flèche. Clic dans le vide : aucune flèche.
4. Avec l'étagère sélectionnée, cliquer ailleurs que sur une flèche, tourner la vue, faire un
   cadre de sélection, zoomer, utiliser le bouton droit : tout se comporte comme d'habitude, dans
   les trois styles de navigation (en **Gesture**, le clic gauche glissé hors flèche tourne la
   vue).
5. Changer d'atelier (Part Design…) : les flèches disparaissent ; revenir à **Menuiserie** : elles
   reviennent avec la sélection.

### S2. Déplacer, aimanter, annuler (C2, C5, C6, C7)

1. Étagère sélectionnée, tirer la flèche **X** vers la joue gauche : la pièce suit la souris le
   long de son axe seulement.
2. Approcher le bout de l'étagère de la joue gauche : à moins de 10 pixels il se **colle** (guide
   rose sur la face de la joue) ; sur la face intérieure de la joue (contact) comme sur sa face
   extérieure (affleurement).
3. Même geste en maintenant **Maj** : aucun aimant, aucun guide dessiné ; relâcher **Maj** pendant
   le geste : l'aimant revient.
4. En plein glissement, **Échap** : l'étagère revient où elle était au début du geste ; relâcher
   le bouton ne fait rien d'autre.
5. Glisser puis relâcher : **Ctrl+Z** annule tout le glissement en une étape (« Déplacer la
   pièce » dans le menu Édition) ; **Ctrl+Y** le rétablit.
6. Tirer la flèche **Z** : l'étagère monte et descend ; la flèche **Y** : elle avance et recule.
   Faire pivoter la vue pour qu'une flèche soit vue de bout : elle n'est plus saisissable (aucun
   saut de la pièce).

### S3. Panneau ouvert : poignées L/l (C1, C2, C4, C7)

1. Double-cliquer l'étagère (ou la créer par **Pièce de bois**) : le panneau s'ouvre, quatre
   poignées orange apparaissent au milieu des bouts et des rives, avec les trois flèches.
2. Tirer la poignée du bout droit vers la joue droite : la longueur augmente, le bout gauche ne
   bouge pas, le champ **Longueur** du panneau suit ; la poignée s'aimante contre la joue. Tirer la
   poignée de la rive arrière : la largeur suit.
3. Tirer une flèche : la pièce bouge, l'aperçu transparent (en création) reste posé.
4. **Annuler** : la pièce retrouve exactement son état d'avant le panneau. Recommencer, **OK**,
   puis **Ctrl+Z** : une seule étape.
5. Fermer le panneau : les poignées disparaissent, les flèches restent si la pièce est
   sélectionnée.

### S4. Dans le bureau de la PR #86 (rangées et épaisseurs vivantes)

Préparation A de `docs/recette/ensembles-epaisseurs-scenarios-manuels.md` (bureau de référence).

1. Tirer le **Voile** de 100 mm vers l'avant par sa flèche : la largeur du bureau ne change pas ;
   au relâchement l'ensemble est relié (les constantes de position du voile sont refaites).
2. Cocher **Cotes fixes** sur le Voile puis tirer sa poignée de longueur (panneau ouvert) : pas de
   poignée sur une pièce verrouillée.
3. Verrouiller deux pièces d'une même rangée, puis déplacer une troisième : le déplacement n'est
   jamais refusé (il ne change ni la cote de l'ensemble ni une épaisseur).
4. Sur une pièce dont la position est pilotée par **votre** formule (expression dans l'éditeur de
   propriétés) : la flèche de l'axe piloté n'est pas dessinée.
5. Déplacer une pièce assemblée (Tourillons) jusqu'à ne plus toucher sa voisine : le déplacement
   est gardé et la vue rapport avertit que l'assemblage ne touche plus.

### S5. Autres objets, caméra en perspective

1. Ajouter un cube **Part > Boîte** (ou un corps PartDesign) à côté de l'étagère : l'étagère
   s'aimante aussi sur ses faces ; il n'est ni déplacé ni modifié.
2. Passer en caméra **perspective** (View > Camera type) : les flèches se saisissent et le
   déplacement suit la souris sans décalage.
3. Ouvrir deux vues 3D du même document : les flèches ne sont saisissables que dans la vue
   active.
