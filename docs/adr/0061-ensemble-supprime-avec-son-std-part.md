# ADR 0061 — Std Part d'ensemble supprimé en gardant son contenu : l'ensemble disparaît aussi

- Statut : **proposé** (demande de jv du 2026-11-15, doute D4 du fil QTest : « oui supprime
  l'ensemble »)
- Date : 2026-11-15
- Remplace : la partie de l'[ADR 0038](0038-ensemble-a-la-souris.md) qui gardait l'objet ensemble
  quand son Std Part est supprimé à la main (`features/std_part_watch.py`)
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008](0008-ensemble-objet-de-cotes.md), [0044](0044-repetition-d-ensembles-et-liaisons-des-copies.md)

## Contexte

Supprimer le Std Part d'un ensemble ouvre la question de FreeCAD « supprimer aussi le contenu ? ».
Avec « Non », le Std Part disparaît, les pièces restent à leur place (ADR 0038, observateur de
documents) mais l'objet « Ensemble » de l'atelier (ses cotes, son épaisseur commune) restait seul
dans le document. jv veut qu'il soit supprimé aussi. Cette zone a déjà planté (PR #204 : supprimer
des objets pendant la boucle de suppression de FreeCAD laisse des pointeurs morts).

## Décision

1. Pendant la suppression (observateur `slotDeletedObject`, atelier actif), **rien n'est
   supprimé** : les ensembles rangés directement dans le Std Part sont seulement notés
   (`left_furnitures`), et la compensation des placements de l'ADR 0038 est inchangée.
2. Une fois la suppression de FreeCAD finie (minuterie Qt à 0 ms), `remove_left_furnitures`
   supprime chaque ensemble noté encore présent et sans Std Part, comme une suppression par
   l'interface (`release_furniture` : membres déliés, gardant leur place ; copies de répétition
   dissociées), dans **sa propre transaction** « Supprimer l'ensemble », puis recalcule.
3. Réponse « Oui » (contenu supprimé) : l'ensemble est déjà parti, rien n'est fait. Annulation,
   rétablissement, restauration : rien n'est noté (l'entrée « Supprimer l'ensemble » a sa propre
   place dans l'historique). Document fermé entre-temps : rien n'est fait (il est retrouvé par
   son nom ; un ensemble n'est supprimé que s'il est encore un ensemble sans Std Part). Une
   transaction encore ouverte (script, macro) : les suppressions s'y ajoutent.
4. Un sous-ensemble rangé dans le Std Part supprimé garde son propre Std Part et sort de son
   parent (ADR 0038, inchangé) ; seul l'ensemble dont le Std Part disparaît est supprimé.

## Conséquences

- **Deux entrées d'annulation** : « Supprimer l'ensemble » puis la suppression du Std Part.
  Ctrl+Z une fois rend l'ensemble (sans Std Part, pièces non reliées), deux fois rend tout.
  FreeCAD ne permet pas d'ajouter des écritures à une transaction déjà validée.
- Sans l'atelier actif (script, autre atelier), l'observateur n'est pas posé : comportement de
  FreeCAD seul, comme pour la compensation des placements (ADR 0038).
