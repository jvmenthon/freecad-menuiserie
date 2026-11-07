# ADR 0039 — Pièces proches qui ne se touchent pas, à l'assemblage

- Statut : **proposé** (demande de jv, 2026-11-07)
- Date : 2026-11-07
- ADR liés : [0026 — Assemblage défait par un déplacement](0026-assemblage-defait-par-un-deplacement.md),
  [0021 — Déplacement à la souris](0021-deplacement-a-la-souris-avec-aimantation.md)

## Contexte

Les assemblages (tourillons, tenon-mortaise, rainure-languette…) demandent des pièces en contact.
Quand jv sélectionne deux pièces à quelques millimètres l'une de l'autre, la commande répond
« Les pièces ne se touchent pas » : il faut sortir, déplacer une pièce à la souris, puis relancer.

## Décision

Avant de créer un assemblage, si les deux pièces sont **d'équerre**, **écartées sur un seul axe**
de moins de **20 mm** (`NEAR_GAP_MM`) et se **recouvrent franchement** sur les deux autres axes
(les rapprocher donne un contact par une face, jamais par une arête), une fenêtre propose :

- **Déplacer** : une pièce est amenée au contact ;
- **Agrandir** : une pièce est étendue jusqu'au contact (sa face opposée ne bouge pas) ;
- **Annuler** : rien n'est créé ni modifié.

La pièce qui bouge ou grandit est l'**invitée**, à défaut l'hôte si l'invitée ne le peut pas
(formule de l'utilisateur sur sa position ou sa cote, cote qui ne se tire pas : épaisseur d'un
panneau, pièce en bois). Une option impossible n'est pas proposée ; sans aucune option, la
commande se comporte comme avant (refus expliqué). Les rôles sont devinés de nouveau une fois les
pièces au contact.

Le rapprochement réutilise `features/part_drag` (même chemin que la souris : membre d'ensemble
relié ensuite, assemblages existants contrôlés) et se fait dans **la même transaction** que
l'assemblage : une seule entrée d'annulation. La mesure de l'écart est pure (`core/near_gap.py`) ;
l'api expose `closing_options` et `close_gap`.

## Conséquences

- Le seuil de 20 mm est une constante ; le rendre réglable relève de la configuration de
  l'atelier (ADR 0031), plus tard.
- Pièces en biais : pas de proposition (comportement actuel inchangé).
- La coulisse de tiroir (jeu voulu entre les côtés, ADR 0033) a sa propre commande et n'est pas
  concernée.
