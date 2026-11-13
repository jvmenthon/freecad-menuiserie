# ADR 0056 — Nommage topologique de FreeCAD 1.1 dans l'atelier

- Statut : **proposé** (jv, 2026-11-13 : « FreeCAD renumérote les arêtes à chaque recalcul : ce
  n'est plus le cas depuis la 1.0. Vérifie si des corrections peuvent être faites dans le code »)
- Date : 2026-11-13
- ADR liés : [0011](0011-apercu-accrochage-et-nom.md),
  [0020](0020-piece-en-bois-enveloppe-d-un-corps.md),
  [0022](0022-distance-entre-deux-pieces.md), [0023](0023-freecad-1-1-minimum.md),
  [0029](0029-profils-d-arete-par-balayage.md), [0030](0030-bande-de-chant.md),
  [0047](0047-repetition-jusqu-a-une-butee.md)

## Contexte

Plusieurs ADR justifient leurs choix par l'instabilité des noms d'éléments (`Face3`, `Edge7`)
d'une forme recalculée. Depuis FreeCAD 1.0 (fusion du travail de realthunder), une forme peut
porter une **carte des éléments** (`ElementMap`) : chaque `FaceN`, `EdgeN`, `VertexN` y reçoit un
nom tiré de l'historique des opérations, et un lien avec sous-élément (`PropertyLinkSub`,
`PropertyLinkSubGlobal`, attachement, cote TechDraw) mémorise ce nom ; au recalcul de la cible, le
lien retrouve le nouveau numéro de l'élément.

Vérifié dans le code source de FreeCAD 1.1.0 et par des tests d'intégration sur FreeCAD 1.1
(`tests/integration/test_nommage_topologique.py`) :

1. Les booléennes de Python (`cut`, `fuse`, `common`, `removeSplitter`, `extrude`…) passent par
   les fonctions `makeElement*` qui tiennent la carte, **mais seulement si leurs entrées en ont
   une ou sont étiquetées** (`Tag` non nul, `TopoShape::canMapElement`). Une forme construite en
   Python (`Part.makeBox`, `Part.Face`, `extrude`) n'a ni carte ni étiquette : le résultat n'a
   pas de carte (`ElementMapSize == 0`).
2. Sans carte, un lien vers `Face3` **garde le numéro** quand la forme change
   (`PropertyLinkBase::_updateElementReference` ne met à jour que s'il existe un nom cartographié).
   Avec carte, il suit l'élément.
3. Seuls les faces, arêtes et sommets sont cartographiés (`TopoShape::getElementTypes`) : un
   `SolidN` reste un numéro.
4. Un corps PartDesign a une carte ; la pièce en bois qui le recopie (`copy`, `transformShape`)
   la garde.

L'affirmation « FreeCAD renumérote à chaque recalcul » est donc fausse pour les objets natifs de
FreeCAD 1.x, mais restait vraie pour les **pièces usinées de l'atelier**, construites en Python
sans étiquette. Une boîte `Part.makeBox` garde par construction la même numérotation quelles que
soient ses cotes : la pièce de bois brute n'est pas concernée.

## Inventaire

| Endroit | Dépend d'un numéro ? | Sévérité | Suite |
|---|---|---|---|
| Pièce usinée (`features/solids.py`, `machined_shape`) : sans carte | oui : un lien d'un autre atelier (cote TechDraw, esquisse attachée, Assembly) vers une de ses faces pointe sur une autre face quand on ajoute ou retire un assemblage | majeur (ADR 0007, compatibilité avec les autres ateliers) | **corrigé** (décision 1) |
| Butée de répétition (ADR 0047, `PropertyLinkSubGlobal`) | sur la brute (boîte : numérotation fixe), sur une pièce en bois ou un objet natif (carte : le lien suit) | mineur | limite de l'ADR 0047 réduite (décision 3) |
| Sélection à la création (accrochage, distance, alignement, `PickedElement`) | lu une fois, jamais mémorisé | aucune | rien |
| Profils d'arête et bande de chant (ADR 0029, 0030) : code local `"Z+Y-"` | non | aucune | choix maintenu (décision 2) |
| Pièce en bois paramétrique à plusieurs solides refusée (ADR 0020) | `SolidN` non cartographié | aucune | choix maintenu |
| Accrochage par attachement natif rejeté (ADR 0011), distance sans référence topologique (ADR 0022) | — | aucune | choix maintenus (décision 2) |

## Décision

1. **La pièce usinée a une carte des éléments.** `machined_shape` étiquette ses entrées avant les
   booléennes : la boîte de la brute reçoit une étiquette de base (une forme dessinée garde la
   sienne, déjà cartographiée), chaque solide d'usinage une étiquette fixée par son **groupe**
   (parties retirées, ajouts, enlèvements) et son **rang**. Les étiquettes sont dans une plage
   au-delà des identifiants d'objets (2³⁰, sous 2³¹ pour le `long` 32 bits de Windows) : aucune
   collision avec l'historique d'une forme dessinée. Elles ne dépendent que de l'usinage : le cache
   des formes usinées reste exact (deux usinages égaux, mêmes noms). `Part::Feature` ré-étiquette
   la forme à l'identifiant de l'objet quand elle est affectée.
   Conséquence : les faces de la brute (dessous, bouts, chants) gardent leur nom quand on ajoute,
   modifie ou retire un assemblage ; les faces d'un usinage gardent le leur tant que les usinages
   qui le précèdent dans son groupe ne changent pas.
2. **Les choix sans numéro d'élément sont maintenus.** Le code local d'arête (ADR 0029, 0030)
   désigne une arête de la boîte brute par son sens, indépendamment de toute forme ; il se teste
   sans FreeCAD et reste juste après une rotation ou un changement de cotes. Les autres raisons des
   ADR 0011 et 0022 (conflit avec les liaisons de `Placement`, solveur, deux éléments à toucher)
   ne dépendent pas du nommage topologique. Leur mention « noms fragiles » se lit désormais : « sur
   les formes construites en Python sans étiquette ».
3. **Butée de répétition** : la limite de l'ADR 0047 (« une face qui change de numéro perd la
   butée ») ne concerne plus que les objets d'autres ateliers construits sans carte ; la brute
   (boîte) et la pièce en bois (carte du corps) ne sont pas concernées.

## Conséquences

- Un document existant n'a rien à migrer : la carte est créée au premier recalcul de la pièce
  usinée. Un lien d'un autre atelier créé avant ce recalcul ne porte qu'un numéro : il prend le nom
  de l'élément qui porte ce numéro au recalcul qui crée la carte, puis le suit.
- Le fichier `.FCStd` grossit (carte enregistrée avec la forme, noms qui s'allongent avec la
  chaîne d'opérations) et le calcul des booléennes ajoute la tenue de la carte ; le coût reste
  proportionnel au nombre d'usinages, comme avant. À mesurer sur un meuble réel avant d'aller
  plus loin (par exemple une carte pour la pièce brute).
- `machined_shape` n'écrit jamais dans la forme reçue : une base sans étiquette est copiée.
- Tout nouvel usinage construit en Python passe par `machined_shape` ou étiquette lui aussi ses
  entrées ; un test d'intégration le vérifie pour la pièce usinée.
- Profils d'arête sur une forme non boîte (fil de la finition des chants, PR #149) : une pièce en
  bois a une carte, une arête de sa forme pourrait donc être mémorisée par lien sans se perdre
  quand le corps change ; à étudier dans ce fil, pas ici.
