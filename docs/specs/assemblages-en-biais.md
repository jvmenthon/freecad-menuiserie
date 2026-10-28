# Assemblages entre pièces en biais (angles composés compris)

- Issue : #114 (priorité moyenne)
- Statut : **proposée** ; jv a répondu à Q1 à Q5 (§ 9), reste Q6. Architecture seule : aucun code.
- Décisions de jv : traiter à part, **après** le jalon « pièce en bois » (#111, 2026-10-27) ;
  « Je veux pouvoir faire des assemblages de pièces avec 0 côté perpendiculaire »
  (2026-10-28) : **toute orientation** est acceptée, angles composés compris ;
  « Par défaut on prend une des faces en référence, sinon coupe la moitié de l'angle »
  (2026-10-28) : **référence du tenon** au choix (§ 4.8), analyse d'impact § 5.1.
- ADR : **[0024 — Assemblages entre pièces en biais : polyèdres convexes, angle quelconque](../adr/0024-assemblages-entre-pieces-en-biais.md)**
  (proposé) ; ADR liés 0006, 0014, 0016, 0019 (PR #86), 0020.
- Découpage : cinq PR, **AB-a → AB-b → (AB-c ∥ AB-d ∥ AB-e)** (§ 5), branche de jalon
  `jalon/assemblages-en-biais` partie de `main` **après la fusion de #111**.

**Vocabulaire.**

- *D'équerre* : rotation relative des deux pièces faite de quarts de tour (cas actuel).
- *En biais* : toute autre rotation, y compris quand aucune face de l'une n'est perpendiculaire
  à une face de l'autre (*angle composé* : pied de tabouret écarté dans deux directions).
- *Plan d'épaulement* : la face de l'hôte que rencontre le bout de l'invitée ; les épaulements
  de l'invitée y sont coupés.
- *Écart à l'équerre* α : angle entre l'axe de l'invitée (normale de sa face de contact) et la
  normale du plan d'épaulement. α = 0 : d'équerre.
- *Coupe composée* : bout coupé selon un plan incliné dans les deux sens ; il se règle par un
  **angle de coupe** (rotation de la table de la scie, biais vu de la face) et une
  **inclinaison de lame** (biais vu du chant). Un biais simple n'a que l'un des deux.
- *Référence du tenon* : la direction que suivent le tenon et la mortaise : l'axe de la pièce à
  tenon, la normale de la face de la pièce mortaisée, ou la bissectrice des deux (mi-angle).
- *Long point* : sur un bout coupé en biais, le point le plus éloigné de l'autre bout (la cote
  que le menuisier reporte avant de couper).

## 1. Contexte

`core/geometry.relative_transform` n'accepte que des rotations d'équerre ; `classify`
(`core/contact`), le choix des rôles (`guess_roles`) et toutes les stratégies passent par elle.
Depuis la recette du jalon pièce en bois (#112), le refus est propre (un seul message, pas de
trace) : « Les deux pièces doivent être d'équerre (angles multiples de 90°) ».

Ce qui existe déjà et sert ici :

- `RigidTransform` (rotation quelconque) et `moved`, qui change de repère un `Prism` pour toute
  rotation ; `Box` et `Cylinder` ne savent être que d'équerre.
- Pièce ramenée au contact dans le calcul seulement, sans toucher la brute : prolongée
  (ADR 0014, `guest_additions`) ou raccourcie (ADR 0016, `guest_trims`, retirés avant les ajouts
  dans `machined_shape`).
- Profil commun tenon / languette (`core/joints/_profile.py` : `ContactFrame`,
  `build_profile`, contrôles de matière et de parois) et ses règles de valeurs automatiques.
- Avertissement de matière manquante pour une pièce en bois (E3 du jalon #73), retournement
  automatique des rôles (`feasible_joint`), avertissement B7 pendant un glissement.

Un tenon dont l'épaulement est coupé selon un plan gauche n'est pas un prisme (ses arêtes n'ont
pas toutes la même longueur) : il faut un nouveau solide, le polyèdre convexe (ADR 0024).

## 2. Objectif

Deux exemples de référence :

1. **Biais simple** (issue) : caisson dont les côtés sont inclinés de 10°, étagères horizontales
   assemblées par tenon-mortaise.
2. **Angle composé** (demande de jv) : tabouret dont les pieds sont écartés de 8° vers l'avant
   et de 8° vers le côté ; ceinture horizontale assemblée aux pieds par tenon-mortaise. Aucune
   face de la ceinture n'est perpendiculaire à une face du pied.

L'utilisateur dessine ses pièces comme d'habitude (pièces d'équerre dans leur propre repère,
tournées par leur `Placement`, à la main ou par les boutons de rotation) et crée l'assemblage
comme aujourd'hui (sélection de deux pièces → « Tenon-mortaise »). Il obtient :

- une **mortaise oblique** qui suit l'axe de l'invitée ;
- des **épaulements coupés selon la face de l'hôte**, que l'invitée ait été dessinée pointe
  contre la face, hors tout (son bout entre dans l'hôte) ou à cheval ;
- un **tenon** droit dans le prolongement de l'invitée ;
- une **liste de débit** juste : longueur au long point, tenon en ajout, réglages de la coupe
  (angle de coupe, inclinaison de lame) ;
- dans un **ensemble**, des pièces en biais qui suivent les cotes par translation (Q4).

## 3. Critères d'acceptation

### AB-a — Polyèdre convexe, relation et contact en biais (`core/`, pur)

- **A1** `core/_polyhedron.py` : `Polyhedron` (boîte dans un repère quelconque, coupée par des
  demi-espaces), `clipped_box(box, frame, planes)`, `moved` pour toute rotation, `vertices()`,
  `faces()`, `volume()`. Polyèdre vide ou plus mince que `CONTACT_TOLERANCE_MM` : `None`
  (rien à usiner), jamais un solide dégénéré.
- **A2** `geometry.is_square(host, guest)` : même tolérance que `_square_axes`. Les fonctions
  actuelles ne changent pas.
- **A3** `contact.relation(host, guest)` renvoie `Contact | Overlap | Separated` (pièces
  d'équerre : exactement le résultat de `classify`) ou `ObliqueContact` (§ 4.3). Refus dédiés :
  écart trop grand (`TOO_OBLIQUE`, angle cité), bout qui rencontre une arête ou un coin de
  l'hôte au lieu d'une face (`EDGE_HIT`).
- **A4** Le contact en biais est reconnu que l'invitée soit dessinée pointe contre la face
  (coin ajouté), hors tout (coin retiré) ou à cheval (les deux). Pièces écartées : `SEPARATED`.
  Invitée qui traverse l'hôte, ou qui y entre par un chant : refus existant `OVERLAPPING`.
- **A5** `guess_roles` passe par `relation` : en biais, l'invitée est la pièce dont le bout
  rencontre une face de l'autre.
- **A6** Tests purs : volumes de boîtes coupées comparés aux formules (coin, biseau, double
  biseau) ; biais simples de 5°, 10°, 30°, 45°, 70° et 71° (refus) ; angles composés (8° / 8°,
  20° / 15°, torsion seule de 30° autour de l'axe de l'invitée) ; les trois façons de dessiner ;
  α sous la tolérance traité d'équerre.

### AB-b — Tenon-mortaise et rainure-languette en biais (`core/joints/`, `features/`)

- **B1** `core/joints/_oblique.py` : `ObliqueFrame` et `build_oblique_profile`, frères de
  `ContactFrame` et `build_profile` (§ 4.4) ; `MortiseTenonStrategy` et `TongueGrooveStrategy`
  choisissent le cadre selon `relation`. `_profile.py` n'est pas modifié.
- **B2** `features/solids.py` construit un `Polyhedron` (§ 4.5) ; `machined_shape` et
  `check_joint_material` l'acceptent comme les autres solides.
- **B3** Plans identiques au bit près pour toute paire d'équerre (tests de non-régression sur
  les plans actuels du Caisson et des tests existants).
- **B4** Continuité : pour α → 0 (1e-4°), le plan en biais égale le plan d'équerre à 1e-6 mm
  près (volumes et sommets).
- **B5** `JointPlan.guest_bevels` (nouveau champ, vide par défaut) : un `Bevel` par bout coupé
  en biais (face de l'invitée, normale du plan d'épaulement dans le repère de l'invitée, long
  point).
- **B6** Feuillure, mi-bois, queue d'aronde, onglet, tourillons : refus `SQUARE_ONLY`
  (« Cet assemblage demande des pièces d'équerre ; entre pièces en biais : tenon-mortaise ou
  rainure-languette. »).
- **B7** `core/furniture/_check.py` compare les relations par `relation()` : modifier un
  ensemble qui contient un assemblage en biais ne lève plus `NOT_SQUARE`.
- **B8** Panneau de l'assemblage : ligne en lecture seule « Biais : 10° » (biais simple) ou
  « Biais : 8° et 8° » (angle composé, angle de coupe et inclinaison) quand α > 0 ; rien
  d'équerre.
- **B9** Intégration FreeCAD : pièce usinée valide (un solide, `isValid`) et volume OCC égal au
  volume calculé par `core` (1e-6 relatif) pour les cas de A6, tenon borgne et débouchant,
  hôte pièce de bois et pièce en bois.

### AB-c — Liste de débit (`features/cutlist_parts.py`, `core/cutlist/`)

- **C1** Cotes finies d'une invitée à bout biais : longueur **au long point** (corps de la pièce,
  coins ajoutés compris, coins retirés exclus) ; le tenon reste un ajout (ADR 0006).
- **C2** Mention de la coupe sur la ligne et dans le PDF / CSV, par bout coupé (formulation
  selon Q3) : « Bout biais 10° » ou « Coupe composée 8° / lame 8° ».
- **C3** Deux pièces de mêmes cotes mais de coupes différentes ne sont pas regroupées.
- **C4** Hôte : inchangé (la mortaise est un enlèvement).

### AB-d — Ensembles (`core/furniture/`, `features/furniture*.py`) — selon Q4

- **D1** Un membre en biais suit **par translation** : son encombrement dans le repère de
  l'ensemble est lié comme un membre verrouillé (cotes fixes, ADR 0019 : jamais étiré),
  colonne « Suit » = « Déplacée (en biais) ».
- **D2** Il n'entre dans aucune rangée et ne bloque aucune épaisseur.
- **D3** Une modification qui défait un assemblage en biais (ceinture qui ne rencontre plus le
  pied) donne l'avertissement existant `JOINT_LOST`, sans refus.
- **D4** Recettes : caisson à côtés inclinés, largeur 600 → 800 ; tabouret, largeur 350 → 400 :
  pièces en biais déplacées, pièces d'équerre allongées, tenons recalculés.

### AB-e — Référence du tenon (`core/joints/`, `features/joints/`, `gui/task_panels/`)

- **E1** Nouveau paramètre `reference` (tenon-mortaise et rainure-languette) : **pièce à tenon**
  (défaut, Q6), **pièce mortaisée** ou **mi-angle** ; propriété `ObliqueReference`
  (`App::PropertyEnumeration`, groupe « Biais »).
- **E2** Sans effet entre pièces d'équerre (plans identiques au bit près, B3 inchangé).
- **E3** Pièce mortaisée : mortaise d'équerre à la face de l'hôte, tenon incliné de α par rapport
  au fil de l'invitée. Mi-angle : tenon et mortaise inclinés chacun de α / 2.
- **E4** La base du tenon sur le plan d'épaulement reste dans l'empreinte du bout de l'invitée
  (`OUTSIDE_CONTACT` étendu) ; avertissement « tenon à fil tranché » dans la vue rapport quand
  le tenon s'écarte du fil de plus de `GRAIN_WARNING_DEG` (20° proposé).
- **E5** Panneau : liste déroulante « Référence », visible seulement en biais ; changement
  appliqué en direct dans la vue 3D (règle de jv).
- **E6** Documents : `Version` des deux types d'assemblage 1 → 2, propriété ajoutée à sa valeur
  par défaut à la réouverture (aucun assemblage en biais n'existe avant ce jalon : aucune forme
  ne change).

## 4. Conception

### 4.1 Principe (ADR 0024)

Chaque solide d'un assemblage en biais est l'intersection d'une **boîte posée dans un repère
quelconque** et de **quelques demi-espaces** : le coin retiré (l'invitée au-delà du plan
d'épaulement), le coin ajouté (le prolongement de l'invitée jusqu'au plan), le tenon (une barre
de la section du tenon, entre le plan d'épaulement et son bout), la mortaise (la même barre,
plus le jeu de fond). Ces solides sont convexes : `core/` en calcule les sommets et les faces
en Python pur, ce qui garde les contrôles de matière, les valeurs effectives et les tests hors
de FreeCAD. Les deux pièces peuvent être tournées l'une par rapport à l'autre de façon
quelconque : aucun axe commun n'est supposé.

### 4.2 Design patterns retenus

- **Strategy** (inchangé) : chaque type garde sa stratégie ; seules deux d'entre elles savent
  le biais pour l'instant.
- **Cadre** (*Parameter Object*) : `ObliqueFrame` regroupe ce que `ContactFrame` regroupe
  aujourd'hui (normale, plans, passage de repère), plus α, le plan d'épaulement et les
  polyèdres de mise au contact. Les règles de valeurs (`_values` de chaque type) restent
  communes aux deux cadres.
- **Value objects** figés : `Plane`, `Polyhedron`, `ObliqueContact`, `Bevel`.

### 4.3 `core/_polyhedron.py`, `core/geometry.py`, `core/contact.py` (AB-a)

- `Plane(point, normal)` : demi-espace gardé du côté opposé à la normale.
  `Polyhedron(box, frame, planes)` : `box` dans le repère `frame` (`RigidTransform`
  quelconque), coupée par `planes` (exprimés dans le repère où vit le polyèdre). `moved`
  transforme `frame` et les plans. Les sommets et faces sont calculés par découpe successive
  des six faces de la boîte (Sutherland–Hodgman en 3D) ; pas de dépendance externe.
- `geometry.is_square` lit la rotation relative comme `_square_axes`, sans lever.
- `contact.relation()` : d'équerre → `classify`. En biais (`_oblique_contact`), dans le repère
  de l'invitée :
  - candidates : ses faces de contact possibles (bout ±X ; chant ±Y aussi pour la languette) ;
    pour chacune, la face de l'hôte qu'elle rencontre **réellement** (celle que traverse ou
    touche son bout, à l'intérieur de son contour), et non la plus proche en angle : jusqu'à
    70°, une face voisine peut être plus proche en angle (α = écart entre les normales) ;
  - distances signées des quatre coins de la face de l'invitée au plan de cette face de l'hôte :
    toutes > tolérance → `Separated` ;
  - le coin retiré (invitée au-delà du plan) doit rester dans l'hôte, sans atteindre sa face
    opposée, et entrer par la face choisie seulement : sinon `OVERLAPPING` ; un bout qui
    déborde de la face sur deux faces voisines de l'hôte → `EDGE_HIT` ;
  - α > `MAX_OBLIQUE_DEG` → `TOO_OBLIQUE`.
- `ObliqueContact` : face de l'invitée, face de l'hôte, α, plan d'épaulement et plan de la face
  opposée de l'hôte (repère de l'invitée), polyèdres retiré et ajouté, transformation exacte
  invitée → hôte (rotation non arrondie).
- Un seul point d'entrée pour les appelants qui doivent accepter le biais : `guess_roles`,
  `core/furniture/_check.py` et les deux stratégies passent par `relation()`.

### 4.4 Profil en biais (AB-b, `core/joints/_oblique.py`)

Dans le repère de l'invitée, *n* = normale de sa face de contact, plan d'épaulement P :

- **Section du tenon** mesurée perpendiculairement à *n* : épaisseur et largeur comme
  aujourd'hui (tiers de l'épaisseur, épaulements d'un sixième de la section de l'invitée),
  décalages compris, contrôlée contre la section de l'invitée (`OUTSIDE_CONTACT` inchangé).
- **Tenon** = barre de cette section le long de *n*, coupée par P côté invitée et par un bout
  d'équerre à *n*. Sa longueur se mesure sur l'axe du tenon, depuis le point où cet axe
  traverse P. Débouchant : la barre est coupée par la face opposée de l'hôte.
- **Longueur automatique** : `mm_round(2 · profondeur / (3 · cos α))`, profondeur = étendue de
  l'hôte perpendiculairement à P : même formule qu'aujourd'hui pour α = 0 (B4). À fort biais
  (jusqu'à 70°, le tenon fait alors près de deux fois la profondeur), elle est réduite au mm
  jusqu'à ce que le point le plus profond de la mortaise laisse une paroi ; une valeur saisie
  n'est jamais réduite (refus `TOO_DEEP`).
- **Mortaise** = la même barre, prolongée du jeu de fond le long de *n* et coupée par P décalé
  de `CUT_OVERRUN_MM` vers l'invitée (elle n'enlève que de la matière de l'hôte) ; exprimée dans
  le repère de l'hôte par `moved`.
- **Contrôles** dans le repère de l'hôte, sur les sommets de la mortaise : point le plus profond
  sous P ≤ profondeur (`TOO_DEEP`, sinon débouchant) ; une paroi de matière de chaque côté, sur
  les deux axes de l'hôte parallèles à P (`NO_WALL`), comme `_check_walls`.
- **Plan** : `host_cuts` = mortaise ; `guest_trims` = coin retiré ; `guest_additions` = coin
  ajouté + tenon ; `guest_bevels` = un `Bevel` pour le bout.
- **Languette** : même calcul ; la rainure filante (`ThroughGroove`) est la barre prolongée le
  long de la largeur de la languette et coupée par les faces de l'hôte (plus `CUT_OVERRUN_MM`) ;
  parois contrôlées seulement de part et d'autre de l'épaisseur.

Les paramètres et les propriétés ne changent pas : `TenonThickness`, `TenonWidth`,
`TenonLength`, décalages, `Through`, `MortiseClearance` gardent leur sens (mesurés
perpendiculairement à l'axe de l'invitée, longueur sur l'axe du tenon).

### 4.5 `features/` (AB-b)

- `features/solids.py` : `_polyhedron_shape` construit la boîte (`Part.makeBox` au repère
  `frame`) puis retire, pour chaque plan, une grande boîte posée sur ce plan du côté exclu
  (taille tirée de la diagonale de la boîte). Booléennes de faces planes : robustes et sans
  couture. Le résultat est contrôlé (`isValid`, un solide) comme les autres.
- `machined_shape` garde l'ordre retirés → ajouts → enlèvements, indispensable ici (le tenon
  occupe la place du coin retiré).
- `features/joints/base.py` : rien à changer pour le calcul (le plan arrive par la stratégie) ;
  le résumé du panneau reçoit les angles du biais par `resolve` (B8).
- `joint_material.check_joint_material` (E3) s'applique tel quel à une pièce en bois en biais.
- `gui/commands/joints.py` : `ordered_roles` et `feasible_joint` inchangés (ils passent par
  `guess_roles` et `plan_for`).

### 4.6 Liste de débit (AB-c)

`machined_extent` calcule aujourd'hui la longueur gardée par `_kept_box`, qui n'accepte que
des boîtes retirées. Il lit en plus les `guest_bevels` des assemblages dont la pièce est
l'invitée : la cote finie sur l'axe du bout est portée au **long point** ; la matière au-delà
(le tenon) reste un ajout. `core/cutlist` tire de la normale du plan d'épaulement
*m* = (mx, my, mz), dans le repère de l'invitée (bout ±X), les deux réglages de la scie :
angle de coupe = atan(|my| / |mx|), inclinaison de lame = atan(|mz| / √(mx² + my²)), arrondis
au dixième de degré. Ils servent à la mention C2 et à la clé de regroupement C3.

### 4.7 Ensembles (AB-d)

`square_spans` renvoie `None` pour un membre en biais (exclu de toute liaison, ADR 0019). AB-d
ajoute `oblique_spans` : l'**encombrement** du membre dans le repère de l'ensemble donne des
règles de position seulement (cotes constantes, comme une pièce verrouillée) ; il n'entre dans
aucune rangée. Le membre est déplacé par son `Placement` (rotation gardée). Les assemblages en
biais sont vérifiés après coup par `relation()` (B7, D3).

### 4.8 Référence du tenon (AB-e, réponse de jv du 2026-10-28)

Le plan d'épaulement reste toujours la face de l'hôte (sinon les épaulements bâillent) ; seule
la **direction** *d* du tenon et de la mortaise change. Avec *n* l'axe de l'invitée et *m* la
normale extérieure du plan d'épaulement (repère de l'invitée) :

| Référence | *d* | Tenon / fil de l'invitée | Mortaise / face de l'hôte | Usage |
|---|---|---|---|---|
| Pièce à tenon (défaut ★) | *n* | dans le fil | inclinée de α | tenon le plus solide, mortaise au ciseau ou défonceuse inclinée |
| Pièce mortaisée | −*m* | incliné de α | d'équerre | mortaiseuse, défonceuse droite |
| Mi-angle | (*n* − *m*) / ‖*n* − *m*‖ | incliné de α / 2 | inclinée de α / 2 | compromis : chaque pièce reçoit la moitié du biais |

Tout le reste du § 4.4 s'applique en remplaçant *n* par *d* : barre de la section du tenon
le long de *d*, section mesurée perpendiculairement à *d* (sa largeur orientée selon la
projection de la largeur de l'invitée), longueur sur l'axe du tenon depuis P,
longueur automatique `mm_round(2 · profondeur / (3 · cos β))` avec β l'angle entre *d* et −*m*
(β = α, 0 ou α / 2), donc toujours la formule d'équerre quand α tend vers 0. Le polyèdre
convexe accepte déjà une barre dans un repère quelconque : aucun nouveau solide.

### 4.9 Sécurité

Pas de nouvelle entrée utilisateur : angles et cotes viennent des `Placement` et des
propriétés existantes, déjà bornées. Les cas dégénérés sont arrêtés avant OCC : α borné (pas
de biais rasant, donc pas de coin infiniment long), polyèdres vides ou trop minces écartés
(A1), valeurs non finies refusées par `Vec3`/`Box`, nombre de plans par polyèdre borné (au plus
quatre). Aucun accès fichier, réseau ou `eval`.

### 4.10 Compatibilité avec les autres ateliers (ADR 0007)

Formes `Part` standard (boîtes et booléennes), aucun réglage global, noms dans notre espace.
Rien de neuf côté dépendances.

## 5. Découpage en PR et impact

| PR | Contenu | Dépend de | Taille estimée |
|---|---|---|---|
| **AB-a** | `Polyhedron`, `is_square`, `relation()`, contact en biais, `guess_roles` (A1 à A6) | #111 fusionnée | moyenne à grande |
| **AB-b** | profil en biais, deux stratégies, solide `Part`, `guest_bevels`, `SQUARE_ONLY`, `_check.py`, panneau (B1 à B9) | AB-a | grande |
| **AB-c** | liste de débit (C1 à C4) | AB-b | petite |
| **AB-d** | ensembles (D1 à D4), selon Q4 | AB-b, #86 / #98 fusionnées (∥ AB-c) | moyenne |
| **AB-e** | référence du tenon (E1 à E6) | AB-b (∥ AB-c, AB-d) | moyenne |

Aucun module d'équerre réécrit : `_profile.py`, `contact.classify`, `relative_transform` et les
cinq autres stratégies ne changent que par le message `SQUARE_ONLY`. La PR #111 fixe la façon
dont les refus s'affichent (`translated_errors`, un seul message) : les nouveaux messages en
profitent sans rien y changer.

### 5.1 Analyse d'impact de la référence du tenon (AB-e)

| Zone | Ce qui change | Effort |
|---|---|---|
| `core/joints/_base.py` | nouveau `ParamKind.CHOICE` (énumération validée comme les autres paramètres, message traduit) | petit |
| `core/joints/mortise_tenon.py`, `tongue_groove.py` | champ `reference` (défaut pièce à tenon) dans les paramètres | petit |
| `core/joints/_oblique.py` | direction *d* selon la référence, contrôle d'empreinte E4, angle du tenon au fil pour l'avertissement | moyen (le polyèdre fait déjà le travail) |
| `features/joints/` | propriété `ObliqueReference` sur deux types, conversion texte ↔ énumération dans `params_from` / `write_params`, `Version` 1 → 2 | petit |
| `features/schema.py` | réouverture d'une énumération à liste fixe (aujourd'hui seule la pièce de bois en a, avec sa propre fonction `restore_enumerations`) : aide commune extraite | petit à moyen |
| `gui/task_panels/joint_fields.py` | premier champ « liste déroulante » des panneaux d'assemblage (aujourd'hui cases et nombres seulement), masqué d'équerre | moyen |
| `api.py`, scripts | rien : les paramètres passent par l'objet valeur ; le nouveau mot-clé est facultatif | nul |
| Liste de débit, ensembles | rien : l'épaulement est toujours sur la face de l'hôte | nul |
| Documents existants | `Version` 2, propriété ajoutée à la réouverture, formes identiques | nul pour l'utilisateur |
| Tests | trois références × cas de A6 (purs), volumes OCC, case du panneau, recette tabouret | moyen |

Bilan : une PR de plus (AB-e, taille moyenne, environ 250 lignes de code et autant de tests),
en parallèle d'AB-c et d'AB-d ; rien à reprendre dans AB-a ni dans le polyèdre. Le seul
nouveau motif d'interface est la liste déroulante du panneau d'assemblage. Le seul risque
métier est le tenon à fil tranché (référence pièce mortaisée à fort biais), couvert par
l'avertissement E4.

## 6. Compatibilité des documents

Aucun type ajouté ; la propriété `ObliqueReference` porte la `Version` du tenon-mortaise et de
la rainure-languette à 2 (AB-e), les autres `Version` (pièces usinées, ensembles, listes de
débit) sont inchangées. Les documents actuels s'ouvrent sans migration et donnent les
mêmes formes (B3). Un document qui contient un assemblage en biais ouvert par une version
antérieure de l'atelier affiche le refus actuel « Les deux pièces doivent être d'équerre »
(pas de perte de données).

## 7. Risques

| Risque | Parade |
|---|---|
| Découpe de polyèdre fausse sur un cas limite (plan qui passe par un sommet, face confondue) | tests par volumes analytiques ; comparaison volume `core` / volume OCC en intégration (B9) ; tolérance de fusion des sommets |
| Coin très aigu à 70° (pointe de près de trois fois l'épaisseur) : épaulement fragile, booléenne OCC délicate | borne `MAX_OBLIQUE_DEG` = 70° (Q1), tests à la borne, `removeSplitter` déjà en place ; avertissement « épaulement très aigu » dans la vue rapport au-delà de 45° |
| Rotation « presque d'équerre » (89,9999°) prise en biais avec un coin de 1e-5 mm | tolérance `ANGLE_TOLERANCE` inchangée, `squared_rotation` des placements ; polyèdre plus mince que `CONTACT_TOLERANCE_MM` écarté (A1) |
| Bout qui tombe sur une arête de l'hôte (pied de section carrée, ceinture décalée) | refus `EDGE_HIT` explicite plutôt qu'un usinage faux |
| Ensemble modifié qui défait un assemblage en biais | avertissement `JOINT_LOST` (D3) ; la pièce usinée garde le refus de recalcul existant |
| Tenon à fil tranché (référence pièce mortaisée, biais fort) | avertissement E4 au-delà de `GRAIN_WARNING_DEG`, défaut pièce à tenon |
| Conflit avec #111 (`core/joints`, validation) et #98 (`core/furniture`) | AB-a part de `main` après #111 ; AB-d après #86 / #98 |

## 8. Hors périmètre (issues à ouvrir si jv le souhaite)

Le socle (`Polyhedron`, `relation()`) sert à tous ; chaque type s'ouvre ensuite au biais sans
nouvelle décision d'architecture :

- Tourillons en biais (`Cylinder` à axe quelconque, perçages suivant l'axe de l'invitée).
- Onglet à angle quelconque (cadre non rectangulaire, coupe à la bissectrice).
- Feuillure, mi-bois et queue d'aronde en biais.
- Accrochage, aimant et « Définir une distance » entre pièces en biais.

## 9. Questions pour jv

### Réponses de jv

- **2026-10-28** : angles composés inclus (« 0 côté perpendiculaire ») ; la restriction à une
  seule charnière de la première version est abandonnée.
- **Q2 — Sens de la mortaise (2026-10-28)** : « Par défaut on prend une des faces en
  référence, sinon coupe la moitié de l'angle » : référence au choix, pièce à tenon, pièce
  mortaisée ou mi-angle (§ 4.8, lot AB-e).

- **Q1 — Borne d'angle (2026-10-28)** : **70° au plus** (`MAX_OBLIQUE_DEG` = 70 ; au-delà,
  refus avec l'angle cité).
- **Q3, Q4, Q5 (2026-10-28)** : recommandations acceptées : « Bout biais 10° » / « Coupe
  composée 8° / lame 8° » ; un membre d'ensemble en biais suit par translation (AB-d) ;
  tenon-mortaise et rainure-languette dans le jalon.

### Question ouverte

- **Q6 — Référence par défaut.** ★ **pièce à tenon** (tenon dans le fil, le plus solide ; la
  mortaise prend le biais). Autre : pièce mortaisée (mortaise d'équerre, plus simple à la
  machine, tenon à fil tranché).
