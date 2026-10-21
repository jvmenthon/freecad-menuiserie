# J4 — Recette manuelle du jalon

Recette de bout en bout du jalon J4 (ensembles, gabarit Caisson, mi-bois, queue d'aronde,
onglet), à dérouler par jv sur **FreeCAD 1.1.4 sous Windows**, atelier installé depuis la
branche du lot. Le détail du panneau de l'ensemble (champs, colonnes, messages) est dans
[J4c](J4c-scenarios-manuels.md) ; l'usage des panneaux d'assemblage dans
[J3e](J3e-scenarios-manuels.md). Reporter dans la PR les écarts et quelques captures.

Raccourci : **Ctrl+clic** pour sélectionner plusieurs objets ; chaque résultat « annuler » se
vérifie dans *Édition › Annuler* (une seule entrée par commande).

## 0. Préparation

Nouveau document, atelier **Menuiserie**. Créer le **bureau de référence** décrit dans
[J4c](J4c-scenarios-manuels.md#préparation--bureau-de-référence-à-la-main) (plateau, deux
joues, voile, deux jeux de tourillons). Ne pas encore créer l'ensemble.

## 1. Créer un ensemble

| N° | Action | Résultat attendu |
|---|---|---|
| 1.1 | Sélectionner les quatre pièces, bouton **Ensemble**. | Ensemble 1200 × 600 × 750 dans l'arbre, pièces et tourillons dessous ; rien ne bouge ; une entrée « Créer un ensemble ». |
| 1.2 | *Annuler* puis *Rétablir*. | L'ensemble disparaît (pièces intactes, sans expression), puis revient. |

## 2. Ajouter et retirer des pièces

| N° | Action | Résultat attendu |
|---|---|---|
| 2.1 | Créer une **Pièce de bois** « Tablette » (800 × 300 × 18) posée entre les joues, puis la sélectionner avec l'ensemble, bouton **Ajouter à l'ensemble**. | Elle apparaît sous l'ensemble, avec ses propriétés du groupe « Ensemble » ; les autres pièces gardent leurs options. |
| 2.2 | Double-clic sur l'ensemble, choisir Tablette. | Elle figure dans la liste des membres avec ses six distances. |
| 2.3 | Sélectionner la tablette, puis la commande *Retirer de l'ensemble*. | Elle garde sa forme, sans expression ni propriété « Ensemble ». *Annuler* la remet. |
| 2.4 | Tenter d'ajouter une pièce déjà membre d'un autre ensemble. | Refus avec un message en français, rien n'est modifié. |

## 3. Changer les cotes, distances fixes et non fixes

Dérouler les étapes 2 à 8 de [J4c](J4c-scenarios-manuels.md#p7--scénario-du-livrable) (profondeur
600 → 800, case « fixe » décochée puis recochée, voile en proportion, refus à 30 mm, formule
de l'utilisateur). Puis :

| N° | Action | Résultat attendu |
|---|---|---|
| 3.1 | Hauteur `800`, OK. | Plateau 50 mm plus haut, joues de 770, voile de 450 de haut, 5 tourillons de chaque côté. |
| 3.2 | Largeur `1400`, OK. | Plateau de 1400, joue droite recalée contre le bord, voile de 1356. |
| 3.3 | Joue gauche : décocher « fixe » à l'arrière, Profondeur `800`, OK. | Les joues ne s'allongent plus (largeur 560) ; le plateau, lui, suit. |
| 3.4 | Dans le panneau, saisir une distance (ex. voile, avant : `300`) sans toucher à « fixe ». | La pièce se déplace en aperçu, la case « fixe » reste telle quelle. |

## 4. Gabarit Caisson

| N° | Action | Résultat attendu |
|---|---|---|
| 4.1 | Nouveau document, bouton **Caisson**. | Panneau « Nouveau caisson » : 600 × 400 × 720, épaisseurs 18 / 8, feuillure 10, 1 étagère, assemblage des côtés « Tourillons ». Aperçu dans la vue 3D. |
| 4.2 | **OK**. | Côtés, dessus, dessous, fond en feuillure, une étagère, 4 jonctions à tourillons, un ensemble « Caisson » ; une entrée « Créer un caisson ». |
| 4.3 | Double-clic sur le caisson, Profondeur `500`, Hauteur `800`, OK. | Tout suit en un recalcul : fond toujours en feuillure, dessus à fleur du haut, étagère reste à sa hauteur (Reste en place), tourillons recomptés. |
| 4.4 | Recommencer **Caisson**, puis **Annuler** dans le panneau. | Aucun objet créé. |
| 4.5 | Dans un document avec le bureau : sélectionner le caisson et le bureau, **Ajouter à l'ensemble**. | Le caisson devient un sous-ensemble du bureau et suit sa profondeur. |

## 5. Mi-bois

| N° | Action | Résultat attendu |
|---|---|---|
| 5.1 | Deux traverses 600 × 60 × 22 : A en (0, 0, 0), B en (330, −270, 0) tournée de 90° autour de Z (croix de 60 × 60 au centre). | Les deux pièces se croisent. |
| 5.2 | Sélectionner A puis B, bouton **Mi-bois**. | Panneau avec profondeur effective 11 mm ; entaille par-dessus sur A, par-dessous sur B ; les deux faces supérieures sont à fleur. |
| 5.3 | Cocher **Inverser** (FlipSide) puis OK. | Les entailles passent de l'autre côté. |
| 5.4 | Changer la largeur de B à 80. | L'entaille de A suit (80 de large), un seul recalcul, aucune erreur. |
| 5.5 | Pièces en contact seulement (déplacer B hors de A), **Mi-bois**. | Refus : « Mi-bois : dessinez les deux pièces qui se croisent… ». |

## 6. Queue d'aronde

| N° | Action | Résultat attendu |
|---|---|---|
| 6.1 | Deux planches 400 × 150 × 18 en angle : H à plat en (0, 0, 0) ; I debout sur son bout en (18, 0, 18), tournée de −90° autour de Y. | Angle droit, face extérieure de I à fleur du bout de H. |
| 6.2 | Sélectionner H puis I, bouton **Queue d'aronde**. | Panneau : 3 queues, griffes 6 mm, pente 1:6 (valeurs automatiques affichées) ; queues sur I, logements dans H, un seul solide chacune. |
| 6.3 | Régler 4 queues, pente 8, OK. | Le dessin change, rien n'est en erreur. |
| 6.4 | Largeur des deux planches à 200 mm (ou mettre les deux dans un ensemble et passer sa profondeur de 150 à 200). | 4 queues automatiques, aucune erreur. |
| 6.5 | Griffes de 60 mm. | Message « Queues trop étroites… », pièces en erreur ; revenir à 0 les rétablit. |

## 7. Onglet

| N° | Action | Résultat attendu |
|---|---|---|
| 7.1 | Deux traverses 500 × 60 × 20 : A en (0, 0, 0) ; B en (60, 0, 0) tournée de 90° autour de Z (elles se chevauchent de 60 × 60 au coin). | Un angle de cadre. |
| 7.2 | Sélectionner A puis B, bouton **Onglet**. | Panneau sans champ, angles affichés (45° et 45°) ; coupe à 45° nette, pièces jointives sans trou ni recouvrement. |
| 7.3 | Largeur de B à 40 (et B en x = 40). | Angles 33,69° et 56,31°, toujours jointifs. |
| 7.4 | Mettre le cadre dans un **Ensemble** (A : décocher « fixe » à l'arrière ; B : décocher « fixe » à droite), Largeur `700`, Profondeur `600`. | Les traverses s'allongent, les onglets restent jointifs, un seul recalcul, aucune erreur. |
| 7.5 | Pièces qui ne se chevauchent pas, **Onglet**. | Refus : « Onglet : dessinez les deux pièces à leur longueur hors tout… ». |

## 8. Annuler / rétablir

Pour chaque commande des sections 1 à 7 (ensemble, ajout, retrait, modification des cotes,
caisson, mi-bois, queue d'aronde, onglet) : *Annuler* puis *Rétablir*. Résultat : une seule
entrée par commande, formes, expressions et options reviennent exactement, aucune pièce en erreur.

## 9. Enregistrer et rouvrir

| N° | Action | Résultat attendu |
|---|---|---|
| 9.1 | Enregistrer le document complet (bureau, caisson, assemblages), fermer FreeCAD, rouvrir. | Arbre, icônes, expressions identiques ; document non modifié (pas d'astérisque). |
| 9.2 | Changer une cote d'ensemble après réouverture. | Tout suit comme avant l'enregistrement. |
| 9.3 | Rouvrir un document de J1 ou J3 (sans ensemble). | S'ouvre sans changement ni avertissement. |

## 10. Compatibilité avec les autres ateliers

| N° | Action | Résultat attendu |
|---|---|---|
| 10.1 | Ranger bureau et pièces dans un **Std Part**, le tourner de 30° ; créer un **App::Link** ; Profondeur `700`. | Original et lien suivent. |
| 10.2 | Atelier **Assembly** : insérer le Std Part comme composant. | Accepté, déplaçable. |
| 10.3 | Atelier **TechDraw** : vue du Std Part. | Recalcul sans erreur. |
| 10.4 | Atelier **Part** (ou **Draft**) activé pendant que le document est ouvert, puis retour à **Menuiserie**. | Rien ne change dans les commandes ni dans l'arbre, aucun message dans la vue rapport. |
| 10.5 | Exporter le Std Part en STEP et le réimporter. | Même volume, formes valides. |
| 10.6 | Supprimer l'ensemble (touche Suppr.). | Pièces intactes, sans expression orpheline ; *Annuler* rétablit tout. |
