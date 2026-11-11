# ADR 0037 — Sous-ensemble créé depuis des pièces déjà membres

- Statut : **accepté** (jv, 2026-11-07)
- Date : 2026-11-07
- ADR liés : [0010 — Gabarits générateurs](0010-gabarits-generateurs.md)

## Contexte

Dans un ensemble, jv sélectionne trois pièces (un tiroir) et lance « Ensemble » : refus
« déjà membre de l'ensemble ». Les sous-ensembles existent déjà, mais seulement à partir de pièces
libres.

## Décision

Si **toutes** les pièces sélectionnées sont membres du **même** ensemble, « Ensemble » crée un
sous-ensemble : les pièces sortent de l'ensemble parent, entrent dans le nouvel ensemble, qui
devient membre du parent. Les autres cas gardent le refus « déjà membre » (sélection mêlant
membres d'ensembles différents, ou membres et pièces libres).

## Conséquences

- Aucune nouvelle commande ; un seul geste, une seule transaction (annulation d'un bloc).
- Les liaisons du parent sont recalculées : le sous-ensemble compte comme un membre.
