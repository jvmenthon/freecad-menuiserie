# ADR 0058 — Coplanarité montrée pendant les déplacements, les copies et la répétition

- Statut : **proposé** (demande de jv du 2026-11-14 : « ajoute les indications de coplanarité
  comme l'aimantation lors des déplacements », puis « pendant les copies, ça va permettre de savoir
  quand j'ai défini le bon espace » ; pas de maquette, à la demande de jv)
- Date : 2026-11-14
- ADR liés : [0021](0021-deplacement-a-la-souris-avec-aimantation.md),
  [0043](0043-repetition-objet-de-cotes-et-copies-liees.md),
  [0045](0045-repetition-en-grille.md)

## Contexte

L'aimant du glissement (ADR 0021) ne retient que les guides **à portée** : un plan voisin dont
l'étendue recouvre la pièce sur les deux autres axes. Une face au ras d'une face d'un autre meuble
(dessus d'une tablette au niveau de celle du caisson d'à côté) n'est ni aimantée ni montrée. Dans
le panneau « Répéter », rien ne dit qu'un pas met une copie au ras d'une pièce voisine.

## Décision

1. **Coplanarité** : une face de la pièce (ou du fantôme, ou d'une copie) normale à un axe est
   coplanaire à une face voisine normale au même axe à la même position, à
   `CONTACT_TOLERANCE_MM` près, **même sans recouvrement** (`core/magnet/_coplanar.py`,
   `PlaneIndex`, pur ; positions triées, recherche par dichotomie).
2. **Glissement d'une flèche (déplacement, copie Ctrl)** : seules les deux faces de l'axe tiré
   comptent (les autres ne changent pas pendant le geste). Faute de guide à portée, l'aimant met
   la face au ras d'un plan hors de portée (`magnet(..., far=True)`) ; un guide à portée garde la
   priorité ; une droite ou un sommet hors de portée n'aimante pas. Maj coupe l'aimant comme avant.
3. **Poignée** : la face tirée montre ses coplanarités (sans aimant hors de portée : la signature de
   `resize` reste à six arguments).
4. **Dessin** : même magenta que les guides aimantés. Les plans voisins coplanaires sont allumés ;
   la face de la pièce aussi quand une de ces voisines est à l'écart (sinon la voisine la montre
   déjà). Au plus `MAX_COPLANAR` (64) faces de plus.
5. **Panneau « Répéter »** : les faces voisines (hors sources, copies, pièces usinées et
   assemblages) sont lues une fois, à la première copie, dans le repère du conteneur des sources
   (celui des axes X, Y, Z de la répétition) ; à chaque saisie, les faces des copies normales aux
   axes répétés qui sont au ras d'une voisine, et ces voisines, sont tracées dans une incrustation
   Coin (`MenuiserieRepeatCoplanar`) retirée à la fermeture du panneau. Rien n'est écrit dans le
   document.

## Conséquences

- Une face peut se coller à une pièce lointaine à la même cote : c'est voulu (alignement entre
  meubles) ; Maj coupe l'aimant, mais une coplanarité exacte reste allumée (jv, 2026-11-15).
- Les voisines du panneau ne sont pas relues pendant la tâche : un objet ajouté ou déplacé pendant
  qu'elle est ouverte n'est pas vu (aucune autre action n'est possible pendant le panneau).
- Faces obliques (pièce tournée hors des axes du conteneur) : ignorées, comme les guides.
