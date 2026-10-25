# Déplacer une pièce à la souris — scénarios de recette manuelle

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

## Préparation A : étagère entre deux joues

Nouveau document, atelier **Menuiserie**. Trois pièces de chêne par **Pièce de bois** :

| Libellé | L × l × e | Position (x, y, z) | Rotation |
|---|---|---|---|
| Joue gauche | 700 × 300 × 22 | (22, 0, 0) | −90° autour de Y |
| Joue droite | 700 × 300 × 22 | (1062, 0, 0) | −90° autour de Y |
| Étagère | 500 × 300 × 18 | (300, 0, 300) | aucune |

Cadrer la vue (**V, F**) pour voir les trois pièces.

## Scénarios

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
3. Verrouiller deux pièces d'une même rangée, puis déplacer une troisième de façon à bloquer la
   rangée : au relâchement la pièce revient et la boîte **Déverrouiller et appliquer** propose les
   pièces verrouillées ; choisir **Déverrouiller et appliquer** refait le déplacement, fermer la
   boîte l'annule.
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
