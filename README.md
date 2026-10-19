# Menuiserie — atelier FreeCAD

Atelier (workbench) FreeCAD pour concevoir des meubles et ouvrages de menuiserie de façon
paramétrique : pièces de bois réelles, assemblages classiques et liste de débit automatique.

> **Statut : en développement (jalon J0 – fondations).** L'atelier se charge dans FreeCAD mais
> ne propose pas encore d'outils.

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

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). Les décisions d'architecture sont consignées dans
[docs/adr](docs/adr).

## Licence

[LGPL-2.1-or-later](LICENSE), comme FreeCAD.
