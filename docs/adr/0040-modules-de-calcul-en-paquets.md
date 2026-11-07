# ADR 0040 — Modules de calcul des assemblages : un paquet quand le fichier approche 400 lignes

- Statut : **proposé** (relecture de la PR #164, demande de jv le 2026-11-07)
- Date : 2026-11-07
- ADR liés : [0033 — Quincaillerie](0033-quincaillerie-catalogue-et-modeles-generiques.md)

## Contexte

La limite de 400 lignes par module (CONTRIBUTING) est presque atteinte par
`core/joints/shelf_pins.py` (377 lignes) et `core/joints/slots.py` (383) : la prochaine
fonctionnalité obligerait à les couper dans l'urgence.

## Décision

1. Un module de `core/joints/` qui approche la limite devient un **paquet du même nom**, sans
   garder l'ancien fichier : `__init__.py` (docstring du module et ré-export de la même interface
   publique), `_params.py` (constantes, messages, paramètres et valeurs) et `_strategy.py`
   (stratégie et calculs). Les importateurs ne changent pas.
2. Les constantes partagées entre `_params` et `_strategy` sont publiques dans le paquet
   (`EPSILON`, `TOLERANCE_MM`) ; rien n'est dupliqué.
3. Appliqué à `shelf_pins` et `slots` ; `slides` (316 lignes) suivra quand il approchera la limite.
4. Une constante commune à plusieurs assemblages (`MIN_WALL_MM`) vit dans `_base.py`.

## Conséquences

- Aucun changement de comportement ni de persistance : les chemins de classes enregistrés dans les
  documents (`features/`) ne bougent pas.
- Un test existant (`test_structure_core`) continue de vérifier les couches.
