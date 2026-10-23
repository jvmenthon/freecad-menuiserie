# ADR 0016 — Tenon, languette, tourillons et queue d'aronde entre pièces qui se chevauchent

- Statut : **accepté** (jv, 2026-10-23 : « Tu dois gérer le cas où elles se chevauchent »)
- Date : 2026-10-23
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0014 — Feuillure, mi-bois et onglet entre pièces au contact](0014-assemblages-par-superposition-au-contact.md)
- Numéro : 0015 est pris par le jalon J2 (épaisseurs de brut).

## Contexte

Le tenon-mortaise, la rainure-languette, les tourillons et la queue d'aronde (J3, J4) se
calculent sur deux pièces **au contact**. Des pièces dessinées hors tout (une traverse tracée
jusqu'au chant extérieur du montant, deux planches d'angle qui se recouvrent au coin) **se
chevauchent** : ces assemblages les refusaient (« Les pièces se chevauchent »). ADR 0014 a fait
l'inverse pour la feuillure, le mi-bois et l'onglet. jv demande que les deux cas soient acceptés
partout.

## Options

1. **Refuser le chevauchement** : rien ne change. Ne répond pas à la demande. Rejetée.
2. **Déplacer ou raccourcir la brute** : modifie une pièce que l'utilisateur a dessinée, casse
   les cotes et les ensembles. Rejetée.
3. **Raccourcir l'invitée dans le calcul seulement** : symétrique d'ADR 0014. Retenue.

## Décision

Quand les deux pièces se chevauchent, l'invitée est **raccourcie** (dans le calcul seulement)
de la partie commune, par la face où elle entre dans l'hôte : la partie commune touche cette face
sans traverser l'invitée jusqu'à la face opposée. Parmi les faces possibles, celle qui retire le
moins de matière l'emporte (le bout d'une traverse plutôt qu'un chant). Le calcul au contact
existant s'applique à cette invitée raccourcie (`core/joints/_bridge.py`, `trimmed`, appelé par
`contact_frame`).

La partie retirée va dans un nouveau champ du plan, `JointPlan.guest_trims`. La pièce usinée
retire ces parties **avant** les ajouts (`machined_shape` : boîte − parties retirées + ajouts −
enlèvements), sinon le tenon, qui occupe justement la place retirée, serait enlevé avec elle.
La brute ne change pas de cotes.

Sans face possible (invitée entièrement dans l'hôte, ou qui le traverse de part en part), le
refus « Les pièces se chevauchent » reste.

## Conséquences

- La pièce usinée d'une invitée dessinée hors tout est plus courte que sa brute (tenon compris) :
  la liste de débit (J2) doit partir de la pièce usinée, ou soustraire les parties retirées.
- Le Caisson, les documents et les scripts au contact ne changent pas (plan identique, aucune
  partie retirée).
- Ensembles : la partie retirée suit les cotes, puisqu'elle est recalculée à chaque recalcul.
