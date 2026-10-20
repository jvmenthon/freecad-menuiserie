# Menuiserie — atelier FreeCAD

Atelier (workbench) FreeCAD pour concevoir des meubles et ouvrages de menuiserie de façon
paramétrique : pièces de bois réelles, assemblages classiques et liste de débit automatique.

> **Statut : en développement (jalon J1 – pièce de bois).** La pièce de bois paramétrique se
> crée depuis la console Python et se modifie dans l'éditeur de propriétés ; la commande de la
> barre d'outils et son panneau arrivent avec la suite du jalon.

## Fonctionnalités prévues

| Jalon | Contenu |
|---|---|
| J0 | Fondations : atelier chargeable, CI, outillage qualité |
| J1 | Pièce de bois paramétrique, bibliothèque d'essences et de panneaux |
| J2 | Liste de débit (tableau FreeCAD + export CSV) |
| J3 | Assemblages : tenon-mortaise, rainure-languette, tourillons |
| J4 | Mi-bois, queue d'aronde, gabarit de caisson |
| J5 | Plans TechDraw, traductions, publication dans l'Addon Manager |

## Prérequis

- FreeCAD **1.0** ou plus récent.

## Installation (développement)

Clonez le dépôt dans le dossier `Mod` de votre profil FreeCAD, puis redémarrez FreeCAD :

| Système | Dossier `Mod` |
|---|---|
| Linux | `~/.local/share/FreeCAD/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/Mod/` |
| Windows | `%APPDATA%\FreeCAD\Mod\` |

```sh
git clone https://github.com/jvmenthon/freecad-menuiserie.git <dossier Mod>/Menuiserie
```

L'atelier **Menuiserie** apparaît alors dans la liste des ateliers.

## Pièce de bois (console Python)

```python
from freecad.menuiserie.api import make_wood_part

planche = make_wood_part(800, 200, 22, "chene")  # longueur, largeur, épaisseur finies en mm
planche.Length = 1000  # ou depuis l'éditeur de propriétés
planche.Material = "Hêtre"  # masse volumique, catégorie, fil et surcotes suivent
```

La pièce est un parallélépipède : longueur selon X, largeur selon Y, épaisseur selon Z, dans
son repère local ; on l'oriente avec `Placement`. Elle garde l'identifiant, la catégorie et la
masse volumique de son matériau : un plan ouvert sur une autre machine reste exact. Pour pouvoir
annuler une création depuis un script, encadrez-la par `doc.openTransaction(…)` et
`doc.commitTransaction()`.

## Ajouter une essence

L'atelier lit, en plus de sa bibliothèque intégrée (`freecad/menuiserie/data/materiaux.json`), un
fichier personnel qu'il ne crée ni ne modifie jamais :

| Système | Fichier (dossier de données utilisateur de FreeCAD) |
|---|---|
| Linux | `~/.local/share/FreeCAD/Menuiserie/materiaux.json` |
| macOS | `~/Library/Application Support/FreeCAD/Menuiserie/materiaux.json` |
| Windows | `%APPDATA%\FreeCAD\Menuiserie\materiaux.json` |

Selon la version de FreeCAD, ce dossier peut être versionné (par exemple `…/FreeCAD/v1-1/`) :
`FreeCAD.getUserAppDataDir()` dans la console Python donne le bon. Pour utiliser un autre
fichier (bibliothèque partagée), renseignez le paramètre `UserLibraryPath` de
`BaseApp/Preferences/Mod/Menuiserie` :

```python
FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Menuiserie").SetString(
    "UserLibraryPath", "/chemin/vers/materiaux.json"
)
```

Exemple complet (format 1, encodage UTF-8) :

```json
{
  "format": 1,
  "materials": [
    {
      "id": "erable",
      "kind": "solid",
      "name": {"fr": "Érable", "en": "Maple"},
      "density": 650,
      "thicknesses": [22, 27, 34],
      "color": "#E8D2A8"
    },
    {
      "id": "cp-chene",
      "kind": "plywood",
      "name": "Contreplaqué plaqué chêne",
      "density": 680,
      "thicknesses": [10, 15, 19],
      "color": "#C49A6C",
      "has_grain": true
    }
  ]
}
```

- `id` : identifiant stable (minuscules sans accent, chiffres, tirets), enregistré dans les plans ;
  un `id` de la bibliothèque intégrée **remplace** entièrement ce matériau.
- `kind` : `solid` (massif), `plywood` (contreplaqué), `mdf` ou `melamine`.
- `name` : libellé français, ou libellés par langue ; il doit être unique.
- `density` : masse volumique en kg/m³ (50 à 2000) ; `thicknesses` : épaisseurs standard en mm
  (0,1 à 300) ; `color` : couleur d'affichage `#RRGGBB` ; `has_grain` (facultatif) : fil du bois.

Le fichier est lu une fois par session ; après l'avoir modifié, relancez FreeCAD ou exécutez
`from freecad.menuiserie.features.library import reload_library; reload_library()`. Une entrée
invalide est ignorée seule et signalée dans la vue rapport ; les pièces déjà créées gardent
leurs valeurs.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). Les décisions d'architecture sont consignées dans
[docs/adr](docs/adr).

## Licence

[LGPL-2.1-or-later](LICENSE), comme FreeCAD.
