# J4c — Scénarios de recette manuelle

Critère P7 de la [spécification J4](../specs/J4-ensembles.md) (et parties visuelles de P1 à
P5), à dérouler à la main sur **FreeCAD 1.0** et **FreeCAD 1.1**, atelier installé depuis la
branche du lot. Les résultats et les captures sont reportés dans la PR.

P1 à P6 et une partie de P7 sont aussi vérifiés automatiquement, hors écran, par
`tests/gui/verifier_atelier.py` (`verifications_ensemble.py`,
`verifications_panneau_ensemble.py`).

## Préparation : bureau de référence (à la main)

Nouveau document, atelier **Menuiserie**. Créer quatre pièces de chêne par **Pièce de bois**,
puis régler leurs cotes et leur `Placement` dans l'éditeur de propriétés :

| Libellé | L × l × e | Position (x, y, z) | Rotation |
|---|---|---|---|
| Plateau | 1200 × 600 × 30 | (0, 0, 720) | aucune |
| Joue gauche | 720 × 560 × 22 | (22, 0, 0) | −90° autour de Y |
| Joue droite | 720 × 560 × 22 | (1200, 0, 0) | −90° autour de Y |
| Voile | 1156 × 400 × 18 | (22, 459, 320) | +90° autour de X |

Relier **Joue gauche** et **Voile**, puis **Joue droite** et **Voile**, par **Tourillons**.

## P7 — Scénario du livrable

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Sélectionner les quatre pièces, bouton **Ensemble** ; renommer l'ensemble « Bureau ». | Un ensemble 1200 × 600 × 750 apparaît, pièces et tourillons rangés dessous ; *Édition › Annuler* propose « Créer un ensemble ». |
| 2 | Double-clic sur **Bureau**. | Panneau « Modifier « Bureau » » : trois cotes, quatre pièces « Reste en place » (Joue gauche « étirée », les autres « étirée, déplacée ») ; Joue gauche choisie : distances 0, 1178, 0, 40, 0, 30 mm, « fixe » coché sauf à droite. |
| 3 | Profondeur `800`. | Plateau de 800, joues de 760 (elles suivent le fond, Q7), voile à 141 mm du fond, tourillons suivis, aussitôt. |
| 4 | Joue gauche : décocher **fixe** à l'arrière, puis le recocher. | Décoché : sa largeur ne suit plus (expression `Width` retirée) ; recoché : l'expression revient. Même chose pour la joue droite. |
| 5 | Voile : décocher **fixe** à l'arrière, Position **Proportion**. | Colonne « Suit » : « étirée, déplacée, proportion ». |
| 6 | Profondeur `30`. | Message rouge « « Joue gauche » deviendrait trop petite… » sous les cotes, **OK** grisé, rien ne bouge. Profondeur `800` : le message disparaît. |
| 7 | **OK**, puis *Annuler* et *Rétablir*. | Une seule entrée « Modifier l'ensemble » ; tout revient puis repart. |
| 8 | Voile, éditeur d'expressions : `Placement.Base.y` = `<<Plateau>>.Width - 141 mm` ; double-clic sur Bureau, choisir Voile. | Avertissement « Placement.Base.y suit une formule… » dans le panneau ; distances avant et arrière et leurs cases grisées, infobulle « Formule de l'utilisateur… ». |
| 9 | Enregistrer, fermer, rouvrir. | Arbre, icônes, expressions identiques, document non modifié. |
| 10 | Ranger Bureau et ses pièces dans un **Std Part**, le tourner de 30°, créer un **App::Link** vers lui ; Profondeur `700`. | Original et lien suivent ; l'atelier **Assembly** accepte le Std Part comme composant. |
| 11 | Atelier **TechDraw** : vue du Std Part. | La vue se recalcule sans erreur. |
| 12 | Supprimer **Bureau** (touche Suppr., confirmer). | Les pièces gardent leur forme, sans expression ni propriété du groupe « Ensemble » ; *Annuler* rétablit tout. |
