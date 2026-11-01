# ADR 0028 — Épaisseurs et formats de panneaux personnels, partagés entre projets

- Statut : **proposé** (demande de jv, issue #71, 2026-10-22 ; choix de conception à valider en
  recette)
- Date : 2026-11-01
- ADR liés : [0002 — Bibliothèque de matériaux](0002-bibliotheque-de-materiaux.md),
  [0015 — Épaisseurs de brut](0015-epaisseurs-de-brut.md)

## Contexte

jv veut ajouter ses propres épaisseurs de matériaux et ses propres formats de panneaux, et les
retrouver dans tous ses projets : ils vivent donc dans le dossier de configuration de FreeCAD, pas
dans le document. La bibliothèque personnelle `materiaux.json` ne convient pas : une entrée du même
`id` **remplace entièrement** le matériau intégré (texture relative comprise), et l'ADR 0002 interdit
à l'atelier de modifier ce fichier. Il n'existait aucune notion de format de panneau.

## Décision

1. Nouveau fichier **`dimensions.json`**, dans le dossier du fichier de bibliothèque personnelle
   (`UserLibraryPath` ou `<dossier utilisateur>/Menuiserie/`) :
   `{"format": 1, "thicknesses": [mm, …], "sheets": [[longueur, largeur], …]}`.
   Le fichier de matériaux n'est jamais touché.
2. Les épaisseurs personnelles s'ajoutent à celles de **tous** les matériaux (menu du panneau de la
   pièce) et comptent comme standard pour l'avertissement « hors standard » d'un panneau. Les
   formats (trois formats du commerce intégrés : 2500 x 1250, 2440 x 1220, 3050 x 1525, plus ceux de
   l'utilisateur) se proposent pour les panneaux et règlent longueur et largeur de la pièce.
3. L'atelier écrit ce fichier (écriture atomique) quand l'utilisateur choisit « Ajouter une
   épaisseur… » ou « Ajouter un format… ». Lecture : 64 Kio au plus, JSON strict (`NaN` refusé),
   50 valeurs de chaque sorte au plus, bornes de `core` ; un fichier invalide est ignoré entier
   avec un avertissement.
4. Le document n'enregistre pas ces valeurs : la pièce garde sa cote, comme avant (autonomie des
   documents, ADR 0002).

## Conséquences

- Pas de suppression ni d'édition depuis l'interface : on modifie le fichier à la main.
- Les formats ne servent pour l'instant qu'à régler les cotes d'une pièce ; le calepinage
  (optimisation de coupe) pourra les réutiliser.
- Une version plus ancienne de l'atelier ignore simplement le fichier.
