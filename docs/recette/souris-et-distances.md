# Souris et distances : scénarios de recette manuelle

Recette de l'issue #65 ([spécification](../specs/souris-et-distances.md),
[ADR 0022](../adr/0022-distance-entre-deux-pieces.md)), à dérouler à la main sur **FreeCAD 1.0** et
**FreeCAD 1.1**, atelier installé depuis la branche du lot. Les résultats et les captures sont
reportés dans la PR. Les règles de calcul et le déplacement sont vérifiés par les tests unitaires
et d'intégration ; l'interface hors écran par `tests/gui/verifier_atelier.py`
(`verifications_distance.py`) ; cette recette sert à **voir** ce que voit jv : la pièce déplacée
suit chaque saisie dans la vue 3D.

Les scénarios de glisser à la souris (SM-c) sont ajoutés à ce fichier par leur lot.

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

### Hors périmètre de ce lot

La case « Garder cette distance » et l'objet `Distance` viennent avec DI-c : le panneau n'en
a pas encore.
