# ADR 0041 — Tenon d'angle

- Statut : **proposé** (issue #174)
- Date : 2026-11-07
- ADR liés : [0006](0006-cotes-visibles-des-assemblages.md), [0024](0024-assemblages-entre-pieces-en-biais.md),
  [0034](0034-assemblages-en-biais-suite.md), [0007](0007-compatibilite-avec-les-autres-ateliers.md)
- Spec : [tenon-d-angle.md](../specs/tenon-d-angle.md)

## Contexte

Au coin franc, le tenon centré refuse (`NO_WALL`). L'atelier utilise un tenon d'angle.

## Décision

1. Le calcul reste dans `core/joints/_profile.py` : `check_walls` signale quel côté échoue ; une
   fonction `corner_section` réduit la section vers l'intérieur. Aucun nouveau solide ni plan.
2. Activation par une propriété énumérée `CornerMode` (Refuser par défaut / Auto) ; jamais
   silencieuse.
3. La corne est une propriété de la pièce hôte (`Horn`), sans usinage.
4. Cotes effectives exposées comme les autres cotes visibles ; la valeur manuelle l'emporte.

## Conséquences

Compatibilité : plans existants inchangés au bit près quand `CornerMode` = Refuser. Risque : la
section décalée doit rester dans la surface de contact (`OUTSIDE_CONTACT` conservé).
