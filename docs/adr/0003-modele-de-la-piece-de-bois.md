# ADR 0003 — Modèle de la pièce de bois : repère local, sens du fil et contrat de persistance

- Statut : proposé (à valider par jv avec la spécification J1)
- Date : 2026-10-19
- Spécification : [docs/specs/J1-piece-de-bois.md](../specs/J1-piece-de-bois.md)

## Contexte

La pièce de bois est l'objet central de l'atelier : la liste de débit (J2) lit ses cotes, son fil et
ses surcotes ; les assemblages (J3) s'appuieront sur ses faces. Une fois des documents enregistrés,
le chemin Python de son proxy, les noms de ses propriétés et les valeurs de ses énumérations sont
écrits dans les fichiers `.FCStd` : les changer casse l'ouverture des plans des utilisateurs. Ces
choix doivent donc être faits une fois, explicitement.

Contraintes : l'objet doit se créer et se recalculer dans `freecadcmd` (`features/` sans Gui), mais
une pièce créée depuis la console de l'interface doit avoir son icône et sa couleur.

## Décision

1. **Objet** : `Part::FeaturePython` avec le proxy `WoodPart`, forme `Part.makeBox` (parallélépipède
   aux cotes **finies**). Les surcotes n'agissent jamais sur la forme, seulement sur le débit.
2. **Repère local** : X = longueur, Y = largeur, Z = épaisseur, origine sur un coin (comme
   `Part::Box`). L'orientation dans l'espace passe uniquement par `Placement`, conservé tel quel
   à chaque recalcul. Aucun ordre n'est imposé entre les cotes.
3. **Sens du fil** : énumération **relative au repère local** (`Length`, `Width`, `None`), et non
   vecteur dans l'espace global. Le fil suit la pièce quand on la tourne, et la liste de débit
   l'exprime directement (« fil dans le sens de la longueur »). `None` sert aux panneaux sans fil.
4. **Valeurs d'énumération stables en anglais** (`Length`, `Solid`…), comme dans les ateliers
   officiels de FreeCAD ; le panneau de tâche les affiche traduites. L'ordre des valeurs est figé :
   on ne fait qu'ajouter en fin de liste.
5. **Contrat de persistance**, vérifié par des tests :
   - chemins figés : `freecad.menuiserie.features.wood_part.WoodPart` et
     `freecad.menuiserie.gui.view_providers.wood_part.ViewProviderWoodPart` ; si un module doit
     bouger, l'ancien chemin reste un alias ;
   - proxies sans état (`dumps()` renvoie `None`), tout l'état est dans des propriétés typées ;
   - propriété masquée `Version` (1 au départ) ; `onDocumentRestored` applique `_migrate` pour
     toute version inférieure (une `Version` absente vaut 0) ; chaque migration a son test de
     réouverture.
6. **`execute()` déterministe** : il ne lit que les trois cotes ; la synchronisation du matériau
   (identifiant, catégorie, densité, fil, surcotes) se fait dans `onChanged`, hors restauration.
7. **Façade `freecad/menuiserie/api.py`** : `make_wood_part()` crée l'objet via `features/` puis
   attache le ViewProvider **seulement si `App.GuiUp`**. C'est le seul module hors `gui/` autorisé
   à importer `gui/`, sous cette condition ; `features/` reste sans aucun import Gui.

## Conséquences

- Les objets restent ouvrables et recalculables dans `freecadcmd` ; la séparation App / Gui
  (ADR 0001) est préservée.
- J2 dispose d'un enregistrement pur (`PartRecord`) indépendant de l'orientation de la pièce ;
  J3 pourra repérer les faces par le repère local (face `+Z` = parement, etc.).
- Les noms de propriétés et les valeurs d'énumération sont en anglais dans l'éditeur de propriétés,
  comme le reste de FreeCAD ; les infobulles et le panneau de tâche sont en français.
- Toute évolution du modèle coûte une migration et un test : c'est voulu.
- Une pièce créée sans interface (`freecadcmd`) n'a pas de ViewProvider Python quand on l'ouvre
  ensuite dans l'interface (icône et couleur génériques) ; une réparation à l'ouverture côté Gui
  est à prévoir dans un lot ultérieur.
- Le parallélépipède ne couvre pas les profils, chanfreins ou formes cintrées : ils viendront
  d'opérations ultérieures (assemblages, usinages), pas d'un changement de ce modèle.
