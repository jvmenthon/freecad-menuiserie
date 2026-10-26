# Pièce en bois : scénarios de recette manuelle

Recette de l'issue #73 ([spécification](../specs/piece-en-bois.md),
[ADR 0020](../adr/0020-piece-en-bois-enveloppe-d-un-corps.md)), à dérouler à la main par jv sur
**FreeCAD 1.1.4 (Windows)**, atelier installé depuis la branche du lot. Les règles de calcul sont
vérifiées par les tests unitaires et d'intégration, l'interface hors écran par
`tests/gui/verifier_atelier.py` (`verifications_piece_en_bois.py`) ; cette recette sert à **voir** ce
que voit jv. Les scénarios E6 (assemblages) seront complétés avec le lot PD-e.

## Préparation

Nouveau document, atelier **Menuiserie**. Dans **PartDesign** : un corps « Pied » avec une
esquisse 45 × 95 mm et une protrusion de 720 mm. Dans **Sketcher**, hors corps : une esquisse
fermée en forme de console galbée.

### Scénario D3 : repère de la pièce dans la vue

1. Sélectionner le corps dans l'arbre, lancer **Convertir en pièce en bois** (barre ou menu).
2. Le panneau s'ouvre. Dans la vue 3D, un trièdre apparaît au coin de la pièce : longueur L en
   rouge, largeur l en vert, épaisseur e en bleu, et une flèche orange du fil sur le dessus.
3. Cliquer **Autour de L** : le trièdre change, la pièce ne bouge pas, les cotes de
   l'**Encombrement** sont relues. Cliquer **Repère automatique** : L revient sur la plus grande
   étendue.
4. **OK** ou **Annuler** : le trièdre disparaît de la vue.

### Scénario D4 : texture et couleur du matériau

1. Choisir **Chêne** dans le panneau : la forme prend la texture du chêne, fil selon la longueur.
2. Sens du fil **Largeur** : la texture tourne aussitôt. Sur les faces planes parallèles au fil la
   texture est juste ; elle est étirée sur le bois de bout et les surfaces gauches (limite
   acceptée, ADR 0004).
3. Fermer puis rouvrir le document : texture et couleur sont revenues.

### Scénario D5 : source sous la pièce, modification du dessin

1. Dans l'arbre, le corps « Pied » apparaît **sous** la pièce en bois, masqué.
2. Double-clic sur le corps : l'édition PartDesign s'ouvre. Allonger la protrusion : la pièce et
   sa cote L suivent.
3. Double-clic sur la pièce : le panneau s'ouvre. **Modifier le dessin** ferme le panneau (validé)
   et ouvre l'édition de la dernière fonction du corps ; pour une pièce tirée d'une esquisse,
   l'esquisse. Le champ **Épaisseur du profil** n'apparaît que pour une esquisse.
4. Supprimer la pièce en bois : le corps est réaffiché, sans avertissement « objets référencés ».
   **Annuler** (Ctrl+Z) la ramène.

### Scénario D6 : accrochage

1. Poser une pièce de bois (planche). Sélectionner le corps (objet entier), puis, avec Ctrl, une
   **face** de la planche. Lancer **Convertir en pièce en bois**.
2. Le panneau s'ouvre ; le groupe Rotation cite « Contre : … » et la pièce est posée contre la
   face. Les boutons X, Y, Z la tournent en la gardant accrochée.
3. Sélectionner une face de la pièce en bois, lancer **Pièce de bois** : la nouvelle planche
   s'accroche à la face, comme sur une pièce de bois.
4. Convertir deux corps à la fois : une pièce par corps, une seule entrée d'annulation, pas de
   panneau. Convertir une esquisse ouverte avec un corps : la boîte de refus liste l'esquisse,
   le corps est converti.

### Scénario E6 : assemblages (à compléter avec PD-e)

À compléter.
