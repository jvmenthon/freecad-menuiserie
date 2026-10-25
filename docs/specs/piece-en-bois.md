# Pièce en bois : convertir un corps Sketcher / PartDesign en pièce de menuiserie

- Issue : #73 (priorité haute)
- Statut : **proposée** (architecture fonctionnelle et technique). jv a répondu aux questions
  le 2026-10-25 (§ 9) : nom « Pièce en bois », esquisse fermée acceptée, volume à acheter,
  **assemblages, ensembles et cotes visibles inclus**. Reste Q3 (plusieurs solides), détaillée
  au § 9.
- Exigence de jv (2026-10-22) : « Pouvoir utiliser une pièce dessinée avec les outils FreeCAD
  (esquisse Sketcher, corps PartDesign) : **importer un corps** comme pièce de menuiserie, avec
  matériau, sens du fil, repère, et prise en compte dans la liste de débit (encombrement de la
  forme). »
- ADR liés : [0002 — Bibliothèque de matériaux](../adr/0002-bibliotheque-de-materiaux.md),
  [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0004 — Rendu des textures](../adr/0004-rendu-des-textures.md),
  [0005 — Mémoire du sens du fil](../adr/0005-memoire-du-sens-du-fil.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md) (complété),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](../adr/0008-ensemble-objet-de-cotes.md),
  [0011 — Aperçu, accrochage et nom](../adr/0011-apercu-accrochage-et-nom.md),
  [0013 — Liste de débit vivante](../adr/0013-liste-de-debit-vivante.md),
  [0019 — Rangées et épaisseurs fixes](../adr/0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (PR #86),
  **[0020 — La pièce en bois, enveloppe d'un corps FreeCAD](../adr/0020-piece-en-bois-enveloppe-d-un-corps.md)** (proposé)
- Découpage : six PR, **PD-a → PD-b → (PD-c ∥ PD-d) → (PD-e ∥ PD-f)** (§ 5)

**Vocabulaire.** Dans ce document, « pièce de bois » est l'objet paramétrique actuel (une boîte,
`WoodPart`) et « pièce en bois » le nouvel objet qui enveloppe un corps dessiné (`ShapedPart`,
nom choisi par jv). Le code les distingue par le prédicat `is_shaped_part` ; `is_timber` couvre
les deux.

## 1. Contexte

La pièce de bois de l'atelier (`WoodPart`) est un parallélépipède paramétrique (ADR 0003) ; les
assemblages y ajoutent tenons et mortaises (ADR 0006). Un pied galbé, une console chantournée,
un accoudoir, une traverse cintrée ne s'obtiennent pas ainsi : le menuisier les dessine avec
Sketcher puis PartDesign (protrusion, poche, congé, révolution…), outils qu'il connaît et que
l'atelier ne doit pas réinventer. Aujourd'hui ces corps n'ont ni matériau, ni fil, ni repère,
la liste de débit les ignore, et on ne peut ni les assembler ni les mettre dans un ensemble.

## 2. Objectif

Le menuisier peut :

1. **convertir** un corps PartDesign, une forme Part (extrusion, révolution, booléenne, import
   STEP) ou une **esquisse fermée** (avec une épaisseur) en **pièce en bois**, par une commande,
   sans que la forme d'origine soit modifiée ni copiée à la main ;
2. lui donner, comme à une pièce de bois, un **matériau** (couleur, texture), un **sens du fil**,
   un **repère** (le libellé suit le repère, J6b) et des **surcotes** ;
3. **continuer à modifier la forme** avec Sketcher / PartDesign : la pièce en bois, sa texture,
   ses cotes et la liste de débit suivent ;
4. la **déplacer et la tourner** comme une pièce de bois (Placement, accrochage, boutons de
   rotation) ;
5. lire ses **cotes d'encombrement** L × l × e dans l'éditeur de propriétés et s'en servir dans
   une expression ou un tableur (Q6) ;
6. retrouver la pièce dans la **liste de débit** avec les cotes de son **encombrement** (la plus
   petite planche dont on peut la tirer : volume et masse **à acheter**, Q4) ;
7. l'**assembler** (tenon-mortaise, rainure-languette, feuillure, tourillons, mi-bois, queue
   d'aronde, onglet) avec une pièce de bois ou une autre pièce en bois (Q5) ;
8. la mettre dans un **ensemble** : elle suit les déplacements de l'ensemble ; ses cotes, qui
   viennent du dessin, ne sont jamais changées par l'ensemble (Q5, § 4.6) ;
9. **défaire** la conversion (supprimer la pièce en bois) : la forme d'origine réapparaît
   intacte.

**Livrable visible** : le menuisier dessine un pied galbé (esquisse du profil, protrusion de
45 mm), le sélectionne, lance **Convertir en pièce en bois** : le pied prend la texture du chêne,
fil selon sa longueur ; il saisit le repère « P1 » ; il l'assemble par tenon-mortaise à une
traverse et l'ajoute au caisson ; la liste de débit affiche « P1 — chêne — 720 × 95 × 45 (forme) »
avec la longueur du tenon de la traverse. Il allonge la protrusion dans PartDesign : la pièce,
la mortaise et la ligne de débit suivent sans autre geste.

## 3. Critères d'acceptation

Légende comme dans les autres spécifications : **U** unitaire sans FreeCAD, **I** intégration
`freecadcmd` (1.0 et 1.1), **G** interface hors écran, **manuel** recette
`docs/recette/piece-en-bois-scenarios-manuels.md` (jv, FreeCAD 1.1.4 Windows).

### PD-a — Repère et encombrement d'une forme (`core/shaped/`)

| N° | Critère | Test |
|---|---|---|
| A1 | Objets valeur validés (`ValueError` citant le champ) : `Axes` (trois vecteurs unitaires orthogonaux directs, renormalisés à `ANGLE_TOLERANCE`), `ShapeSample` (points, faces planes `(normale, aire)`, arêtes droites `(direction, longueur)`, plafonds de taille § 4.9), `ShapeSignature`. | U |
| A2 | `principal_axes(sample)` : parmi des repères candidats (axes de la source, puis, pour chaque famille de faces planes parallèles, sa normale avec chacune des arêtes droites de ces faces), retient celui dont la **boîte englobante des points a le plus petit volume** ; à volume égal à 0,1 % près, ordre figé : axes de la source d'abord, puis aire plane décroissante. Résultat **déterministe** (indépendant de l'ordre des faces). | U |
| A3 | Les axes retenus sont ensuite **ordonnés** : X = plus grande étendue (longueur), Z = plus petite (épaisseur), Y = Z × X (repère direct). Exemples : plateau 800 × 400 × 22 tourné de 30° autour de Z → X le long des 800, Z normal au plateau ; pied tourné (révolution) → X sur l'axe de révolution ; pied galbé dessiné dans le plan XZ → Z = normale de l'esquisse. | U |
| A4 | `turned_axes(axes, turn)` : quarts de tour (boutons X / Y / Z de J6, Q1 de J6) qui changent quel axe de la forme est la longueur, la largeur, l'épaisseur ; 24 orientations atteintes, quatre quarts de tour reviennent au départ. | U |
| A5 | `core/` n'importe ni FreeCAD ni Qt ; couverture de `core/shaped/` ≥ 90 % ; aucun module > 400 lignes. | U |

### PD-b — L'objet pièce en bois (`features/shaped_part*.py`, `features/wood_material.py`, `api.py`)

| N° | Critère | Test |
|---|---|---|
| B1 | `api.make_shaped_part(source, material=None, mark="")` crée un `Part::FeaturePython` de proxy `ShapedPart` (type `Menuiserie::ShapedPart`), dans le **même conteneur** que la source, lié par `Source` ; la source n'est **jamais modifiée** (ni propriété, ni forme, ni placement, ni expression) ; elle est masquée (après la liaison, pour que l'annulation la réaffiche). | I |
| B2 | Sources acceptées : `PartDesign::Body` (forme de son `Tip`), toute fonction PartDesign (ramenée à son corps), tout `Part::Feature` (dont `Part::FeaturePython` d'un autre atelier) dont la forme est **un seul solide valide** ; `Sketcher::SketchObject` (ou `Part::Part2DObject`) **plan et fermé** : extrudé de `ProfileThickness` le long de sa normale (mode profil, Q2). Refus traduits, sans objet créé : plusieurs solides (Q3, en attente), forme vide ou invalide, esquisse ouverte ou non plane, objet de l'atelier (pièce de bois, pièce usinée, pièce en bois, ensemble), source déjà convertie, cote hors `[MIN_DIMENSION_MM, MAX_DIMENSION_MM]`. | I |
| B3 | **Forme** : `execute()` ne lit que `Source`, `SourceAxes` et `ProfileThickness` ; forme = solide de la source **dans son propre repère** (placement de la source défait), exprimé dans le repère de la pièce (origine au coin minimal de l'encombrement, X = L, Y = l, Z = e). La pièce occupe [0, L] × [0, l] × [0, e] dans son repère, comme une `WoodPart`. | I |
| B4 | **Placement libre** : le `Placement` de la pièce en bois est une donnée comme celui d'une `WoodPart` (jamais recalculé). À la conversion il est initialisé pour que la pièce soit **exactement à la place** de la source ; ensuite, déplacer ou tourner la pièce ne touche pas la source, et déplacer la source ne déplace pas la pièce. | I |
| B5 | **Cotes visibles (Q6)** : `Length`, `Width`, `Thickness` (`App::PropertyLength`, groupe « Dimensions », mêmes noms que `WoodPart`) = encombrement exact (`optimalBoundingBox` sans triangulation ni tolérance) dans le repère de la pièce, arrondi au centième ; **en lecture seule** dans l'éditeur, statut `Output` (leur écriture ne remet pas l'objet à recalculer), écrites par `execute()` (exception à la règle CONTRIBUTING, § 4.4). Une expression `P1.Length` dans un autre objet ou un tableur suit le dessin. Une expression posée **sur** ces cotes est refusée (message traduit). | I |
| B6 | **La forme suit** : modifier la protrusion, l'esquisse ou un congé du corps recalcule la pièce en bois et ses cotes dans le même recalcul ; `SourceAxes` est **gardé** (pas de nouveau calcul automatique, sauf commande « Repère automatique ») : une pièce allongée garde son fil et son repère. | I |
| B7 | Propriétés de matériau **identiques à `WoodPart`** (mêmes noms, types, groupes, énumérations, comportement de `onChanged`) : `Material`, `MaterialId`, `Category`, `Density`, `GrainDirection` (+ mémoire du fil, ADR 0005), `Mark`, `LengthAllowance`, `WidthAllowance`, `ThicknessAllowance`, `Version` = 1 ; libellé = repère (J6b) ; partagées par composition (§ 4.4), **sans aucun changement de `WoodPart`** (`Version` inchangée, documents existants ouverts sans migration). | I |
| B8 | Supprimer la pièce en bois réaffiche la source, sans l'avertissement « objets référencés » ; supprimer la source met la pièce en bois en erreur (message traduit), sans exception Python. | I |
| B9 | Contrat de persistance (ADR 0003 appliqué) : chemins figés `freecad.menuiserie.features.shaped_part.ShapedPart` et `freecad.menuiserie.gui.view_providers.shaped_part.ViewProviderShapedPart`, proxy sans état, réouverture (propriété absente, type inattendu, `Version` plus récente) testée comme pour `WoodPart`. Document ouvert **sans l'atelier** : la forme enregistrée s'affiche, la source existe et reste éditable. | I |
| B10 | Compatibilité (ADR 0007) : la forme d'une pièce en bois sert dans un `Part::Cut`, une vue TechDraw, un export STEP ; un `App::Link` vers elle est compté dans la liste de débit. | I |

### PD-c — Liste de débit (`features/cutlist_*.py`, `core/cutlist/`)

| N° | Critère | Test |
|---|---|---|
| C1 | La collecte lit les pièces en bois (nouveau lecteur dans la table du visiteur `cutlist_collect`), dans le document, la sélection, un conteneur ou par lien, et la liste vivante (ADR 0013) en dépend : modifier le corps la met à jour. | I |
| C2 | Cotes finies = encombrement (B5), cotes de débit = encombrement + surcotes + ajouts d'assemblage, **volume et masse = bois à acheter** (sur l'encombrement, Q4), épaisseur de brut standard (ADR 0015) comme pour une pièce de bois. | U, I |
| C3 | La ligne porte la mention « forme » (colonne « Remarque » de la feuille, du CSV et du PDF) ; la miniature montre le rectangle d'encombrement (le contour réel est hors périmètre, § 8). | U |
| C4 | **Regroupement** : deux pièces en bois sont regroupées (« 2 × ») seulement si, en plus de la clé actuelle (matériau, cotes, ajouts, surcotes, fil), leur **empreinte de forme** est la même (volume, aire et nombre de faces arrondis, dans le repère de la pièce) ; une pièce en bois n'est jamais regroupée avec une pièce de bois. | U, I |
| C5 | La numérotation des repères (`cutlist_marks`) traite les pièces en bois comme les pièces de bois. | I |

### PD-d — Commande, panneau, vue (`gui/`)

| N° | Critère | Test |
|---|---|---|
| D1 | Commande `Menuiserie_ShapedPart` « **Convertir en pièce en bois** » (barre et menu de l'atelier, icône générée par `tools/generer_icones.py`) : active si la sélection contient au moins une source acceptable ; une pièce en bois par source sélectionnée, **une seule transaction** ; les refus (B2) sont listés dans une boîte de refus (comme #45), les sources acceptées sont converties. | G |
| D2 | Le panneau s'ouvre après la conversion et au double-clic (arbre et vue 3D, ADR 0018) : **Identification** (repère), **Matériau** (filtre de type, matériau, fil), **Repère de la pièce** (trois boutons de quart de tour qui changent quel axe est la longueur, la largeur, l'épaisseur — la pièce ne bouge pas —, bouton « Repère automatique »), **Encombrement** (L × l × e en lecture seule, en direct), **Rotation** (boutons X / Y / Z de J6 : la pièce tourne sur place), **Surcotes**, **Épaisseur du profil** (mode profil seulement). Toute saisie s'affiche en direct (règle jv du 2026-10-22), « Annuler » revient à l'état d'avant. | G |
| D3 | Le repère de la pièce est montré dans la vue pendant l'édition (trièdre L / l / e et flèche du fil, nœud Coin propre au panneau, retiré à la fermeture). | G, manuel |
| D4 | Texture et couleur du matériau sur la forme (ADR 0004, projection dans le repère local : juste sur les faces planes parallèles au fil, étirée sur le bois de bout et les surfaces gauches, limite acceptée) ; propriété de vue `MaterialColor` comme `WoodPart`. | G, manuel |
| D5 | Dans l'arbre, la source apparaît **sous** la pièce en bois (`claimChildren`) et reste éditable par double-clic (PartDesign, Sketcher) ; un bouton « Modifier le dessin » du panneau ferme le panneau et ouvre l'édition de la fonction `Tip` du corps ou de l'esquisse. | G, manuel |
| D6 | Accrocher une nouvelle pièce de bois sur une face d'une pièce en bois (J6d) fonctionne sans changement ; une pièce en bois se pose elle-même par accrochage à sa conversion si des éléments étaient sélectionnés en plus de la source (même règle que J6d). | G, manuel |

### PD-e — Assemblages avec une pièce en bois (Q5 ; `features/joints/`, `features/machined_part.py`, `features/solids.py`)

| N° | Critère | Test |
|---|---|---|
| E1 | Les sept types d'assemblages acceptent une pièce en bois comme hôte ou invitée (`HostPart`, `GuestPart`), avec une pièce de bois ou une autre pièce en bois. Le plan d'usinage est calculé **comme aujourd'hui**, sur la boîte d'encombrement (cotes B5) au `Placement` de la pièce : aucune stratégie de `core/joints` ne change. | I |
| E2 | La pièce usinée d'une pièce en bois part de **sa forme réelle** (et non de la boîte) : forme = (forme dessinée − parties retirées ∪ ajouts) − enlèvements, dans le repère de la pièce. Les pièces de bois gardent exactement leur forme actuelle (tests de non-régression des formes usinées). | I |
| E3 | **Contrôle de la matière réelle** : pour chaque enlèvement (mortaise, rainure, logement) et chaque contact (épaulement de tenon), l'assemblage compare la matière enlevée sur la forme réelle et sur la boîte ; s'il en manque plus de 5 % (assemblage sur une face courbe, ou dans un vide de la forme), avertissement traduit citant l'assemblage et la pièce, **sans refus** (l'assemblage reste fait, le menuisier juge). | I |
| E4 | Pièce en bois assemblée : graphe sans cycle `source → pièce en bois → assemblage → pièce usinée` ; modifier le dessin recalcule l'assemblage et la pièce usinée dans le même recalcul. | I |
| E5 | La liste de débit compte les ajouts d'assemblage d'une pièce en bois (tenon) comme pour une pièce de bois (`machined_extent` inchangé : il lit déjà la forme usinée). | I |
| E6 | Commandes et panneaux d'assemblage : sélection d'une pièce en bois acceptée dans la vue et l'arbre ; aucune autre différence visible. | G, manuel |

### PD-f — Pièce en bois dans un ensemble (Q5 ; `features/furniture*.py`, `core/furniture`)

| N° | Critère | Test |
|---|---|---|
| F1 | `add_to_furniture` accepte une pièce en bois : elle suit l'ensemble **par son `Placement`** (règles de suivi de J4, expressions natives ADR 0009) ; ses trois cotes sont **toujours fixes** (comme une épaisseur fixe de l'ADR 0019) : une règle qui voudrait l'étirer la déplace à la place, avec un avertissement traduit (« cote dessinée : modifiez le dessin »). | I |
| F2 | Dans le panneau de l'ensemble, les options « non fixe » / étirement sont grisées pour une pièce en bois, avec une infobulle qui dit pourquoi. | G |
| F3 | Redimensionner l'ensemble (« profondeur du bureau ») déplace les pièces en bois comme les pièces de bois à distance fixe ; aucune expression n'est posée sur la source ni sur `Length` / `Width` / `Thickness` de la pièce en bois. | I |
| F4 | Une pièce en bois membre d'un ensemble et assemblée (PD-e) suit l'ensemble avec sa pièce usinée, comme une pièce de bois. | I |

## 4. Conception

### 4.1 Principe (ADR 0020)

La pièce en bois est un **nouvel objet qui enveloppe la forme d'un autre**, sans la posséder :
`ShapedPart` (`Part::FeaturePython`) lie sa `Source`, recopie son solide **dans son propre
repère** et porte les propriétés de menuiserie, avec **son propre `Placement`**, comme une pièce
de bois. Graphe de recalcul : `Sketch → Pad → Body → ShapedPart`, sans cycle ; aucun objet de
l'atelier n'écrit dans la source. C'est la même idée que la pièce usinée qui enveloppe sa brute
(ADR 0006), appliquée à une forme qui n'est pas la nôtre ; et le même schéma que les objets
intégrés `Part::Refine` ou `PartDesign::SubShapeBinder`.

**Pourquoi un `Placement` libre** (et non celui de la source) : c'est ce qui permet les
assemblages et les ensembles (Q5) sans toucher à la source. Un ensemble pose des expressions sur
le `Placement` de ses membres, l'accrochage et les boutons de rotation l'écrivent, la pièce
usinée le reporte sur sa brute : tous ces mécanismes marchent tels quels sur une pièce en bois,
alors qu'ils devraient sinon écrire dans le `Placement` d'un corps PartDesign (objet d'un autre
atelier, ADR 0007) ou d'un corps placé dans un `App::Part`. Contrepartie : le corps masqué reste
à sa place d'origine ; s'il est réaffiché ou ouvert en édition, il peut être ailleurs que la
pièce (§ 7).

Options rejetées (détail dans l'ADR) : `WoodPart` à forme facultative (casse le contrat de
l'ADR 0003, migration de tous les documents) ; propriétés ajoutées **sur le corps PartDesign**
(contraire à l'ADR 0007) ; copie figée de la forme (perd le suivi) ; lien `App::Link` (aucune
forme propre enregistrée, placement partagé avec la cible).

### 4.2 Design patterns retenus

| Pattern | Où | Pourquoi |
|---|---|---|
| **Adaptateur / enveloppe** | `ShapedPart` autour de la source | réutiliser une forme d'un autre atelier sans la modifier |
| **Composition** (fonctions partagées) | `features/wood_material.py` | mêmes propriétés et même `onChanged` de matériau pour `WoodPart` et `ShapedPart`, sans héritage ni duplication |
| **Stratégie** | `features/shaped_sources.py` : un lecteur par sorte de source (corps, forme Part, esquisse) | ajouter une sorte de source sans toucher au reste |
| **Méthode patron** (existant) | forme de base de la pièce usinée : boîte (`WoodPart`) ou forme dessinée (`ShapedPart`) | une seule fonction `machined_shape`, la base change |
| **Visiteur** (existant) | `cutlist_collect` | un lecteur de plus dans la table |
| **Objet valeur** | `Axes`, `ShapeSample`, `ShapeSignature` | testés sans FreeCAD |

### 4.3 `core/shaped/` (PD-a, Python pur)

- `_axes.py` : `Axes`, `principal_axes(sample)`, `ordered(axes, extents)`, `turned_axes`.
  L'enveloppe de volume minimal exacte (algorithme de O'Rourke) est inutilement coûteuse : les
  pièces de menuiserie ont presque toujours une face plane de référence (le parement, le plan de
  l'esquisse) et une arête droite ; les candidats tirés des faces planes suffisent, avec les axes
  de la source en premier pour rester d'équerre avec le dessin.
- `_sample.py` : `ShapeSample` = points (sommets et points de maillage grossier fournis par
  `features/`), faces planes et arêtes droites ; validation et plafonds (§ 4.9).
- `_signature.py` : `ShapeSignature(volume, area, faces)` arrondie, pour le regroupement (C4).
- `_material_check.py` : `missing_material_ratio(on_box, on_shape)` et seuil de 5 % (E3).
- Réutilise `core/geometry.py` (vecteurs, tolérances) et les constantes de `part_model`.

### 4.4 `features/` (PD-b)

- `shaped_part_schema.py` : propriétés propres — `Source` (`App::PropertyLink`, groupe
  « Forme », même portée que la source), `SourceAxes` (`App::PropertyRotation`, à confirmer en
  1.0 dans PD-b, sinon `App::PropertyPlacement` à origine nulle ; masquée : axes de la pièce
  dans le repère de la source), `ProfileThickness` (`App::PropertyLength`, mode profil, masquée
  sinon), `Length` / `Width` / `Thickness` (sortie, lecture seule, B5), `Version`.
- **Exception à « `execute()` ne fait que reconstruire `obj.Shape` »** (Q6) : `execute()` écrit
  aussi les trois cotes de sortie **de son propre objet**, avec le statut `Output` (FreeCAD ne
  remet pas l'objet à recalculer) et seulement si la valeur change. Aucune écriture dans un
  autre objet : la règle de fond (un objet n'écrit jamais dans un autre pendant le recalcul)
  est respectée. L'exception est inscrite dans l'ADR 0020 et dans CONTRIBUTING.
- `wood_material.py` (**nouveau, par extraction**) : les `PropertySpec` de matériau, fil, repère
  et surcotes de `wood_part_schema.py`, et les fonctions de synchronisation du matériau
  aujourd'hui dans `WoodPart.onChanged` (matériau → identifiant, catégorie, densité, fil
  mémorisé, surcotes) deviennent des fonctions qui prennent l'objet. `WoodPart` les appelle :
  **comportement et propriétés inchangés**, prouvés par la suite de tests actuelle. Cette
  extraction touche `wood_part.py`, modifié par la PR #86 (épaisseurs fixes) : **PD-b démarre
  après la fusion de #86** dans `main` (PD-a, purement `core/`, peut partir tout de suite).
- `shaped_sources.py` : stratégie par sorte de source (`Body.Shape`, `Feature.Shape`,
  `Part.Face(contours de l'esquisse).extrude(normale × épaisseur)`), placement de la source
  défait, refus de B2.
- `shaped_part.py` : proxy `ShapedPart` (`execute`, `onChanged`, `onDocumentRestored`,
  `onBeforeChangeLabel` comme `WoodPart`), `record_of` (rend un `PartRecord` : **la liste de
  débit ne voit pas la différence**), `signature_of`, `base_shape_of` (forme dans le repère de
  la pièce, pour la pièce usinée).
- `dimensions_of(obj)` et `record_of(obj)` deviennent valables pour les deux sortes de pièces
  (elles lisent `Length` / `Width` / `Thickness`, mêmes noms) ; prédicats `is_shaped_part` et
  `is_timber` (pièce de bois **ou** pièce en bois). Les **30 appels** actuels de `is_wood_part`
  (10 fichiers) sont revus un par un : `is_timber` là où une pièce en bois doit être acceptée
  (collecte, repères, assemblages, ensembles, sélection), `is_wood_part` gardé là où la boîte
  paramétrique est exigée (saisie des cotes, gabarit Caisson, aperçu de création J6c).
- `api.py` : `make_shaped_part`, `is_shaped_part`, `reset_shaped_axes` ; refus en
  `ValueError`/`TypeError` traduits, comme `make_wood_part`.

### 4.5 Assemblages (PD-e, complète l'ADR 0006)

- **Aucun changement de `core/joints`** : chaque stratégie calcule son plan d'usinage à partir
  des cotes et du `Placement` des deux pièces ; pour une pièce en bois, ce sont l'encombrement
  et son `Placement`. Les assemblages lisent toujours des pièces « brutes » (pièce de bois ou
  pièce en bois), jamais des pièces usinées : le graphe de l'ADR 0006 reste sans cycle.
- `MachinedPart.Base` accepte une pièce en bois ; `solids.machined_shape` reçoit la **forme de
  base** au lieu des cotes (boîte pour une pièce de bois, forme dessinée pour une pièce en bois).
  Contrat de persistance de `MachinedPart` inchangé (même propriété `Base`, même `Version`).
- **Limite assumée** : l'atelier place un tenon, une mortaise ou une rainure sur une face de la
  boîte d'encombrement. Sur une face plane de la pièce qui coïncide avec cette boîte (bout de
  pied, chant droit de traverse : le cas courant), c'est exact. Sur une face courbe ou en
  retrait, l'usinage est au mauvais endroit : le contrôle E3 l'annonce. Reconnaître les faces
  réelles (parement, chant, bout) d'une forme libre est hors périmètre (§ 8).

### 4.6 Ensembles (PD-f, complète l'ADR 0008)

- Une pièce en bois membre d'un ensemble n'a que son `Placement` piloté par l'ensemble ; ses
  trois cotes sont fixes, comme une épaisseur fixe de l'ADR 0019 (PR #86) : PD-f réutilise le
  mécanisme de cotes bloquées que #86 introduit (`core/furniture/_blocked.py`), d'où la
  dépendance à sa fusion.
- **Pourquoi pas d'étirement** : les cotes d'une pièce en bois viennent du dessin (une
  protrusion, une contrainte d'esquisse). Les piloter depuis l'ensemble voudrait poser des
  expressions dans les fonctions PartDesign du menuisier, donc modifier un objet d'un autre
  atelier (ADR 0007) et deviner quelle contrainte correspond à quelle cote. Le menuisier peut le
  faire lui-même par les expressions natives de FreeCAD (`Pad.Length = Bureau.Depth - 40`), ce
  que l'atelier n'empêche pas.

### 4.7 Liste de débit (PD-c)

- `cutlist_collect` : lecteur `_shaped` dans la table (une ligne), `is_source` étendu.
- `cutlist_parts.entry_of` accepte une pièce en bois : `record_of` + `rough_thicknesses` +
  ajouts d'assemblage (`machined_extent`) comme une brute.
- `core/cutlist` : `CutEntry` et `CutLine` reçoivent un champ facultatif
  `shape: ShapeSignature | None = None` (ajout en fin, valeur par défaut : aucune pièce actuelle
  ne change) ; `group_key` l'inclut ; la remarque « forme » vient de lui (CSV, HTML/PDF, feuille).

### 4.8 `gui/` (PD-d, PD-e, PD-f)

- `gui/commands/shaped_part.py`, `gui/task_panels/shaped_part.py` (réutilise les widgets du
  panneau de la pièce de bois : matériau, repère, surcotes, rotation),
  `gui/view_providers/shaped_part.py` (texture et couleur partagées avec `ViewProviderWoodPart`
  par les aides de `gui/textures.py` ; `claimChildren` = `[Source]` ; `onDelete` réaffiche la
  source ; `canDelete` comme #43).
- Double-clic vue 3D : la pièce en bois s'ajoute à la table de l'ADR 0018.
- Commandes d'assemblage et d'ensemble : filtres de sélection passés à `is_timber` ; panneau de
  l'ensemble : options grisées (F2).
- Icônes : `Menuiserie_ShapedPart.svg` et l'icône d'objet, ajoutées au script générateur.

### 4.9 Sécurité

Une forme peut venir d'un STEP hostile ou d'un document d'autrui : nombre de faces, d'arêtes et
de points lus pour le repère automatique plafonnés (par exemple 5 000 faces, 20 000 points,
maillage à tolérance bornée), au-delà le repère retombe sur les axes de la source avec un
avertissement ; temps borné, aucune boucle sur des données non bornées ; aucune évaluation de
texte (pas d'`eval` d'expression), aucun fichier lu. Le contrôle E3 (booléennes OCC) est fait
une fois par recalcul de l'assemblage, borné de même.

### 4.10 Compatibilité avec les autres ateliers (ADR 0007)

- La source n'est jamais modifiée ; seule sa **visibilité** change (masquée sous la pièce en
  bois) : deuxième exception à l'ADR 0007 § 3, après la brute sous sa pièce usinée, inscrite
  dans l'ADR 0020.
- La forme de la pièce en bois est un solide Part enregistré : TechDraw, Assembly, CAM, STEP,
  BIM l'utilisent ; sans l'atelier, le document s'ouvre avec la forme et la source intactes.
- Fonctionne avec un corps créé par n'importe quel atelier qui produit un `Part::Feature`
  (Part, PartDesign, Curves, Fasteners…) ; aucune dépendance à leur code.

## 5. Découpage en PR et impact

| PR | Contenu | Dépend de | Taille estimée |
|---|---|---|---|
| **PD-a** | `core/shaped/` (A1 à A5) | — | moyenne |
| **PD-b** | `wood_material.py` (extraction), `shaped_part*.py`, `shaped_sources.py`, `api.py`, revue des appels `is_wood_part` (B1 à B10) | PD-a, **#86 fusionnée** | grande |
| **PD-c** | liste de débit (C1 à C5) | PD-b | petite |
| **PD-d** | commande, panneau, ViewProvider, icônes, recette (D1 à D6) | PD-b (∥ PD-c) | moyenne |
| **PD-e** | assemblages (E1 à E6) | PD-b | moyenne |
| **PD-f** | ensembles (F1 à F4) | PD-b, #86 (∥ PD-e) | petite à moyenne |

Q5 et Q6 ajoutent deux PR (PD-e, PD-f) et une exception de règle (B5), sans toucher aux
stratégies d'assemblage ni au modèle de l'ensemble ; aucun document existant n'est migré.
Branche de jalon `jalon/piece-en-bois` depuis `main` ; sous-lots squashés sur CI verte ;
relecture complète et captures sur la PR finale vers `main` (règles du projet).

## 6. Compatibilité des documents

Aucun objet existant ne change : `WoodPart`, `MachinedPart`, assemblages, ensembles et listes
de débit gardent leur `Version` ; les documents actuels s'ouvrent sans migration et les formes
usinées actuelles sont identiques (E2). Le champ `shape` de `CutEntry` a une valeur par défaut.

## 7. Risques

| Risque | Parade |
|---|---|
| Repère automatique « faux » pour une forme libre (pièce sculptée) | boutons de quart de tour et ordre figé ; le repère choisi est gardé (B6) |
| Assemblage sur une face courbe placé sur la boîte d'encombrement | contrôle de matière réelle E3 avec avertissement ; recette manuelle dédiée |
| Corps masqué resté à sa place d'origine, loin de la pièce déplacée : surprise à l'édition | « Modifier le dessin » (D5) l'annonce ; l'édition PartDesign montre le corps à sa place ; à étudier en recette (option : recaler le placement du corps sur demande) |
| `optimalBoundingBox` lent sur une forme lourde | calcul seulement au recalcul de la pièce, plafonds § 4.9 |
| Corps PartDesign dans un `App::Part` (portée des liens) | pièce en bois créée dans le même conteneur (B1), test dédié |
| Conflit avec la PR #86 (`wood_part.py`, `core/furniture`) | PD-b et PD-f après sa fusion (§ 4.4, § 4.6) |
| Mode profil : esquisse avec des trous ou plusieurs contours | `Part.Face` de tous les contours fermés (trous gérés), plusieurs faces disjointes refusées (Q3) |
| Nom proche de « Pièce de bois » | commande « Convertir en pièce en bois », icône distincte ; à confirmer en recette |

## 8. Hors périmètre (issues à ouvrir si jv le souhaite)

- Reconnaître les faces réelles (parement, chant, bout) d'une forme libre pour placer un
  assemblage sur une face courbe.
- Étirer une pièce en bois depuis un ensemble en pilotant le dessin (expressions sur les
  fonctions PartDesign).
- Contour réel dans la miniature et le PDF de la liste de débit ; gabarit de traçage à
  l'échelle 1.
- Calepinage (placement des encombrements dans des planches du commerce).
- Conversion inverse (pièce de bois → corps PartDesign pour y dessiner un galbe).

## 9. Questions pour jv

### Réponses de jv (2026-10-25)

- **Q1 — Nom** : « Pièce en bois » (commande « Convertir en pièce en bois »).
- **Q2 — Esquisse seule** : oui, une esquisse fermée devient une pièce de l'épaisseur saisie.
- **Q4 — Volume** : le volume **à acheter** (encombrement) dans la liste de débit.
- **Q5 — Assemblages et ensembles** : inclus (PD-e, PD-f ; limites § 4.5 et § 4.6).
- **Q6 — Cotes visibles** : incluses (B5).

### Question restante

**Q3 — Une forme qui contient plusieurs solides.** Cas réels : un corps PartDesign où
l'option « Autoriser un composé » (FreeCAD 1.0) laisse deux protrusions qui ne se touchent pas ;
une fusion ou un composé Part de pièces séparées ; un fichier STEP d'un meuble entier importé
d'un autre logiciel. Trois choix :

1. ★ **Refus** avec le message « cette forme contient N solides : séparez-les (PartDesign,
   Part > Composé > Éclater) puis convertissez-les un par un ». Simple et sûr ; le STEP d'un
   meuble entier demande un éclatement préalable, que FreeCAD sait faire.
2. **Une pièce en bois par solide**, toutes liées à la même source par un numéro de solide.
   Pratique pour un STEP de meuble, mais fragile : quand le dessin change, OCC peut renuméroter
   les solides, et une pièce changerait alors de forme (et de matériau, de repère, d'assemblage)
   sans prévenir. Il faudrait reconnaître chaque solide par sa géométrie : une PR de plus.
3. **Une seule pièce pour tous les solides** : faux pour la liste de débit (un encombrement qui
   couvre plusieurs pièces séparées). Déconseillé.
