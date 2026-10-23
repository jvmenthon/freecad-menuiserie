# ADR 0014 — Feuillure, mi-bois et onglet entre pièces au contact

- Statut : **accepté** (jv, 2026-10-22, carte de décision « Contact ou superposition »)
- Date : 2026-10-22
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0011 — Aperçu, accrochage et nom](0011-apercu-accrochage-et-nom.md)
- Numéro : 0012 et 0013 sont pris par le jalon J2 (liste de débit).
- Pendant : [ADR 0016](0016-assemblages-au-contact-entre-pieces-qui-se-chevauchent.md) accepte
  le chevauchement pour les assemblages au contact.

## Contexte

La feuillure, le mi-bois et l'onglet (J3, J4) se calculent sur deux pièces qui **se
superposent** : la boîte commune donne l'enlèvement. Depuis J6, l'accrochage crée des pièces qui
**se touchent**. Pour ces trois assemblages, l'utilisateur devait donc déplacer ou allonger une
pièce à la main. jv demande que des pièces au contact soient acceptées.

## Options

1. **Contact seulement** : la superposition est refusée. Il faudrait réécrire le Caisson, les
   documents existants et les tests. Rejetée.
2. **Garder la superposition seulement** : rien ne change. Ne répond pas à la demande. Rejetée.
3. **Contact ou superposition** : des pièces au contact sont ramenées à la superposition.
   Retenue.

## Décision

Quand les deux pièces se touchent par une face, l'invitée est **prolongée** (dans le calcul
seulement) par sa face au contact jusque dans l'hôte. Le calcul par superposition existant
s'applique à cette invitée prolongée (`core/joints/_bridge.py`, `bridged`) :

| Assemblage | Prolongement | Cas typique |
| --- | --- | --- |
| Feuillure | `Depth` (nouvelle propriété, 0 = moitié de l'hôte traversé ; moins que l'hôte) | fond posé sur les joues |
| Mi-bois | toute l'épaisseur de l'hôte traversée | traverse bout contre le chant d'un montant |
| Onglet | toute l'étendue de l'hôte, jusqu'au coin extérieur | deux traverses bout contre face |

La partie ajoutée est un **ajout** de la pièce usinée de l'invitée (comme un tenon, ADR 0006).
Les enlèvements calculés sur l'invitée prolongée sont ramenés dans le repère de l'invitée. La
brute ne change pas de cotes.

## Conséquences

- Les documents, le Caisson et les scripts qui superposent les pièces ne changent pas.
- La pièce usinée de l'invitée posée au contact est plus longue que sa brute : la liste de débit
  (J2) doit compter les ajouts, comme pour un tenon.
- Une pièce posée **sur** l'autre (face contre face) est prolongée dans son épaisseur. Le mi-bois
  et l'onglet la refusent alors (épaisseurs différentes, pas à fleur). La feuillure l'accepte :
  c'est le fond posé sur la joue.
- Ensembles : le prolongement suit les cotes, puisqu'il est recalculé à chaque recalcul.
