# ADR 0060 — Épaisseur qui défait un assemblage : de quel côté l'ajouter

- Statut : **proposé** (jv a choisi le 2026-11-15 la maquette C pour le panneau et la maquette
  souris B pour les poignées ; le reste est à valider)
- Date : 2026-11-15
- Spécification : [docs/specs/epaisseur-d-une-piece-assemblee.md](../specs/epaisseur-d-une-piece-assemblee.md)
- ADR liés : [0019](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md),
  [0021](0021-deplacement-a-la-souris-avec-aimantation.md),
  [0026](0026-assemblage-defait-par-un-deplacement.md),
  [0043](0043-repetition-objet-de-cotes-et-copies-liees.md)

## Contexte

Le repère d'une pièce de bois a son origine sur sa face basse : une épaisseur saisie déplace sa
face haute. Les pièces **posées** sur cette face la suivent déjà (issue #133). Mais une pièce qui
**traverse** et doit arriver **à fleur** de la face (queue d'aronde : la pièce à griffes à fleur
de la face extérieure de la pièce à queues) n'y arrive plus : l'assemblage passe en erreur, sans
message dans le panneau et avec « OK » actif (doute D1 du fil QTest, scénario S4).

## Décision

1. **Panneau de la pièce** (maquette C, sans fenêtre) : quand l'épaisseur saisie d'une pièce
   **isolée** défait un assemblage qui tenait, un encadré apparaît sous les cotes avec trois
   choix :
   - « Vers l'intérieur (reste à fleur) » : l'écart est ajouté du côté de la face basse ; la pièce
     recule de l'écart, sa face haute ne bouge pas ; les pièces posées contre sa face basse la
     suivent (même règle que #133, face opposée) ;
   - « Vers l'extérieur et allonger « X » de N mm » : épaisseur telle que saisie, et chaque autre
     pièce de l'assemblage défait, à fleur de la face haute, est prolongée de l'écart (sa cote
     sur l'axe de l'épaisseur ; son origine recule si c'est son bout de début qui est à fleur) ;
   - « Revenir à N mm ».
   « Intérieur » / « extérieur » se lit par rapport à l'autre pièce ; pour une épaisseur réduite,
   « Côté intérieur » / « raccourcir ». Le premier choix possible est coché et appliqué aussitôt
   (aperçu en direct) ; « OK » valide l'état affiché, en une seule entrée d'annulation.
   **Assemblage qui tient** (jv, 2026-11-15) : si l'épaisseur saisie d'une pièce isolée assemblée
   ne défait rien (tenon qui suit la face haute, #133), l'encadré apparaît aussi, avec en tête
   « Laisser en l'état » (épaisseur telle que saisie, coché et appliqué), puis les mêmes choix,
   portant sur tous les assemblages de la pièce. Rien n'apparaît pour l'épaisseur de départ.
2. **Choix possible** : essayé sans recalcul du document (plans d'usinage des assemblages, comme
   ADR 0026) ; il l'est s'il ne défait aucun assemblage qui tenait. Sinon il est grisé, avec sa
   raison : autre pièce **copie de répétition**, **membre d'un ensemble**, **pièce en bois**
   (cotes du dessin), cote ou position **pilotée par une expression**, pièce pas à fleur, trop
   courte, ou assemblage encore défait. Si **aucun** choix ne tient (étape « 2 » d'une saisie
   « 22 », épaisseur trop mince), rien n'est écrit, l'encadré le dit et « OK » est inactif :
   jamais d'assemblage en erreur pendant la frappe. Chaque choix cliqué recalcule l'aperçu de
   toutes les pièces qu'il écrit (l'autre pièce allongée comprise).
3. **Saisies successives** : tant que l'encadré est affiché, chaque saisie d'épaisseur repart de
   l'état d'avant la première (`ThicknessEdit`, Memento) : taper « 3 » puis « 30 » ne cumule rien.
   Toute autre saisie (cote, rotation, glissement, matériau) fige l'état et masque l'encadré.
4. **À la souris** (maquette souris B, sans fenêtre) : la poignée tirée dit le côté. Une pièce
   assemblée à fleur de la face tirée, dont l'assemblage serait défait par cette face qui bouge
   (essai à +5 mm au premier pas), est **prolongée en direct** ; son écart s'affiche près de la
   souris (« « H » +12,00 mm ») et le relâchement l'écrit dans la vue rapport. Si elle ne peut
   pas l'être (mêmes raisons qu'au point 2), la poignée **s'arrête** à l'épaisseur du début
   (butée, message en rouge près de la souris) : il reste à tirer l'autre face. Échap rend tout.
   Les pièces **posées** sur la face tirée (règle de #133, assemblages de proche en proche) la
   **suivent aussi en direct**, sans être prolongées ; celles que #133 laisse en place (bloquées,
   membres d'ensemble) restent en place. Échap les rend à leur placement du début ; une pièce
   supprimée pendant le glissement est ignorée. L'aperçu recalcule les assemblages qui tiennent
   (chacun une fois par pas), puis la pièce usinée, de la pièce tirée et de toutes les pièces
   suivies. Au relâchement, la vue rapport donne le même message qu'en #133.
5. **Membre d'ensemble assemblé** (jv, 2026-11-17, amende la première version qui gardait l'ADR
   0019) : dans le panneau, l'encadré propose **les mêmes choix qu'une pièce seule**. Le temps de
   l'encadré, les liaisons de l'atelier des membres de l'ensemble sont mises de côté : les choix
   déplacent ou prolongent ses membres comme des pièces seules (un membre d'un **autre** ensemble,
   ou à cotes fixes pour une cote, reste bloqué). À la fin (« OK », ou autre saisie qui fige
   l'état), la boîte de l'ensemble est recalée sur l'enveloppe de ses membres, celle d'un
   sous-ensemble comprise, puis celles de ses parents (ADR 0049, ADR 0065) et tous ses membres
   sont reliés d'après la géométrie obtenue ; « Annuler » rend tout, liaisons comprises
   (transaction du panneau). Exemple : joue gauche du bureau de 22 à 30 mm « vers l'intérieur » :
   la voile et la joue droite sont poussées de 8 mm, l'ensemble passe à 1208 mm. Un membre sans
   assemblage, ou lui-même à cotes fixes, garde le comportement de l'ADR 0019 (l'ensemble garde
   ses cotes, les voisines s'adaptent). L'éditeur de propriétés et les scripts gardent celui de
   #133 (face haute, sans question).
6. **Poignée d'épaisseur d'un membre assemblé** (jv, 2026-11-23 : tiré vers l'extérieur, le côté
   d'un caisson grandissait vers l'intérieur). Dès la première épaisseur tirée, les liaisons de
   l'atelier des membres de l'ensemble sont mises de côté, comme dans le panneau (point 5). Si la
   boîte de l'ensemble change (face extérieure tirée, pour grandir ou rétrécir), la face tirée
   décide comme pour une pièce seule (point 4) : les voisines à fleur se prolongent en direct, ou
   la poignée s'arrête, et au relâchement l'ensemble est relié d'après le résultat, boîtes
   recalées (ADR 0065). Sinon (face intérieure), rien ne suit pendant le geste et la rangée
   absorbe au relâchement (ADR 0019), comme avant. Un membre à cotes fixes, ou sans assemblage,
   garde l'ADR 0019. Échap ou refus de liaison : tout est rendu, liaisons comprises.

## Conséquences

- Code : `core/thickness_side.py` (pur : `flush_extension`, `grows_toward`, `other_side_shift`),
  `core/thickness_follow.py` (`lowered`), `features/thickness_common.py` (assemblages de proche en
  proche, une seule raison « ne peut pas changer » partagée avec #133, écritures sans réaction),
  `features/thickness_choice.py` (`ThicknessEdit`, choix), `features/thickness_texts.py` (phrases
  complètes traduisibles de l'encadré), `features/thickness_drag.py` (souris, `FaceFollows`),
  `features/thickness_member.py` (`MemberFreedom` : liaisons de l'ensemble mises de côté puis
  refaites), `features/thickness_follow.py` (`FollowPlan`, `follow_plan` de #133, réutilisés par
  `DragFollow`), `features/blank_preview.py` (aperçu des brutes pendant un geste),
  `gui/task_panels/wood_part_conflict.py` (encadré), `features/part_drag.resize_part` (renvoie la
  raison d'une butée).
- Prolonger l'autre pièce modifie une pièce que l'utilisateur n'a pas touchée : c'est dit dans
  l'encadré (panneau) ou près de la souris et dans la vue rapport (poignées).
- Les scénarios QTest de ces comportements sont ajoutés par le fil QTest (ADR 0059).
