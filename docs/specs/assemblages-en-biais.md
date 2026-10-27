# Assemblages entre pièces en biais (tenon-mortaise oblique…)

- Issue : #114 (priorité moyenne)
- Statut : **proposée**, en attente des réponses de jv (§ 9). Architecture seule : aucun code.
- Décision de jv (2026-10-27) : traiter à part, **après** le jalon « pièce en bois » (#111).
- ADR : **[0024 — Assemblages entre pièces en biais : une charnière, un calcul plan](../adr/0024-assemblages-entre-pieces-en-biais.md)**
  (proposé) ; ADR liés 0006, 0014, 0016, 0019 (PR #86), 0020.
- Découpage : quatre PR, **AB-a → AB-b → (AB-c ∥ AB-d)** (§ 5), branche de jalon
  `jalon/assemblages-en-biais` partie de `main` **après la fusion de #111**.

**Vocabulaire.**

- *D'équerre* : rotation relative des deux pièces faite de quarts de tour (cas actuel).
- *Charnière* : axe commun aux deux pièces autour duquel l'une est tournée (la profondeur d'un
  caisson à côtés inclinés, l'épaisseur d'un cadre trapézoïdal).
- *Écart à l'équerre* α : angle entre l'axe de l'invitée (normale de sa face de contact) et la
  normale de la face de l'hôte qu'elle rencontre. α = 0 : d'équerre. Un côté incliné de 10° sur
  la verticale reçoit une étagère horizontale avec α = 10°.
- *Plan d'épaulement* : la face de l'hôte touchée ; les épaulements de l'invitée y sont coupés.
- *Long point* : sur un bout coupé en biais, l'arête la plus éloignée de l'autre bout (la cote
  que le menuisier reporte avant de couper le biais).

## 1. Contexte

`core/geometry.relative_transform` n'accepte que des rotations d'équerre ; `classify`
(`core/contact`), le choix des rôles (`guess_roles`) et toutes les stratégies passent par elle.
Depuis la recette du jalon pièce en bois (#112), le refus est propre (un seul message, pas de
trace) : « Les deux pièces doivent être d'équerre (angles multiples de 90°) ».

Ce qui existe déjà et sert ici :

- `Prism` : polygone plan extrudé, orientation quelconque ; `moved` le change de repère pour
  toute rotation ; `features/solids.py` en fait un solide `Part` (queue d'aronde, onglet).
- Pièce ramenée au contact dans le calcul seulement, sans toucher la brute : prolongée
  (ADR 0014, `guest_additions`) ou raccourcie (ADR 0016, `guest_trims`, retirés avant les ajouts
  dans `machined_shape`).
- Profil commun tenon / languette (`core/joints/_profile.py` : `ContactFrame`,
  `build_profile`, contrôles de matière et de parois).
- Avertissement de matière manquante pour une pièce en bois (E3 du jalon #73), retournement
  automatique des rôles (`feasible_joint`), avertissement B7 pendant un glissement.

## 2. Objectif

Exemple de référence (issue) : caisson dont les deux côtés sont inclinés de 10°, étagères
horizontales assemblées par tenon-mortaise. L'utilisateur dessine ses pièces comme d'habitude
(pièces de bois d'équerre dans leur propre repère, côtés tournés de 10° autour de la profondeur)
et crée l'assemblage comme aujourd'hui (sélection de deux pièces → « Tenon-mortaise »). Il
obtient :

- une **mortaise oblique** dans le côté, qui suit l'axe de l'étagère ;
- des **épaulements coupés en biais** selon la face du côté, que l'étagère ait été dessinée
  pointe contre la face, ou hors tout (son bout entre dans le côté) ;
- un **tenon** droit dans le prolongement de l'étagère ;
- une **liste de débit** juste : longueur au long point, tenon en ajout, mention de la coupe
  biaise ;
- dans un **ensemble**, des côtés inclinés qui suivent la largeur par translation (Q4).

Les angles composés, les tourillons, l'onglet à angle quelconque et l'accrochage en biais sont
hors périmètre (§ 8).

## 3. Critères d'acceptation

### AB-a — Relation angulaire et contact en biais (`core/geometry.py`, `core/oblique.py`, pur)

- **A1** `angular_relation(host, guest)` renvoie `Square(axes)` (cas actuel, même tolérance),
  `Hinged(host_axis, guest_axis, angle)` ou `Compound`. Les fonctions actuelles ne changent pas.
- **A2** `relation(host, guest)` renvoie `Contact | Overlap | Separated` (inchangés pour des
  pièces d'équerre, même résultat que `classify`) ou `ObliqueContact` (§ 4.3) ; elle lève
  `JointError` avec un message dédié pour un angle composé (`COMPOUND_ANGLE`), une torsion
  (`TWISTED`) ou un écart trop grand (`TOO_OBLIQUE`, angle cité).
- **A3** Le contact en biais est reconnu que l'invitée soit dessinée pointe contre la face
  (coin ajouté), hors tout (coin retiré) ou à cheval (les deux). Pièces écartées : `SEPARATED`.
  Invitée qui traverse l'hôte, ou qui y entre par un chant : refus existant `OVERLAPPING`.
- **A4** `guess_roles` passe par `relation` : en biais, l'invitée est la pièce dont le bout
  rencontre la face de l'autre.
- **A5** Tests purs : α = 5°, 10°, 30°, 45°, 46° (refus) ; charnière selon la largeur et selon
  l'épaisseur de l'invitée ; les trois façons de dessiner ; torsion et angle composé refusés ;
  α inférieur à la tolérance traité d'équerre.

### AB-b — Tenon-mortaise et rainure-languette en biais (`core/joints/`, `features/joints/`)

- **B1** `core/joints/_oblique.py` : `ObliqueFrame` et `build_oblique_profile`, frères de
  `ContactFrame` et `build_profile` (§ 4.4) ; `MortiseTenonStrategy` et `TongueGrooveStrategy`
  choisissent le cadre selon `relation`. `_profile.py` n'est pas modifié.
- **B2** Tenon : charnière selon la largeur (biais dans l'épaisseur) ou selon l'épaisseur
  (biais dans la largeur). Languette : charnière le long de la rainure seulement.
- **B3** Plans identiques au bit près pour toute paire d'équerre (tests de non-régression sur
  les plans actuels du Caisson et des tests existants).
- **B4** Continuité : pour α → 0 (1e-4°), le plan en biais égale le plan d'équerre à 1e-6 mm.
- **B5** `JointPlan.guest_bevels` (nouveau champ, vide par défaut) décrit chaque bout coupé en
  biais : face de l'invitée, angle α, coordonnées du long point et du court point.
- **B6** Feuillure, mi-bois, queue d'aronde, onglet, tourillons : refus
  `SQUARE_ONLY` (« Cet assemblage demande des pièces d'équerre ; entre pièces en biais :
  tenon-mortaise ou rainure-languette. »).
- **B7** `core/furniture/_check.py` compare les relations par `relation()` : modifier un
  ensemble qui contient un assemblage en biais ne lève plus `NOT_SQUARE`.
- **B8** Panneau de l'assemblage : ligne en lecture seule « Biais : 10° » quand α > 0 (rien
  d'équerre) ; les valeurs effectives restent celles du tenon, mesurées perpendiculairement à
  l'axe de l'invitée.
- **B9** Intégration FreeCAD : pièce usinée valide (un solide, `isValid`) pour α ∈ {5, 10, 30,
  45}, les deux charnières, les trois façons de dessiner, tenon borgne et débouchant, hôte pièce
  de bois et pièce en bois.

### AB-c — Liste de débit (`features/cutlist_parts.py`, `core/cutlist/`)

- **C1** Cotes finies d'une invitée à bout biais : longueur **au long point** (corps de la pièce,
  coins ajoutés compris, coins retirés exclus) ; le tenon reste un ajout (ADR 0006).
- **C2** Mention de la coupe sur la ligne et dans le PDF / CSV : « Bout biais 10° » par bout
  coupé (formulation selon Q3).
- **C3** Deux pièces de même cotes mais de biais différents ne sont pas regroupées sur une
  même ligne.
- **C4** Hôte : inchangé (la mortaise est un enlèvement).

### AB-d — Ensembles (`core/furniture/`, `features/furniture*.py`) — selon Q4

- **D1** Un membre en biais autour d'un axe de l'ensemble suit **par translation** : son
  encombrement dans le repère de l'ensemble est lié comme un membre verrouillé (cotes fixes,
  ADR 0019 : jamais étiré), colonne « Suit » = « Déplacée (en biais) ».
- **D2** Il n'entre dans aucune rangée et ne bloque aucune épaisseur.
- **D3** Une modification qui défait un assemblage en biais (étagère qui ne rencontre plus le
  côté) donne l'avertissement existant `JOINT_LOST`, sans refus.
- **D4** Recette : caisson à côtés inclinés de 10°, largeur 600 → 800 : côtés déplacés,
  étagères allongées, tenons recalculés.

## 4. Conception

### 4.1 Principe (ADR 0024)

Une rotation autour d'**une** charnière commune ramène tout à un problème **plan** : dans le
plan perpendiculaire à la charnière (la *section*), l'hôte et l'invitée sont deux rectangles,
l'un tourné de α ; le long de la charnière, leur recouvrement est un intervalle, comme
aujourd'hui. Chaque solide du plan (coin retiré, coin ajouté, tenon, mortaise) est un polygone
de la section extrudé le long de la charnière : un `Prism`. Aucun nouveau type de solide,
aucune booléenne dans `core/`.

### 4.2 Design patterns retenus

- **Strategy** (inchangé) : chaque type garde sa stratégie ; seules deux d'entre elles
  savent le biais.
- **Cadre** (*Parameter Object*) : `ObliqueFrame` regroupe ce que `ContactFrame` regroupe
  aujourd'hui (normale, plans, axes, passage de repère), plus la charnière, α et les prismes
  de mise au contact. Les règles de valeurs (`_values` de chaque type) restent communes.
- **Value objects** figés : `Hinged`, `ObliqueContact`, `Bevel`.

### 4.3 `core/geometry.py` et `core/oblique.py` (AB-a)

- `geometry.angular_relation` lit la rotation relative `R` (invitée → hôte). D'équerre : comme
  `_square_axes`. Sinon, cherche les couples (axe i de l'invitée, axe j de l'hôte) tels que
  `R·eᵢ = ±eⱼ` à `ANGLE_TOLERANCE` près : un seul couple → `Hinged(j, i, θ)` ; aucun →
  `Compound`.
- `oblique.oblique_contact(host, guest, hinged)` travaille dans la section, en 2D :
  - repère la face de l'invitée qui rencontre l'hôte (bout ±X, ou chant ±Y pour la languette),
    et la face de l'hôte rencontrée (plan d'épaulement) ; α = écart entre leurs normales ;
  - distances signées des deux coins du bout de l'invitée au plan d'épaulement : toutes deux
    > tolérance → `Separated` ; un coin au-delà de la face opposée de l'hôte, ou un chant de
    l'invitée qui entre dans l'hôte hors du bout → `OVERLAPPING` ;
  - coin retiré = partie de l'invitée au-delà du plan ; coin ajouté = bande de l'invitée
    prolongée jusqu'au plan, moins l'invitée ; chacun est un polygone (triangle ou trapèze)
    extrudé sur l'étendue de l'invitée le long de la charnière ;
  - le rectangle de contact le long de la charnière est l'intersection des deux étendues.
- `ObliqueContact` : faces, charnière (axe de l'invitée et de l'hôte), α, plan d'épaulement
  (point, normale, repère de l'invitée), plan de la face opposée de l'hôte, prismes retiré et
  ajouté, intervalle de contact sur la charnière, transformation exacte invitée → hôte (rotation
  non arrondie : `RigidTransform`, sans passer par `relative_transform`).
- `contact.relation()` appelle `classify` si `angular_relation` est `Square`, sinon
  `oblique_contact` : un seul point d'entrée pour les appelants qui doivent accepter le biais
  (`guess_roles`, `core/furniture/_check.py`, les deux stratégies).

### 4.4 Profil en biais (AB-b, `core/joints/_oblique.py`)

Dans le repère de l'invitée, section ⟂ charnière (axes : normale de contact *n*, et l'axe
*s* de la section qui n'est pas *n*) :

- **Section du tenon** mesurée perpendiculairement à *n* : épaisseur et largeur comme
  aujourd'hui (tiers de l'épaisseur, épaulements d'un sixième), décalages compris, contrôlées
  contre la section de l'invitée (`OUTSIDE_CONTACT` inchangé) et, le long de la charnière,
  contre l'intervalle de contact.
- **Tenon** : polygone borné par le plan d'épaulement côté invitée et par un bout d'équerre à
  *n* ; sa longueur se mesure sur l'axe du tenon, depuis l'épaulement. Débouchant : le bout
  est coupé selon la face opposée de l'hôte.
- **Longueur automatique** : `mm_round(2 · profondeur / (3 · cos α))` (profondeur = étendue de
  l'hôte perpendiculairement à sa face) : même formule qu'aujourd'hui pour α = 0 (B4).
- **Mortaise** : le tenon prolongé du jeu de fond le long de *n*, et reculé de
  `CUT_OVERRUN_MM` hors de l'hôte côté épaulement (il n'enlève que de la matière de l'hôte) ;
  exprimée dans le repère de l'hôte par `moved`.
- **Contrôles** dans le repère de l'hôte, sur les sommets de la mortaise : point le plus
  profond ≤ profondeur de l'hôte (`TOO_DEEP`, sinon débouchant), parois de chaque côté sur
  l'axe de la section et sur la charnière (`NO_WALL`), comme `_check_walls`.
- **Plan** : `host_cuts` = mortaise ; `guest_trims` = coin retiré ; `guest_additions` = coin
  ajouté + tenon ; `guest_bevels` = un `Bevel` pour le bout.
- **Languette** : même calcul, *s* = épaisseur ; la rainure est prolongée sur toute l'étendue
  de l'hôte le long de la charnière quand `ThroughGroove` est vrai.

Les paramètres et les propriétés ne changent pas : `TenonThickness`, `TenonWidth`,
`TenonLength`, décalages, `Through`, `MortiseClearance` gardent leur sens (mesurés
perpendiculairement à l'axe de l'invitée, longueur sur l'axe du tenon).

### 4.5 `features/` (AB-b)

- `features/joints/base.py` : rien à changer pour le calcul (le plan arrive par la stratégie).
  Le résumé du panneau (`SUMMARY`) reçoit un champ `bevel_angle` de `resolve`, affiché
  seulement s'il est non nul.
- `features/solids.py` : rien (prismes déjà construits) ; `machined_shape` garde l'ordre
  retirés → ajouts → enlèvements, indispensable ici (le tenon occupe la place du coin retiré).
- `joint_material.check_joint_material` (E3) s'applique tel quel à une pièce en bois en biais.
- `gui/commands/joints.py` : `ordered_roles` et `feasible_joint` inchangés (ils passent par
  `guess_roles` et `plan_for`). Le message de refus d'un assemblage d'équerre seulement est
  `SQUARE_ONLY` (B6).

### 4.6 Liste de débit (AB-c)

`machined_extent` calcule aujourd'hui la longueur gardée par `_kept_box`, qui n'accepte que
des boîtes retirées. Il lit en plus les `guest_bevels` des assemblages dont la pièce est
l'invitée : la cote finie sur l'axe du bout est portée au **long point** (coins ajoutés compris,
coins retirés exclus) ; le reste de la matière au-delà (le tenon) reste un ajout. La ligne
porte la liste des biais (face, angle) pour la mention C2 et pour la clé de regroupement C3
(`core/cutlist`).

### 4.7 Ensembles (AB-d)

`square_spans` renvoie `None` pour un membre en biais (exclu de toute liaison, ADR 0019). AB-d
ajoute `hinged_spans` : pour un membre dont la rotation est une charnière selon un axe de
l'ensemble, son **encombrement** dans le repère de l'ensemble donne des règles de position
seulement (cotes constantes, comme une pièce verrouillée) ; il n'entre dans aucune rangée. Le
membre est déplacé par son `Placement` (rotation gardée). Les assemblages en biais sont
vérifiés après coup par `relation()` (B7, D3).

### 4.8 Sécurité

Pas de nouvelle entrée utilisateur : angles et cotes viennent des `Placement` et des
propriétés existantes, déjà bornées. Les cas dégénérés sont arrêtés avant OCC : α borné
(pas de biais rasant, donc pas de coin infiniment long), polygones contrôlés par
`check_prism` (`ValueError` sinon), valeurs non finies refusées par `Vec3`/`Box`. Aucun accès
fichier, réseau ou `eval`.

### 4.9 Compatibilité avec les autres ateliers (ADR 0007)

Formes `Part` standard (prismes extrudés, booléennes), aucun réglage global, noms dans notre
espace. Rien de neuf côté dépendances.

## 5. Découpage en PR et impact

| PR | Contenu | Dépend de | Taille estimée |
|---|---|---|---|
| **AB-a** | relation angulaire, contact en biais, `relation()`, `guess_roles` (A1 à A5) | #111 fusionnée | moyenne |
| **AB-b** | profil en biais, deux stratégies, `guest_bevels`, `SQUARE_ONLY`, `_check.py`, panneau (B1 à B9) | AB-a | grande |
| **AB-c** | liste de débit (C1 à C4) | AB-b | petite |
| **AB-d** | ensembles (D1 à D4), selon Q4 | AB-b, #86 / #98 fusionnées (∥ AB-c) | moyenne |

Aucun module d'équerre réécrit : `_profile.py`, `contact.classify`, `relative_transform` et les
cinq autres stratégies ne changent que par le message `SQUARE_ONLY`. La PR #111 fixe la façon
dont les refus s'affichent (`translated_errors`, un seul message) : les nouveaux messages en
profitent sans rien y changer.

## 6. Compatibilité des documents

Aucune propriété ni aucun type ajouté ; `Version` des assemblages, pièces usinées, ensembles
et listes de débit inchangées. Les documents actuels s'ouvrent sans migration et donnent les
mêmes formes (B3). Un document qui contient un assemblage en biais ouvert par une version
antérieure de l'atelier affiche le refus actuel « Les deux pièces doivent être d'équerre »
(pas de perte de données).

## 7. Risques

| Risque | Parade |
|---|---|
| Coin très aigu à 45° : épaulement fragile, booléenne OCC délicate | borne `MAX_OBLIQUE_DEG` (Q1), tests d'intégration à la borne, `removeSplitter` déjà en place |
| Rotation « presque d'équerre » (89,9999°) prise en biais avec un coin de 1e-5 mm | tolérance `ANGLE_TOLERANCE` inchangée, `squared_rotation` des placements ; coin plus fin que `CONTACT_TOLERANCE_MM` ignoré |
| Charnière vraie mais placements arrondis (angle saisi au degré, 1e-12 de bruit) | recherche de la charnière à `ANGLE_TOLERANCE`, pas à l'égalité exacte |
| Ensemble modifié qui défait un assemblage en biais | avertissement `JOINT_LOST` (D3) ; la pièce usinée garde le refus de recalcul existant |
| Conflit avec #111 (`core/joints`, validation) et #98 (`core/furniture`) | AB-a part de `main` après #111 ; AB-d après #86 / #98 |
| Utilisateur qui attend une mortaise d'équerre à la face (façon mortaiseuse) | hors périmètre, Q2 ; le choix de la spec suit l'issue |

## 8. Hors périmètre (issues à ouvrir si jv le souhaite)

- Angles composés (pied de chaise écarté dans deux directions).
- Torsion (invitée tournée autour de son propre axe).
- Tourillons en biais (cylindre à axe quelconque : `Cylinder` à généraliser).
- Onglet à angle quelconque (cadre non rectangulaire, coupe à la bissectrice).
- Feuillure, mi-bois et queue d'aronde en biais.
- Accrochage, aimant et « Définir une distance » entre pièces en biais.
- Mortaise d'équerre à la face de l'hôte avec tenon coudé (Q2, option b).

## 9. Questions pour jv

- **Q1 — Borne d'angle.** ★ Écart à l'équerre **jusqu'à 45°** compris (au-delà, refus avec
  l'angle cité). Autres choix : 30° (prudent, épaulement moins fragile) ou 60°.
- **Q2 — Sens de la mortaise.** ★ (a) **suit l'axe de l'invitée** (ce que dit l'issue : tenon
  droit, mortaise oblique taillée au ciseau ou à la défonceuse inclinée). (b) d'équerre à la
  face de l'hôte (mortaiseuse), tenon coudé : hors périmètre.
- **Q3 — Mention dans la liste de débit.** ★ « Bout biais 10° » (écart à l'équerre, l'angle
  qu'on règle sur la scie). Autre : « Bout à 80° » (angle entre le bout et le chant).
- **Q4 — Ensembles.** ★ (a) un membre en biais **suit par translation**, sans jamais être
  étiré (AB-d). (b) aucune liaison comme aujourd'hui (AB-d réduit à B7 : pas d'erreur) ; on
  repousse AB-d.
- **Q5 — Rainure-languette.** ★ **dans le jalon** (même code de profil que le tenon, coût
  faible). Autre : tenon-mortaise seul.
