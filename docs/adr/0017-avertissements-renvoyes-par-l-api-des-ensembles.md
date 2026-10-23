# ADR 0017 — Avertissements renvoyés par l'API des ensembles

- Statut : **proposé** (dette technique de fin J4, issue #40), en attente de jv
- Date : 2026-10-23
- Spécification : [docs/specs/J4-ensembles.md](../specs/J4-ensembles.md), § 4.4.4
- ADR liés : [0008 — Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi par expressions natives](0009-suivi-par-expressions-natives.md)

## Contexte

Les fonctions de l'API qui modifient un ensemble écrivent leurs avertissements traduits dans la
vue rapport (formule de l'utilisateur gardée, pièce pas d'équerre, épaisseur gardée, pièce qui
dépasse…) et les renvoient sous forme de `tuple[str, ...]` : `make_furniture` et
`make_carcass` (avec l'objet créé), `add_to_furniture`, `set_member_options`,
`set_edge_distance`, `rebind_furniture`. Deux exceptions, fixées par la spécification J4
(§ 4.4.4) :

- `resize_furniture` renvoie `None` : ses avertissements (cote qui fait dépasser une pièce,
  sous-ensemble qui suit…) vont dans la vue rapport mais un script ne peut pas les lire ;
- `remove_from_furniture` renvoie `None` : il ne produit aucun avertissement aujourd'hui.

Un script doit donc savoir, fonction par fonction, s'il peut lire les avertissements, et la
commande « Retirer de l'ensemble » enveloppe l'appel pour renvoyer un tuple vide comme les
autres commandes de l'ensemble.

## Options

1. **Garder `None`** et documenter l'écart. Rien ne change, mais les avertissements d'un
   redimensionnement restent inaccessibles aux scripts.
2. **`resize_furniture` seul** renvoie ses avertissements ; `remove_from_furniture` garde `None`.
3. **Règle unique** ★ : toute fonction de l'API qui modifie un ensemble renvoie ses
   avertissements traduits (`tuple[str, ...]`, vide s'il n'y en a pas) ; une fonction qui crée
   un objet renvoie `(objet, avertissements)`.

## Décision proposée

Option 3. `resize_furniture` renvoie les avertissements qu'il écrit déjà dans la vue rapport ;
`remove_from_furniture` renvoie `()` (aucun avertissement aujourd'hui, mais le contrat est le
même si un retrait doit un jour prévenir, par exemple d'un assemblage qui ne suit plus).

Les autres familles ne changent pas : les fabriques d'assemblage renvoient l'assemblage (un
refus est une exception, il n'y a pas d'avertissement), les fonctions de la liste de débit
renvoient leur résultat (liste, feuille, chemin écrit, repères attribués).

## Conséquences

- Compatible avec les scripts existants : une valeur de retour ignorée reste ignorée ; seul un
  script qui testerait `is None` serait touché (aucun dans le dépôt).
- Les commandes de l'ensemble n'ont plus de cas particulier : chacune renvoie les avertissements
  de l'API, rappelés dans la barre d'état.
- La spécification J4 (§ 4.4.4) reste le texte d'origine ; cet ADR la remplace sur ce point.
