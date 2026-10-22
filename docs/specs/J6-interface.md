# [J6] Amélioration de l'interface : aperçu, accrochage à la sélection, rotation, nom = repère

- Jalon : J6 (issue #37), à faire après J4 ; version cible à confirmer par jv
- Statut : **proposée** (en attente des réponses de jv aux questions du § 9 ; en attendant, la
  spécification applique les recommandations ★)
- Exigences de jv (mot pour mot, 2026-10-21) : « lorsque je fais une nouvelle piece de bois une
  prévisualisation apparait; si une ou plusieurs face; point; ligne est selectionnée la nouvelle
  piece doit toucher celle-ci; ajoute un bouton rotation » ; puis : « la pièce doit porter le même
  nom que son repère » (libellé de l'objet = repère, mis à jour quand le repère change)
- ADR liés : [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0004 — Rendu des textures](../adr/0004-rendu-des-textures.md),
  [0005 — Mémoire du sens du fil](../adr/0005-memoire-du-sens-du-fil.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](../adr/0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi par expressions natives](../adr/0009-suivi-par-expressions-natives.md),
  **[0011 — Aperçu, accrochage ponctuel et nom = repère](../adr/0011-apercu-accrochage-et-nom.md)** (proposé)
- Découpage : quatre PR, **(J6a ∥ J6b) → J6c → J6d** (§ 5)

## 1. Contexte

Aujourd'hui, la commande **Pièce de bois** crée une pièce de 800 × 200 × 22 mm **à l'origine du
document**, axes alignés sur X, Y, Z, puis ouvre son panneau. La pièce est déjà un vrai objet,
recalculé à chaque saisie, dans la transaction « Créer une pièce de bois » (« Annuler » la fait
disparaître) ; mais rien ne la distingue d'une pièce validée, elle est souvent loin de l'endroit où
le menuisier travaille, et il doit ensuite la déplacer et la tourner avec les outils de FreeCAD
(Placement, Std Transform), en calculant lui-même les coordonnées pour qu'elle touche les autres
pièces. Enfin, l'arborescence affiche « Pièce de bois », « Pièce de bois001 »… alors que le
menuisier nomme ses pièces par leur **repère** (`Mark` : « M1 », « Joue gauche »), qui n'apparaît
que dans l'éditeur de propriétés.

## 2. Objectif

Le menuisier peut :

1. **voir la nouvelle pièce en aperçu** (semi-transparente) pendant qu'il la règle dans le
   panneau : elle suit chaque saisie (cotes, matériau, rotation) ; « OK » la rend définitive en
   une seule entrée d'annulation, « Annuler » ne laisse rien, ni objet ni entrée d'annulation ;
2. **sélectionner avant de lancer la commande** une à trois faces, arêtes ou sommets (de ses
   pièces, de pièces d'un ensemble, ou de n'importe quel objet Part d'un autre atelier) : la
   nouvelle pièce est posée **contre** cet élément, du côté extérieur de la matière ; avec deux
   éléments, elle touche les deux (une tablette entre deux joues, posée sur une traverse) ;
3. **faire tourner la pièce par quarts de tour** avec des boutons du panneau, en création (elle
   reste accrochée) comme en modification (elle tourne sur place) ; le fil tourne avec elle ;
4. **retrouver chaque pièce sous son repère** dans l'arborescence : le libellé de la pièce est son
   repère, et changer l'un change l'autre.

**Livrable visible** : dans le caisson de référence de J4d, le menuisier sélectionne la face
intérieure du côté gauche puis celle du côté droit, lance **Pièce de bois** : une tablette en
aperçu apparaît entre les deux côtés, à la bonne longueur ; « Pivoter » la tourne, « OK » la
valide ; il saisit le repère « E2 » et l'arborescence affiche « E2 ».

## 3. Critères d'acceptation

Légende : **U** = unitaire sans FreeCAD, **I** = intégration dans `freecadcmd` (1.0 et 1.1),
**G** = interface hors écran (1.0 et 1.1), **manuel** = recette décrite dans
`docs/recette/J6-scenarios-manuels.md` (jv la passe sur FreeCAD 1.1.4 sous Windows). Les lettres
des critères sont propres à cette spécification.

**Conventions.** Repère local de la pièce (`part_model`) : X = longueur L, Y = largeur l, Z =
épaisseur e. Pièce par défaut : 800 × 200 × 22. **Repère d'accrochage** d'un élément : origine O,
axes x, y, z orthonormés directs, z = normale **sortante** (côté où la pièce est posée). La pièce
est d'abord orientée (§ 4.3, `Orientation`), puis translatée pour que sa boîte occupe
[0, a] × [0, b] × [0, c] dans ce repère : **elle touche le plan z = 0 par dessous et part du
coin O**.

### J6a — Géométrie de l'accrochage (`core/snap/`)

| N° | Critère | Test |
|---|---|---|
| S1 | Objets valeur validés à la construction (`ValueError` citant le champ) : `Frame` (origine et axes finis, axes unitaires orthogonaux directs à `ANGLE_TOLERANCE` près, renormalisés), `FaceTarget`, `EdgeTarget` (extrémités distinctes de plus de `CONTACT_TOLERANCE_MM`), `VertexTarget`, `Orientation` (`tilt` ∈ {0, 1, 2}, `pivot` ∈ {0, 1, 2, 3}). Un cas refusé et un cas limite accepté par objet. | U |
| S2 | **Sans élément** : `snap(dimensions, Orientation(), ())` donne le `Placement` identité (comportement actuel inchangé) ; avec une orientation, la boîte tournée reste dans l'octant positif, coin en (0, 0, 0). | U |
| S3 | **Face plane seule**, face supérieure 600 × 300 d'un bloc en z = 100, coin le plus proche du point cliqué en (0, 0, 100), plus longue arête selon X : la pièce est **à plat** sur la face (Z local = z), sa longueur le long de la plus longue arête, son coin sur le coin de la face le plus proche du point cliqué, vers l'intérieur : boîte globale [0, 800] × [0, 200] × [100, 122]. Face verticale (normale −Y, plan y = 0) : boîte [0, 800] × [−22, 0] × [z…]. Face inclinée à 30° : la pièce est inclinée de même (le `Placement` n'est pas d'équerre avec le document). | U |
| S4 | **Face non plane** (cylindre, B-spline) : plan tangent au point cliqué ; la pièce y est posée par son coin sur le point, longueur selon la projection de l'axe X du document (Y s'il est normal au plan). | U |
| S5 | **Arête seule** (droite) : longueur le long de l'arête depuis l'extrémité la plus proche du point cliqué, pièce **à plat sur la face d'appui** (face adjacente la plus tournée vers l'observateur, normale `support`), vers l'intérieur de cette face (`inward`) : une arête de la pièce est confondue avec l'arête choisie. Arête courbe : tangente au point cliqué. Arête libre (esquisse) : face d'appui = plan qui contient l'arête et fait face à l'observateur. | U |
| S6 | **Sommet seul** : coin de la pièce sur le point, axes du repère de l'objet sélectionné (ceux du document pour un objet sans `Placement` tourné) ; des huit octants, le premier (ordre figé : `+++`, `−++`, `+−+`, `−−+`, `++−`, `−+−`, `+−−`, `−−−`) que `is_free` accepte ; aucun accepté ou `is_free` absent : le premier. | U |
| S7 | **Deux ou trois éléments** : le premier fixe l'orientation et le plan d'appui ; chaque élément suivant contraint un axe libre (x ou y du repère d'appui) : face dont la normale sortante est ±x ou ±y → la face de la pièce de ce côté vient sur ce plan, du côté extérieur ; arête perpendiculaire à un axe libre, ou sommet → la face de la pièce la plus proche vient sur sa coordonnée (les deux axes pour un sommet). Exemple : face du dessus d'une traverse puis face intérieure d'une joue → la pièce est posée sur la traverse et touche la joue par son bout. Résultat indépendant de l'ordre des éléments suivants. | U |
| S8 | **Deux faces face à face** (normales opposées sur un même axe, écart ≥ `MIN_DIMENSION_MM`) : la pièce les touche toutes les deux ; la cote locale selon cet axe devient l'écart (Q2 ★) — tablette entre deux joues à 22 et 578 : L = 556. Si cet axe est celui de l'épaisseur, l'épaisseur n'est **jamais** changée (règle de J4) : notice `ThicknessGap`, élément ignoré. Écart nul, négatif ou > `MAX_DIMENSION_MM` : notice `GapOutOfRange`, élément ignoré. Face parallèle au plan d'appui et en vis-à-vis (dessous d'un plateau au-dessus d'une traverse) : même règle sur z. | U |
| S9 | **Refus doux** : un élément suivant qui n'est ni parallèle ni perpendiculaire aux axes libres (face à 30°) → notice `NotSquare` citant l'élément ; plus de trois éléments → les trois premiers, notice `TooMany` ; un axe déjà contraint par un élément du même côté → le dernier l'emporte, notice `Conflict`. Jamais d'exception : `snap` renvoie toujours un placement et la liste des éléments retenus. | U |
| S10 | **Rotation** : `Orientation.turned(Turn.PIVOT)` = quart de tour autour de z du repère d'appui, `turned(Turn.TILT)` = à plat → sur chant → en bout → à plat (Z, puis Y, puis X local selon z) ; quatre pivots ou trois bascules reviennent au départ ; les 12 orientations distinctes d'une boîte sont atteintes. Après rotation, la pièce **reste accrochée** (S3 à S8 recalculés : elle touche toujours le plan d'appui et le coin O). `turned_in_place(placement, dimensions, turn)` (modification, sans accrochage) : même rotation dans le repère local, **centre de la boîte inchangé**. | U |
| S11 | `core/` n'importe ni FreeCAD ni Qt ; couverture de `core/snap/` ≥ 90 % ; aucun module > 400 lignes ; complexité dans les seuils de ruff. | U |

### J6b — Nom de la pièce = repère (`core/naming.py`, `features/wood_part.py`)

| N° | Critère | Test |
|---|---|---|
| L1 | `label_for_mark(mark, default, taken)` : repère non vide (espaces de tête et de fin ignorés pour le test du vide, texte gardé tel quel) → le repère s'il est libre, sinon `« M1 (2) »`, `« M1 (3) »`… (premier libre) ; repère vide → `default` (« Pièce de bois ») selon la même règle. `taken` = libellés des **autres** objets du document. | U |
| L2 | `mark_from_label(label, default)` : retire un suffixe ` (n)` final (n ≥ 2) ; libellé égal à `default` (avec ou sans suffixe) → repère vide. Aller-retour : `mark_from_label(label_for_mark(m, d, t), d)` vaut `m` pour un repère non vide qui ne finit pas lui-même par ` (n)`, `""` pour un repère vide (échantillon : `«  »`, `« M1 »`, `« Joue gauche »`, `« Pièce de bois »`, `taken` vide ou plein). Limite documentée : un repère saisi « A (2) » **dans l'arborescence** devient « A » (le panneau et l'éditeur de propriétés le gardent tel quel, car l'écriture du libellé par l'atelier ne relit jamais le repère). | U |
| L3 | **Repère → nom** : changer `Mark` (panneau, éditeur de propriétés, script, expression qui pilote `Mark`) met à jour `Label` dans la même transaction ; la pièce usinée suit : `« E2 (usinée) »`. Une nouvelle pièce prend le libellé `label_for_mark` de son repère (`make_wood_part(mark="M1")` → « M1 »). | I |
| L4 | **Nom → repère** (Q4 ★) : renommer la pièce dans l'arborescence (F2) ou par `obj.Label = …` change `Mark` ; renommer la pièce usinée change le repère de sa brute (et le libellé de l'usinée redevient `« {repère} (usinée) »`). `Mark` pilotée par une expression : le repère ne change pas, avertissement dans la vue rapport, le libellé revient à celui du repère. | I |
| L5 | **Doublons** : deux pièces de repère « M1 » s'appellent « M1 » et « M1 (2) » ; toutes deux gardent `Mark` = « M1 » (la liste de débit de J2 les regroupe). Renommer « M1 (2) » en « M1 » dans l'arborescence : le repère reste « M1 », le libellé reste « M1 (2) » (FreeCAD interdit deux libellés égaux ; aucune préférence de FreeCAD n'est modifiée). | I |
| L6 | **Réouverture, annuler, rétablir** : aucune synchronisation pendant la restauration ou une annulation (garde `restoring_or_undoing`) ; un document J1–J4 dont les libellés diffèrent des repères s'ouvre **sans aucun changement** et sans être marqué modifié (Q5 ★) ; la synchronisation s'applique à la première modification du repère ou du nom de chaque pièce. | I |
| L7 | **Expressions** : une expression de l'utilisateur qui cite la pièce par son libellé (`<<M1>>.Length` dans une feuille de calcul) suit le changement de repère (réécriture native de FreeCAD) ; les liaisons d'un ensemble (qui ne citent que le libellé de l'ensemble) ne changent pas. | I |

### J6c — Aperçu et boutons de rotation (`gui/task_panels/`, `features/placement.py`)

| N° | Critère | Test |
|---|---|---|
| V1 | **Aperçu** : en création, la pièce est affichée à 60 % de transparence tant que le panneau est ouvert, puis à sa transparence d'origine après « OK » ; texture et couleur du matériau inchangées (ADR 0004). En modification, aucun changement d'affichage. | G |
| V2 | L'aperçu suit chaque saisie (cotes, matériau, fil, rotation) sans recalculer le reste du document (`recompute_preview`, comme aujourd'hui). | G |
| V3 | **Annuler / rétablir** : « OK » laisse exactement une entrée d'annulation « Créer une pièce de bois » (libellé, placement et transparence compris) ; « Annuler » ne laisse ni objet ni entrée d'annulation ; en modification, « Annuler » rétablit cotes, `Placement`, repère et libellé. Document fermé ou objet supprimé pendant le panneau : comportement de J3e inchangé. | G |
| V4 | **Boutons** (Q1 ★) « Pivoter » et « Basculer » dans un groupe « Position » du panneau, infobulles traduites, icônes générées par `tools/generer_icones.py` ; en création, chaque clic applique S10 (la pièce reste accrochée) ; en modification, la pièce tourne sur place (centre fixe), sa pièce usinée et ses assemblages suivent au recalcul de l'aperçu. | G |
| V5 | **Sens du fil** : la rotation ne change ni `GrainDirection` ni `PreferredGrainDirection` (le fil est lié aux axes de la pièce, ADR 0005) ; la texture tourne avec la pièce. | G |
| V6 | Boutons inactifs (infobulle explicative) si le `Placement` de la pièce est piloté par une expression (membre d'un ensemble J4, formule de l'utilisateur) : « Cette pièce suit l'ensemble « Caisson » : tournez-la avec Std Transform après l'avoir retirée de l'ensemble. » | G |
| V7 | Aucun observateur ni filtre de sélection laissé en place après la fermeture du panneau ; aucune préférence écrite hors de `Mod/Menuiserie` (ADR 0007). | G |

### J6d — Accrochage à la sélection (`features/snap_targets.py`, `gui/commands/wood_part.py`)

| N° | Critère | Test |
|---|---|---|
| T1 | La commande lit la sélection **avant** de créer la pièce (`Gui.Selection.getSelectionEx("", 0)`, ordre de sélection conservé) ; chaque sous-élément `FaceN`, `EdgeN`, `VertexN` devient une cible (`features/snap_targets.py`, géométrie lue en coordonnées **globales** par `Part.getShape(racine, chemin, needSubElement=True)`) ; un objet entier sélectionné sans sous-élément, un objet sans forme Part (ensemble, maillage, page TechDraw) ou une forme nulle sont ignorés avec un message dans le panneau ; sans cible retenue, comportement de S2. | I + G |
| T2 | **Point cliqué** : `PickedPoints` de la sélection ; absent ou sélection par script : centre de masse de l'élément. **Côté extérieur** d'une face d'un solide : normale orientée vers l'extérieur (contrôlée par `isInside` sur un point décalé de 1 mm) ; face sans solide (esquisse, Part Plane) : côté tourné vers l'observateur (direction de la vue passée par la commande ; +Z en `freecadcmd`). | I |
| T3 | **La pièce touche chaque élément retenu** : distance (`distToShape`) entre la forme de la pièce et chaque élément ≤ `CONTACT_TOLERANCE_MM` ; **sommet** : la pièce ne chevauche pas l'objet sélectionné (`is_free` = volume commun < 1 mm³). Scénarios de référence : face, arête, sommet d'une pièce de bois ; deux joues face à face (S8) ; traverse + joue (S7) ; face d'un cube `Part::Box` ; face d'un `PartDesign::Body` ; face cylindrique d'un `Part::Cylinder` (S4) ; arête d'une esquisse (S5). | I |
| T4 | **Conteneur** : la pièce est créée dans le Std Part (`App::Part` strict) le plus profond du chemin du **premier** élément, sans traverser un `App::Link` (un élément vu à travers un lien place la pièce à côté de la copie, jamais dans l'original) ; son `Placement` est exprimé dans le repère de ce conteneur (placement global du conteneur inversé). Un `PartDesign::Body` ou un assemblage n'est jamais un conteneur de la pièce (on remonte au Std Part qui les contient, ou au document). Std Part tourné de 90° et déplacé : T3 vérifié en global. | I |
| T5 | **Ensemble** (Q3 ★) : si le premier élément appartient à une pièce membre d'un ensemble (sa brute porte `Furniture`), une case « Ajouter à l'ensemble « Caisson » » apparaît, **cochée** ; à « OK », la pièce entre dans l'ensemble par `add_to_furniture` (options par défaut de J4, positions relatives à `Origin` calculées depuis la géométrie), dans la même transaction. Tablette entre les deux côtés du caisson de référence, ensemble élargi de 100 mm : la tablette suit (L + 100). Refus de l'ensemble (autre conteneur…) : la pièce est créée hors de l'ensemble, message traduit. | I + G |
| T6 | Le panneau affiche, en création, « Contre : Face3 de « Côté gauche », Face1 de « Côté droit » » (libellés de FreeCAD) et les notices de S8–S9 traduites ; une cote étirée (S8) est écrite dans son champ et reste modifiable : la changer ensuite garde la valeur saisie (la pièce reste contre le premier élément). | G |
| T7 | Changer une cote, le matériau ou l'orientation recalcule l'accrochage : la pièce touche toujours les éléments retenus (une pièce qui touche par sa face « haute » recule quand sa longueur grandit). | G |
| T8 | La sélection de l'utilisateur n'est pas modifiée par la commande ni par le panneau (elle reste visible comme repère de l'accrochage). | G |
| T9 | **Recette manuelle** sur FreeCAD 1.1.4 Windows (jv) : livrable visible du § 2, sélection dans un Std Part tourné, face d'un objet d'un autre atelier, Annuler, Ctrl+Z après OK. | manuel |

## 4. Conception

### 4.1 Principe (ADR 0011)

- **Aperçu = l'objet réel** dans la transaction du panneau, comme aujourd'hui (pas de nœud Coin3D
  séparé) ; seul son affichage change le temps du panneau (transparence). Les champs à expression
  (`Gui.ExpressionBinding`), les assemblages et les pièces usinées continuent de fonctionner sur
  l'objet lui-même.
- **Accrochage ponctuel** : la commande calcule un `Placement` (et éventuellement une cote) une
  fois les éléments choisis ; **aucun lien persistant** n'est créé vers l'élément touché (ni
  expression, ni `AttachExtension`). La pièce reste une `Part::FeaturePython` ordinaire, libre de
  ses mouvements ; le suivi paramétrique reste le rôle de l'Ensemble (J4).
- **Séparation** : la géométrie (repères, orientations, contraintes, étirement) est pure, dans
  `core/snap/` ; la lecture des formes OCC en cibles est dans `features/snap_targets.py` (Part,
  sans Gui, testable dans `freecadcmd`) ; la lecture de la sélection, de la direction de vue et
  l'affichage sont dans `gui/`.
- **Nom = repère** : `Mark` reste la donnée (liste de débit, plans) ; `Label` en est le reflet,
  synchronisé par le `onChanged` de la pièce, règles pures dans `core/naming.py`.

```
freecad/menuiserie/
├── core/
│   ├── naming.py               J6b  label_for_mark, mark_from_label
│   └── snap/
│       ├── __init__.py         J6a  façade : Frame, FaceTarget, EdgeTarget, VertexTarget, Target, Orientation, Turn, SnapResult, SnapNotice, snap, turned_in_place
│       ├── _model.py           J6a  objets valeur, validation
│       ├── _frames.py          J6a  repère d'appui de chaque cible, orientation → matrice
│       └── _solve.py           J6a  contraintes des éléments suivants, étirement, notices
├── features/
│   ├── wood_part.py            J6b  onChanged Mark/Label, onBeforeChangeLabel, libellé à la création
│   ├── machined_part.py        J6b  libellé de l'usinée d'après le repère
│   ├── placement.py            J6c  RigidTransform ↔ App.Placement (rotation exacte), placement local d'un conteneur
│   └── snap_targets.py         J6d  formes OCC → cibles, is_free, contrôle « touche »
└── gui/
    ├── commands/wood_part.py   J6d  lecture de la sélection avant création
    ├── selection.py            J6d  SelectionObject → (racine, chemin, point), conteneur, direction de vue
    └── task_panels/
        ├── wood_part.py/.ui    J6c  groupe « Position », Pivoter, Basculer ; J6d « Contre : … », case Ensemble
        └── preview.py          J6c  PreviewStyle (transparence posée puis rétablie)
```

### 4.2 Design patterns retenus

| Besoin | Pattern | Justification |
|---|---|---|
| Face, arête, sommet | **Strategy** par type de cible : chaque cible fournit son repère d'appui (`anchor_frame`) et sa contrainte d'élément suivant (`constraint`) derrière une interface commune, choisie par type (registre `FRAME_BUILDERS`), pas de chaîne de `if type == …` | trois variantes dès J6, point d'extension (axe de perçage, plan de référence) |
| Données de l'accrochage | **objets valeur** immuables (`Frame`, cibles, `Orientation`, `SnapResult`) | testables sans FreeCAD, comme `core/geometry` |
| Création | **Fabrique** existante `make_wood_part`, enrichie de `placement` (et `container`) ; la commande ne crée rien elle-même | une seule voie de création (console, tests, commande) |
| Commande | **Command** FreeCAD existante `Menuiserie_WoodPart` | règle du projet |
| Aperçu | **Memento** léger (`PreviewStyle` : transparence d'origine mémorisée, rétablie à « OK ») | rien de persistant ajouté ; une seule classe |
| Nom ↔ repère | **Observer** : `onChanged` du proxy de la pièce (et de l'usinée), hors restauration et annulation | pas d'observateur global (ADR 0007) |

### 4.3 `core/snap/` (J6a)

```python
ANGLE_TOLERANCE  # de core.geometry ; CONTACT_TOLERANCE_MM de même

@dataclass(frozen=True)
class Frame:            # repère d'appui : z = normale sortante
    origin: Vec3
    x: Vec3
    y: Vec3
    z: Vec3
    def to_transform(self) -> RigidTransform: ...

@dataclass(frozen=True)
class FaceTarget:
    name: str                       # « Face3 de « Côté gauche » », pour les notices
    frame: Frame                    # O = coin du rectangle englobant le plus proche du point cliqué
    extent: tuple[float, float]     # rectangle englobant dans le plan (0, 0) si non plane
    planar: bool

@dataclass(frozen=True)
class EdgeTarget:
    name: str
    start: Vec3                     # extrémité la plus proche du point cliqué (tangente : point cliqué)
    end: Vec3
    support: Vec3                   # normale sortante de la face d'appui (S5)
    inward: Vec3                    # vers l'intérieur de la face d'appui, ⟂ à l'arête

@dataclass(frozen=True)
class VertexTarget:
    name: str
    point: Vec3
    axes: Frame                     # repère de l'objet sélectionné, origine = point

Target = FaceTarget | EdgeTarget | VertexTarget

class Turn(Enum):
    PIVOT = "Pivot"                 # quart de tour autour de z du repère d'appui
    TILT = "Tilt"                   # à plat → sur chant → en bout

@dataclass(frozen=True)
class Orientation:
    tilt: int = 0                   # 0 à plat (e selon z), 1 sur chant (l selon z), 2 en bout (L selon z)
    pivot: int = 0                  # 0 à 3 quarts de tour
    def turned(self, turn: Turn) -> Orientation: ...
    def rotation(self) -> Matrix3: ...

class SnapNoticeKind(Enum):  ThicknessGap, GapOutOfRange, NotSquare, TooMany, Conflict
@dataclass(frozen=True)
class SnapNotice:  kind: SnapNoticeKind; target: str  # + template, message (gabarits traduisibles)

@dataclass(frozen=True)
class SnapResult:
    placement: RigidTransform       # repère global
    dimensions: Dimensions          # L ou l étirée (S8), e jamais
    used: tuple[str, ...]           # noms des cibles retenues
    notices: tuple[SnapNotice, ...]

FreeTest = Callable[[RigidTransform, Dimensions], bool]

def snap(dimensions: Dimensions, orientation: Orientation, targets: Sequence[Target],
         *, stretch: bool = True, is_free: FreeTest | None = None) -> SnapResult: ...
def turned_in_place(placement: RigidTransform, dimensions: Dimensions, turn: Turn) -> RigidTransform: ...
```

Algorithme de `snap` (fonctions pures, chacune ≤ 50 instructions) :

1. Garder les trois premières cibles (`TooMany`). Sans cible : repère identité (S2).
2. **Repère d'appui** de la première cible (Strategy) : face → `frame` ; arête → O = `start`,
   x = `end − start` normé, z = `support`, y = `inward` ; sommet → `axes`, puis choix de l'octant
   (S6 : on retourne x, y et/ou z, en gardant un repère direct par l'ordre figé).
3. **Orientation** : rotation `Orientation.rotation()` dans le repère d'appui ; boîte tournée
   ramenée dans l'octant positif (coin O).
4. **Éléments suivants** exprimés dans le repère d'appui (`Frame.to_transform().inverse()`) :
   chacun donne au plus deux **contraintes d'axe** `AxisConstraint(axis, side, value)` (`side` =
   `LO` ou `HI` : quelle face de la boîte vient sur `value`) ; deux contraintes `LO` et `HI` sur
   le même axe → **étirement** de la cote locale portée par cet axe (`relative_axes` de
   `core.geometry` pour savoir laquelle), sauf l'épaisseur (S8) ; `stretch=False` (Q2 non) →
   seule la première est gardée.
5. **Translation** finale de la boîte selon les contraintes, puis composition :
   `placement = frame ∘ rotation ∘ translation`.

`relative_axes`, `RigidTransform`, `Vec3`, `Axis`, `Box` et `moved_box` de `core/geometry.py`
sont réutilisés ; une face inclinée produit un `Placement` non d'équerre avec le document, ce que
`RigidTransform` accepte (seules les rotations **relatives** des assemblages doivent être
d'équerre).

### 4.4 `core/naming.py` et synchronisation (J6b)

```python
DUPLICATE_SUFFIX = " ({n})"          # n ≥ 2
def label_for_mark(mark: str, default: str, taken: Collection[str]) -> str: ...
def mark_from_label(label: str, default: str) -> str: ...
```

- `WoodPart.onChanged(obj, "Mark")` (hors `_syncing`, restauration et annulation) :
  `obj.Label = label_for_mark(obj.Mark, translated(_DEFAULT_LABEL), autres libellés du document)`,
  puis libellé de la pièce usinée (`machined_part_of`) : `« {label} (usinée) »`. Écriture dans un
  autre objet : **exception documentée** de l'ADR 0011 (le `Label` de l'usinée seul, qui est la
  face visible de la brute selon l'ADR 0006 ; jamais pendant un recalcul).
- `WoodPart.onBeforeChangeLabel(obj, label)` (méthode des `FeaturePython`, appelée avant que
  FreeCAD ne rende le libellé unique) mémorise le repère saisi `mark_from_label(label, défaut)` et
  renvoie `label_for_mark(...)` : c'est notre suffixe « (2) », pas celui de FreeCAD, qui rend le
  libellé unique ; `onChanged(obj, "Label")` écrit ensuite `Mark` (sous `_syncing`), ou avertit
  si `Mark` est pilotée par une expression. **À vérifier en début de J6b sur 1.0 et 1.1** (R1) ;
  repli si l'appel n'existe pas : `onChanged(obj, "Label")` seul, sur le libellé déjà rendu unique
  par FreeCAD, puis libellé réécrit par `label_for_mark`.
- `MachinedPart.onChanged(obj, "Label")` : repère de la brute = `mark_from_label` du libellé saisi
  privé du suffixe « (usinée) » traduit.
- `create_wood_part(..., mark=…)` pose `Label = label_for_mark(mark, …)` ; aucune propriété
  nouvelle ; l'infobulle de `Mark` devient « Repère de la pièce sur les plans et dans la liste de
  débit (ex. « M1 ») ; c'est aussi son nom dans l'arborescence. Des pièces identiques peuvent
  partager le même repère. »

### 4.5 Aperçu et rotation dans le panneau (J6c)

- `gui/task_panels/preview.py` : `PreviewStyle(vobj)` mémorise `vobj.Transparency`, pose 60 ;
  `restore()` remet la valeur (appelé par `accept` avant `_finish`, et sans effet si l'objet a
  disparu). Seule la composante de transparence est touchée : `show_diffuse` de
  `part_appearance` conserve déjà l'alpha.
- `WoodPartTaskPanel` reçoit, en création, un `SnapSession` (cibles, orientation courante,
  conteneur, ensemble candidat) ; en modification, aucun. Groupe « Position » du `.ui` : ligne
  « Contre : … » et notices (J6d), boutons **Pivoter** et **Basculer** (`QToolButton`, icônes
  `Menuiserie_Pivot.svg`, `Menuiserie_Tilt.svg` générées), case « Ajouter à l'ensemble » (J6d).
- `_recompute()` : en création, `snap(...)` puis écriture de `Placement` (et de la cote étirée par
  le champ, comme `_choose_thickness`) avant `preview()` ; en modification, un clic écrit
  `turned_in_place(...)`.
- `features/placement.py` : `to_placement(transform) -> App.Placement` (rotation reconstruite par
  `App.Matrix`, arrondie à la permutation exacte quand elle est d'équerre à `ANGLE_TOLERANCE`
  près, pour ne pas laisser 1e-16 dans les fichiers) ; `from_placement` réutilise
  `RigidTransform.from_matrix` ; `local_placement(global_, container_global)`.
- `make_wood_part(..., placement: App.Placement | None = None, container: DocumentObject | None = None)` :
  le conteneur reçoit la pièce par `container.addObject` (Std Part) ; signature rétrocompatible.

### 4.6 Accrochage à la sélection (J6d)

- `gui/selection.py` : `picked_elements() -> list[PickedElement]` (`root`, `subname` complet,
  `element` « Face3 », `point` global ou `None`, `label` pour l'affichage) ;
  `container_of(element) -> DocumentObject | None` (dernier `App::Part` du chemin
  `root.getSubObjectList(subname)` avant tout `App::Link`) ; `view_direction() -> Vec3`.
- `features/snap_targets.py` : `target_of(element, view_direction) -> Target | None` (Strategy par
  type de sous-forme, `Part.Face`, `Part.Edge`, `Part.Vertex`) ; `free_test(shape) -> FreeTest` ;
  `touches(part_shape, element_shape) -> bool` (T3) ; `furniture_candidate(element)` (brute
  membre d'un ensemble, T5). Aucun import de `FreeCADGui`.
- `CreateWoodPartCommand.Activated` : lit la sélection, construit les cibles, **puis** ouvre la
  transaction et crée la pièce dans le conteneur ; `show_panel(obj, creating=True, session=…)`.
- À « OK » : `PreviewStyle.restore()`, puis `add_to_furniture` si la case est cochée, puis
  `_finish` (une seule transaction).

### 4.7 Sécurité

Aucune entrée nouvelle hors de FreeCAD : la sélection et les libellés sont des données ; les
libellés ne sont jamais évalués ni écrits dans une expression par l'atelier (les liaisons de J4 ne
citent que le libellé de l'ensemble, déjà contrôlé par `label_reference`). `label_for_mark`
borne la recherche du suffixe libre (au plus `len(taken) + 1` essais).

### 4.8 Compatibilité avec les autres ateliers (ADR 0007)

- Formes lues par `Part.getShape` : tout objet Part (Part, PartDesign, Draft, BIM, Sketcher,
  objets d'addons) peut servir de cible ; aucun n'est modifié.
- Pas de filtre ni d'observateur de sélection installé ; la sélection est lue une fois.
- La pièce créée reste une `Part::FeaturePython` au `Placement` ordinaire, dans le document ou un
  Std Part ; aucune pièce n'est ajoutée à un `PartDesign::Body`, à un assemblage, ni à l'original
  d'un `App::Link`.
- Les libellés restent uniques par nos propres suffixes : la préférence « libellés en double » de
  FreeCAD n'est ni lue ni modifiée.

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères | Dépend de |
|---|---|---|---|---|---|
| **J6a** | `feat/accrochage-core` | `core/snap/` (modèle, repères, orientation, contraintes, étirement, notices) | ≈ 380 | S1–S11 | — |
| **J6b** | `feat/nom-repere` | `core/naming.py`, `WoodPart` et `MachinedPart` (`onChanged`, `onBeforeChangeLabel`), libellé à la création, infobulle, CHANGELOG | ≈ 220 | L1–L7 | — |
| **J6c** | `feat/apercu-rotation` | `features/placement.py`, `make_wood_part(placement=, container=)`, `PreviewStyle`, groupe « Position » et boutons du panneau, icônes, recette (partie aperçu) | ≈ 350 | V1–V7 | J6a |
| **J6d** | `feat/accrochage-selection` | `gui/selection.py`, `features/snap_targets.py`, commande, ligne « Contre », case Ensemble, recette complète, README « Poser une pièce contre une autre » | ≈ 400 | T1–T9 | J6a, J6c |

J6a et J6b partent en parallèle : J6a est une bibliothèque testée sans FreeCAD, J6b est livrable
seul (le nom suit le repère dès sa fusion). J6c rend l'aperçu visible et ajoute la rotation, sans
sélection (la pièce part de l'origine, comme aujourd'hui) ; J6d branche la sélection. Si J6d
déborde, la case « Ajouter à l'ensemble » (T5) passe dans un lot J6e.

## 6. Compatibilité

- **Documents J1–J4** : aucune propriété ajoutée, aucune `Version` changée, aucune migration ;
  ouverts sans modification (L6, Q5 ★). Les libellés existants restent tels quels jusqu'à la
  première modification du repère ou du nom de chaque pièce.
- **Document J6 ouvert par un atelier plus ancien** : rien de nouveau n'est enregistré (libellés
  et placements ordinaires) ; il s'ouvre normalement ; seule la synchronisation nom ↔ repère
  n'a plus lieu.
- **Transparence** : posée et rétablie dans la transaction de création ; jamais enregistrée à
  60 % (« OK » la rétablit avant validation, « Annuler » supprime l'objet).
- **FreeCAD 1.0 et 1.1** : `getSelectionEx("", 0)`, `PickedPoints`, `Part.getShape(…,
  needSubElement=True)`, `getSubObjectList`, `onBeforeChangeLabel` des `FeaturePython`,
  `ViewObject.Transparency` : à vérifier en début de lot sur les deux versions (R1, R2) ;
  recette de jv sur 1.1.4 Windows.

## 7. Risques

| N° | Risque | Effet | Parade |
|---|---|---|---|
| R1 | `onBeforeChangeLabel` absent ou appelé après l'unicité de FreeCAD (1.0 / 1.1). | Renommer en un nom déjà pris donnerait « M2 » ou « M1001 », lu comme un nouveau repère. | Test en début de J6b sur les deux versions ; repli décrit au § 4.4 (le repère prend le libellé tel que FreeCAD l'a rendu, documenté). |
| R2 | Chemin de sélection et placement global différents entre 1.0 et 1.1 (liens, Std Part imbriqués). | Pièce posée au mauvais endroit dans un conteneur. | T3 et T4 en intégration sur les deux versions, Std Part tourné et `App::Link` ; contrôle « touche » (T3) affiché dans le panneau. |
| R3 | Normale d'une face mal orientée (face inversée, coque non fermée). | Pièce posée dans la matière. | `isInside` sur un point décalé (T2) ; à défaut, côté de l'observateur. |
| R4 | Règles d'accrochage inattendues (coin choisi, face d'appui d'une arête). | Pièce posée « à côté » de l'endroit voulu. | Règles simples et visibles en aperçu ; Pivoter / Basculer ; recette manuelle de jv. |
| R5 | Transparence et texture (ADR 0004) qui interfèrent. | Aperçu opaque ou texture perdue. | `show_diffuse` garde l'alpha ; V1 vérifie couleur et texture. |
| R6 | Label écrit dans la pièce usinée depuis le `onChanged` de la brute. | Écart à la règle « l'objet n'écrit que dans lui-même » (ADR 0009). | Exception limitée au `Label`, documentée par l'ADR 0011 ; jamais pendant un recalcul, une restauration ou une annulation. |

## 8. Hors périmètre

- **Lien persistant** entre la pièce et l'élément touché (la pièce ne suit pas si l'élément
  bouge) : c'est le rôle de l'Ensemble (J4) ; pas d'`AttachExtension`.
- Rotation d'un angle libre ou autour d'un axe choisi à la souris (Std Transform le fait) ;
  bouton « Inverser le côté » ; déplacement par glisser dans la vue ; cadrage automatique de la
  vue sur l'aperçu.
- Sélection **pendant** que le panneau est ouvert (on sélectionne avant de lancer la commande) ;
  accrochage des autres commandes (Caisson, Ensemble) ; création dans le Std Part « actif » sans
  sélection.
- Numérotation automatique des repères (M1, M2…) : à voir avec la liste de débit (J2).
- Renommage en masse des pièces des anciens documents (Q5 : non par défaut).

## 9. Questions pour jv

Une réponse d'un mot suffit ; la recommandation est marquée ★.

**Q1 — Quels boutons pour tourner la pièce ?** **Deux boutons** ★ : « Pivoter » (un quart de tour
en restant à plat sur la face où elle est posée) et « Basculer » (à plat → sur chant → en bout) /
**Un seul bouton** « Tourner de 90° » (à plat seulement ; pour la mettre sur chant, on échange les
cotes) / **Trois boutons**, un par axe X, Y, Z. ★ parce que deux boutons suffisent pour toutes les
positions d'une planche et que la pièce reste contre ce qu'on a sélectionné. Dans tous les cas, le
fil tourne avec la pièce.

**Q2 — Je sélectionne les faces intérieures de deux joues : la pièce prend-elle la longueur
entre les deux ?** **Oui** ★ (la tablette fait exactement la distance entre les joues ; vous
pouvez encore changer la longueur ensuite) / **Non** (elle garde sa longueur et touche seulement
la première joue). L'épaisseur, elle, n'est jamais changée.

**Q3 — La nouvelle pièce touche une pièce d'un ensemble (le caisson) : l'ajouter à cet
ensemble ?** **Oui, case cochée** ★ (elle suivra les cotes du caisson ; décochez pour la laisser
à part) / **Non, case décochée** (vous l'ajoutez vous-même avec « Ajouter à l'ensemble »).

**Q4 — Renommer la pièce dans l'arborescence change-t-il son repère ?** **Oui** ★ (un seul nom :
repère et nom sont toujours les mêmes ; deux pièces de même repère « M1 » s'affichent « M1 » et
« M1 (2) ») / **Non** (seul le repère commande le nom ; un nom changé à la main est remplacé au
prochain changement de repère).

**Q5 — Vos anciens fichiers : renommer les pièces d'après leur repère dès l'ouverture ?** **Non**
★ (le fichier s'ouvre sans changement ; chaque pièce prend son repère comme nom dès que vous
touchez à son repère ou à son nom) / **Oui** (toutes les pièces avec un repère sont renommées à
l'ouverture ; le fichier est marqué modifié).
