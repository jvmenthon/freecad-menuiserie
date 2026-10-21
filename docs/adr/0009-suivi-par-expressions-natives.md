# ADR 0009 — Suivi des pièces d'un ensemble par des expressions natives posées à la liaison

- Statut : **accepté** (jv, 2026-10-21 ; règle des distances fixes d'après sa réponse à Q3)
- Date : 2026-10-21
- Spécification : [docs/specs/J4-ensembles.md](../specs/J4-ensembles.md), § 4.3, § 4.4.2, § 4.4.3
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md)

## Contexte

Quand une cote de l'ensemble change, chaque pièce doit s'étirer, se déplacer ou rester en place.
Les assemblages de J3 doivent suivre. jv a fixé quatre règles. Une pièce intérieure a deux modes au
choix, distance au bord ou proportion. Par défaut, elle ne bouge pas. Si sa position est pilotée
par une formule ou une contrainte, la formule s'applique, avec un avertissement. Enfin (Q3,
2026-10-21) : « lorsque je défini une distance, je veux pouvoir indiqué si elle est fix ou non » :
aucun seuil automatique ne décide à sa place si une pièce suit un bord. L'ADR 0007 impose des liens
par l'`ExpressionEngine` natif.

Options étudiées :

1. **Recalcul par l'atelier à chaque changement de cote** : l'ensemble réécrit les cotes et
   positions des pièces, sous forme de nombres. Cela demande d'écrire dans d'autres objets hors
   recalcul, ce que le projet interdit pour `execute()` (J3, option 4 de l'ADR 0006). Le résultat
   est fragile à l'annulation, invisible pour l'utilisateur et faux sans l'atelier. Rejetée.
2. **Expressions natives posées une fois, à la liaison** : l'atelier calcule une expression par
   propriété concernée (`Width = <<Bureau>>.Depth - 40 mm`). Ensuite, FreeCAD seul les évalue.
   Retenue.
3. **Expressions écrites par l'utilisateur** avec un assistant : souple, mais ne répond pas à
   « modifier facilement ». Les formules de l'utilisateur restent permises (point 4 ci-dessous).

## Décision

1. **Règles pures** dans `core/furniture/`. Chaque face d'un membre a une distance au bord de
   l'ensemble de son côté (gauche, droite, avant, arrière, bas, haut), et chaque distance porte
   une option explicite **fixe / non fixe**. Une face à distance fixe suit son bord ; une face à
   distance non fixe suit le mode de la pièce (`Stay`, valeur par défaut : elle ne bouge pas ;
   `Proportional` : elle garde sa proportion de la cote). Une épaisseur n'est jamais étirée (une
   seule règle par pièce sur cet axe).
   **Options par défaut**, calculées une seule fois, quand le membre entre dans l'ensemble :
   fixe si la face touche le bord (≤ 0,01 mm) ou touche, de proche en proche, une face qui suit
   ce même bord ; non fixe sinon, quelle que soit la distance. C'est le choix sûr : une pièce
   intérieure ou en retrait ne bouge pas tant que le menuisier ne coche pas « fixe », et une pièce
   contre le bord (une joue) le suit. Ensuite, l'atelier ne change plus jamais les options ; un
   gabarit les donne explicitement (ADR 0010). Le seuil `EdgeMargin` d'abord proposé est
   abandonné.
2. **Liaison = expression FreeCAD** sur la **brute** (`Length`, `Width`, `Placement.Base.x/y/z`)
   ou sur un sous-ensemble (`Width`, `Depth`, `Height`, `Origin.x/y/z`). Elle vise le libellé de
   l'ensemble, avec des constantes figées au moment de la liaison. Les liaisons sont écrites par
   l'API (création, ajout, changement de mode ou d'option, « Relier les pièces ») ou, quand le
   menuisier change une option ou le mode dans l'éditeur de propriétés, par le `onChanged` du
   membre lui-même (`WoodPart`, ou `Furniture` pour un sous-ensemble), qui ne réécrit que ses
   propres liaisons, hors restauration et hors annulation. Toujours dans la transaction en cours,
   jamais pendant un recalcul, et jamais dans un autre objet.
3. **Propriétés de membre** dynamiques, ajoutées à l'entrée dans l'ensemble et retirées à la
   sortie (groupe « Ensemble ») :
   - `Furniture` (`App::PropertyLink`) ;
   - `PositionMode` (`App::PropertyEnumeration`, valeurs stables `Stay`, `Proportional`, ordre
     figé, ajouts en fin seulement ; modifiable) ;
   - `FixedLeft`, `FixedRight`, `FixedFront`, `FixedBack`, `FixedBottom`, `FixedTop`
     (`App::PropertyBool`, modifiables : l'option fixe de chaque distance) ;
   - `FurnitureBindings` (`App::PropertyMap`, propriété → texte de l'expression posée, relu après
     écriture).

   `WoodPart`, `MachinedPart` et les assemblages ne changent pas de `Version` (seul le crochet de
   `WoodPart.onChanged` est ajouté, sans effet hors ensemble). Le proxy de l'ensemble contrôle ces
   propriétés à la réouverture, selon les règles de l'ADR 0003 ; une option mal typée est recréée
   à sa valeur par défaut, sans réécrire les liaisons.
4. **Formules de l'utilisateur** : une propriété dont l'expression actuelle diffère du texte
   enregistré, ou une pièce référencée par un joint de l'atelier Assembly, est **pilotée**.
   L'atelier n'y pose ni n'y retire jamais rien. La formule s'applique et un avertissement est
   émis à la liaison et à chaque changement de cote concerné. En cas de doute (texte réécrit par
   FreeCAD, copie), la propriété est traitée comme pilotée. C'est le cas sûr : rien n'est détruit.
5. **Assemblages** : rien de nouveau. Ils lisent les brutes (ADR 0006), qui suivent leurs
   expressions dans le même recalcul. Le panneau et `resize_furniture` refusent d'avance une cote
   qui rendrait une pièce trop petite ou ferait perdre un contact d'assemblage (`check_resize`).

## Conséquences

- Changer une cote n'exécute aucun code de l'atelier : le comportement est natif, annulable,
  visible dans l'éditeur d'expressions et conservé sans l'atelier (ADR 0007).
- Les constantes figées ne voient pas une pièce modifiée à la main après la liaison. La commande
  « Relier les pièces » les recalcule (risque R3 de la spécification).
- Les noms `Furniture`, `PositionMode`, les six `Fixed…`, `FurnitureBindings` et les valeurs
  `Stay` et `Proportional` entrent dans le contrat de persistance. Aucun document J4 n'existant
  avant cette décision, l'abandon d'`EdgeMargin` et le renommage de la valeur `Fixed` en `Stay`
  (pour ne pas confondre « distance fixe » et « reste en place ») ne demandent aucune migration.
- Le menuisier voit et règle, pièce par pièce, ce qui suit quel bord ; le cas fréquent d'une
  pièce en retrait qui devrait suivre (joue à 40 mm du fond) demande une case à cocher (question
  Q7 de la spécification ; voir la mise à jour ci-dessous).
- Une modification de cote faite dans l'éditeur de propriétés n'est pas refusée d'avance
  (question Q4, recommandation retenue par jv). Les objets touchés passent en erreur sans forme
  partielle, comme en J3, avec un avertissement.
- Défaire cette décision (recalcul par l'atelier) demanderait de retirer les expressions de tous
  les documents J4 : c'est une décision difficile à défaire.

## Mise à jour du 2026-10-21 (réponse de jv à Q7, sous-lot J4a)

- **Options par défaut** (point 1 de la décision) : jv a répondu à Q7 « La pièce bouge par
  défaut ». Toute distance au bord est fixe par défaut, nulle ou non ; sur l'axe de son épaisseur,
  une pièce ne garde que la face la plus proche de son bord. La règle de contact, de proche en
  proche, est retirée. L'option « non fixe » reste au choix du menuisier.
- **Liaisons** (point 2) : les positions s'écrivent relativement à l'`Origin` de l'ensemble
  (`<<Bureau>>.Origin.x + <<Bureau>>.Width`) pour qu'un sous-ensemble dont l'`Origin` bouge
  entraîne ses membres. Détails : spécification J4, notes de réalisation de J4a.
