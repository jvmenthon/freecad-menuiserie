# ADR 0050 — Répétition des pièces en bois (ShapedPart)

- Statut : **proposé** (décision de jv : étendre la répétition aux pièces converties)
- Date : 2026-11-12
- ADR liés : [0003](0003-modele-de-la-piece-de-bois.md), [0020](0020-piece-en-bois-enveloppe-d-un-corps.md),
  [0043](0043-repetition-objet-de-cotes-et-copies-liees.md), [0044](0044-repetition-d-ensembles-et-liaisons-des-copies.md),
  [0045](0045-repetition-en-grille.md)

## Contexte

`repeat_sources._checked_source` refuse tout ce qui n'est pas une pièce de bois (boîte) ou un
ensemble (`_NOT_A_WOOD_PART`). Or une copie est créée par `create_wood_part` et ses cotes sont
liées par expression, ce qui ne convient pas à une `ShapedPart` : ses `Length`, `Width` et
`Thickness` sont des sorties de `execute()` (ADR 0020, décision 5) et `onChanged` retire toute
expression posée dessus.

## Décision

1. Sont répétables : pièce de bois, `ShapedPart` et ensembles dont tous les membres sont l'une ou
   l'autre (`_checked_furniture`). Prédicat commun `is_timber` (déjà dans `shaped_part.py`).
2. Une copie de `ShapedPart` est une `ShapedPart` qui lie **le même `Source`** (le corps n'est
   jamais copié ni modifié). Fabrique `new_shaped_copy` dans `repeat_new.py`, qui n'appelle pas
   `create_shaped_parts` (refus « déjà convertie »).
3. Réglages recopiés : `SourceAxes`, `ProfileThickness`, `SolidIndex`, `SolidSignature`, matériau,
   fil, surcotes. Liés par expression : matériau, fil, surcotes, `Placement` (comme une pièce
   de bois), plus `SourceAxes` et `ProfileThickness` pour que la copie suive la source.
   `SolidIndex` et `SolidSignature` sont copiés par valeur.
4. **Aucune expression sur les cotes d'encombrement** : `cell_expressions` et `inner_expressions`
   omettent `DIMENSIONS` pour une `ShapedPart` ; elles se recalculent depuis `Source`.
5. Dissociation, suppression, assemblages, ensembles : mêmes chemins que pour une pièce de bois,
   les contrôles `is_wood_part` étant remplacés par `is_timber`.
6. `converted_part_of` (plusieurs `ShapedPart` ont désormais le même `Source`) ne doit plus servir
   de test d'unicité pour les copies : il ignore les pièces qui sont des copies liées.

## Conséquences

- Aucun changement du format des documents ni de `MODEL_VERSION` : propriétés existantes.
- Une copie dépend du corps : le supprimer met toutes les copies en erreur (message existant).
- Un corps plus petit ou plus grand fait varier les cotes de toutes les copies, sans avertissement
  de répétition (`_DRAWN_SIZE_CHANGED` seulement si membre d'ensemble).
- Annuler la décision : retour au refus, copies existantes à dissocier (valeurs gardées).
