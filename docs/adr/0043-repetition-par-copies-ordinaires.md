# ADR 0043 — Répétition : des copies de pièces ordinaires, sans objet « Répétition »

- Statut : **proposé** (en attente de jv, questions Q1 à Q8 de la spécification)
- Date : 2026-11-07
- Spécification : [docs/specs/repetition.md](../specs/repetition.md), issue #180
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0010 — Gabarits générateurs](0010-gabarits-generateurs.md)

## Contexte

jv veut répéter des pièces N fois à pas régulier. Options :

1. **Objet « Répétition » persistant** qui produit les copies à chaque recalcul. FreeCAD interdit
   de créer ou supprimer des objets pendant un recalcul ; il faudrait des copies virtuelles
   (une seule forme composée), donc sans usinage ni assemblage par copie, et absentes de la liste
   de débit. Rejetée.
2. **Copies ordinaires créées par une commande** : le calcul des décalages est pur, une fabrique
   unique crée pièces, assemblages et quincaillerie. Retenue (même esprit que l'ADR 0010).

## Décision

1. `core/repeat/` (Python pur) calcule les décalages à partir du mode, de N, du pas, de la
   longueur et de l'axe ; il valide les bornes (N de 1 à 100, pas > 0).
2. `features/repeat.py` crée, dans une transaction et un recalcul, les copies via les fabriques
   existantes (`create_wood_part`, fabriques d'assemblage J3, quincaillerie) ; `_api/repeat.py`
   expose `make_repeat(...)`.
3. Chaque copie reçoit deux propriétés en lecture seule, `RepeatGroup` et `RepeatIndex`, pour
   permettre plus tard « Changer le nombre » sans objet persistant.
4. Aucun lien par expression vers la source par défaut (copies indépendantes).

## Conséquences

- Rien à migrer, aucun nouveau type persistant, liste de débit et ensembles inchangés.
- Les copies ne suivent pas la source : modifier la source ne modifie pas les copies.
- Les copies dans un ensemble ne se redistribuent pas au redimensionnement.
