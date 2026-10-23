# ADR 0018 — Double-clic dans la vue 3D

- Statut : **accepté** (option 3, choisie par jv le 2026-10-23 ; issue #76, demande de jv :
  « le double-clic doit aussi marcher sur le dessin »)
- Date : 2026-10-23
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

Un double-clic sur un objet de l'atelier doit ouvrir son panneau de tâche, dans l'arbre **et dans
la vue 3D**. Dans l'arbre, FreeCAD appelle `doubleClicked` du ViewProvider (fait depuis J1c). Dans
la vue 3D, FreeCAD n'appelle rien (vérifié dans les sources de la 1.0) : le style de navigation
(`NavigationStyle::processClickEvent`) reconnaît le second clic et l'absorbe. Aucune API Python
ne permet à un ViewProvider de recevoir ce double-clic.

Il faut donc écouter le double-clic nous-mêmes, ce que l'ADR 0007, § 3, encadre : « pas
d'observateur global permanent hors de la durée d'une opération de l'atelier, et toujours retiré
ensuite ».

## Options

1. **Ne rien faire** : double-clic dans l'arbre seulement. Contraire à la demande.
2. **Filtre d'évènements Qt permanent** (posé au chargement de l'atelier, jamais retiré) : marche
   même depuis un autre atelier, mais contraire à l'ADR 0007.
3. **Filtre d'évènements Qt posé tant que l'atelier est actif** : `Activated` le pose,
   `Deactivated` le retire.
4. **Commande dans le menu contextuel** (« Modifier ») au lieu du double-clic : pas de filtre,
   mais ne répond pas à la demande.

## Décision

Option 3 (`freecad/menuiserie/gui/double_click.py`). Le filtre :

- est posé sur l'application (`QApplication.installEventFilter`). Un filtre posé sur la zone
  d'affichage de chaque vue a été essayé : le filtre de Quarter (la vue 3D de FreeCAD), posé sur
  cette même zone après le nôtre, passe avant lui et traite le clic. Les filtres d'application
  passent avant ceux des widgets. Coût : une comparaison de type par évènement Qt tant que
  l'atelier est actif ;
- ne réagit qu'au double-clic gauche dont la cible est la zone d'affichage d'une vue 3D
  (`QGraphicsView` dans une `Gui::View3DInventor`), lit l'objet sous le clic (`getObjectInfo`, objet final
  des liens résolu par FreeCAD) et n'agit que si son ViewProvider est un `PanelEditing` de
  l'atelier ;
- ne consomme l'évènement que si le panneau s'est ouvert ; sinon (objet d'un autre atelier, vide,
  panneau déjà ouvert) l'évènement suit son cours habituel ;
- est retiré quand on quitte l'atelier.

L'ADR 0007 est respecté au sens de son § 3 : la « durée d'une opération de l'atelier » est ici la
période où l'atelier est actif.

## Conséquences

- Dans un autre atelier, le double-clic sur une pièce dans la vue 3D ne fait rien (comportement
  actuel de FreeCAD) ; il reste disponible dans l'arbre.
- Vérification d'interface : double-clic simulé sur la pièce (panneau ouvert), point vide (rien),
  filtre retiré en quittant l'atelier et reposé en y revenant. Hors écran, FreeCAD plante en
  traitant lui-même un clic ou un mouvement de souris (cube de navigation sans contexte OpenGL) :
  la vérification n'envoie que le double-clic que le filtre doit consommer.
