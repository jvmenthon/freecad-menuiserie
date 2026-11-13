# ADR 0054 — Aligner deux faces : tourner puis plaquer

- Statut : **proposé** (jv a choisi « tourner puis plaquer » le 2026-11-13 ; les autres choix
  ci-dessous sont des recommandations à valider)
- Date : 2026-11-13
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0022](0022-distance-entre-deux-pieces.md), [0025](0025-rotation-libre-d-une-piece.md),
  [0026](0026-assemblage-defait-par-un-deplacement.md)

## Contexte

« Définir une distance » refuse deux faces non parallèles et ne fait que translater. Le menuisier
veut poser une pièce **dans le plan** d'une autre (dessus au ras, face contre face), même si elle
est penchée.

## Décision

1. Commande **« Aligner deux faces »** : deux faces planes de deux objets (même sélection que
   « Définir une distance »). La pièce de l'atelier qui porte la seconde face bouge (sinon celle
   de la première) ; un objet d'un autre atelier ne bouge jamais (ADR 0007).
2. Mouvement rigide en deux temps (`core/align`, pur) : rotation **minimale** autour d'un point de
   la face mobile qui rend les faces parallèles, puis translation le long de la normale de la
   référence qui les rend coplanaires. Aucun glissement dans le plan de la face.
3. Modes : `flush` (au ras, normales de même sens), `facing` (face contre face, normales
   opposées), `auto` (défaut : la plus petite rotation ; à 90° exacts, au ras).
4. On écrit le `Placement` de la brute par `part_drag` (comme glissement et rotation) : un
   membre d'ensemble est relié ensuite, les assemblages défaits sont proposés avant tout
   recalcul (ADR 0026). Un `Placement` piloté par une formule refuse la commande.
5. Une transaction, sans panneau : le geste est immédiat et annulable (Ctrl+Z). L'API
   `api.align_faces(first, second, moving=None, mode="auto")` expose les trois modes.

## Conséquences

- Aucun objet nouveau dans le document, rien à relire sans l'atelier (ADR 0009).
- L'alignement n'est pas gardé : comme une distance hors ensemble, il est ponctuel.
- Reporté : panneau de choix du mode et de la pièce déplacée, aperçu en direct, alignement
  d'arêtes ou de sommets.
