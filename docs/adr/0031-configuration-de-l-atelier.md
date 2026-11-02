# ADR 0031 — Configuration de l'atelier : page de préférences, dossier de l'atelier, export / import

- Statut : **proposé** (demande de jv, issue #148, 2026-11-01 ; « go » de jv le 2026-11-02)
- Date : 2026-11-02
- ADR liés : [0002 — Bibliothèque de matériaux](0002-bibliotheque-de-materiaux.md),
  [0028 — Dimensions personnelles](0028-dimensions-personnelles-partagees.md),
  [0029 — Profils d'arête](0029-profils-d-arete-par-balayage.md)

## Contexte

Un seul réglage existe (`UserLibraryPath`). Les valeurs par défaut (surcotes, jeux d'usinage,
aimantation, liste de débit…) sont écrites en dur. jv veut une configuration de l'atelier,
d'abord pour « arête cassée sur les pièces neuves » (spécification de la finition des chants, Q8),
avec une interface soignée, un export / import et un emplacement réglable.

## Décision

1. **Deux natures de réglages, deux supports.**
   - Réglages simples (nombres, cases, choix) : paramètres FreeCAD sous
     `User parameter:BaseApp/Preferences/Mod/Menuiserie` (déjà utilisé), lus par un module
     unique `features/settings.py` ; `core/` ne lit jamais de paramètre, il reçoit des valeurs.
   - Données personnelles (matériaux, épaisseurs, formats) : fichiers JSON existants
     (`materiaux.json`, ADR 0002 ; `dimensions.json`, ADR 0028), inchangés.
2. **Dossier de l'atelier.** Nouveau réglage `WorkshopFolder`, défaut
   `<dossier de données utilisateur>/Menuiserie/`. Il contient `materiaux.json`, `dimensions.json`
   et `atelier.json`. `UserLibraryPath`, s'il est renseigné, reste prioritaire pour `materiaux.json`
   seul (compatibilité). Le dossier peut être synchronisé (cloud) entre machines.
3. **Page de préférences** « Menuiserie » dans Édition > Préférences, enregistrée par
   `FreeCADGui.addPreferencePage` (aucune modification d'une page de FreeCAD). Groupes : pièces
   neuves, assemblages, interface, liste de débit, stockage. Chaque réglage : unité, infobulle,
   valeur par défaut visible ; bouton « Rétablir les valeurs par défaut » par groupe. Les valeurs
   sont bornées par `core` ; une saisie invalide est refusée avec un message clair.
4. **Export / import.** `atelier.json` : `{"format": 1, "settings": {…}, "dimensions": {…}}`.
   Lecture stricte comme l'ADR 0028 (64 Kio, JSON strict, valeurs bornées, clés inconnues ignorées
   avec avertissement, fichier invalide refusé entier). L'import montre un aperçu des changements
   et demande confirmation ; il n'écrit rien avant. Écriture atomique à l'export.
5. **Effet sur les documents.** Les réglages ne servent que de valeurs par défaut à la création
   (pièce neuve, assemblage neuf) : une pièce existante garde ses valeurs, un document reste
   autonome (ADR 0002). Seuls l'aimantation, la transparence en édition et le dossier d'export
   agissent en direct.
6. **Arête cassée par défaut** : case désactivée par défaut, taille 1 mm ; à la création d'une
   pièce, si elle est cochée, un profil « arête cassée » est ajouté à toutes les arêtes (dépend de
   l'ADR 0029).
7. **Hors configuration** : tolérances géométriques, plafonds de sécurité, marge de contact des
   assemblages (règles de l'atelier).

## Réglages retenus

Pièces neuves : arête cassée (oui / non, taille), dimensions, matériau, sens du fil, surcotes.
Assemblages : jeux de mortaise, de rainure et de trous de tourillons, longueur de languette, angle
de queue d'aronde, mortaise et feuillure débouchantes. Interface : tolérance d'aimant (px), pas de
rotation (°), tolérance des anneaux (px), transparence en édition. Liste de débit : préfixe des
repères, marge du PDF, style, dossier d'export. Stockage : dossier de l'atelier, chemin de
bibliothèque.

## Conséquences

- Découpage : lot 1 = `settings.py` + page minimale (arête cassée, surcotes, dimensions, jeux,
  dossier) ; lot 2 = export / import ; lot 3 = reste des réglages et édition de `dimensions.json`.
- Un réglage à ajouter plus tard = une ligne dans le catalogue de `settings.py` (clé, type,
  bornes, défaut, libellé) : la page, l'export et le « rétablir » le prennent sans autre code.
- Une version plus ancienne de l'atelier ignore les paramètres et le fichier `atelier.json`.
- Les tests de `core/` n'ont besoin d'aucun paramètre FreeCAD ; `settings.py` se teste avec un
  faux jeu de paramètres.

## Questions ouvertes

- Faut-il inclure `materiaux.json` dans l'export (fichier potentiellement volumineux, textures
  relatives) ? Recommandation : non en lot 2, les matériaux se copient avec le dossier.
