# ADR 0009 — Suivi des pièces d'un ensemble par des expressions natives posées à la liaison

- Statut : **proposé**
- Date : 2026-10-21
- Spécification : [docs/specs/J4-ensembles.md](../specs/J4-ensembles.md), § 4.3, § 4.4.2, § 4.4.3
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md)

## Contexte

Quand une cote de l'ensemble change, chaque pièce doit s'étirer, se déplacer ou rester en place.
Les assemblages de J3 doivent suivre. jv a fixé trois règles. Une pièce intérieure a deux modes au
choix, distance au bord ou proportion. Par défaut, elle ne bouge pas. Si sa position est pilotée
par une formule ou une contrainte, la formule s'applique, avec un avertissement. L'ADR 0007 impose
des liens par l'`ExpressionEngine` natif.

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

1. **Règles pures** dans `core/furniture/`. Pour chaque membre et chaque axe, chaque face suit la
   première règle qui s'applique : accroche à un bord ; contact avec une face déjà accrochée,
   propagé jusqu'à un point fixe ; retrait jusqu'à `EdgeMargin` ; enfin le mode de la pièce
   (`Fixed`, valeur par défaut : elle ne bouge pas ; `Proportional`). Une épaisseur n'est jamais
   étirée.
2. **Liaison = expression FreeCAD** sur la **brute** (`Length`, `Width`, `Placement.Base.x/y/z`)
   ou sur un sous-ensemble (`Width`, `Depth`, `Height`, `Origin.x/y/z`). Elle vise le libellé de
   l'ensemble, avec des constantes figées au moment de la liaison. Les liaisons sont écrites
   seulement par l'API : création, ajout, changement de mode, « Relier les pièces ». Elles le sont
   dans la transaction de l'appelant, jamais pendant un recalcul.
3. **Propriétés de membre** dynamiques, ajoutées à l'entrée dans l'ensemble et retirées à la
   sortie (groupe « Ensemble ») :
   - `Furniture` (`App::PropertyLink`) ;
   - `PositionMode` (`App::PropertyEnumeration`, valeurs stables `Fixed`, `Proportional`, ordre
     figé, ajouts en fin seulement) ;
   - `FurnitureBindings` (`App::PropertyMap`, propriété → texte de l'expression posée, relu après
     écriture).

   `WoodPart`, `MachinedPart` et les assemblages ne changent pas de `Version`. Le proxy de
   l'ensemble contrôle ces propriétés à la réouverture, selon les règles de l'ADR 0003.
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
- Les noms `Furniture`, `PositionMode`, `FurnitureBindings` et les valeurs `Fixed` et
  `Proportional` entrent dans le contrat de persistance.
- Une modification de cote faite dans l'éditeur de propriétés n'est pas refusée d'avance
  (question Q4). Les objets touchés passent en erreur sans forme partielle, comme en J3.
- Défaire cette décision (recalcul par l'atelier) demanderait de retirer les expressions de tous
  les documents J4 : c'est une décision difficile à défaire.
