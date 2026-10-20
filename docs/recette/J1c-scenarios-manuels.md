# J1c — Scénarios de recette manuelle

Critères C7 et C9 de la [spécification J1](../specs/J1-piece-de-bois.md) (et parties manuelles
de C4 à C6), à dérouler à la main sur **FreeCAD 1.0** et **FreeCAD 1.1**, avec un profil
utilisateur sans bibliothèque personnelle (`UserLibraryPath` vide, pas de
`Menuiserie/materiaux.json` dans le dossier de données utilisateur). Les résultats sont reportés
dans la PR.

Les critères C1 à C6 et C8 sont aussi vérifiés automatiquement, hors écran, par
`tests/gui/verifier_atelier.py` (`tests/gui/verifications_panneau.py`).

## C9 — Scénario du livrable

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Nouveau document, atelier **Menuiserie**, bouton **Pièce de bois** de la barre d'outils. | Une pièce « Pièce de bois » apparaît (chêne, 800 × 200 × 22 mm) et le panneau « Nouvelle pièce de bois » s'ouvre. Le bouton est grisé tant que le panneau est ouvert. |
| 2 | **OK**. | Le panneau se ferme ; *Édition > Annuler* propose « Créer une pièce de bois ». |
| 3 | Double-clic sur la pièce dans l'arbre. | Le panneau « Modifier « Pièce de bois » » s'ouvre avec 800, 200, 22 mm, Chêne, fil en longueur. |
| 4 | Matériau **Hêtre**, puis Longueur `1000`, Largeur `250`, Épaisseur `27` (ou menu **Épaisseurs standard > 27 mm**). | Chaque modification se voit aussitôt dans la vue 3D (dimensions, couleur du hêtre). |
| 5 | **OK**. | Une seule entrée d'annulation « Modifier une pièce de bois » au-dessus de « Créer une pièce de bois ». |
| 6 | *Édition > Annuler*. | Retour à 800 × 200 × 22 en chêne (forme et couleur). |
| 7 | *Édition > Rétablir*. | De nouveau 1000 × 250 × 27 en hêtre. |
| 8 | Enregistrer, fermer, rouvrir le fichier. | Pièce identique (1000 × 250 × 27, Hêtre, couleur du hêtre, icône de la pièce de bois), aucun avertissement, document non marqué modifié. |

## C7 — Unités et cotes refusées

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Dans le panneau, Longueur `80 cm`. | La longueur vaut 800 mm. |
| 2 | Largeur `2'` (deux pieds). | La largeur vaut 609,6 mm. |
| 3 | Épaisseur `0`, puis `-5`. | Le champ signale une valeur invalide (rouge) ; la pièce garde sa dernière épaisseur valide. |
| 4 | **Annuler**. | Toutes les valeurs d'origine reviennent. |

## C4 à C6 — Vérifications visuelles

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Type **MDF**. | Seul le MDF est proposé et il est appliqué ; fil « Sans fil », surcotes à 0. **Tous** rétablit la liste complète. |
| 2 | Contreplaqué bouleau, Épaisseur `17`. | Avertissement orange « Épaisseur hors standard pour ce panneau » ; **OK** reste possible. Rien pour un bois massif. |
| 3 | Dans l'éditeur de propriétés, `Length` = `=Width*4`, puis double-clic. | Le champ Longueur montre l'icône d'expression et n'est pas modifiable directement ; après **OK**, l'expression est toujours là. |
| 4 | **Surcotes de débit**. | La zone se déplie et montre les trois surcotes. |

## Résultats

| Scénario | FreeCAD 1.0 | FreeCAD 1.1 |
|---|---|---|
| C9 | à reporter | à reporter |
| C7 | à reporter | à reporter |
| C4 à C6 (visuel) | à reporter | à reporter |
