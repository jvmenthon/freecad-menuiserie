# J3e — Scénarios de recette manuelle

Critère E6 de la [spécification J3](../specs/J3-assemblages.md) (et parties visuelles de E1 à
E5), à dérouler à la main sur **FreeCAD 1.0** et **FreeCAD 1.1** (Windows : 1.1.4), atelier
installé depuis la branche du lot, profil utilisateur sans bibliothèque personnelle. Les
résultats et les captures sont reportés dans la PR.

Les critères E1 à E5 sont aussi vérifiés automatiquement, hors écran, par
`tests/gui/verifier_atelier.py` (`tests/gui/verifications_panneau_assemblage.py`).

## Préparation : cadre de référence (à la main)

Nouveau document, atelier **Menuiserie**. Créer quatre pièces par le bouton **Pièce de bois**
(chêne, Épaisseur 22, Largeur 60), puis régler leur `Placement` dans l'éditeur de propriétés :

| Libellé | Longueur | Position (x, y, z) | Rotation |
|---|---|---|---|
| M1 | 600 | (0, 0, 0) | aucune |
| M2 | 600 | (0, 340, 0) | aucune |
| T1 | 280 | (60, 60, 0) | 90° autour de Z |
| T2 | 280 | (600, 60, 0) | 90° autour de Z |

Vue de dessus : un cadre de 600 × 400 mm, traverses entre les montants.

## E6 — Scénario du livrable

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Sélectionner **M1** puis **T1** (Ctrl+clic), bouton **Tenon-mortaise**. | Le panneau « Nouvel assemblage : Tenon-mortaise » s'ouvre : « Pièce hôte : « M1 » », « Pièce invitée : « T1 » », bouton **Inverser** ; Épaisseur 7 mm, Largeur 40 mm, Longueur 40 mm grisées avec **Auto** coché ; jeu de fond 2 mm. Dans la vue 3D, le tenon dépasse du bout de T1 dans M1 ; « M1 (usinée) » et « T1 (usinée) » apparaissent dans l'arbre, brutes rangées dessous. |
| 2 | **Annuler**. | Plus d'assemblage ni de pièce usinée ; M1 et T1 de nouveau visibles ; *Édition > Annuler* ne propose rien de nouveau. |
| 3 | Refaire 1, décocher **Auto** de l'épaisseur, saisir `8`, **OK**. | Le tenon s'épaissit aussitôt ; *Édition > Annuler* propose une seule entrée « Créer un assemblage tenon-mortaise ». |
| 4 | Sélectionner **T1** puis **M2** (ordre inverse), **Tenon-mortaise**, **OK** ; de même M1 / T2 et M2 / T2. | Chaque fois M1 ou M2 reçoit la mortaise (rôles devinés) ; quatre tenons-mortaises dans l'arbre. |
| 5 | Double-clic sur un **Tenon-mortaise** dans l'arbre. | Panneau « Modifier « Tenon-mortaise » » ; cocher **Tenon traversant** : la mortaise débouche aussitôt ; **Annuler** : elle redevient borgne, aucune entrée d'annulation. |
| 6 | Double-clic sur le même assemblage, **Inverser**. | Les libellés des pièces s'échangent ; un message rouge (traduit) signale l'assemblage impossible. **Inverser** de nouveau : le message disparaît. **OK** : entrée « Modifier un assemblage ». |
| 7 | Double-clic, décocher **Auto** de la longueur, saisir `100`. | Message rouge « tenon trop long » ; **OK** reste possible ; l'assemblage est marqué en erreur dans l'arbre. *Édition > Annuler* : tout redevient correct. |
| 8 | Sélectionner la brute **M1** (sous « M1 (usinée) ») : Largeur `80` **et** Position y `-20` (le chant intérieur reste à y = 60) ; puis T1 et T2 : Largeur `50`. | Mortaises et tenons suivent : largeur automatique du tenon, tenon de 53 mm et mortaise de 55 mm dans M1 (deux tiers de la nouvelle largeur). Sans le déplacement en y, M1 chevaucherait T1 et l'assemblage passerait en erreur « les pièces se chevauchent ». |
| 9 | *Édition > Annuler* quatre fois, puis *Rétablir* quatre fois. | Retour aux largeurs de 60 mm puis de nouveau 80 / 50, assemblages corrects à chaque étape. |
| 10 | Enregistrer, fermer, rouvrir. | Document identique, icônes des types, couleurs et textures du chêne, aucun avertissement, document non marqué modifié. |
| 11 | Dans l'éditeur de propriétés de l'assemblage, `TenonWidth` = `=30 mm` ; double-clic. | Champ Largeur et sa case **Auto** grisés, 30 mm affiché ; **OK** : l'expression est toujours là. |
| 12 | Atelier **TechDraw** : nouvelle page, vue de **M1 (usinée)** (face) ; dans les propriétés de la vue, mettre **Hard Hidden** à vrai. | Les mortaises apparaissent en traits cachés. |
| 13 | Double-clic sur **M1 (usinée)** puis *Édition > Annuler* pendant que le panneau est ouvert. | Le panneau se ferme, le mode édition est quitté (double-clic de nouveau possible). |
| 14 | Préparation : créer deux nouvelles pièces de bois **P1** et **P2** qui se touchent, puis *Std Part* (bouton « Créer une pièce ») et glisser **P1** dans cette Part. Sélectionner **P1** (dans la Part) et **P2** (hors de la Part), **Tenon-mortaise**. | Rien n'est créé ; message dans la barre d'état et la vue rapport : les pièces doivent être dans le même conteneur. |

## Captures à joindre à la PR

Panneau à l'étape 1, cadre assemblé (étape 4), vue TechDraw (étape 12).

## Résultats

| Scénario | FreeCAD 1.0 | FreeCAD 1.1 |
|---|---|---|
| E6, étapes 1 à 7 (panneau) | à reporter | à reporter |
| E6, étapes 8 à 11 (suivi, annuler, réouverture) | à reporter | à reporter |
| E6, étapes 12 à 14 (TechDraw, fermeture forcée, refus) | à reporter | à reporter |
