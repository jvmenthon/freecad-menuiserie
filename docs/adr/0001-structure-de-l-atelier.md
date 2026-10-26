# ADR 0001 — Structure de l'atelier

- Statut : accepté
- Date : 2026-10-19

## Contexte

L'atelier doit être maintenable sur la durée, installable par l'Addon Manager et compatible avec
FreeCAD 1.x (Qt5 et Qt6). La logique de menuiserie (débit, essences, assemblages) doit être testable
rapidement, sans lancer FreeCAD.

## Décision

1. Layout « namespace » `freecad/menuiserie/` avec `init_gui.py`, décrit par `package.xml`.
2. Trois couches :
   - `core/` : Python pur, sans aucun import FreeCAD ni Qt ;
   - `features/` : objets du document (FeaturePython), sans import FreeCADGui ni Qt ;
   - `gui/` : commandes, ViewProviders, panneaux de tâche.
3. Cible FreeCAD ≥ 1.0 (≥ 1.1 depuis l'[ADR 0023](0023-freecad-1-1-minimum.md)), Python ≥ 3.10, Qt via le module `PySide` fourni par FreeCAD.
4. Licence LGPL-2.1-or-later, identique à FreeCAD.

## Conséquences

- Les tests unitaires de `core/` tournent en quelques secondes sans FreeCAD ; un test vérifie les
  imports interdits par couche.
- Les documents s'ouvrent et se recalculent dans `freecadcmd` (scripts, CI).
- Les tests d'intégration nécessitent un FreeCAD réel (conda-forge dans la CI).
