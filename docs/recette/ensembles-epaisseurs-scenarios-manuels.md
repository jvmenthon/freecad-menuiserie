# Ensembles — épaisseurs fixes et pièces verrouillées : scénarios de recette manuelle

Critères G1 à G4 de la [spécification](../specs/ensembles-epaisseurs-fixes.md) et
[ADR 0019](../adr/0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (règle de jv du
2026-10-23), à dérouler à la main sur **FreeCAD 1.1** (minimum depuis l’ADR 0023), atelier installé depuis
la branche du lot. Les résultats et les captures sont reportés dans la PR.

Les règles de calcul (E1 à E9) et le document (D1 à D6) sont vérifiés par les tests unitaires et
d'intégration ; G1 à G3 aussi hors écran, par `tests/gui/verifier_atelier.py`
(`verifications_panneau_verrous.py`). Cette recette sert à **voir** ce que voit jv : chaque
changement du formulaire doit apparaître tout de suite dans la vue 3D.

## Préparation A : bureau de référence

Nouveau document, atelier **Menuiserie**. Créer quatre pièces de chêne par **Pièce de bois**,
régler leurs cotes et leur `Placement` dans l'éditeur de propriétés :

| Libellé | L × l × e | Position (x, y, z) | Rotation |
|---|---|---|---|
| Plateau | 1200 × 600 × 30 | (0, 0, 720) | aucune |
| Joue gauche | 720 × 560 × 22 | (22, 0, 0) | −90° autour de Y |
| Joue droite | 720 × 560 × 22 | (1200, 0, 0) | −90° autour de Y |
| Voile | 1156 × 400 × 18 | (22, 459, 320) | +90° autour de X |

Relier **Joue gauche** et **Voile**, puis **Joue droite** et **Voile**, par **Tourillons**. Les
sélectionner toutes les quatre, bouton **Ensemble**, renommer l'ensemble « Bureau » (1200 × 600 ×
750), options par défaut.

## Préparation B : étagère à deux niveaux

Autre document (ou après avoir caché le bureau). Cinq pièces de chêne, toutes de profondeur 300 :

| Libellé | L × l × e | Position (x, y, z) | Rotation |
|---|---|---|---|
| Joue gauche | 700 × 300 × 22 | (22, 0, 0) | −90° autour de Y |
| Joue droite | 700 × 300 × 22 | (1062, 0, 0) | −90° autour de Y |
| Montant | 700 × 300 × 18 | (440, 0, 0) | −90° autour de Y |
| Étagère 1 | 400 × 300 × 18 | (22, 0, 300) | aucune |
| Étagère 2 | 600 × 300 × 18 | (440, 0, 300) | aucune |

Les regrouper en un ensemble « Étagère » (1062 × 300 × 700), options par défaut. Les deux étagères
se touchent par le montant : la rangée est Joue gauche | Étagère 1 | Montant | Étagère 2 | Joue
droite.

## G1 à G4 — Scénarios de jv

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | **Bureau** : double-clic sur l'ensemble, Largeur `1400`. | Seuls le **Plateau** (1400) et le **Voile** (1356, de x = 22 à 1378) changent de cote ; la **Joue droite** se déplace contre le bord (x de 1378 à 1400) ; la **Joue gauche** et la profondeur ne bougent pas ; les tourillons suivent ; tout se voit aussitôt. |
| 2 | Largeur `1200`, puis **OK**. | Une seule entrée « Modifier l'ensemble » dans *Édition › Annuler*. |
| 3 | Double-clic sur **Joue gauche** (pièce de bois), Épaisseur `25`. | Aussitôt : la joue grandit **vers l'intérieur** (x de 0 à 25), le **Voile** raccourcit de 3 mm (1153, x de 25 à 1178), la **Joue droite** ne bouge pas, l'ensemble reste à **1200** de large, les tourillons Joue gauche–Voile restent valides. Aucun avertissement dans la vue rapport. |
| 4 | Épaisseur `22`, **OK**. | La joue reprend 22 mm ; une seule entrée « Modifier une pièce de bois ». Même chose en changeant la propriété `Thickness` de la **Joue droite** dans l'éditeur de propriétés : elle grandit vers l'intérieur (x de 1175 à 1200 pour 25 mm), la largeur du bureau ne bouge pas. |
| 5 | Éditeur de propriétés du **Voile**, propriété `Length` (icône d'expression). | La formule cite la largeur du bureau et les deux épaisseurs de joue par le nom interne des pièces (`<<Bureau>>.Width - WoodPart001.Thickness - WoodPart002.Thickness`). Renommer la **Joue gauche** en « Joue G » : la formule ne change pas et suit toujours la joue. Dupliquer le Std Part : les joues de la copie suivent la copie. |
| 6 | **Étagère** : double-clic sur l'ensemble, Largeur `1162` (+ 100). | **Étagère 1** passe à 440 et **Étagère 2** à 660 (**au prorata** de leurs longueurs 400 et 600) ; le **Montant** garde son épaisseur de 18 mm et se déplace (x de 462 à 480) ; les joues gardent 22 mm ; aperçu immédiat. |
| 7 | Largeur `1062` (retour), puis choisir **Étagère 1** dans la liste et cocher **Cotes fixes**. | Étagères à 400 et 600. Colonne « Suit » de l'Étagère 1 : « cotes fixes… ». Rien ne bouge. |
| 8 | Largeur `1162`. | **Étagère 1** reste à **400**, **Étagère 2** absorbe tout (**700**), le Montant est à x de 422 à 440. |
| 9 | **Annuler** (bouton du panneau). | Tout revient : largeur 1062, étagères à 400 et 600, case **Cotes fixes** décochée. |
| 10 | **Bureau** : double-clic sur l'ensemble, choisir **Voile**, cocher **Cotes fixes** (à côté de la position). | Le Voile ne change plus de cotes ; colonne « Suit » : « cotes fixes, déplacée ». La **Joue droite** est reliée au Voile (elle suit désormais les épaisseurs et le Voile, au lieu de la largeur). Rien ne bouge dans la vue. |
| 11 | Profondeur `800`, puis **OK**. | Accepté : le Voile suit le fond (de y = 641 à 659) sans changer de cotes ; une entrée « Modifier l'ensemble ». |
| 12 | Double-clic sur **Bureau**, Largeur `1300`. | Message rouge sous les cotes : « Impossible de changer la largeur de l'ensemble à 1300 mm : aucune pièce de la rangée (…) ne peut s'adapter (cotes fixes : « Voile »). » **Rien n'est écrit**, **OK** est grisé. Dessous : « Pièces aux cotes fixes à déverrouiller », une case **Voile** **cochée** et le bouton **Déverrouiller et appliquer**. |
| 13 | Décocher la case **Voile**. | Le bouton **Déverrouiller et appliquer** se grise ; recocher la case le réactive. |
| 14 | Largeur `1250` (toujours refusée). | Le message est mis à jour (1250 mm) ; la case **Voile** reste cochée. |
| 15 | Largeur `1200`. | Le message, la case et le bouton disparaissent ; **OK** est de nouveau actif. |
| 16 | Largeur `1300`, puis **Déverrouiller et appliquer**. | Aussitôt dans la vue : la largeur est de **1300**, le Voile fait 1256 (de x = 22 à 1278), la Joue droite est contre le bord (x de 1278 à 1300) ; le message, la case et le bouton disparaissent, **OK** est actif. Choisir le Voile dans la liste : **Cotes fixes** est décochée. |
| 17 | **OK**, puis *Édition › Annuler*. | Une seule entrée « Modifier l'ensemble » : le Voile redevient **verrouillé**, la largeur redevient 1200 (profondeur 800 gardée) d'un coup. |
| 18 | Double-clic sur **Joue gauche** (le Voile étant verrouillé), Épaisseur `25`. | Même message rouge (« Impossible de changer l'épaisseur de « Joue gauche » à 25 mm… »), même case **Voile** cochée, même bouton ; l'épaisseur n'est pas écrite, **OK** est grisé. |
| 19 | **Déverrouiller et appliquer**. | La joue passe à 25 mm, le Voile est déverrouillé et se décale (de x = 25 à 1178), **OK** est actif ; **OK** donne une seule entrée « Modifier une pièce de bois ». |
| 20 | Verrouiller de nouveau le Voile (panneau de l'ensemble, **OK**), puis dans l'éditeur de propriétés : `Width` du Bureau = 1300, ou `Thickness` de la Joue gauche = 25. | Appliqué (règle Q4 : l'éditeur ne refuse pas) ; avertissement « Impossible de changer… » dans la vue rapport. Décocher **Cotes fixes** du Voile dans le panneau de l'ensemble rend l'ensemble cohérent. |
| 21 | Enregistrer, fermer, rouvrir ; double-clic sur Bureau, choisir le Voile. | La case **Cotes fixes** garde son état ; document non modifié à la réouverture. |
