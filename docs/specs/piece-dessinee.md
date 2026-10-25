# Pièce dessinée : convertir un corps Sketcher / PartDesign en pièce de bois

- Issue : #73 (priorité haute)
- Statut : **proposée** (architecture fonctionnelle et technique ; questions pour jv au § 9,
  recommandations ★ appliquées en attendant ses réponses)
- Exigence de jv (2026-10-22) : « Pouvoir utiliser une pièce dessinée avec les outils FreeCAD
  (esquisse Sketcher, corps PartDesign) : **importer un corps** comme pièce de menuiserie, avec
  matériau, sens du fil, repère, et prise en compte dans la liste de débit (encombrement de la
  forme). »
- ADR liés : [0002 — Bibliothèque de matériaux](../adr/0002-bibliotheque-de-materiaux.md),
  [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0004 — Rendu des textures](../adr/0004-rendu-des-textures.md),
  [0005 — Mémoire du sens du fil](../adr/0005-memoire-du-sens-du-fil.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md),
  [0011 — Aperçu, accrochage et nom](../adr/0011-apercu-accrochage-et-nom.md),
  [0013 — Liste de débit vivante](../adr/0013-liste-de-debit-vivante.md),
  **[0020 — La pièce dessinée, enveloppe d'un corps FreeCAD](../adr/0020-piece-dessinee-enveloppe-d-un-corps.md)** (proposé)
- Découpage : quatre PR, **PD-a → (PD-b ∥ PD-c) → PD-d** (§ 5)

## 1. Contexte

La pièce de bois de l'atelier (`WoodPart`) est un parallélépipède paramétrique (ADR 0003) ; les
assemblages y ajoutent tenons et mortaises (ADR 0006). Un pied galbé, une console chantournée,
un accoudoir, une traverse cintrée ne s'obtiennent pas ainsi : le menuisier les dessine avec
Sketcher puis PartDesign (protrusion, poche, congé, révolution…), outils qu'il connaît et que
l'atelier ne doit pas réinventer. Aujourd'hui ces corps n'ont ni matériau, ni fil, ni repère, et
la liste de débit les ignore.

## 2. Objectif

Le menuisier peut :

1. **convertir** un corps PartDesign, une forme Part (extrusion, révolution, booléenne, import
   STEP) ou une **esquisse fermée** (avec une épaisseur) en **pièce dessinée** de l'atelier, par
   une commande, sans que la forme d'origine soit modifiée ni copiée à la main ;
2. lui donner, comme à une pièce de bois, un **matériau** (couleur, texture), un **sens du fil**,
   un **repère** (le libellé suit le repère, J6b) et des **surcotes** ;
3. **continuer à modifier la forme** avec Sketcher / PartDesign : la pièce dessinée, sa texture
   et la liste de débit suivent ;
4. retrouver la pièce dans la **liste de débit** (feuille vivante, CSV, PDF) avec les cotes de
   son **encombrement** dans son repère (la plus petite planche dont on peut la tirer), son
   matériau, son fil et sa masse ;
5. **défaire** la conversion (supprimer la pièce dessinée) : la forme d'origine réapparaît
   intacte.

**Livrable visible** : le menuisier dessine un pied galbé (esquisse du profil, protrusion de
45 mm), le sélectionne, lance **Pièce dessinée** : le pied prend la texture du chêne, fil selon
sa longueur ; il saisit le repère « P1 » ; la liste de débit affiche « P1 — chêne — 720 × 95 ×
45 (encombrement) ». Il allonge la protrusion dans PartDesign : la ligne passe à l'épaisseur
réelle sans autre geste.

## 3. Critères d'acceptation

Légende comme dans les autres spécifications : **U** unitaire sans FreeCAD, **I** intégration
`freecadcmd` (1.0 et 1.1), **G** interface hors écran, **manuel** recette
`docs/recette/piece-dessinee-scenarios-manuels.md` (jv, FreeCAD 1.1.4 Windows).

### PD-a — Repère et encombrement d'une forme (`core/shaped/`)

| N° | Critère | Test |
|---|---|---|
| A1 | Objets valeur validés (`ValueError` citant le champ) : `Axes` (trois vecteurs unitaires orthogonaux directs, renormalisés à `ANGLE_TOLERANCE`), `ShapeSample` (points, faces planes `(normale, aire)`, arêtes droites `(direction, longueur)`, plafonds de taille § 4.7). | U |
| A2 | `principal_axes(sample)` : parmi des repères candidats (axes de la source, puis, pour chaque famille de faces planes parallèles, sa normale avec chacune des arêtes droites de ces faces), retient celui dont la **boîte englobante des points a le plus petit volume** ; à volume égal à 0,1 % près, ordre figé : axes de la source d'abord, puis aire plane décroissante. Résultat **déterministe** (indépendant de l'ordre des faces). | U |
| A3 | Les axes retenus sont ensuite **ordonnés** : X = plus grande étendue (longueur), Z = plus petite (épaisseur), Y = Z × X (repère direct). Exemples : plateau 800 × 400 × 22 tourné de 30° autour de Z → X le long des 800, Z normal au plateau ; pied tourné (révolution) → X sur l'axe de révolution ; pied galbé dans le plan XZ de son esquisse → Z = normale de l'esquisse. | U |
| A4 | `turned_axes(axes, turn)` : permutations par quart de tour (boutons X / Y / Z de J6, Q1) ; 24 orientations atteintes, quatre quarts de tour reviennent au départ ; `ordered` (A3) réapplicable. | U |
| A5 | `core/` n'importe ni FreeCAD ni Qt ; couverture de `core/shaped/` ≥ 90 % ; aucun module > 400 lignes. | U |

### PD-b — L'objet pièce dessinée (`features/shaped_part*.py`, `api.py`)

| N° | Critère | Test |
|---|---|---|
| B1 | `api.make_shaped_part(source, material=None, mark="")` crée un `Part::FeaturePython` de proxy `ShapedPart` (type `Menuiserie::ShapedPart`), dans le **même conteneur** que la source, lié par `Source` ; la source n'est **jamais modifiée** (ni propriété, ni forme, ni expression) ; elle est masquée (après la liaison, pour que l'annulation la réaffiche). | I |
| B2 | Sources acceptées : `PartDesign::Body` (forme de son `Tip`), toute fonction PartDesign (ramenée à son corps), tout `Part::Feature` (dont `Part::FeaturePython` d'un autre atelier) dont la forme est **un seul solide valide** ; `Sketcher::SketchObject` (ou `Part::Part2DObject`) **plan et fermé** : extrudé de `ProfileThickness` le long de sa normale (mode profil, Q2 ★). Refus traduits, sans objet créé : plusieurs solides (Q3 ★), forme vide ou invalide, esquisse ouverte ou non plane, objet de l'atelier (pièce de bois, pièce usinée, pièce dessinée, ensemble), source déjà convertie, cote hors `[MIN_DIMENSION_MM, MAX_DIMENSION_MM]`. | I |
| B3 | `execute()` ne lit que `Source` (et `ProfileThickness`, `SourceAxes`) : forme = solide de la source exprimé dans le **repère de la pièce** (origine au coin minimal de l'encombrement, X = L, Y = l, Z = e), `Placement` = placement de la source × repère de la pièce. La pièce occupe donc [0, L] × [0, l] × [0, e] dans son repère, comme une `WoodPart` ; sa position dans l'espace est exactement celle de la source. | I |
| B4 | **Encombrement** `dimensions_of(shaped)` = boîte englobante **exacte** (`optimalBoundingBox` sans triangulation ni tolérance) de la forme dans son repère, arrondie au centième ; recalculée à la lecture, jamais stockée (CONTRIBUTING : `execute` n'écrit que `Shape`). | I |
| B5 | **La forme suit** : modifier la protrusion, l'esquisse ou un congé du corps recalcule la pièce dessinée dans le même recalcul ; `SourceAxes` (repère choisi) est **gardé** : une pièce allongée garde son fil et son repère (pas de nouveau calcul automatique, sauf commande « Repère automatique »). | I |
| B6 | Propriétés de matériau **identiques à `WoodPart`** (mêmes noms, types, groupes, énumérations, comportement de `onChanged`) : `Material`, `MaterialId`, `Category`, `Density`, `GrainDirection` (+ mémoire du fil, ADR 0005), `Mark`, `LengthAllowance`, `WidthAllowance`, `ThicknessAllowance`, `Version` = 1 ; libellé = repère (J6b) ; partagées par composition (§ 4.4), **sans aucun changement de `WoodPart`** (`Version` inchangée, documents existants ouverts sans migration). | I |
| B7 | Déplacer la pièce dessinée (Placement, Std Transform) reporte le déplacement sur la source, comme la pièce usinée sur sa brute ; source au `Placement` lié par une expression ou placée par une contrainte : refus explicite avec avertissement (règle N6 de J4). | I |
| B8 | Supprimer la pièce dessinée réaffiche la source, sans l'avertissement « objets référencés » ; supprimer la source met la pièce dessinée en erreur (message traduit), sans exception Python. | I |
| B9 | Contrat de persistance (ADR 0003 appliqué) : chemins figés `freecad.menuiserie.features.shaped_part.ShapedPart` et `freecad.menuiserie.gui.view_providers.shaped_part.ViewProviderShapedPart`, proxy sans état, réouverture (propriété absente, type inattendu, `Version` plus récente) testée comme pour `WoodPart`. Document ouvert **sans l'atelier** : la forme enregistrée s'affiche, la source aussi existe et reste éditable. | I |
| B10 | Compatibilité (ADR 0007) : la forme d'une pièce dessinée sert dans un `Part::Cut`, une vue TechDraw, un export STEP ; un `App::Link` vers elle est compté dans la liste de débit. | I |

### PD-c — Liste de débit (`features/cutlist_*.py`, `core/cutlist/`)

| N° | Critère | Test |
|---|---|---|
| C1 | La collecte lit les pièces dessinées (nouveau lecteur dans la table du visiteur `cutlist_collect`), dans le document, la sélection, un conteneur ou par lien, et la liste vivante (ADR 0013) en dépend : modifier le corps la met à jour. | I |
| C2 | Cotes finies = encombrement (B4), cotes de débit = encombrement + surcotes, masse et volume sur l'encombrement (bois acheté, Q4 ★), épaisseur de brut standard (ADR 0015) comme pour une pièce de bois. | U, I |
| C3 | La ligne porte la mention « forme » (colonne « Remarque » de la feuille, du CSV et du PDF) ; la miniature montre le rectangle d'encombrement (le contour réel est hors périmètre, § 8). | U |
| C4 | **Regroupement** : deux pièces dessinées sont regroupées (« 2 × ») seulement si, en plus de la clé actuelle (matériau, cotes, surcotes, fil), leur **empreinte de forme** est la même (volume, aire et nombre de faces arrondis, dans le repère de la pièce) ; une pièce dessinée n'est jamais regroupée avec une pièce de bois. | U, I |
| C5 | La numérotation des repères (`cutlist_marks`) traite les pièces dessinées comme les pièces de bois. | I |

### PD-d — Commande, panneau, vue (`gui/`)

| N° | Critère | Test |
|---|---|---|
| D1 | Commande `Menuiserie_ShapedPart` « Pièce dessinée » (barre et menu de l'atelier, icône générée par `tools/generer_icones.py`) : active si la sélection contient au moins une source acceptable ; une pièce dessinée par source sélectionnée, **une seule transaction** « Convertir en pièce dessinée » ; les refus (B2) sont listés dans une boîte de refus (comme #45), les sources acceptées sont converties. | G |
| D2 | Le panneau s'ouvre après la conversion et au double-clic (arbre et vue 3D, ADR 0018) : **Identification** (repère), **Matériau** (filtre de type, matériau, fil), **Repère de la pièce** (trois boutons de quart de tour X / Y / Z qui changent quel axe est la longueur, la largeur, l'épaisseur — la pièce ne bouge pas —, bouton « Repère automatique »), **Encombrement** (L × l × e en lecture seule, mis à jour en direct), **Surcotes**, **Épaisseur du profil** (mode profil seulement). Toute saisie s'affiche en direct (règle jv du 2026-10-22), « Annuler » revient à l'état d'avant. | G |
| D3 | Le repère de la pièce est montré dans la vue pendant l'édition (trièdre L / l / e et flèche du fil, nœud Coin propre au panneau, retiré à la fermeture). | G, manuel |
| D4 | Texture et couleur du matériau sur la forme (ADR 0004, projection dans le repère local : juste sur les faces planes parallèles au fil, étirée sur le bois de bout et les surfaces gauches, limite acceptée) ; propriété de vue `MaterialColor` comme `WoodPart`. | G, manuel |
| D5 | Dans l'arbre, la source apparaît **sous** la pièce dessinée (`claimChildren`) et reste éditable par double-clic (PartDesign, Sketcher) ; un bouton « Modifier la forme » du panneau ferme le panneau et ouvre l'édition du corps (fonction `Tip`) ou de l'esquisse. | G, manuel |
| D6 | Accrocher une nouvelle pièce de bois sur une face d'une pièce dessinée (J6d) fonctionne sans changement (c'est un objet Part ordinaire). | manuel |

## 4. Conception

### 4.1 Principe (ADR 0020)

La pièce dessinée est un **nouvel objet qui enveloppe la forme d'un autre**, sans la posséder :
`ShapedPart` (`Part::FeaturePython`) lie sa `Source`, recopie son solide dans son propre repère et
porte les propriétés de menuiserie. Graphe de recalcul : `Sketch → Pad → Body → ShapedPart`, sans
cycle, en une passe ; aucun objet de l'atelier n'écrit dans la source. C'est la même idée que la
pièce usinée qui enveloppe sa brute (ADR 0006), appliquée à une forme qui n'est pas la nôtre ;
et le même schéma que les objets intégrés `Part::Refine` ou `PartDesign::SubShapeBinder`.

Options rejetées (détail dans l'ADR) : faire de `WoodPart` une boîte **ou** une forme (casse le
contrat de l'ADR 0003, migration de tous les documents) ; ajouter nos propriétés **sur le corps
PartDesign** lui-même (modifie l'objet d'un autre atelier, données sans proxy ni `Version`,
contraire à l'ADR 0007) ; copie figée de la forme (`Part::Feature` simple, perd le suivi) ;
lien `App::Link` avec extension (`claimChildren`, sélection et placement plus fragiles, aucune
forme propre enregistrée).

### 4.2 Design patterns retenus

| Pattern | Où | Pourquoi |
|---|---|---|
| **Adaptateur / enveloppe** | `ShapedPart` autour de la source | réutiliser une forme d'un autre atelier sans la modifier |
| **Composition** (mixin d'aides partagées) | `features/wood_material.py` | mêmes propriétés et même `onChanged` de matériau pour `WoodPart` et `ShapedPart`, sans héritage ni duplication |
| **Stratégie** | `core/shaped/` : un lecteur par sorte de source (corps, forme Part, esquisse) | ajouter une sorte de source sans toucher au reste |
| **Visiteur** (existant) | `cutlist_collect` | un lecteur de plus dans la table |
| **Objet valeur** | `Axes`, `ShapeSample`, `ShapeSignature` | testés sans FreeCAD |

### 4.3 `core/shaped/` (PD-a, Python pur)

- `_axes.py` : `Axes`, `principal_axes(sample)`, `ordered(axes, extents)`, `turned_axes`.
  L'enveloppe de volume minimal exacte (algorithme de O'Rourke) est inutilement coûteuse : les
  pièces de menuiserie ont presque toujours une face plane de référence (le parement, le plan de
  l'esquisse) et une arête droite ; les candidats tirés des faces planes suffisent, avec les axes
  de la source en premier pour rester d'équerre avec le dessin.
- `_sample.py` : `ShapeSample` = points (sommets et points de maillage grossier fournis par
  `features/`), faces planes et arêtes droites ; validation et plafonds (§ 4.7).
- `_signature.py` : `ShapeSignature(volume, area, faces)` arrondie, pour le regroupement (C4).
- Réutilise `core/geometry.py` (vecteurs, tolérances) et les constantes de `part_model`.

### 4.4 `features/` (PD-b)

- `shaped_part_schema.py` : propriétés propres — `Source` (`App::PropertyLink`, groupe
  « Forme », même portée que la source), `SourceAxes` (`App::PropertyRotation`, à confirmer en 1.0 dans PD-b, sinon `App::PropertyPlacement` à origine nulle ; masquée : axes
  de la pièce dans le repère de la source), `ProfileThickness` (`App::PropertyLength`, mode
  profil, masquée sinon), `Version`.
- `wood_material.py` (**nouveau, par extraction**) : les `PropertySpec` de matériau, fil, repère
  et surcotes de `wood_part_schema.py`, et les fonctions de synchronisation du matériau
  aujourd'hui dans `WoodPart.onChanged` (matériau → identifiant, catégorie, densité, fil
  mémorisé, surcotes) deviennent des fonctions qui prennent l'objet. `WoodPart` les appelle :
  **comportement et propriétés inchangés**, prouvés par la suite de tests actuelle. Cette
  extraction touche `wood_part.py`, modifié par la PR #86 (épaisseurs fixes) : **PD-b démarre
  après la fusion de #86** dans `main` (PD-a, purement `core/`, peut partir tout de suite).
- `shaped_part.py` : proxy `ShapedPart` (`execute`, `onChanged`, `onDocumentRestored`,
  `onBeforeChangeLabel` comme `WoodPart`), `_source_solid(obj)` (stratégie par sorte de source :
  `Body.Shape`, `Feature.Shape`, `Part.Face(sketch.Shape).extrude(normale × épaisseur)`),
  `dimensions_of`, `record_of` (rend un `PartRecord` : **la liste de débit ne voit pas la
  différence**), `signature_of`, report du déplacement (même code que
  `MachinedPart._follow_placement`, mis en commun dans `features/placement.py`).
- Prédicat `is_timber(obj)` (pièce de bois **ou** pièce dessinée) pour les seuls usages qui
  doivent accepter les deux : collecte, numérotation des repères, apparence, commandes de
  matériau. `is_wood_part` garde son sens strict : assemblages et ensembles refusent une pièce
  dessinée avec un message clair (Q5 ★).
- `api.py` : `make_shaped_part`, `is_shaped_part`, `reset_shaped_axes` ; refus en
  `ValueError`/`TypeError` traduits, comme `make_wood_part`.

### 4.5 Liste de débit (PD-c)

- `cutlist_collect` : lecteur `_shaped` dans la table (une ligne), `is_source` étendu.
- `cutlist_parts.entry_of` accepte une pièce dessinée : `record_of` + `rough_thicknesses` comme
  une brute ; pas d'ajouts (la forme est déjà finie).
- `core/cutlist` : `CutEntry` et `CutLine` reçoivent un champ facultatif
  `shape: ShapeSignature | None = None` (ajout en fin, valeur par défaut : aucune pièce actuelle
  ne change) ; `group_key` l'inclut ; la remarque « forme » vient de lui (CSV, HTML/PDF, feuille).

### 4.6 `gui/` (PD-d)

- `gui/commands/shaped_part.py`, `gui/task_panels/shaped_part.py` (réutilise les widgets du
  panneau de la pièce de bois : matériau, repère, surcotes, boutons de rotation),
  `gui/view_providers/shaped_part.py` (texture et couleur partagées avec `ViewProviderWoodPart`
  par les aides de `gui/textures.py` ; `claimChildren` = `[Source]` ; `onDelete` réaffiche la
  source ; `canDelete` comme #43).
- Double-clic vue 3D : la pièce dessinée s'ajoute à la table de l'ADR 0018.
- Icônes : `Menuiserie_ShapedPart.svg` et l'icône d'objet, ajoutées au script générateur.

### 4.7 Sécurité

Une forme peut venir d'un STEP hostile ou d'un document d'autrui : nombre de faces, d'arêtes et
de points lus pour le repère automatique plafonnés (par exemple 5 000 faces, 20 000 points,
maillage à tolérance bornée), au-delà le repère retombe sur les axes de la source avec un
avertissement ; temps borné, aucune boucle sur des données non bornées ; aucune évaluation de
texte (pas d'`eval` d'expression), aucun fichier lu.

### 4.8 Compatibilité avec les autres ateliers (ADR 0007)

- La source n'est jamais modifiée ; seule sa **visibilité** change (masquée sous la pièce
  dessinée) : deuxième exception à l'ADR 0007 § 3, après la brute sous sa pièce usinée,
  inscrite dans l'ADR 0020.
- La forme de la pièce dessinée est un solide Part enregistré : TechDraw, Assembly, CAM, STEP,
  BIM l'utilisent ; sans l'atelier, le document s'ouvre avec la forme et la source intactes.
- Fonctionne avec un corps créé par n'importe quel atelier qui produit un `Part::Feature`
  (Part, PartDesign, Curves, Fasteners…) ; aucune dépendance à leur code.

## 5. Découpage en PR

| PR | Contenu | Dépend de |
|---|---|---|
| **PD-a** | `core/shaped/` (A1 à A5) | — |
| **PD-b** | `features/wood_material.py` (extraction), `shaped_part*.py`, `api.py` (B1 à B10) | PD-a, **#86 fusionnée** |
| **PD-c** | liste de débit (C1 à C5) | PD-b |
| **PD-d** | commande, panneau, ViewProvider, icônes, recette (D1 à D6) | PD-b (∥ PD-c) |

Branche de jalon `jalon/piece-dessinee` depuis `main` ; sous-lots squashés sur CI verte ;
relecture complète et captures sur la PR finale vers `main` (règles du projet).

## 6. Compatibilité des documents

Aucun objet existant ne change : `WoodPart`, `MachinedPart`, assemblages, ensembles et listes
de débit gardent leur `Version` ; les documents actuels s'ouvrent sans migration. Le champ
`shape` de `CutEntry` a une valeur par défaut.

## 7. Risques

| Risque | Parade |
|---|---|
| Repère automatique « faux » pour une forme libre (pièce sculptée) | boutons de quart de tour et ordre figé ; le repère choisi est gardé (B5) |
| `optimalBoundingBox` lent sur une forme lourde | calcul seulement à la lecture (collecte, panneau), mis en cache par la liste vivante |
| Corps PartDesign dans un `App::Part` (portée des liens) | pièce dessinée créée dans le même conteneur (B1), test dédié |
| Conflit avec la PR #86 sur `wood_part.py` | PD-b après sa fusion (§ 4.4) |
| Mode profil : esquisse avec des trous ou plusieurs contours | `Part.Face` de tous les contours fermés (trous gérés), plusieurs faces disjointes refusées (Q3) |

## 8. Hors périmètre (issues à ouvrir si jv le souhaite)

- Assemblages (tenon, mortaise, tourillons…) sur une pièce dessinée, et pièce dessinée membre
  d'un ensemble (Q5).
- Contour réel dans la miniature et le PDF de la liste de débit ; gabarit de traçage à
  l'échelle 1.
- Calepinage (placement des encombrements dans des planches du commerce).
- Conversion inverse (pièce de bois → corps PartDesign pour y dessiner un galbe).

## 9. Questions pour jv

1. **Q1 — Nom** : « Pièce dessinée » pour l'objet et la commande ? ★ oui (autres idées : « Pièce
   de forme », « Corps en bois »).
2. **Q2 — Esquisse seule** : une esquisse fermée sélectionnée devient une pièce de l'épaisseur
   saisie (mode profil) ? ★ oui, c'est le cas le plus courant (console, pied chantourné) ; sinon
   il faudrait d'abord faire une protrusion PartDesign.
3. **Q3 — Plusieurs solides** dans une même forme (corps PartDesign multi-solides, composé
   Part) : ★ refus avec message « convertissez-les un par un » ; autre choix : une pièce
   dessinée par solide.
4. **Q4 — Masse et volume** dans la liste de débit : ★ sur l'encombrement (le bois acheté), comme
   les cotes ; autre choix : volume réel de la forme pour la masse finie.
5. **Q5 — Assemblages et ensembles** : ★ hors de ce lot (refus clair), à traiter ensuite si
   besoin ; autre choix : les inclure maintenant (gros travail : une forme quelconque n'a pas de
   faces « parement / chant / bout » sûres).
6. **Q6 — Cotes visibles** : l'encombrement L × l × e doit-il aussi apparaître dans l'éditeur de
   propriétés (utilisable dans une expression, un tableur) ? ★ non pour l'instant (panneau et
   liste de débit seulement : `execute` n'écrit que la forme) ; sinon trois propriétés en lecture
   seule écrites au recalcul, exception à documenter.
