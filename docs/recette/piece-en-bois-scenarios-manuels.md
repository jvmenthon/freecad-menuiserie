# Pièce en bois : scénarios de recette manuelle

Recette de l'issue #73 ([spécification](../specs/piece-en-bois.md),
[ADR 0020](../adr/0020-piece-en-bois-enveloppe-d-un-corps.md)), à dérouler à la main par jv sur
**FreeCAD 1.1.4 (Windows)**, atelier installé depuis la branche du lot. Les règles de calcul sont
vérifiées par les tests unitaires et d'intégration, l'interface hors écran par
`tests/gui/verifier_atelier.py` (`verifications_piece_en_bois.py`) ; cette recette sert à **voir** ce
que voit jv. Les scénarios E6 (assemblages) et L1 à L4 (cas limites de fin de jalon) complètent les scénarios D3 à D6.

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

### Scénario E6 : assemblages

1. Convertir un pied galbé (corps PartDesign) en pièce en bois, poser une traverse (pièce de bois)
   bout contre son chant plat. Sélectionner dans la **vue 3D** le pied puis la traverse : la commande
   **Tenon-mortaise** est active. Recommencer en sélectionnant les deux dans l'**arbre**.
2. Le panneau de l'assemblage s'ouvre comme pour deux pièces de bois, sans autre différence visible.
   **OK** : la mortaise est creusée dans la forme réelle du pied (pas dans une boîte).
3. Double-clic sur la pièce usinée du pied (dans l'arbre ou la vue) : le panneau de la **pièce en
   bois** s'ouvre. Allonger la protrusion du corps : pied, mortaise et ligne de débit suivent.
4. Assembler la traverse sur une face **courbe** du pied : l'assemblage est fait, un avertissement
   « matière manquante » cite l'assemblage et la pièce (vue rapport). Essayer les six autres types
   (rainure-languette, feuillure, tourillons, mi-bois, queue d'aronde, onglet) sur des faces planes.
5. **Annuler** (Ctrl+Z) : l'assemblage et les pièces usinées disparaissent, le pied reste.

### Scénario L1 : cas limites des sources

1. Convertir un corps vide, une esquisse ouverte, une esquisse à deux contours séparés, un lien
   (App::Link) : chaque refus est expliqué dans la boîte de refus, rien n'est créé.
2. Convertir une esquisse avec un trou : la pièce est percée, l'épaisseur du profil se règle.
3. Corps dans un App::Part lui-même dans un App::Part, tournés : la pièce est rangée dans le
   conteneur de la source et coïncide avec elle ; déplacer le conteneur emporte les deux.

### Scénario L2 : annuler, supprimer, rouvrir

1. Convertir, **Annuler**, **Rétablir** : la pièce revient avec sa texture et ses cotes.
2. Supprimer le **corps** source (pas la pièce) : la pièce passe en erreur sans message technique ;
   **Annuler** la rétablit. Enregistrer en erreur, rouvrir : la forme enregistrée s'affiche.
3. Ouvrir le fichier sur une machine **sans l'atelier** : la forme et le corps s'affichent et se
   modifient.

### Scénario L3 : tailles extrêmes et forme tournée

1. Pied de 20 m puis de 0,1 mm d'épaisseur : acceptés ; au-delà : refus traduit. Réduire la
   protrusion d'un pied converti à 0,05 mm : la pièce passe en erreur, la rétablir la corrige.
2. Forme importée (STEP) tournée de 30° : L suit la plus grande étendue, e la plus petite. Forme très
   détaillée (plus de 5 000 faces) : avertissement « trop détaillée », axes de la source gardés.
3. STEP à deux solides identiques : deux pièces, « 2 × » dans la liste de débit.

### Scénario L4 : accrochage sur une pièce en bois d'un ensemble

1. Mettre un pied (pièce en bois) dans un ensemble. Sélectionner une de ses faces et lancer
   **Pièce de bois** : la planche s'accroche ; elle devrait entrer dans l'ensemble comme sur une
   pièce de bois (constat ouvert du rapport de relecture).
