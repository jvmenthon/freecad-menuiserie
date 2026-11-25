# Configuration de l'atelier : spécification

- Statut : **brouillon**, questions Q1 à Q7 posées à jv (§ 7). Aucun code.
- Demande : issue #148 (jv, 2026-11-01), reprise par jv le 2026-11-25.
- ADR : [0031 — Configuration de l'atelier](../adr/0031-configuration-de-l-atelier.md) (fusionné,
  statut « proposé », à passer en « accepté » au premier lot). Les compléments du § 4 demandent un
  nouvel ADR, écrit quand jv dit « go ». ADR liés : 0002 (matériaux), 0007 (compatibilité),
  0028 (dimensions personnelles), 0029 et 0063 (profils d'arête), 0033 (quincaillerie).
- Liens : gabarits de meubles (PR #162, dossier `gabarits/` et palette des rôles), assistant
  « Nouveau projet » (`/mnt/project-files/specs/nouveau-projet.md`, dossier des projets), mineur Q2
  de `docs/corrections-mineures.md` (faux tenons).

## 1. But

Réunir dans un seul endroit les valeurs par défaut de l'atelier, aujourd'hui écrites en dur,
pour que l'utilisateur les règle une fois et les retrouve dans tous ses projets et sur toutes ses
machines (dossier synchronisé, export / import).

## 2. Périmètre

Dans le périmètre :

- une page « Menuiserie » dans **Édition > Préférences** (ADR 0031, point 3) ;
- un catalogue unique des réglages (`features/settings.py`) : clé, type, bornes, défaut, libellé,
  infobulle, groupe. La page, le « Rétablir », l'export et l'import se construisent à partir de lui ;
- le **dossier de l'atelier** qui regroupe les fichiers personnels ;
- l'export / import de `atelier.json` (lot 2).

Hors périmètre : tolérances géométriques, plafonds de sécurité, marge de contact des assemblages
(règles de l'atelier, ADR 0031 point 7) ; les états d'interface déjà retenus seuls (format CSV
choisi, vue « patron / boîte » des arêtes, panneau Structure fermé) restent des mémoires
silencieuses et ne vont pas dans la page ; l'édition des matériaux et de la quincaillerie.

## 3. Réglages candidats

Valeurs actuelles relevées dans le code (`main`, 2026-11-25). ★ = proposé pour le lot 1.

| Groupe | Réglage | Défaut actuel | Où dans le code |
|---|---|---|---|
| Pièces neuves | ★ Arête cassée sur les pièces neuves (oui / non) | non | nouveau |
| | ★ Taille de l'arête cassée | 1 mm | nouveau |
| | ★ Dimensions par défaut | 800 × 200 × 22 mm | `features/wood_part_schema.py` |
| | ★ Matériau par défaut, sens du fil | premier de la bibliothèque | `features/wood_part_schema.py` |
| | ★ Surcotes massif / panneau | 20 / 5 / 0 et 0 / 0 / 0 mm | `core/part_model.py` |
| | Épaisseurs et formats personnels (ajout, suppression) | `dimensions.json` | `features/user_dimensions.py` |
| Assemblages | ★ Jeux : mortaise, rainure, fond des tourillons | 2 / 1 / 1 mm | `core/joints/` |
| | ★ Longueur de languette, angle de queue d'aronde | 10 mm, 10° | `core/joints/` |
| | Mortaise et feuillure débouchantes | non | `core/joints/` |
| | ★ Faux tenons : liste de tailles ou taille libre (mineur Q2) | liste | `features/joints/slots.py` |
| | Écart « pièces proches » proposé à l'assemblage | 20 mm | `core/near_gap.py` |
| | Jeu des étagères du caisson | 1 mm | `core/templates/carcass.py` |
| Interface | Tolérance de l'aimant, des anneaux | 10 px, 8 px | `gui/drag/` |
| | Pas de rotation aimanté | 15° | `core/rotation/_turn.py` |
| | Aimant des champs à flèches | 1 mm | `core/magnet/_coplanar.py` |
| | Pièce en transparence pendant l'édition | oui | `gui/task_panels/base.py` |
| Liste de débit | Préfixe des repères, marge du PDF | « M », 10 mm | `core/cutlist/`, `gui/cutlist_pdf.py` |
| | Style par défaut, dossier d'export | — | `gui/commands/cutlist.py` |
| Stockage | ★ Dossier de l'atelier | `<données FreeCAD>/Menuiserie/` | `features/library.py` |
| | Dossier des projets (assistant « Nouveau projet ») | — | à venir |
| Gabarits | Palette des rôles : esthétique, daltonien, personnalisée | esthétique | à venir (PR #162) |

Règle : un réglage ne sert que de valeur par défaut à la **création** (ADR 0031 point 5) ; une
pièce ou un assemblage existant garde ses valeurs. Seuls les réglages d'interface agissent en direct.

## 4. Stockage

1. **Réglages simples** : paramètres FreeCAD sous
   `User parameter:BaseApp/Preferences/Mod/Menuiserie` (déjà utilisé). Lus par
   `features/settings.py` seul ; `core/` reçoit des valeurs, ne lit jamais de paramètre.
2. **Dossier de l'atelier** (`WorkshopFolder`). Il contient tous les fichiers personnels, pour
   qu'un seul dossier se synchronise entre machines :

   ```
   <dossier de l'atelier>/
     materiaux.json      bibliothèque personnelle (ADR 0002)
     dimensions.json     épaisseurs et formats (ADR 0028)
     quincaillerie.json  catalogue personnel (ADR 0033)
     gabarits/           gabarits personnels (PR #162)
     atelier.json        export des réglages (lot 2)
   ```

   Complément à l'ADR 0031 : aujourd'hui `dimensions.json` et `quincaillerie.json` suivent le
   dossier de `UserLibraryPath`. Pour ne déplacer aucun fichier, le défaut du dossier de l'atelier
   est **le dossier de `UserLibraryPath` s'il est renseigné**, sinon `<données FreeCAD>/Menuiserie/`.
   `UserLibraryPath` reste lu pour `materiaux.json` (compatibilité) mais n'est plus montré (Q3).
3. **Dossier des projets** : réglage séparé, lu par l'assistant « Nouveau projet » ; ce n'est pas
   le dossier de l'atelier (les projets ne se partagent pas forcément).
4. **Export / import** : `atelier.json` = `{"format": 1, "settings": {…}, "dimensions": {…}}`,
   lecture stricte (64 Kio, JSON strict, bornes de `core`, clés inconnues ignorées avec
   avertissement, fichier invalide refusé entier), aperçu avant application, écriture atomique.

## 5. Compatibilité avec les autres ateliers

- Page ajoutée par `FreeCADGui.addPreferencePage` : aucune page de FreeCAD modifiée.
- Paramètres seulement sous `Mod/Menuiserie` ; aucun paramètre global de FreeCAD n'est écrit.
- Aucune dépendance nouvelle (Qt de FreeCAD seulement).
- Les fichiers du dossier de l'atelier ne sont lus que par l'atelier ; une version plus ancienne
  ignore les paramètres nouveaux et `atelier.json`.
- Les documents restent autonomes : rien de la configuration n'est nécessaire pour rouvrir un
  fichier `.FCStd` sur une autre machine.

## 6. Découpage

- **CA-a** : `features/settings.py` (catalogue, lecture bornée, faux jeu de paramètres pour les
  tests) ; les constantes du lot 1 passent par lui, sans changement de comportement.
- **CA-b** : page de préférences du lot 1, après le choix de jv parmi **3 maquettes** (règle du
  projet) ; arête cassée à la création.
- **CA-c** : export / import de `atelier.json`.
- **CA-d** : reste des réglages, édition de `dimensions.json`, dossier des projets.

## 7. Questions pour jv

★ = choix recommandé.

- **Q1 Lot 1.** ★ Les lignes ★ du tableau (arête cassée, dimensions, matériau, surcotes, jeux,
  languette, aronde, faux tenons, dossier de l'atelier). Sinon : tout d'un coup.
- **Q2 Arête cassée par défaut, sur quoi ?** ★ Toute pièce neuve : pièce simple, pièce en bois
  (forme dessinée, ADR 0063) et pièces des gabarits ; pas les copies ni les répétitions (elles
  gardent les profils de la source). Sinon : pièces simples seulement.
- **Q3 Ancien chemin de bibliothèque.** ★ Le dossier de l'atelier reprend le dossier de
  `UserLibraryPath` s'il est renseigné ; ce réglage disparaît de l'interface. Sinon : garder les
  deux réglages visibles.
- **Q4 Dossier des projets** dans cette page (groupe Stockage). ★ Oui, défaut
  `Documents/Menuiserie`. Sinon : seulement dans l'assistant « Nouveau projet ».
- **Q5 Export.** ★ Réglages et dimensions seulement ; matériaux, quincaillerie et gabarits se
  partagent en copiant le dossier de l'atelier. Sinon : une archive de tout le dossier.
- **Q6 Où régler ?** ★ Page standard dans Édition > Préférences (ADR 0031). Sinon : une commande
  « Configuration de l'atelier » dans la barre de l'atelier qui ouvre la même page.
- **Q7 Palette des gabarits.** ★ Réglage ajouté avec le lot des gabarits (il n'a pas de sens
  avant). Sinon : prévu dès le lot 1.
