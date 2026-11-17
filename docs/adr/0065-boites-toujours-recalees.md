# ADR 0065 — Boîte d'un ensemble toujours recalée sur ses membres, sous-ensembles compris

- Statut : **accepté** (jv, 2026-11-17 : « Les boîtes doivent toujours être recalculées, tu peux
  le noter en ADR »)
- Date : 2026-11-17
- ADR liés : [0038](0038-ensemble-a-la-souris.md), [0049](0049-cotes-du-parent-a-l-enveloppe.md)
  (point 3 remplacé), [0060](0060-epaisseur-qui-defait-un-assemblage.md) (point 5 amendé)

## Contexte

L'ADR 0049 recale la boîte d'un ensemble sur l'enveloppe de ses membres, mais seulement pour un
ensemble de plus haut niveau, et seulement après le déplacement d'un sous-ensemble. Un
sous-ensemble ne l'était jamais : sa position est portée par le `Placement` de son Std Part avec
un `Origin` nul (ADR 0038). Avec l'épaisseur d'un membre choisie dans l'encadré (ADR 0060
point 5), le côté d'un caisson épaissi vers l'extérieur sortait de la boîte du caisson ; une pièce
déplacée à la souris hors de son ensemble ne l'agrandissait pas non plus.

## Décision

1. **Gestes qui recalent.** À la fin de chacun de ces gestes, la boîte de l'ensemble concerné est
   recalée sur l'enveloppe exacte de ses membres (elle grandit ou rétrécit, sans marge), ses
   membres sont reliés d'après la géométrie obtenue, puis on **remonte** : la boîte du parent est
   recalée et il est relié, jusqu'à l'ensemble de plus haut niveau.
   - épaisseur d'un membre choisie dans l'encadré du panneau (ADR 0060 point 5) ;
   - sous-ensemble déplacé ou tourné (souris, `api.move_furniture`) : on part de son parent ;
   - pièce déplacée à la souris dans un ensemble (hors poignée d'épaisseur, qui garde l'ADR 0019) ;
   - pièce ou sous-ensemble qui entre dans un ensemble, qui en sort ou qui change d'ensemble
     (`api.add_to_furniture`, `api.remove_from_furniture`, panneau « Structure ») : l'ensemble
     rejoint et l'ensemble quitté sont recalés.
2. **Sous-ensemble.** Son `Origin` reste nul. Le Std Part avance du coin bas de l'enveloppe (dans
   son repère) et ses membres reculent d'autant : pièces par leur `Placement`, sous-ensembles par
   celui de leur Std Part. **Rien ne bouge à l'écran.** Ses cotes deviennent la taille de
   l'enveloppe. Les liaisons que son parent pose sur lui (cotes, position du Std Part) sont
   retirées avant le recalage, puis reposées par le parent d'après la boîte recalée : sinon le
   recalcul ramènerait l'ancienne boîte.
3. **Exceptions** (inchangées de l'ADR 0049, étendues aux sous-ensembles) : un ensemble dont une
   formule autre qu'une liaison de l'atelier pilote ou lit l'`Origin` ou une cote (répétition
   « Suivre le redimensionnement », formule de l'utilisateur) n'est pas recalé ; ni un
   sous-ensemble dont un membre est placé par une telle formule (copie d'une répétition), car le
   décaler ferait bouger ce qui en dépend. La remontée continue au parent.
4. **Retour arrière.** Si un niveau ne peut pas être relié (cycle avec une formule de
   l'utilisateur), boîtes, `Placement` des Std Parts et des pièces, et liaisons de toute la chaîne
   sont rendus avant de relancer l'erreur.
5. **Pièce ajoutée ou retirée** (jv, 2026-11-17 : « la boîte doit également rétrécir si besoin,
   elle doit toujours englober ses composants mais sans marges »). Remplace le complément du
   2026-11-16 de l'ADR 0049 : la boîte n'est plus seulement agrandie à l'entrée d'une pièce,
   elle est recalée exactement ; une marge donnée à la main disparaît au geste suivant.
6. Hors de ce périmètre pour l'instant : copies d'une répétition, « Relier les pièces », poignée
   d'épaisseur d'un membre (ADR 0019), cotes saisies dans l'éditeur de propriétés. Ils gardent
   leur comportement.

## Conséquences

- Code : `features/furniture_envelope.py` (`reframe` d'un sous-ensemble, `_movable`),
  `features/furniture_reframe.py` (`relink_framed`, remontée et retour arrière), appelés par
  `thickness_member.MemberFreedom.finish`, `furniture_drag._relink`, `part_drag._relink`,
  `api.add_to_furniture` et `api.remove_from_furniture`. `furniture_envelope.grow` est retiré.
- L'ADR 0049 point 3 (« seul un ensemble de plus haut niveau est recalé ») est remplacé ; la
  limite connue de l'ADR 0060 point 5 disparaît.
- Tests d'intégration : `tests/integration/test_boites_recalees.py` (pièce sortie d'un
  sous-ensemble imbriqué, sous-ensemble imbriqué déplacé puis ramené, retour arrière),
  `tests/integration/test_epaisseur_ensemble.py` (côté d'un caisson épaissi vers l'extérieur),
  `tests/integration/test_ensemble_membres.py` (marge retirée à l'ajout, boîte qui rétrécit à
  la sortie, pièce qui change d'ensemble).
