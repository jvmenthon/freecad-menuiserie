# ADR 0054 — Aligner deux faces : tourner puis plaquer

- Statut : **proposé** (jv a choisi « tourner puis plaquer » le 2026-11-13 et demandé le même jour
  l'inversion annulable, le mode d'équerre et l'action sur le 3e axe ; le reste est à valider)
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
   opposées), `perpendicular` (d'équerre : la rotation s'arrête à 90°) et `auto` (défaut : au
   ras ou face contre face, selon la plus petite rotation ; à 90° exacts, au ras).
4. **Décalage sur les trois axes** de la face de référence : deux dans son plan, le 3e le long de
   sa normale (distance entre les faces, ou jeu). Le pivot de la rotation est un point de la face
   mobile, ramené dans le plan de la référence avant décalage.
5. **Panneau de tâche** (transaction « Aligner deux faces ») : aperçu en direct, mode, décalages,
   bouton **Inverser** (échange la pièce pilotée et la pilotante ; la première revient avant que
   la seconde bouge), **Annuler** remet tout en place. OK relie l'ensemble et propose les
   assemblages défaits avant tout recalcul (ADR 0026). Un `Placement` piloté par une formule
   refuse la commande.
6. On écrit le `Placement` de la brute par `part_drag` (comme glissement et rotation).
   `api.align_faces(first, second, moving=None, mode="auto", offset=(0, 0, 0))` fait la même
   chose d'un geste.

## Conséquences

- Aucun objet nouveau dans le document, rien à relire sans l'atelier (ADR 0009).
- L'alignement n'est pas gardé : comme une distance hors ensemble, il est ponctuel.
- Reporté : alignement d'arêtes ou de sommets, rotation autour de la normale (3e rotation).
