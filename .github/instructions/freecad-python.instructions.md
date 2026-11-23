---
applyTo: "freecad/**/*.py,tests/**/*.py,tools/**/*.py"
---

# Revue du code Python de l'atelier « Menuiserie » (FreeCAD ≥ 1.1)

Classe chaque point **[Bloquant]**, **[Majeur]** ou **[Mineur]** (voir
`.github/copilot-instructions.md`) et rédige en français.

## Règles FreeCAD (`CONTRIBUTING.md`)

- **Séparation App / Gui** : un document doit s'ouvrir et se recalculer dans `freecadcmd`.
  Un import `FreeCADGui`, `PySide` ou Qt dans `core/` ou `features/` est bloquant.
- **FeaturePython** : propriétés groupées avec infobulle ; `execute()` déterministe qui ne fait
  que reconstruire `obj.Shape` (seule exception, ADR 0020 : cotes de sortie `Output` en lecture
  seule de son propre objet, écrites seulement si elles changent) ; proxy sérialisé par
  `dumps` / `loads` ; propriété `Version` et migration dans `onDocumentRestored` pour qu'un
  ancien `.FCStd` reste lisible.
- **Annuler / rétablir** : chaque commande entre `openTransaction` et `commitTransaction`
  (ou `abortTransaction` en cas d'échec), jamais de transaction laissée ouverte.
- **Qt** : `from PySide import QtCore, QtGui` uniquement ; `PySide2` / `PySide6` interdits
  (seule exception : `tests/qtest/qttest.py`, ADR 0059).
- **Traductions** : toute chaîne visible passe par `translate()` ou `QT_TRANSLATE_NOOP`.
- **Unités** : mm en interne, `App::PropertyLength` pour les cotes.
- **Chargement léger** : imports différés dans `Initialize()`.

## Pièges connus

- **ViewObject et transactions** : modifier une propriété du `ViewObject` (transparence,
  couleur) pendant une transaction ouverte crée une entrée d'annulation. Les effets
  d'affichage temporaires se posent hors transaction et se restaurent après sa clôture.
- **Objet supprimé** : lire `obj.Name` sur un objet supprimé peut lever `TypeError` (pas
  seulement `ReferenceError` / `RuntimeError`) ; garder les références d'objets dans les
  panneaux et observateurs avec prudence.
- **Nommage topologique (ADR 0056)** : depuis FreeCAD 1.0, un lien vers `Face3` / `Edge7` suit
  l'élément seulement si la forme a une carte des éléments (`ElementMap`). Une forme construite
  en Python (`Part.makeBox`, booléennes sur entrées sans `Tag`) n'en a pas : tout nouveau lien
  mémorisé vers un sous-élément d'une forme de l'atelier doit être justifié. Les pièces usinées
  étiquettent leurs entrées (`machined_shape`) ; ne pas casser cet étiquetage. Un `SolidN`
  n'est jamais cartographié.
- **Suppression d'un groupe (Std Part)** : un `onDelete` qui supprime d'autres objets pendant
  une suppression récursive fait planter FreeCAD (voir `gui/view_providers/deletion.py`).
- **Observateurs et filtres Qt** : tout observateur de document ou filtre d'application posé
  dans `Activated` / à l'ouverture d'un panneau doit être retiré à la sortie, y compris sur
  erreur.
- **Vue 3D** : le double-clic dans la vue 3D n'atteint pas `doubleClicked` du ViewProvider
  (ADR 0018).

## Tests

- Chaque garde-fou d'entrée a son test (0, juste sous le minimum, au minimum).
- Les tests d'intégration ne doivent pas coder en dur les `Name` générés (`WoodPart001`) :
  construire les attentes depuis les objets.
- Un test d'interface hors écran ne doit envoyer aucun clic que FreeCAD traiterait lui-même
  (plantage du NaviCube sans contexte OpenGL).
