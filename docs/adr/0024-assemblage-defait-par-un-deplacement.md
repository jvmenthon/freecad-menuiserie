# ADR 0024 — Assemblage défait par un déplacement : choix au relâchement, sans trace Python

- Statut : **accepté** (décision de jv, propriétaire, après la recette de la PR #112 ; extension aux
  rotations et à la création d'un assemblage demandée le 2026-10-27)
- Date : 2026-10-27
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0021 — Déplacement à la souris](0021-deplacement-a-la-souris-avec-aimantation.md) (**B7
  modifié** ; critère B7 de la [spécification](../specs/souris-et-distances.md)),
  [0022 — Distance entre deux pièces](0022-distance-entre-deux-pieces.md)

## Contexte

Le critère B7 de l'ADR 0021 gardait le déplacement quand un assemblage ne touchait plus ses pièces
et prévenait dans la vue rapport (règle Q4 de J4 : « toujours appliquer, prévenir »). Mais le
recalcul du relâchement faisait lever `ValueError` par `plan_for` (`features/joints/base.py`, via
`translated_errors`) dans `execute()` de l'assemblage puis de la pièce usinée : FreeCAD imprime la
trace Python de toute exception d'`execute()`, et le message paraissait plusieurs fois. La même
trace sortait à la création d'un assemblage entre pièces qui ne sont pas d'équerre (la fabrique de
l'api recalculait avant de tester la faisabilité).

## Décision

1. **Au relâchement**, si le déplacement défait un ou plusieurs assemblages liés à la pièce, une
   fenêtre propose :
   - « Annuler le déplacement » (choix par défaut) : la pièce revient à sa position de départ ;
   - « Supprimer l'assemblage » (« Supprimer les assemblages » au pluriel ; les noms des
     assemblages concernés sont listés) : les assemblages impossibles sont supprimés
     (`doc.removeObject`, la pièce usinée est recalculée sans eux), puis chaque pièce usinée de
     leurs pièces qui n'a plus d'assemblage est supprimée (`remove_machined_part`, la brute est
     réaffichée) ; le déplacement est gardé.
   Échap ou la fermeture de la fenêtre valent « Annuler ». Une seule fenêtre pour tous les
   assemblages défaits.
2. **Aucune trace** : la faisabilité de chaque assemblage lié (`HostPart` ou `GuestPart` = la
   brute) est testée **avant tout recalcul**, par `plan_for` dans un `try` (`features/drag_joints.py`,
   fonction commune `settle_joints`). Un assemblage déjà en erreur avant le déplacement ne compte
   pas. Pendant le tirage, rien ne change par rapport à l'ADR 0021 : aucun recalcul par image
   (une poignée ne recalcule pas la pièce usinée tant que son assemblage ne tient plus).
3. **Une seule transaction** annulable (Ctrl+Z) : suppressions comprises, dans la transaction
   « Déplacer la pièce » (ou celle du panneau ouvert). Annuler le déplacement abandonne la
   transaction propre du glissement ou, dans celle d'un panneau, remet la pièce (`restore`).
4. **Fenêtre injectable** : `features/` reçoit une fonction de choix `labels -> bool`
   (`JointChoice`, paramètre `choose` de `end_drag`, de `DistanceMove.finish` et de
   `rotate_checked`). `gui/joint_choice.py` fournit la fenêtre (`ask`) et l'attribut de module
   `chooser`, que les tests remplacent ; sans fenêtre à cliquer hors écran, les vérifications
   d'interface la pilotent aussi par minuterie (boutons, Échap, fermeture).
5. **Outils concernés** (tout changement de `Placement` fait par l'atelier) : le glissement
   (flèches et poignées), « Définir une distance » (panneau ; Annuler ferme le panneau comme
   « Annuler » du panneau) et les boutons de rotation X, Y, Z du panneau de la pièce (pièce de bois
   et pièce en bois, en modification). En création, aucun assemblage n'existe encore.
   `api.set_distance` et les scripts n'ont pas de fenêtre : sans fonction de choix, le B7 d'origine
   reste (déplacement gardé, avertissement dans la vue rapport).
6. **Création d'un assemblage** : les fabriques `api.make_…` acceptent le mot-clé `check`, appelé
   sur l'assemblage créé **avant le premier recalcul** ; la commande y passe
   `features.joints.feasible.feasible_joint` (essai, rôles inversés au besoin). Un assemblage
   impossible donne un seul message de refus, sans trace, rien n'est créé.
7. **Hors de nos outils** (éditeur de propriétés, expression, script qui écrit `Placement`) : on ne
   peut pas intercepter l'écriture. L'erreur n'est au moins signalée qu'une fois : la pièce usinée
   ne relève plus l'erreur de son assemblage impossible, elle garde sa forme d'avant et suit le
   placement de la brute ; c'est l'assemblage, en erreur, qui le dit.

## Conséquences

- Aucune propriété ni migration nouvelles.
- Le B7 de la spécification est remplacé (tableau SM-b). L'ADR 0021 garde son statut ; sa note du
  2026-10-25 sur l'absence de refus au relâchement reste vraie : annuler est un choix de
  l'utilisateur, pas un refus de l'atelier.
- Non couvert : une modification de position par l'éditeur de propriétés, une expression ou un
  script qui défait un assemblage imprime encore la trace de l'assemblage (une seule fois).
  `api.set_distance` (script) garde le B7 d'origine, trace comprise.
