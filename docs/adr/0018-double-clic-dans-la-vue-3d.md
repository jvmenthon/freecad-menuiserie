# ADR 0018 — Double-clic dans la vue 3D

- Statut : **proposé** (issue #76, demande de jv du 2026-10-23 : « le double-clic doit aussi
  marcher sur le dessin »)
- Date : 2026-10-23
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

Un double-clic sur un objet de l'atelier doit ouvrir son panneau de tâche, dans l'arbre **et dans
la vue 3D**. Dans l'arbre, FreeCAD appelle `doubleClicked` du ViewProvider (fait depuis J1c). Dans
la vue 3D, FreeCAD 1.0 et 1.1 n'appellent rien : le style de navigation
(`NavigationStyle::processClickEvent`) reconnaît le second clic et l'absorbe. Aucune API Python
ne permet à un ViewProvider de recevoir ce double-clic.

Il faut donc écouter le double-clic nous-mêmes, ce que l'ADR 0007, § 3, encadre : « pas
d'observateur global permanent hors de la durée d'une opération de l'atelier, et toujours retiré
ensuite ».

## Options

1. **Ne rien faire** : double-clic dans l'arbre seulement. Contraire à la demande.
2. **Filtre d'évènements Qt permanent** (posé au chargement de l'atelier, jamais retiré) : marche
   même depuis un autre atelier, mais contraire à l'ADR 0007.
3. **Filtre d'évènements Qt posé tant que l'atelier est actif** : `Activated` le pose sur la zone
   d'affichage de chaque vue 3D (et des vues ouvertes ensuite), `Deactivated` le retire.
4. **Commande dans le menu contextuel** (« Modifier ») au lieu du double-clic : pas de filtre,
   mais ne répond pas à la demande.

## Décision

Option 3 (`freecad/menuiserie/gui/double_click.py`). Le filtre :

- est posé sur la zone d'affichage (`graphicsView().viewport()`) des vues 3D seulement, pas sur
  l'application entière (aucun coût sur les autres évènements ni les autres fenêtres) ;
- ne réagit qu'au double-clic gauche, lit l'objet sous le curseur (`getObjectInfo`, objet final
  des liens résolu par FreeCAD) et n'agit que si son ViewProvider est un `PanelEditing` de
  l'atelier ;
- ne consomme l'évènement que si le panneau s'est ouvert ; sinon (objet d'un autre atelier, vide,
  panneau déjà ouvert) l'évènement suit son cours habituel ;
- est retiré de toutes les vues quand on quitte l'atelier.

L'ADR 0007 est respecté au sens de son § 3 : la « durée d'une opération de l'atelier » est ici la
période où l'atelier est actif.

## Conséquences

- Dans un autre atelier, le double-clic sur une pièce dans la vue 3D ne fait rien (comportement
  actuel de FreeCAD) ; il reste disponible dans l'arbre.
- Vérification d'interface : double-clic simulé sur la pièce (panneau ouvert), dans le vide (rien),
  atelier quitté (rien).
