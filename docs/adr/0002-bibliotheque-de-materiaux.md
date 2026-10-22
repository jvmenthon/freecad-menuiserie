# ADR 0002 — Bibliothèque de matériaux (essences et panneaux)

- Statut : accepté (questions Q1 et Q3 de la spécification J1 validées par jv le 2026-10-19)
- Date : 2026-10-19
- Spécification : [docs/specs/J1-piece-de-bois.md](../specs/J1-piece-de-bois.md)

## Contexte

Chaque pièce de bois a besoin d'un matériau : essence massive ou panneau (contreplaqué, MDF,
mélaminé), avec une masse volumique, des épaisseurs standard et une couleur d'affichage. Cette
bibliothèque doit être versionnée avec l'atelier, extensible par l'utilisateur sans modifier
l'atelier, lisible sans risque (aucune exécution de code) et testable sans FreeCAD. La liste de
débit (J2) calculera volumes et masses à partir de ces données ; elle doit donner le même résultat
sur toutes les machines.

Options étudiées :

1. **Système de matériaux natif de FreeCAD** (`.FCMat`, `MaterialManager`, `ShapeMaterial`) :
   intégré à l'interface, mais API encore mouvante entre 1.0 et 1.1, sans notion d'épaisseurs
   standard ni de famille de panneau, et non testable dans `core/`.
2. **Fichier JSON propre à l'atelier**, lu et validé par `core/` : simple, testable, conforme au plan
   validé (« bibliothèque JSON versionnée »).

Pour le lien entre pièce et matériau :

- (a) la pièce ne garde que l'identifiant et relit la bibliothèque à chaque calcul ;
- (b) la pièce garde l'identifiant **et un instantané** des valeurs utiles aux calculs.

## Décision

1. **Format** : fichier JSON `{"format": 1, "materials": [...]}` ; chaque matériau a un `id`, un
   `kind` (`solid`, `plywood`, `mdf`, `melamine`), un `name` (chaîne ou objet `{langue: libellé}`),
   `density` (kg/m³), `thicknesses` (mm), `color` (`#RRGGBB`) et `has_grain` facultatif. Clés en
   anglais, libellés en français. Règles de validation détaillées dans la spécification J1.
   Une `texture` facultative (image relative au fichier de bibliothèque et taille réelle couverte,
   en mm) peut compléter la couleur, qui reste le rendu de secours si l'image manque.
   `rough_thicknesses` facultatif (épaisseurs de brut, mm) : voir l'[ADR 0014](0014-epaisseurs-de-brut.md).
2. **Le type de la pièce est une caractéristique du matériau** (`kind`) : il n'est pas choisi
   indépendamment de l'essence (cf. question Q3 de la spécification).
3. **Identifiant stable** (`chene`, `cp-bouleau`) : c'est lui qui relie une pièce à un matériau ;
   les libellés peuvent être corrigés ou traduits sans casser les documents.
4. **Instantané dans le document** (option b) : la pièce enregistre `MaterialId`, `Category` et
   `Density` au moment du choix du matériau. Le recalcul (`execute`) et les calculs de débit
   n'utilisent jamais la bibliothèque locale (cf. question Q1).
5. **Bibliothèque intégrée** `freecad/menuiserie/data/materiaux.json`, validée en CI (zéro anomalie).
6. **Extension utilisateur** : un fichier unique `<getUserAppDataDir()>/Menuiserie/materiaux.json`,
   ou le chemin du paramètre `BaseApp/Preferences/Mod/Menuiserie/UserLibraryPath`. Il est fusionné
   par identifiant : un nouvel `id` ajoute un matériau, un `id` existant remplace entièrement le
   matériau intégré. L'atelier ne crée ni ne modifie jamais ce fichier.
7. **Robustesse** : une entrée invalide est ignorée seule ; un fichier invalide est ignoré en entier ;
   les anomalies sont signalées une fois par session dans la vue rapport, jamais par une exception
   qui empêcherait l'atelier de fonctionner.
8. **Sécurité** : JSON uniquement (`json.loads`, `NaN`/`Infinity` refusés), taille bornée à 1 Mio
   avant lecture, types et bornes vérifiés pour chaque valeur.

## Conséquences

- Les documents sont **autonomes et reproductibles** : un fichier envoyé à un autre utilisateur
  garde ses masses, même s'il n'a pas les mêmes matériaux.
- En contrepartie, corriger une densité dans la bibliothèque **ne met pas à jour** les pièces
  existantes : il faudra une commande explicite « Mettre à jour depuis la bibliothèque » (hors J1).
- Les libellés français servent de valeurs à la liste déroulante `Material` : ils doivent être
  uniques dans la bibliothèque fusionnée.
- Le format porte un numéro (`format`) : toute évolution incompatible incrémente ce numéro et les
  versions suivantes de l'atelier devront continuer à lire le format 1.
- Une passerelle vers le système de matériaux natif de FreeCAD reste possible plus tard (par
  exemple en exportant la couleur et la densité vers `ShapeMaterial`), sans changer ce format.
- Le dossier utilisateur de FreeCAD peut être versionné selon la version installée ; le fichier
  utilisateur suit la migration proposée par FreeCAD, ou un chemin fixe via `UserLibraryPath`.
