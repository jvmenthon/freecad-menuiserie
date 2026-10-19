# [J1] Pièce de bois paramétrique et bibliothèque de matériaux

- Jalon : J1 (version cible 0.1.0)
- Statut : **validée par jv le 2026-10-19** (questions Q1 à Q3 : recommandations retenues)
- ADR liés : [0002 — Bibliothèque de matériaux](../adr/0002-bibliotheque-de-materiaux.md),
  [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md)
- Découpage : trois PR successives **J1a → J1b → J1c** (voir § 5)

## 1. Contexte

Le menuisier dessine avec des pièces de bois réelles : une planche a une longueur, une largeur et une
épaisseur finies, une essence (ou un type de panneau), un sens du fil et un repère qui la désigne sur
le plan et dans la liste de débit. Pour débiter, il ajoute une surcote à ses cotes finies. Aujourd'hui
(J0) l'atelier se charge mais ne propose aucun outil : il faudrait passer par `Part::Box`, qui ne sait
rien de l'essence, du fil ni du débit.

La liste de débit (J2) et les assemblages (J3) s'appuieront entièrement sur cet objet : ses
propriétés, son repère local et son format de fichier deviennent un contrat qu'il faudra respecter
dans tous les documents enregistrés.

## 2. Objectif

Le menuisier peut :

1. créer une **pièce de bois** paramétrique (planche, tasseau, panneau) en choisissant ses cotes
   finies et son matériau dans une **bibliothèque d'essences et de panneaux** ;
2. la modifier à tout moment dans l'éditeur de propriétés ou dans un panneau de tâche, avec
   annulation possible ;
3. compléter la bibliothèque avec ses propres essences et panneaux, sans toucher à l'atelier.

**Livrable visible** : créer une planche de chêne 800 × 200 × 22 et la modifier
(J1b : depuis la console Python et l'éditeur de propriétés ; J1c : depuis la barre d'outils).

## 3. Critères d'acceptation

Légende du type de test : **U** = unitaire sans FreeCAD (`tests/unit`), **I** = intégration dans
`freecadcmd` (`tests/integration`, FreeCAD 1.0 et 1.1), **G** = interface hors écran
(`tests/gui/verifier_atelier.py`).

### J1a — Bibliothèque et calculs (`core/`, `data/`)

| N° | Critère | Test |
|---|---|---|
| A1 | `data/materiaux.json` se charge **sans aucune anomalie** et contient au moins les 12 matériaux du § 4.3.4, avec des identifiants uniques et des libellés français uniques. | U |
| A2 | Chaque règle de validation du § 4.3.2 est vérifiée : une entrée qui la viole est rejetée avec une anomalie qui cite la source, l'identifiant (s'il est lisible) et le champ fautif ; les autres entrées du fichier restent chargées. | U (un cas par règle) |
| A3 | Un fichier illisible, qui n'est pas du JSON valide, qui dépasse 1 Mio, dont la racine n'est pas un objet ou dont `format` n'est pas `1` est **ignoré en entier** avec une seule anomalie de niveau erreur ; `NaN`/`Infinity` sont refusés. | U |
| A4 | Fusion : une entrée utilisateur d'identifiant nouveau est ajoutée après les matériaux intégrés ; une entrée utilisateur d'identifiant existant **remplace entièrement** le matériau intégré (anomalie de niveau info) ; une entrée utilisateur dont le libellé français est déjà porté par un autre identifiant est rejetée. Un fichier utilisateur absent ne produit aucune anomalie. | U |
| A5 | Calculs : pour 800 × 200 × 22 mm, `volume_m3` = 0,00352 m³ et `mass_kg` à 710 kg/m³ = 2,4992 kg (à 1e-9 près) ; `rough_dimensions` avec des surcotes 20 / 5 / 0 donne 820 × 205 × 22. | U |
| A6 | `Dimensions` refuse toute cote ≤ 0, non finie ou > 20 000 mm ; `Allowances` refuse toute surcote < 0, non finie ou > 20 000 mm (exception `InvalidDimensionsError`). | U |
| A7 | Règles de changement de matériau : vers un matériau sans fil → `GrainDirection.NONE` ; vers un matériau avec fil alors que le fil valait `NONE` → `LENGTH` ; sinon le fil est conservé. Les surcotes ne sont remplacées par celles de la nouvelle famille (massif / panneau) **que si** elles valent encore exactement celles de l'ancienne famille. | U |
| A8 | `is_standard_thickness` reconnaît 18 mm pour le contreplaqué bouleau (tolérance 0,05 mm) et refuse 17 mm. | U |
| A9 | `core/` n'importe ni FreeCAD ni Qt (test existant `test_separation_app_gui` toujours vert) ; couverture de `core/` ≥ 90 %. | U |

### J1b — Objet du document (`features/`, `api.py`, ViewProvider)

| N° | Critère | Test |
|---|---|---|
| B1 | Dans `freecadcmd`, `create_wood_part(doc, length=800, width=200, thickness=22, material_id="chene")` puis `doc.recompute()` donne un objet valide : `Shape.Volume` = 3 520 000 mm³, boîte englobante de 800 (X) × 200 (Y) × 22 (Z) avec un coin à l'origine du repère local, `MaterialId` = `"chene"`, `Category` = `"Solid"`, `Density` = 710 kg/m³, `GrainDirection` = `"Length"`, `Version` = 1. | I |
| B2 | Chaque propriété du tableau du § 4.4.2 existe avec le type, le groupe, l'infobulle et le mode d'édition indiqués. | I |
| B3 | Modifier `Length` à 1000 mm puis recalculer donne un volume de 4 400 000 mm³ ; le `Placement` (préalablement déplacé et tourné) est **inchangé**. Idem pour `Width` et `Thickness`. | I |
| B4 | Une expression sur une cote fonctionne : `Length` = `Width * 4` donne 800 mm, puis 1000 mm après `Width` = 250. | I |
| B5 | Choisir `Material` = « Hêtre » met à jour `MaterialId`, `Category`, `Density` sans changer les cotes ; choisir « MDF » passe `GrainDirection` à `"None"` et les surcotes 20 / 5 / 0 à 0 / 0 / 0 (critère A7). | I |
| B6 | Une cote à 0 met l'objet en erreur au recalcul (`isValid()` faux, message traduit « cote invalide » dans `getStatusString()`), sans exception non rattrapée ni blocage du document ; remettre une cote valide rend l'objet valide. Une valeur négative n'est jamais retenue (la propriété reste ≥ 0). | I |
| B7 | Enregistrer, fermer, rouvrir : toutes les propriétés sont identiques, l'objet est valide et le volume inchangé. Si la bibliothèque est inchangée, aucun objet n'est marqué « Touched » après réouverture. | I |
| B8 | Réouverture avec une bibliothèque où le matériau n'existe plus (fichier utilisateur retiré) : `MaterialId`, le libellé de `Material` et `Density` sont conservés, l'objet reste valide, un seul avertissement est écrit dans la vue rapport. | I |
| B9 | Migration : un objet enregistré sans `Version` ni `ThicknessAllowance` (propriétés supprimées avant enregistrement pour simuler un ancien fichier) est rouvert avec les propriétés manquantes recréées à leur valeur par défaut et `Version` = 1. | I |
| B10 | Annuler / rétablir : création encadrée par `openTransaction` / `commitTransaction`, puis `undo()` supprime la pièce et `redo()` la restaure avec ses propriétés (`UndoMode` = 1). Idem pour une modification de `Length`. | I |
| B11 | Le proxy enregistré dans le document est `freecad.menuiserie.features.wood_part.WoodPart` et `dumps()` renvoie `None` (test « contrat de persistance », cf. ADR 0003). | I |
| B12 | `record_of(obj)` renvoie un `PartRecord` cohérent avec les propriétés (prépare J2) ; `is_wood_part` vaut vrai pour une pièce et faux pour un `Part::Box`. | I |
| B13 | Dans l'interface, `api.make_wood_part(800, 200, 22, "chene")` crée une pièce avec l'icône de l'atelier dans l'arbre et la couleur d'affichage du chêne ; changer de matériau change la couleur. Dans `freecadcmd`, la même fonction fonctionne sans importer `FreeCADGui`. | G + I |
| B14 | Une anomalie de la bibliothèque utilisateur est signalée **une seule fois** par session dans la vue rapport, traduite, sans empêcher la création de pièces avec les matériaux valides. | I |

### J1c — Commande et panneau de tâche (`gui/`)

| N° | Critère | Test |
|---|---|---|
| C1 | La commande `Menuiserie_WoodPart` (« Pièce de bois ») apparaît dans la barre d'outils et le menu Menuiserie, avec icône et infobulle ; elle est inactive sans document ou si un panneau de tâche est déjà ouvert. | G |
| C2 | Lancer la commande crée une pièce (chêne, 800 × 200 × 22 par défaut) et ouvre le panneau ; « OK » laisse **une** pièce et **une** entrée d'annulation « Créer une pièce de bois ». | G |
| C3 | « Annuler » dans le panneau de création ne laisse ni pièce ni entrée d'annulation. | G |
| C4 | Double-clic sur une pièce : le panneau s'ouvre avec ses valeurs actuelles ; chaque modification est visible immédiatement dans la vue 3D ; « OK » crée **une** entrée d'annulation « Modifier une pièce de bois » ; « Annuler » rétablit toutes les valeurs d'origine. | G (+ manuel) |
| C5 | Le filtre « Type » (Tous, Massif, Contreplaqué, MDF, Mélaminé) restreint la liste des matériaux ; les épaisseurs standard du matériau choisi sont proposées en un clic ; une épaisseur hors standard pour un **panneau** affiche un avertissement visible mais **non bloquant**. | G (+ manuel) |
| C6 | Si une cote est pilotée par une expression, le champ l'affiche (icône d'expression) et le panneau ne supprime pas l'expression. | G (+ manuel) |
| C7 | Les champs de cote acceptent les unités (`80 cm`, `2'`) et refusent une valeur ≤ 0. | manuel |
| C8 | Toute chaîne visible (commande, panneau, `.ui`, messages) passe par `translate()`, `QT_TRANSLATE_NOOP` ou les chaînes traduisibles du `.ui` ; aucun import `PySide2`/`PySide6`. | revue + test d'imports |
| C9 | Scénario du livrable, déroulé à la main sur FreeCAD 1.0 et 1.1 et décrit dans la PR : créer une planche de chêne 800 × 200 × 22, la passer à 1000 × 250 × 27 en hêtre, annuler, rétablir, enregistrer, rouvrir. | manuel |

## 4. Conception

### 4.1 Vue d'ensemble

```
freecad/menuiserie/
├── api.py                         J1b  façade publique pour scripts et console
├── core/
│   ├── i18n.py                    J1a  marqueur QT_TRANSLATE_NOOP pur Python
│   ├── materials.py               J1a  Material, MaterialKind, MaterialLibrary, lecture/validation/fusion
│   └── part_model.py              J1a  Dimensions, Allowances, GrainDirection, PartRecord, calculs, règles
├── data/
│   └── materiaux.json             J1a  bibliothèque intégrée (format 1)
├── features/
│   ├── library.py                 J1b  accès à la bibliothèque depuis FreeCAD (chemins, cache, journal)
│   └── wood_part.py               J1b  proxy WoodPart (Part::FeaturePython) + fonctions utilitaires
├── gui/
│   ├── view_providers/wood_part.py J1b icône, couleur ; J1c : édition (double-clic)
│   ├── commands/wood_part.py      J1c  commande Menuiserie_WoodPart
│   └── task_panels/
│       ├── wood_part.py           J1c  WoodPartTaskPanel
│       └── wood_part.ui           J1c  formulaire Qt Designer
├── resources/icons/piece-de-bois.svg  J1b
└── init_gui.py                    J1c  enregistrement de la commande dans Initialize()
```

Principes (ADR 0002 et 0003) :

- `core/` porte toute la logique (validation, fusion, calculs, règles de changement de matériau) et
  ne travaille qu'en **mm** et **kg/m³**, en flottants. Les conversions d'unités FreeCAD se font
  uniquement dans `features/`.
- `execute()` ne lit **que** `Length`, `Width`, `Thickness` : il ne consulte jamais la bibliothèque,
  ce qui garantit un recalcul identique sur toutes les machines.
- Le document conserve un **instantané** du matériau (identifiant stable, catégorie, masse
  volumique) : un fichier envoyé à quelqu'un qui n'a pas la même bibliothèque reste exact.

### 4.2 `core/` (J1a)

#### `core/i18n.py`

```python
CONTEXT: Final = "Menuiserie"


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:
    """Marque une chaîne pour lupdate sans la traduire (core/ ne peut pas importer Qt)."""
```

Les messages produits par `core/` sont des **gabarits** français marqués par ce marqueur, avec
paramètres nommés (`"{source} : matériau « {id} », champ « {field} » : {reason}"`). La couche
`features/` les traduit (`translate(CONTEXT, gabarit).format(**params)`).

#### `core/materials.py`

```python
FORMAT_VERSION: Final = 1
MAX_FILE_BYTES: Final = 1_048_576
MAX_MATERIALS: Final = 500

class MaterialKind(str, Enum):
    SOLID = "solid"
    PLYWOOD = "plywood"
    MDF = "mdf"
    MELAMINE = "melamine"

    @property
    def is_panel(self) -> bool: ...

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass(frozen=True)
class LibraryIssue:
    severity: Severity
    source: str                       # chemin du fichier ou "intégrée"
    template: str                     # gabarit français marqué QT_TRANSLATE_NOOP
    params: Mapping[str, str]
    material_id: str | None = None

    def format(self) -> str:          # gabarit non traduit, rempli (tests, journaux)

@dataclass(frozen=True)
class Material:
    id: str
    kind: MaterialKind
    names: Mapping[str, str]          # code langue ISO 639-1 -> libellé ; au moins une entrée
    density: float                    # kg/m³
    thicknesses: tuple[float, ...]    # mm, triées croissantes, sans doublon
    color: tuple[int, int, int]       # RVB 0–255
    has_grain: bool

    def name(self, lang: str = "fr") -> str:
        """Libellé dans la langue demandée, sinon français, sinon la première langue disponible."""

class UnknownMaterialError(KeyError): ...
class LibraryFormatError(ValueError): ...      # usage interne, converti en LibraryIssue

class MaterialLibrary:
    """Collection immuable et ordonnée ; identifiants et libellés français uniques (ValueError sinon)."""
    def __init__(self, materials: Iterable[Material]) -> None: ...
    def __contains__(self, material_id: object) -> bool: ...
    def __iter__(self) -> Iterator[Material]: ...       # intégrés puis ajouts utilisateur, ordre des fichiers
    def __len__(self) -> int: ...
    def get(self, material_id: str) -> Material: ...    # UnknownMaterialError
    def find(self, material_id: str) -> Material | None: ...
    def find_by_name(self, name: str, lang: str = "fr") -> Material | None: ...
    def by_kind(self, *kinds: MaterialKind) -> list[Material]: ...
    def default_material(self) -> Material: ...         # premier matériau massif, sinon le premier

def parse_materials(data: object, source: str) -> tuple[list[Material], list[LibraryIssue]]: ...
def read_materials_file(path: Path, source: str | None = None) -> tuple[list[Material], list[LibraryIssue]]: ...
def merge_materials(builtin: Sequence[Material], user: Sequence[Material], user_source: str
                    ) -> tuple[MaterialLibrary, list[LibraryIssue]]: ...
def load_library(builtin_path: Path, user_path: Path | None
                 ) -> tuple[MaterialLibrary, list[LibraryIssue]]: ...
```

`read_materials_file` : taille vérifiée **avant** lecture, décodage UTF-8 strict,
`json.loads(..., parse_constant=<refus>)` ; aucune autre forme de désérialisation. Un fichier
utilisateur absent renvoie `([], [])`.

#### `core/part_model.py`

```python
MAX_DIMENSION_MM: Final = 20_000.0
STANDARD_THICKNESS_TOLERANCE_MM: Final = 0.05


class GrainDirection(str, Enum):  # valeurs stockées dans les documents : ne jamais les renommer
    LENGTH = "Length"
    WIDTH = "Width"
    NONE = "None"


class InvalidDimensionsError(ValueError):
    template: str
    params: Mapping[str, str]


@dataclass(frozen=True)
class Dimensions:  # cotes finies en mm ; 0 < x ≤ MAX_DIMENSION_MM, finies
    length: float
    width: float
    thickness: float


@dataclass(frozen=True)
class Allowances:  # surcotes TOTALES (pas par face) en mm ; 0 ≤ x ≤ MAX
    length: float = 0.0
    width: float = 0.0
    thickness: float = 0.0


DEFAULT_SOLID_ALLOWANCES: Final = Allowances(20.0, 5.0, 0.0)  # cf. question ouverte Q2
DEFAULT_PANEL_ALLOWANCES: Final = Allowances()


@dataclass(frozen=True)
class PartRecord:  # entrée de la future liste de débit (J2)
    mark: str
    material_id: str
    material_name: str
    kind: MaterialKind
    finished: Dimensions
    allowances: Allowances
    grain: GrainDirection
    density: float  # kg/m³

    @property
    def rough(self) -> Dimensions: ...
    def volume_m3(self, rough: bool = False) -> float: ...
    def mass_kg(self, rough: bool = False) -> float: ...


def default_allowances(kind: MaterialKind) -> Allowances: ...
def rough_dimensions(finished: Dimensions, allowances: Allowances) -> Dimensions: ...
def volume_m3(dimensions: Dimensions) -> float: ...
def mass_kg(dimensions: Dimensions, density_kg_m3: float) -> float: ...
def is_standard_thickness(
    material: Material, thickness: float, tolerance: float = STANDARD_THICKNESS_TOLERANCE_MM
) -> bool: ...
def grain_after_material_change(new: Material, current: GrainDirection) -> GrainDirection: ...
def allowances_after_material_change(
    old_kind: MaterialKind | None, new_kind: MaterialKind, current: Allowances
) -> Allowances: ...
```

### 4.3 Bibliothèque de matériaux (J1a)

#### 4.3.1 Format JSON (format 1)

```json
{
  "format": 1,
  "materials": [
    {
      "id": "chene",
      "kind": "solid",
      "name": {"fr": "Chêne", "en": "Oak"},
      "density": 710,
      "thicknesses": [18, 22, 27, 34, 41, 54],
      "color": "#B8875A",
      "has_grain": true
    },
    {
      "id": "noyer-noir",
      "kind": "solid",
      "name": "Noyer noir",
      "density": 610,
      "thicknesses": [22, 27],
      "color": "#4A3326"
    }
  ]
}
```

Clés en anglais (identifiants), valeurs affichées en français. Les unités sont implicites et
documentées : `density` en kg/m³ (bois à environ 12 % d'humidité), `thicknesses` en mm.

#### 4.3.2 Règles de validation

| Élément | Règle | En cas de violation |
|---|---|---|
| Fichier | ≤ 1 Mio, UTF-8, JSON valide, sans `NaN`/`Infinity` | fichier ignoré, 1 erreur |
| Racine | objet contenant `format` (entier, pas booléen) et `materials` (liste) | fichier ignoré, 1 erreur |
| `format` | égal à 1 ; supérieur → message « fichier créé par une version plus récente de l'atelier » | fichier ignoré, 1 erreur |
| `materials` | ≤ 500 entrées, chacune un objet | entrées en trop / non-objets ignorés, 1 erreur |
| `id` | obligatoire, chaîne, `^[a-z0-9]+(-[a-z0-9]+)*$`, 1 à 64 caractères ; unique dans le fichier | entrée rejetée (doublon : la 2ᵉ), 1 erreur |
| `kind` | obligatoire, l'une de `solid`, `plywood`, `mdf`, `melamine` | entrée rejetée |
| `name` | obligatoire ; chaîne (équivaut à `{"fr": …}`) ou objet `{langue: libellé}` non vide ; langue `^[a-z]{2}$` ; libellé de 1 à 80 caractères après suppression des espaces de bord, sans caractère de contrôle | entrée rejetée |
| `density` | obligatoire, nombre fini (pas booléen), 50 ≤ d ≤ 2000 | entrée rejetée |
| `thicknesses` | obligatoire, liste non vide de 1 à 50 nombres finis, 0 < e ≤ 300 ; triée et dédoublonnée au chargement | entrée rejetée |
| `color` | obligatoire, chaîne `^#[0-9A-Fa-f]{6}$` | entrée rejetée |
| `has_grain` | facultatif, booléen ; défaut : vrai pour `solid` et `plywood`, faux pour `mdf` et `melamine` | entrée rejetée si non booléen |
| Clé inconnue | (racine ou entrée) | ignorée, 1 avertissement (aide à repérer les fautes de frappe) |

Fusion (fichier utilisateur sur bibliothèque intégrée) : identifiant nouveau → ajouté à la fin ;
identifiant existant → **remplacement complet** de l'entrée intégrée, à sa place (anomalie info) ;
libellé français déjà utilisé par un autre identifiant → entrée utilisateur rejetée (les libellés
servent de valeurs à la liste déroulante `Material`, ils doivent être uniques).

#### 4.3.3 Extension par l'utilisateur

- Fichier unique : `<dossier de données utilisateur FreeCAD>/Menuiserie/materiaux.json`, soit
  `Path(App.getUserAppDataDir()) / "Menuiserie" / "materiaux.json"`. Selon la version de FreeCAD ce
  dossier peut être versionné (`…/FreeCAD/v1-1/`) ; il suit alors l'outil de migration de FreeCAD.
- Le paramètre `User parameter:BaseApp/Preferences/Mod/Menuiserie` → `UserLibraryPath` (chaîne,
  vide par défaut) permet de pointer un autre fichier (bibliothèque partagée). Pas de page de
  préférences en J1.
- L'atelier **ne crée ni n'écrit jamais** ce fichier ; il le lit une fois par session
  (`features.library.get_library()`), `reload_library()` permet de le relire depuis la console.
  La documentation utilisateur (README, section « Ajouter une essence ») donne un exemple complet.

#### 4.3.4 Contenu initial de `data/materiaux.json`

Valeurs moyennes indicatives, **à relire par jv lors de la revue de J1a** (cf. ADR 0002 : une
correction ultérieure n'affecte pas les pièces déjà créées).

| id | kind | fr / en | densité (kg/m³) | épaisseurs standard (mm) | couleur | fil |
|---|---|---|---|---|---|---|
| `chene` | solid | Chêne / Oak | 710 | 18, 22, 27, 34, 41, 54 | `#B8875A` | oui |
| `hetre` | solid | Hêtre / Beech | 720 | 18, 22, 27, 34, 41, 54 | `#D9B48A` | oui |
| `frene` | solid | Frêne / Ash | 690 | 18, 22, 27, 34, 41, 54 | `#E3CFA5` | oui |
| `noyer` | solid | Noyer / Walnut | 650 | 18, 22, 27, 34, 41 | `#6B4A33` | oui |
| `merisier` | solid | Merisier / Cherry | 620 | 18, 22, 27, 34, 41 | `#B5654A` | oui |
| `pin-sylvestre` | solid | Pin sylvestre / Scots pine | 520 | 18, 22, 27, 34, 45 | `#E8C68E` | oui |
| `sapin-epicea` | solid | Sapin – épicéa / Fir – spruce | 450 | 18, 22, 27, 34, 45 | `#EEDDB8` | oui |
| `douglas` | solid | Douglas / Douglas fir | 530 | 22, 27, 34, 45 | `#D49A6A` | oui |
| `cp-bouleau` | plywood | Contreplaqué bouleau / Birch plywood | 680 | 4, 6.5, 9, 12, 15, 18, 21, 24 | `#E6D3B0` | oui |
| `cp-peuplier` | plywood | Contreplaqué peuplier / Poplar plywood | 450 | 5, 10, 15, 18, 22 | `#EADFC4` | oui |
| `mdf` | mdf | MDF / MDF | 750 | 3, 6, 10, 12, 16, 19, 22, 25 | `#A98B6D` | non |
| `melamine-blanc` | melamine | Mélaminé blanc / White melamine | 650 | 8, 16, 19, 22 | `#F2F2F0` | non |

### 4.4 Objet du document (J1b)

#### 4.4.1 `features/library.py`

```python
PARAM_PATH: Final = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
USER_LIBRARY_PARAM: Final = "UserLibraryPath"


def builtin_library_path() -> Path: ...  # DATA_DIR / "materiaux.json"
def user_library_path() -> Path: ...  # paramètre s'il est renseigné, sinon dossier utilisateur
def get_library() -> (
    MaterialLibrary
): ...  # chargée au premier appel, anomalies journalisées une fois
def reload_library() -> MaterialLibrary: ...
def display_language() -> str: ...  # "fr" en J1 (choix de la langue : J5)
```

Journalisation : `ERROR` → `App.Console.PrintError`, `WARNING` → `PrintWarning`,
`INFO` → `PrintLog` ; messages traduits via `translate("Menuiserie", issue.template)`.

#### 4.4.2 Propriétés de l'objet `WoodPart` (`Part::FeaturePython`)

Infobulles déclarées avec `QT_TRANSLATE_NOOP("App::Property", …)` pour être traduites par
l'éditeur de propriétés. « Lecture seule » = `setEditorMode(nom, 1)`, « masquée » = mode 2 (modes
réappliqués dans `onDocumentRestored`).

| Propriété | Type | Groupe | Défaut | Édition | Infobulle |
|---|---|---|---|---|---|
| `Length` | `App::PropertyLength` | Dimensions | 800 mm | oui | Longueur finie de la pièce, mesurée selon l'axe X local. |
| `Width` | `App::PropertyLength` | Dimensions | 200 mm | oui | Largeur finie de la pièce, mesurée selon l'axe Y local. |
| `Thickness` | `App::PropertyLength` | Dimensions | 22 mm | oui | Épaisseur finie de la pièce, mesurée selon l'axe Z local. |
| `Material` | `App::PropertyEnumeration` (libellés de la bibliothèque) | Matériau | matériau par défaut | oui | Essence ou panneau, choisi dans la bibliothèque de matériaux. |
| `MaterialId` | `App::PropertyString` | Matériau | `chene` | lecture seule | Identifiant stable du matériau dans la bibliothèque. C'est lui qui est enregistré et utilisé par les calculs. |
| `Category` | `App::PropertyEnumeration` (`Solid`, `Plywood`, `MDF`, `Melamine`) | Matériau | `Solid` | lecture seule | Type de matériau, déduit du matériau choisi : massif ou panneau (contreplaqué, MDF, mélaminé). |
| `Density` | `App::PropertyDensity` | Matériau | 710 kg/m³ | lecture seule | Masse volumique recopiée de la bibliothèque au choix du matériau ; sert au calcul de la masse. |
| `GrainDirection` | `App::PropertyEnumeration` (`Length`, `Width`, `None`) | Matériau | `Length` | oui | Sens du fil par rapport aux cotes de la pièce : le long de la longueur, de la largeur, ou sans fil (MDF, mélaminé uni). |
| `Mark` | `App::PropertyString` | Débit | `""` | oui | Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 »). Des pièces identiques peuvent partager le même repère. |
| `LengthAllowance` | `App::PropertyLength` | Débit | 20 mm (massif) / 0 (panneau) | oui | Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit. |
| `WidthAllowance` | `App::PropertyLength` | Débit | 5 mm (massif) / 0 (panneau) | oui | Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit. |
| `ThicknessAllowance` | `App::PropertyLength` | Débit | 0 mm | oui | Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit. |
| `Version` | `App::PropertyInteger` | Base | 1 | masquée | Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers. |

`Placement` et `Label` sont hérités. `Label` par défaut : `translate("Menuiserie", "Pièce de bois")`.
Nom interne : `WoodPart`.

Ordre des valeurs des énumérations figé ; on ne peut qu'**ajouter** des valeurs en fin de liste
(ADR 0003). `Density` est stockée en unités internes FreeCAD (kg/mm³) : conversion par
`Quantity(f"{d} kg/m^3")` et `getValueAs("kg/m^3")`, uniquement dans `features/`.

#### 4.4.3 `features/wood_part.py`

```python
class WoodPart:
    """Proxy du FeaturePython « pièce de bois ». Chemin de module figé (ADR 0003)."""

    TYPE: ClassVar[str] = "Menuiserie::WoodPart"
    VERSION: ClassVar[int] = 1

    def __init__(self, obj: DocumentObject) -> None: ...  # obj.Proxy = self ; ajoute les propriétés
    def onDocumentRestored(self, obj: DocumentObject) -> None: ...
    def onChanged(self, obj: DocumentObject, prop: str) -> None: ...
    def execute(self, obj: DocumentObject) -> None: ...
    def dumps(self) -> None: ...
    def loads(self, state: object) -> None: ...


def create_wood_part(
    doc: Document,
    *,
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    mark: str = "",
) -> DocumentObject: ...  # App seulement, sans transaction
def is_wood_part(obj: object) -> bool: ...
def set_material(obj: DocumentObject, material_id: str) -> None: ...  # UnknownMaterialError
def dimensions_of(obj: DocumentObject) -> Dimensions: ...
def allowances_of(obj: DocumentObject) -> Allowances: ...
def record_of(obj: DocumentObject) -> PartRecord: ...  # entrée de J2
```

Comportement :

- **`execute`** : construit `Dimensions` depuis les trois cotes (en cas d'`InvalidDimensionsError`,
  lève `ValueError` avec le message traduit, ce qui met l'objet en erreur), puis
  `Part.makeBox(length, width, thickness)` ; **sauvegarde et réapplique `obj.Placement`** autour de
  l'affectation de `obj.Shape` (sinon FreeCAD remet le placement de la forme). Aucune lecture de la
  bibliothèque, aucune écriture d'autre propriété.
- **`onChanged("Material")`**, hors restauration (`"Restore" in obj.State`) et hors
  resynchronisation interne (drapeau de réentrance, lu avec `getattr(self, "_syncing", False)`
  car `__init__` n'est pas rappelé à la réouverture) : retrouve le matériau par libellé, met à jour
  `MaterialId`, `Category`, `Density`, puis `GrainDirection` et les surcotes selon les règles
  `core` (critère A7). Les cotes ne sont **jamais** modifiées automatiquement.
- **`onDocumentRestored`** : migration (`_migrate(obj, from_version)`, où une `Version` absente vaut
  0 : ajout des propriétés manquantes avec leurs défauts, puis `Version = VERSION`), réapplication
  des modes d'édition, puis reconstruction de la liste `Material` depuis la bibliothèque **seulement
  si elle diffère** ; si `MaterialId` est inconnu localement, le libellé enregistré est conservé
  comme valeur supplémentaire de la liste et `Density`/`Category` ne sont pas touchés.
- **`dumps`/`loads`** : le proxy ne porte aucun état (tout est dans les propriétés).

#### 4.4.4 `api.py` (façade pour scripts et console)

```python
def make_wood_part(
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    *,
    mark: str = "",
    doc: Document | None = None,
) -> DocumentObject: ...
```

Crée la pièce dans `doc` (document actif par défaut, nouveau document s'il n'y en a pas), attache
le ViewProvider **si `App.GuiUp`** (import de `gui` à l'intérieur de ce test uniquement), recalcule
et renvoie l'objet. N'ouvre pas de transaction : c'est l'appelant (commande, script) qui le fait.
`api.py` n'est importé ni par `__init__.py` ni par `features/`.

Usage console (livrable J1b) :

```python
from freecad.menuiserie.api import make_wood_part

planche = make_wood_part(800, 200, 22, "chene")
planche.Length = 1000  # ou depuis l'éditeur de propriétés
```

#### 4.4.5 `gui/view_providers/wood_part.py`

```python
class ViewProviderWoodPart:
    """Chemin de module figé (ADR 0003)."""

    def __init__(self, vobj: ViewObject) -> None: ...
    def attach(self, vobj: ViewObject) -> None: ...
    def getIcon(self) -> str: ...  # piece-de-bois.svg
    def updateData(
        self, obj: DocumentObject, prop: str
    ) -> None: ...  # "MaterialId" → couleur, hors restauration
    def onChanged(self, vobj: ViewObject, prop: str) -> None: ...
    def dumps(self) -> None: ...
    def loads(self, state: object) -> None: ...
    # J1c :
    def setEdit(
        self, vobj: ViewObject, mode: int
    ) -> bool | None: ...  # mode 0 : panneau ; sinon None
    def unsetEdit(self, vobj: ViewObject, mode: int) -> bool | None: ...
    def doubleClicked(self, vobj: ViewObject) -> bool: ...
```

Couleur : couleur du matériau de la bibliothèque appliquée à `ShapeAppearance` (couleur diffuse,
présente en 1.0 et 1.1) ; si le matériau est inconnu localement, la couleur enregistrée est conservée.

### 4.5 Commande et panneau de tâche (J1c)

#### `gui/commands/wood_part.py`

```python
COMMAND_NAME: Final = "Menuiserie_WoodPart"


class CreateWoodPartCommand:
    def GetResources(
        self,
    ) -> dict[str, str]: ...  # Pixmap, MenuText « Pièce de bois », ToolTip (QT_TRANSLATE_NOOP)
    def IsActive(self) -> bool: ...  # document actif et aucun panneau de tâche ouvert
    def Activated(self) -> None: ...


def register() -> None: ...  # Gui.addCommand(COMMAND_NAME, CreateWoodPartCommand())
```

`Activated` : `doc.openTransaction(translate("Menuiserie", "Créer une pièce de bois"))`,
`api.make_wood_part(doc=doc)`, puis `Gui.Control.showDialog(WoodPartTaskPanel(obj, creating=True))`.

`init_gui.py` : dans `Initialize()`, import différé de `gui.commands.wood_part`, appel de
`register()` ; `commands = ("Menuiserie_WoodPart",)`.

#### `gui/task_panels/wood_part.py` + `wood_part.ui`

```python
class WoodPartTaskPanel:
    def __init__(
        self, obj: DocumentObject, *, creating: bool
    ) -> None: ...  # form = Gui.PySideUic.loadUi(...)
    def accept(self) -> bool: ...
    def reject(self) -> bool: ...
    def getStandardButtons(self) -> int: ...  # Ok | Cancel
```

Formulaire (`.ui`, chaînes traduisibles, champs de cote en `Gui::QuantitySpinBox` unité mm,
minimum strictement positif) :

| Zone | Widgets |
|---|---|
| Identification | Repère (`QLineEdit`) |
| Matériau | Type (`QComboBox` filtre : Tous, Massif, Contreplaqué, MDF, Mélaminé), Matériau (`QComboBox`, libellés), Sens du fil (`QComboBox` : Longueur, Largeur, Sans fil) |
| Dimensions finies | Longueur, Largeur, Épaisseur (`Gui::QuantitySpinBox`), bouton menu « Épaisseurs standard », étiquette d'avertissement « épaisseur hors standard pour ce panneau » |
| Surcotes de débit (repliable) | Longueur, Largeur, Épaisseur (`Gui::QuantitySpinBox`) |

- Les libellés d'énumération affichés sont traduits ; la valeur écrite reste la valeur stable
  (`Length`, `Width`, `None`).
- Chaque champ est lié par `Gui.ExpressionBinding(widget).bind(obj, prop)` ; chaque modification
  est écrite immédiatement dans l'objet puis `obj.recompute()` (aperçu en direct).
- Transactions : la création ouvre « Créer une pièce de bois » (commande) ; l'édition ouvre
  « Modifier une pièce de bois » dans `setEdit`. `accept` → `commitTransaction`,
  `reject` → `abortTransaction` (supprime la pièce en création, rétablit les valeurs en édition),
  puis `doc.recompute()` et `Gui.ActiveDocument.resetEdit()`.

### 4.6 Sécurité

Lecture des fichiers de matériaux en JSON uniquement, taille bornée avant lecture, toutes les
valeurs typées et bornées (§ 4.3.2) ; aucune écriture de fichier ; aucun chemin construit à partir
du contenu d'un document ; `api.py` est le seul module hors `gui/` autorisé à importer `gui/`, et
seulement sous `if App.GuiUp`.

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères |
|---|---|---|---|---|
| **J1a** | `feat/bibliotheque-materiaux` | `core/i18n.py`, `core/materials.py`, `core/part_model.py`, `data/materiaux.json`, ADR 0002 accepté | ≈ 320 lignes + 130 lignes de données | A1–A9 |
| **J1b** | `feat/piece-de-bois` | `features/library.py`, `features/wood_part.py`, `api.py`, ViewProvider (icône, couleur), icône SVG, README « Ajouter une essence », ADR 0003 accepté | ≈ 380 lignes | B1–B14 |
| **J1c** | `feat/panneau-piece-de-bois` | commande, panneau de tâche + `.ui`, édition au double-clic, `init_gui.py`, test G | ≈ 300 lignes + `.ui` | C1–C9 |

Chaque lot est livrable seul : J1a est invisible mais entièrement testé, J1b atteint déjà le
livrable du jalon par la console et l'éditeur de propriétés, J1c apporte l'outil graphique.

## 6. Compatibilité

- **Fichiers `.FCStd` existants** : aucun objet de l'atelier n'existe encore ; aucune migration
  n'est nécessaire. J1b introduit le **premier format persistant** (`Version` = 1).
- **Contrat de persistance** (ADR 0003), vérifié par test : chemins
  `freecad.menuiserie.features.wood_part.WoodPart` et
  `freecad.menuiserie.gui.view_providers.wood_part.ViewProviderWoodPart`, noms des propriétés,
  valeurs des énumérations (ajout en fin seulement), unités. Toute évolution passe par
  `Version` + `_migrate` dans `onDocumentRestored`, avec un test de réouverture d'un fichier ancien.
- **Fichiers de bibliothèque** : `format` = 1 ; une version future qui change le format devra
  continuer à lire le format 1.
- **FreeCAD 1.0 et 1.1** : `App::PropertyDensity`, `ShapeAppearance` et `obj.State` existent dans
  les deux ; le dossier utilisateur peut être versionné selon la version (le fichier utilisateur
  suit la migration de FreeCAD, ou le paramètre `UserLibraryPath`).
- **Limite connue** : une pièce créée dans `freecadcmd` puis ouverte dans l'interface n'a pas de
  ViewProvider Python (icône et couleur génériques). Suivi par une issue dédiée (réparation à
  l'ouverture via un observateur de document côté interface).

## 7. Hors périmètre

- Liste de débit, regroupement, Spreadsheet, export CSV (J2) — seuls `PartRecord` et les calculs
  de volume / masse sont fournis.
- Commande « Mettre à jour depuis la bibliothèque » pour rafraîchir l'instantané d'un matériau.
- Page de préférences, éditeur graphique de la bibliothèque, plusieurs fichiers utilisateur.
- Choix de la langue des libellés de matériaux (toujours `fr` en J1) et fichiers `.ts`/`.qm` (J5) ;
  les chaînes sont seulement marquées.
- Intégration au système de matériaux natif de FreeCAD (`.FCMat`, `ShapeMaterial`).
- Sections non rectangulaires, chanfreins, profils ; orientation prédéfinie (debout, de chant) :
  on utilise `Placement`.
- Numérotation automatique des repères, quantités et Links (J2/J4), prix, humidité, choix de
  l'épaisseur brute de débit.
- Assemblages (J3).

## 8. Questions ouvertes pour jv

**Q1 — Masse volumique figée dans la pièce ou lue en direct dans la bibliothèque ?**
Si vous corrigez la densité du chêne dans votre fichier, faut-il que les pièces existantes changent
de masse ?
*Recommandation : figée (instantané au choix du matériau).* Un plan donne la même liste de débit sur
toutes les machines et dans le temps ; une commande explicite « Mettre à jour depuis la
bibliothèque » viendra plus tard. (ADR 0002)

**Q2 — Surcotes de débit par défaut.**
Proposition : surcotes **totales** (et non par face), massif : longueur + 20 mm, largeur + 5 mm,
épaisseur + 0 mm (l'épaisseur brute se choisit en débit) ; panneaux : 0 / 0 / 0.
*Recommandation : ces valeurs, modifiables par pièce ; une préférence globale viendra avec la page
de préférences.* Quelles valeurs utilisez-vous à l'atelier ?

**Q3 — Le type (massif / contreplaqué / MDF / mélaminé) est déduit du matériau.**
Le plan listait « essence » et « type » comme deux propriétés. Les rendre indépendantes permettrait
des combinaisons absurdes (« chêne » + « MDF »). Je propose que le type soit une caractéristique du
matériau de la bibliothèque, affiché en lecture seule sur la pièce et utilisé comme filtre dans le
panneau ; un contreplaqué plaqué chêne serait un matériau à part entière (`cp-chene`).
*Recommandation : type déduit du matériau.* (ADR 0002)
