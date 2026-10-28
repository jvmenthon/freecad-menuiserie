# ADR 0024 — Assemblages entre pièces en biais : polyèdres convexes, angle quelconque

- Statut : **proposé** (issue #114 ; jv a tranché les questions de conception le 2026-10-28, reste le défaut de la référence)
- Date : 2026-10-27, revu deux fois le 2026-10-28 (demandes de jv : « Je veux pouvoir faire des assemblages
  de pièces avec 0 côté perpendiculaire » : les angles composés sont dans le périmètre ; référence du tenon au choix, mi-angle compris)
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
inclinés, un piètement écarté dans deux directions (chaise, tabouret), une pièce posée de
travers ne peuvent donc recevoir aucun assemblage, alors qu'en atelier ils se font (mortaise
oblique, épaulements coupés en biais, coupe composée).

jv demande que **n'importe quelle orientation** soit acceptée, y compris quand aucune face de
l'une n'est perpendiculaire à une face de l'autre.

Ce qui existe : `Box` et `Cylinder` ne savent être que d'équerre ; `Prism` (polygone extrudé)
accepte une orientation quelconque mais une seule direction d'extrusion, ce qui ne suffit pas
pour un tenon dont l'épaulement est coupé selon un plan gauche par rapport à sa section.

## Options

1. **Une charnière, un calcul plan** (première version de cet ADR) : rotation autour d'un seul
   axe commun, tout en prismes. Ne couvre pas la demande (angles composés refusés). Rejetée.
2. **Booléennes OCC dans `features/`** : le calcul quitte `core/` (plus de tests purs, plus de
   valeurs effectives affichables sans FreeCAD, contrôles de matière faits après coup). Rejetée.
3. **Polyèdres convexes calculés dans `core/`** : chaque solide d'un assemblage en biais (coin
   retiré, coin ajouté, tenon, mortaise, rainure) est l'intersection d'une boîte, posée dans un
   repère quelconque, avec quelques demi-espaces. Un tel solide est convexe ; `core/` calcule
   ses sommets et ses faces en Python pur (découpe d'une boîte par des plans), `features/` en
   fait un solide `Part`. **Retenue.**

## Décision

1. **Nouveau solide `Polyhedron`** (`core/geometry`, pur) : polyèdre convexe donné par ses faces
   (polygones plans orientés vers l'extérieur), construit par `clipped_box(box, frame, planes)`
   (boîte dans le repère `frame`, coupée par des demi-espaces). Il se déplace par `moved` pour
   toute rotation, donne son volume et ses sommets (contrôles et tests sans FreeCAD).
   `features/solids.py` le construit par `Part.Face` / `Part.Shell` / `Part.Solid`.
   `Box`, `Cylinder` et `Prism` ne changent pas.
2. **Relation angulaire** : la rotation relative est *d'équerre* (cas actuel, même tolérance
   `ANGLE_TOLERANCE`) ou *en biais* (toute autre rotation, angles composés compris). Les
   fonctions actuelles (`relative_axes`, `relative_transform`, `classify`) ne changent pas : le
   cas d'équerre garde **exactement** son calcul et ses plans.
3. **Contact en biais** : la face de contact de l'invitée (bout ±X pour un tenon, bout ou chant
   pour une languette) rencontre une face de l'hôte, le *plan d'épaulement*. L'écart à
   l'équerre α est l'angle entre leurs normales ; il est accepté pour 0 < α ≤ `MAX_OBLIQUE_DEG`
   (**70°**, choix de jv du 2026-10-28). La section de l'invitée peut être tournée sur ce plan (torsion) : c'est
   un cas comme un autre.
4. **Mise au contact dans le calcul seulement**, comme en ADR 0014 et 0016 : la partie de
   l'invitée au-delà du plan d'épaulement va dans `guest_trims`, le coin qui manque entre son
   bout d'équerre et le plan va dans `guest_additions`. La brute ne change pas.
5. **Profil** (tenon, languette) : section mesurée perpendiculairement à l'axe de l'invitée,
   comme on la trace à l'établi ; le profil part du plan d'épaulement et suit l'axe de
   l'invitée ; son bout est d'équerre à cet axe (débouchant : coupé selon la face opposée de
   l'hôte). Profondeur et parois du logement sont contrôlées dans le repère de l'hôte sur ses
   sommets.
   **Référence** (jv, 2026-10-28 : « Par défaut on prend une des faces en référence, sinon coupe
   la moitié de l'angle ») : tenon et logement suivent, au choix, l'axe de l'invitée (défaut
   proposé), la normale de la face de l'hôte, ou la bissectrice des deux (mi-angle) ; le plan
   d'épaulement reste toujours la face de l'hôte. Paramètre `reference`, propriété
   `ObliqueReference`.
6. **Assemblages acceptés en biais** : tenon-mortaise et rainure-languette (lot 1, même code de
   profil). Les autres restent d'équerre seulement, avec un message qui nomme ceux qui
   acceptent le biais ; leur ouverture au biais se fait type par type (spec § 8), sur le même
   socle.
7. **Le plan porte les biais** : `JointPlan.guest_bevels` (bout coupé en biais : face, normale du
   plan d'épaulement dans le repère de l'invitée, long point), vide par défaut. La liste de
   débit en tire les deux réglages d'une coupe composée (angle de coupe et inclinaison de la
   lame) et la longueur au long point.
8. **Persistance** : aucun nouveau type d'objet ; une seule propriété nouvelle,
   `ObliqueReference`, sur le tenon-mortaise et la rainure-languette (`Version` 1 → 2, ajoutée à
   sa valeur par défaut à la réouverture). Les paramètres actuels gardent leur sens (mesurés
   perpendiculairement à la direction du tenon).

## Conséquences

- Les documents et scripts actuels donnent les mêmes plans au bit près : le chemin d'équerre
  n'est pas touché, le chemin en biais ne s'ouvre que là où l'on refusait.
- Continuité : quand α tend vers 0, le plan en biais tend vers le plan d'équerre (valeurs
  automatiques comprises) ; un test le vérifie.
- `core/` gagne la découpe de polyèdres convexes (`core/_polyhedron.py`, ~150 lignes, testée
  par volumes et sommets) et un cadre en biais (`core/joints/_oblique.py`) à côté de
  `_profile.py`.
- Tout appel à `classify` sur un couple d'assemblés doit accepter le biais : le choix des rôles
  et les ensembles passent par une nouvelle fonction `relation()`.
- Ensembles : un membre en biais peut suivre par translation (spec, Q4). L'accrochage, l'aimant
  et « Définir une distance » restent d'équerre.
- Le même socle (`Polyhedron`, `relation()`) servira à ouvrir au biais les autres assemblages
  sans nouvelle décision d'architecture.
