# ADR 0052 — Commandes toujours actives, sélection attendue expliquée

- Statut : **proposé** (issue #221, revue UX de novembre 2026, point A3 ; « go » de jv le 2026-11-11)
- Date : 2026-11-11
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0048](0048-selection-par-ensemble-dans-la-vue-3d.md)

## Contexte

Les commandes d'assemblage, de quincaillerie, d'ensemble, de répétition, « Définir une distance »
et « Convertir en pièce en bois » demandent une sélection faite **avant** le clic. Leur `IsActive`
lisait la sélection : sans la bonne sélection, le bouton était grisé sans dire pourquoi. Un
débutant voyait une barre d'outils grise. Un bouton grisé ne peut rien expliquer au clic, et son
infobulle décrit la commande, pas ce qui manque.

## Options

1. **Commandes actives, explication au clic.** Retenue. Une commande est active dès qu'un
   document est ouvert et qu'aucun panneau de tâche ne l'est. Lancée sans la bonne sélection, elle
   ne crée rien et affiche « Libellé : sélectionnez d'abord… puis relancez la commande. » dans la
   barre d'état et dans la boîte non modale de l'atelier (icône d'information).
2. **Panneau de choix guidé** (« choisissez la première pièce, puis la seconde ») : meilleur
   confort, mais un panneau et un mode de sélection par commande. Reporté ; l'option 1 ne
   l'empêche pas.
3. **Infobulle et barre d'état seulement, bouton toujours grisé** : n'explique rien à qui clique,
   et FreeCAD n'offre pas d'infobulle qui dépende de la sélection. Rejetée.

## Décision

- `TransactionCommand.IsActive` renvoie `command_ready()` (document ouvert, aucun panneau de
  tâche) ; l'examen de la sélection passe dans `selection_ok()`, en lecture seule.
- `Activated` appelle `explain_selection()` quand la sélection ne convient pas : aucune
  transaction, aucun objet, rien dans la vue rapport (ce n'est pas une erreur).
- Les phrases sont réunies dans `gui/commands/hints.py`. Elles citent Ctrl+clic, qui garde la
  sélection native pièce par pièce (ADR 0048).
- `add_command` enregistre la commande auprès de FreeCAD et la retient ; `would_run(nom)` dit si
  elle agirait sur la sélection actuelle (contrôles d'interface).
- Inchangé : « Pièce de bois », « Caisson », la liste de débit et « Structure » n'attendent
  aucune sélection ; « Convertir en pièce en bois » reste grisée sans matériau dans la
  bibliothèque ; le menu contextuel « Définir une distance » n'apparaît qu'avec deux éléments.

## Conséquences

- Le bouton ne renseigne plus, par son seul état, sur la validité de la sélection. Le panneau
  « Structure » garde ses entrées grisées avec la raison en infobulle (ADR 0046).
- Aucun effet hors de l'atelier : pas d'observateur, pas de préférence, les commandes des autres
  ateliers ne sont pas touchées (ADR 0007).
- Une nouvelle commande à sélection doit fournir `selection_ok` et `SELECTION_HINT` ; un test
  statique le contrôle (`tests/unit/test_selection_attendue.py`).
