# ADR 0024 — Assemblages entre pièces en biais : une charnière, un calcul plan

- Statut : **proposé** (issue #114, en attente de jv)
- Date : 2026-10-27
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0014 — Feuillure, mi-bois et onglet entre pièces au contact](0014-assemblages-par-superposition-au-contact.md),
  [0016 — Assemblages entre pièces qui se chevauchent](0016-assemblages-au-contact-entre-pieces-qui-se-chevauchent.md),
  [0019 — Rangées et épaisseurs fixes](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (PR #86),
  [0020 — La pièce en bois, enveloppe d'un corps](0020-piece-en-bois-enveloppe-d-un-corps.md)
- Spec : [assemblages-en-biais.md](../specs/assemblages-en-biais.md)
- Numéro : 0019, 0021 et 0022 sont pris par les jalons en attente de fusion (#86, #98).

## Contexte

Tous les calculs d'assemblage (`core/joints`) se font dans le repère de l'hôte, sur des boîtes
alignées : `relative_transform` exige une rotation relative d'équerre et lève sinon
« Les deux pièces doivent être d'équerre (angles multiples de 90°) ». Un caisson à côtés
inclinés, un cadre trapézoïdal ou un piètement écarté ne peuvent donc pas recevoir de
tenon-mortaise, alors qu'en atelier c'est courant (mortaise oblique, épaulements coupés en
biais).

Trois faits du code orientent la décision :

1. `Prism` (polygone plan extrudé) accepte déjà n'importe quelle orientation, et `moved` le
   change de repère quelle que soit la rotation ; `features/solids.py` le construit déjà.
2. `Box` et `Cylinder` (axe signé `Axis`) ne savent être que d'équerre.
3. Les pièces en biais réelles tournent presque toujours autour d'**un seul axe commun** aux
   deux pièces : la profondeur du caisson pour des côtés inclinés, l'épaisseur du cadre pour
   un cadre trapézoïdal. Les angles composés (pied de chaise écarté dans deux directions) sont
   rares et relèvent d'un autre niveau de difficulté, en atelier comme dans le calcul.

## Options

1. **Calcul 3D général** (rotation quelconque, demi-espaces, booléennes OCC dans `features/`).
   Couvre les angles composés, mais sort le calcul de `core/` (plus de tests purs), multiplie
   les cas (sections en losange, épaulements gauches) et les messages. Rejetée pour ce jalon.
2. **Arrondir à l'équerre** (calculer comme si la pièce était d'équerre, puis tourner le
   résultat). Faux : épaulements qui baillent, mortaise qui sort de la matière. Rejetée.
3. **Une charnière, un calcul plan** : accepter seulement une rotation relative autour d'un axe
   commun aux deux pièces ; tout le problème se ramène alors à des polygones dans le plan
   perpendiculaire à cet axe, extrudés le long de lui (des `Prism`). **Retenue.**

## Décision

1. **Relation angulaire** (`core/geometry`, pur) : la rotation relative de deux pièces est
   classée en *d'équerre* (cas actuel, tolérance `ANGLE_TOLERANCE` inchangée), *en biais autour
   d'une charnière* (un axe de l'invitée est, au signe près, un axe de l'hôte ; l'angle est la
   rotation autour de cet axe) ou *composée* (refus, message dédié). Les fonctions actuelles
   (`relative_axes`, `relative_transform`, `classify`) ne changent pas : le cas d'équerre garde
   **exactement** son calcul et ses plans.
2. **Écart à l'équerre** α : angle entre la normale de la face de contact de l'invitée et celle
   de la face de l'hôte qu'elle rencontre. Accepté pour 0 < α ≤ `MAX_OBLIQUE_DEG` (45° proposé,
   question Q1 de la spec). Le biais « en torsion » (charnière = axe de la normale de contact)
   est refusé dans ce jalon.
3. **Plan de l'épaulement** : la face de l'hôte touchée. L'invitée est ramenée à ce plan dans
   le calcul seulement, comme en ADR 0014 et 0016 : la partie qui entre dans l'hôte va dans
   `guest_trims`, le coin qui manque entre son bout d'équerre et le plan (pièce dessinée pointe
   contre la face) va dans `guest_additions`. Les deux sont des prismes. La brute ne change pas.
4. **Profil** (tenon, puis languette) : section mesurée perpendiculairement à l'axe de
   l'invitée, comme on le trace à l'établi ; le profil part du plan de l'épaulement et suit
   l'axe de l'invitée ; son bout est d'équerre à cet axe (débouchant : coupé selon la face
   opposée de l'hôte). Le logement **suit l'axe de l'invitée** (mortaise oblique) ; ses parois et
   sa profondeur sont contrôlées dans le repère de l'hôte, au point le plus profond.
5. **Assemblages acceptés en biais** : tenon-mortaise (lot 1) et rainure-languette (même code de
   profil, rainure le long de la charnière). Tourillons, feuillure, mi-bois, queue d'aronde et
   onglet restent d'équerre seulement, avec un message qui nomme les assemblages possibles.
6. **Le plan porte les biais** : nouveau champ `JointPlan.guest_bevels` (bout coupé en biais :
   face, angle, long point), vide par défaut. La liste de débit s'en sert (cotes au long point,
   mention de la coupe) sans refaire de géométrie.
7. **Persistance** : aucune nouvelle propriété, aucun nouveau type d'objet ; les paramètres
   actuels (`TenonThickness`… `MortiseClearance`) gardent leur sens, mesurés perpendiculairement
   à l'axe de l'invitée. `Version` inchangée.

## Conséquences

- Les documents et scripts actuels donnent les mêmes plans au bit près : le chemin d'équerre
  n'est pas touché, le chemin en biais ne s'ouvre que là où l'on refusait.
- Continuité : quand α tend vers 0, le plan en biais tend vers le plan d'équerre (valeurs
  automatiques comprises) ; un test le vérifie.
- `core/joints` gagne un module de cadre en biais (`_oblique.py`) à côté de `_profile.py` ;
  `MortiseTenonStrategy` et `TongueGrooveStrategy` choisissent le cadre selon la relation.
- Tout appel à `classify` sur un couple d'assemblés doit accepter le biais : les ensembles
  (`core/furniture/_check.py`) et le choix des rôles (`guess_roles`) passent par une nouvelle
  fonction `relation()` qui renvoie aussi le contact en biais.
- Ensembles : un membre en biais n'est plus seulement « pas d'équerre » ; il peut suivre par
  translation (spec, Q4). L'accrochage, l'aimant et « Définir une distance » restent d'équerre.
- Les angles composés, les tourillons et l'onglet à angle quelconque restent hors périmètre ;
  l'option 1 reste ouverte pour eux, sans remettre en cause ce découpage.
