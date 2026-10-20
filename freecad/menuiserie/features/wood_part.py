# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce de bois paramétrique : proxy ``WoodPart`` du FeaturePython et fonctions utilitaires.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``WoodPart``,
les noms des propriétés et les valeurs des énumérations sont écrits dans les documents ; ils
ne changent jamais. Toute évolution passe par ``Version`` et :meth:`WoodPart._migrate`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind, MaterialLibrary
from freecad.menuiserie.core.part_model import (
    Allowances,
    Dimensions,
    GrainDirection,
    InvalidDimensionsError,
    PartRecord,
    allowances_after_material_change,
    default_allowances,
    grain_after_material_change,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.library import display_language, get_library, translated

DocumentObject = Any  # objets FreeCAD, sans annotations de type
Document = Any

OBJECT_NAME: Final = "WoodPart"
DENSITY_UNIT: Final = "kg/m^3"
CATEGORY_BY_KIND: Final[Mapping[MaterialKind, str]] = MappingProxyType(
    {
        MaterialKind.SOLID: "Solid",
        MaterialKind.PLYWOOD: "Plywood",
        MaterialKind.MDF: "MDF",
        MaterialKind.MELAMINE: "Melamine",
    }
)
# Valeurs des énumérations, stockées dans les documents : ordre figé, ajouts en fin seulement.
CATEGORIES: Final = tuple(CATEGORY_BY_KIND.values())
GRAIN_DIRECTIONS: Final = tuple(grain.value for grain in GrainDirection)
KIND_BY_CATEGORY: Final = {category: kind for kind, category in CATEGORY_BY_KIND.items()}

_EDITABLE: Final = 0
_READ_ONLY: Final = 1
_HIDDEN: Final = 2
DEFAULT_DIMENSIONS: Final = Dimensions(800.0, 200.0, 22.0)
# Version du modèle de données (propriété ``Version``), cf. :meth:`WoodPart._migrate`.
MODEL_VERSION: Final = 1

_DEFAULT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce de bois")
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois."
)
EMPTY_LIBRARY_MIGRATION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : bibliothèque de matériaux vide, propriétés manquantes recréées avec "
    "des valeurs par défaut (massif si la catégorie manque).",
)
_INVALID_VERSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : version du modèle illisible (« {value} »), document traité comme un "
    "ancien fichier (version 0).",
)
_NEWER_VERSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : document créé par une version plus récente de l'atelier (modèle "
    "{version}, {supported} au plus ici) ; mettez l'atelier à jour avant de le modifier.",
)
_UNKNOWN_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : valeur « {value} » inconnue pour {property}, remplacée par "
    "« {replacement} ».",
)
_MISSING_MATERIAL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : matériau « {id} » absent de la bibliothèque locale, "
    "valeurs enregistrées conservées (masse volumique, catégorie, libellé).",
)


@dataclass(frozen=True)
class _PropertySpec:
    """Propriété de la pièce : type FreeCAD, groupe, mode d'édition et infobulle."""

    name: str
    type_id: str
    group: str
    mode: int
    tooltip: str


_PROPERTIES: Final = (
    _PropertySpec(
        "Length",
        "App::PropertyLength",
        "Dimensions",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Longueur finie de la pièce, mesurée selon l'axe X local."
        ),
    ),
    _PropertySpec(
        "Width",
        "App::PropertyLength",
        "Dimensions",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Largeur finie de la pièce, mesurée selon l'axe Y local."
        ),
    ),
    _PropertySpec(
        "Thickness",
        "App::PropertyLength",
        "Dimensions",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Épaisseur finie de la pièce, mesurée selon l'axe Z local."
        ),
    ),
    _PropertySpec(
        "Material",
        "App::PropertyEnumeration",
        "Matériau",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Essence ou panneau, choisi dans la bibliothèque de matériaux."
        ),
    ),
    _PropertySpec(
        "MaterialId",
        "App::PropertyString",
        "Matériau",
        _READ_ONLY,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Identifiant stable du matériau dans la bibliothèque. C'est lui qui est enregistré "
            "et utilisé par les calculs.",
        ),
    ),
    _PropertySpec(
        "Category",
        "App::PropertyEnumeration",
        "Matériau",
        _READ_ONLY,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Type de matériau, déduit du matériau choisi : massif ou panneau (contreplaqué, "
            "MDF, mélaminé).",
        ),
    ),
    _PropertySpec(
        "Density",
        "App::PropertyDensity",
        "Matériau",
        _READ_ONLY,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Masse volumique recopiée de la bibliothèque au choix du matériau ; sert au calcul "
            "de la masse.",
        ),
    ),
    _PropertySpec(
        "GrainDirection",
        "App::PropertyEnumeration",
        "Matériau",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Sens du fil par rapport aux cotes de la pièce : le long de la longueur, de la "
            "largeur, ou sans fil (MDF, mélaminé uni).",
        ),
    ),
    _PropertySpec(
        "Mark",
        "App::PropertyString",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 »). Des "
            "pièces identiques peuvent partager le même repère.",
        ),
    ),
    _PropertySpec(
        "LengthAllowance",
        "App::PropertyLength",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit.",
        ),
    ),
    _PropertySpec(
        "WidthAllowance",
        "App::PropertyLength",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit.",
        ),
    ),
    _PropertySpec(
        "ThicknessAllowance",
        "App::PropertyLength",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit.",
        ),
    ),
    _PropertySpec(
        "Version",
        "App::PropertyInteger",
        "Base",
        _HIDDEN,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers.",
        ),
    ),
)
TYPE_BY_NAME: Final = MappingProxyType({spec.name: spec.type_id for spec in _PROPERTIES})


class WoodPart:
    """Proxy du FeaturePython « pièce de bois ». Chemin de module figé (ADR 0003).

    Le proxy ne porte aucun état : tout est dans les propriétés de l'objet. Le drapeau de
    resynchronisation ``_syncing`` est lu avec ``getattr`` car ``__init__`` n'est pas rappelé
    à la réouverture d'un document.
    """

    TYPE: ClassVar[str] = "Menuiserie::WoodPart"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        obj.Proxy = self
        library = get_library()
        with self._synchronizing():
            add_missing_properties(obj, library, library.default_material())
            apply_editor_modes(obj)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version contrôlée, énumérations canoniques, migration, modes d'édition, puis liste des
        matériaux de la bibliothèque locale."""
        with self._synchronizing():
            version = restored_version(obj)
            restore_enumerations(obj, get_library())
            self._migrate(obj, version)
            apply_editor_modes(obj)
            restore_material_choices(obj, get_library())

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Choix d'un matériau dans la liste : recopie son identifiant, sa catégorie, sa masse
        volumique, et ajuste le fil et les surcotes (règles de ``core.part_model``)."""
        if prop != "Material" or not self._follows_user_changes(obj):
            return
        material = get_library().find_by_name(obj.Material, display_language())
        if material is not None:
            self.select_material(obj, material)

    def execute(self, obj: DocumentObject) -> None:
        """Reconstruit la forme depuis les seules cotes, sans toucher au ``Placement``."""
        try:
            dimensions = dimensions_of(obj)
        except InvalidDimensionsError as error:
            raise ValueError(_dimension_message(error)) from error
        placement = obj.Placement
        obj.Shape = Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)
        obj.Placement = placement

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state

    def select_material(self, obj: DocumentObject, material: Material) -> None:
        """Sélectionne ``material`` dans la liste et recopie ses valeurs dans la pièce."""
        with self._synchronizing():
            label = material.name(display_language())
            select_label(obj, material_choices(get_library(), label), label)
            _apply_material(obj, material)

    def _follows_user_changes(self, obj: DocumentObject) -> bool:
        """Faux pendant une resynchronisation interne, une restauration ou une annulation."""
        syncing: bool = getattr(self, "_syncing", False)
        return not syncing and "Restore" not in obj.State and not obj.Document.Transacting

    @contextmanager
    def _synchronizing(self) -> Iterator[None]:
        previous: bool = getattr(self, "_syncing", False)
        self._syncing = True
        try:
            yield
        finally:
            self._syncing = previous

    def _migrate(self, obj: DocumentObject, from_version: int) -> None:
        """Version 0 (absente) → 1 : ajoute les propriétés manquantes avec leurs défauts, déduits
        du matériau de la pièce (``MaterialId``). Aboutit même si la bibliothèque est vide."""
        if from_version >= self.VERSION:
            return
        library = get_library()
        if not len(library):
            warn(obj, EMPTY_LIBRARY_MIGRATION)
        add_missing_properties(obj, library, migration_material(obj, library))
        obj.Version = self.VERSION


def create_wood_part(
    doc: Document,
    *,
    length: float = DEFAULT_DIMENSIONS.length,
    width: float = DEFAULT_DIMENSIONS.width,
    thickness: float = DEFAULT_DIMENSIONS.thickness,
    material_id: str | None = None,
    mark: str = "",
) -> DocumentObject:
    """Crée une pièce de bois dans ``doc`` (sans ViewProvider ni transaction ni recalcul).

    Cotes en mm ; ``material_id`` vaut par défaut le matériau par défaut de la bibliothèque.
    ``InvalidDimensionsError`` ou ``UnknownMaterialError`` sont levées avant toute création.
    """
    dimensions, material = validated_arguments(length, width, thickness, material_id)
    obj = doc.addObject("Part::FeaturePython", OBJECT_NAME)
    proxy = WoodPart(obj)
    obj.Label = translated(_DEFAULT_LABEL)
    proxy.select_material(obj, material)
    obj.Length = dimensions.length
    obj.Width = dimensions.width
    obj.Thickness = dimensions.thickness
    obj.Mark = mark
    return obj


def validated_arguments(
    length: float, width: float, thickness: float, material_id: str | None
) -> tuple[Dimensions, Material]:
    """Cotes et matériau d'une future pièce, sans rien créer : ``InvalidDimensionsError`` ou
    ``UnknownMaterialError`` (matériau inconnu, bibliothèque vide) s'ils sont refusés."""
    dimensions = Dimensions(length, width, thickness)
    library = get_library()
    material = library.default_material() if material_id is None else library.get(material_id)
    return dimensions, material


def is_wood_part(obj: object) -> bool:
    """Vrai si ``obj`` est une pièce de bois de l'atelier (faux pour un objet supprimé)."""
    try:
        proxy = getattr(obj, "Proxy", None)
    except ReferenceError:  # objet FreeCAD supprimé du document
        return False
    return isinstance(proxy, WoodPart)


def set_material(obj: DocumentObject, material_id: str) -> None:
    """Change le matériau de la pièce (``UnknownMaterialError`` si l'identifiant est inconnu)."""
    if not is_wood_part(obj):
        raise TypeError(translated(_NOT_A_WOOD_PART, {"label": str(obj.Label)}))
    obj.Proxy.select_material(obj, get_library().get(material_id))


def dimensions_of(obj: DocumentObject) -> Dimensions:
    """Cotes finies de la pièce en mm (``InvalidDimensionsError`` si l'une est invalide)."""
    return Dimensions(obj.Length.Value, obj.Width.Value, obj.Thickness.Value)


def allowances_of(obj: DocumentObject) -> Allowances:
    """Surcotes de débit de la pièce en mm."""
    return Allowances(
        obj.LengthAllowance.Value, obj.WidthAllowance.Value, obj.ThicknessAllowance.Value
    )


def record_of(obj: DocumentObject) -> PartRecord:
    """Pièce vue par la liste de débit (J2), d'après ses seules propriétés."""
    return PartRecord(
        mark=obj.Mark,
        material_id=obj.MaterialId,
        material_name=obj.Material,
        kind=KIND_BY_CATEGORY[obj.Category],
        finished=dimensions_of(obj),
        allowances=allowances_of(obj),
        grain=GrainDirection(obj.GrainDirection),
        density=float(obj.Density.getValueAs(DENSITY_UNIT)),
    )


def density_quantity(value_kg_m3: float) -> Any:
    """Masse volumique en unités FreeCAD (``Quantity``), depuis des kg/m³."""
    return App.Units.Quantity(f"{value_kg_m3} {DENSITY_UNIT}")


def _dimension_message(error: InvalidDimensionsError) -> str:
    """Message traduit d'une cote refusée, nom de la cote compris."""
    params = dict(error.params)
    params["field"] = translated(params["field"])
    return translated(error.template, params)


def migration_material(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau de la pièce d'après ``MaterialId`` ; s'il est absent ou inconnu localement, le
    matériau par défaut de la bibliothèque ; ``None`` si la bibliothèque est vide."""
    material_id = obj.MaterialId if "MaterialId" in obj.PropertiesList else ""
    material = library.find(material_id)
    if material is None and len(library):
        material = library.default_material()
    return material


def part_kind(obj: DocumentObject, material: Material | None) -> MaterialKind:
    """Famille de la pièce : sa catégorie, sinon celle de ``material``, sinon le massif."""
    if "Category" in obj.PropertiesList:
        return KIND_BY_CATEGORY[obj.Category]
    return material.kind if material is not None else MaterialKind.SOLID


def default_grain(kind: MaterialKind, material: Material | None) -> GrainDirection:
    """Fil par défaut d'une pièce de famille ``kind`` : celui de ``material`` s'il est de cette
    famille, sinon celui de la famille."""
    if material is not None and material.kind is kind:
        has_grain = material.has_grain
    else:
        has_grain = kind.has_grain_by_default
    return GrainDirection.LENGTH if has_grain else GrainDirection.NONE


def _default_values(obj: DocumentObject, material: Material | None) -> dict[str, object]:
    """Valeurs par défaut des propriétés : cotes de 800 x 200 x 22 mm, ``material``, puis
    catégorie, fil et surcotes de la famille de la pièce (:func:`part_kind`).

    Sans matériau (bibliothèque vide), ``Material``, ``MaterialId`` et ``Density`` n'ont pas de
    valeur par défaut : une propriété absente garde la valeur vide de son type.
    """
    kind = part_kind(obj, material)
    allowances = default_allowances(kind)
    values: dict[str, object] = {
        "Length": DEFAULT_DIMENSIONS.length,
        "Width": DEFAULT_DIMENSIONS.width,
        "Thickness": DEFAULT_DIMENSIONS.thickness,
        "Category": CATEGORY_BY_KIND[kind],
        "GrainDirection": default_grain(kind, material).value,
        "Mark": "",
        "LengthAllowance": allowances.length,
        "WidthAllowance": allowances.width,
        "ThicknessAllowance": allowances.thickness,
        "Version": MODEL_VERSION,
    }
    if material is not None:
        values["Material"] = material.name(display_language())
        values["MaterialId"] = material.id
        values["Density"] = density_quantity(material.density)
    return values


def add_missing_properties(
    obj: DocumentObject, library: MaterialLibrary, material: Material | None
) -> None:
    """Ajoute les propriétés absentes de ``obj``, à leur valeur par défaut (cf.
    :func:`_default_values`)."""
    defaults = _default_values(obj, material)
    enumerations = {
        "Material": material_choices(library),
        "Category": list(CATEGORIES),
        "GrainDirection": list(GRAIN_DIRECTIONS),
    }
    for spec in _PROPERTIES:
        if spec.name in obj.PropertiesList:
            continue
        obj.addProperty(spec.type_id, spec.name, spec.group, spec.tooltip)
        if spec.name in enumerations:
            setattr(obj, spec.name, enumerations[spec.name])
        if spec.name in defaults:
            setattr(obj, spec.name, defaults[spec.name])


def apply_editor_modes(obj: DocumentObject) -> None:
    for spec in _PROPERTIES:
        obj.setEditorMode(spec.name, spec.mode)


def material_choices(library: MaterialLibrary, current: str | None = None) -> list[str]:
    """Libellés de la bibliothèque, plus ``current`` s'il n'en fait pas partie."""
    lang = display_language()
    labels = [material.name(lang) for material in library]
    if current is not None and current not in labels:
        labels.append(current)
    return labels


def select_label(obj: DocumentObject, choices: list[str], label: str) -> None:
    """Liste et valeur de ``Material``, écrites seulement si elles changent."""
    if obj.getEnumerationsOfProperty("Material") != choices:
        obj.Material = choices
    if obj.Material != label:
        obj.Material = label


def _apply_material(obj: DocumentObject, material: Material) -> None:
    """Recopie le matériau dans la pièce ; fil et surcotes suivent les règles de ``core``."""
    old_kind = KIND_BY_CATEGORY[obj.Category]
    grain = grain_after_material_change(material, GrainDirection(obj.GrainDirection))
    allowances = allowances_after_material_change(old_kind, material.kind, allowances_of(obj))
    obj.MaterialId = material.id
    obj.Category = CATEGORY_BY_KIND[material.kind]
    obj.Density = density_quantity(material.density)
    obj.GrainDirection = grain.value
    obj.LengthAllowance = allowances.length
    obj.WidthAllowance = allowances.width
    obj.ThicknessAllowance = allowances.thickness


def restore_material_choices(obj: DocumentObject, library: MaterialLibrary) -> None:
    """Liste ``Material`` de la bibliothèque locale ; un matériau inconnu localement garde son
    libellé enregistré (ajouté à la liste) et ses valeurs, avec un avertissement."""
    material = library.find(obj.MaterialId)
    if material is None:
        label = obj.Material
        warn(obj, _MISSING_MATERIAL, id=obj.MaterialId)
    else:
        label = material.name(display_language())
    select_label(obj, material_choices(library, label), label)


def warn(obj: DocumentObject, template: str, **params: object) -> None:
    """Avertissement traduit dans la vue rapport. Le libellé de la pièce (``{label}``) et les
    ``params``, lus dans un document, y sont cités tronqués et échappés (``quoted_value``)."""
    quoted = {name: quoted_value(value) for name, value in params.items()}
    quoted["label"] = quoted_value(obj.Label)
    App.Console.PrintWarning(f"Menuiserie : {translated(template, quoted)}\n")


def restore_enumerations(obj: DocumentObject, library: MaterialLibrary) -> None:
    """Listes canoniques de ``Category`` et ``GrainDirection`` (celles du fichier sont des
    données externes) ; une valeur inconnue devient la catégorie du matériau de la pièce (ou
    ``Solid``) et le fil par défaut, avec un avertissement."""
    material_id = obj.MaterialId if "MaterialId" in obj.PropertiesList else ""
    material = library.find(material_id)
    kind = material.kind if material is not None else MaterialKind.SOLID
    _restore_enumeration(obj, "Category", CATEGORIES, CATEGORY_BY_KIND[kind])
    grain = default_grain(part_kind(obj, material), material)
    _restore_enumeration(obj, "GrainDirection", GRAIN_DIRECTIONS, grain.value)


def _restore_enumeration(
    obj: DocumentObject, name: str, choices: tuple[str, ...], fallback: str
) -> None:
    """Liste ``choices`` pour l'énumération ``name`` si elle existe ; valeur conservée si elle
    en fait partie, sinon remplacée par ``fallback``. N'écrit que ce qui change."""
    if name not in obj.PropertiesList:
        return
    value = getattr(obj, name)
    if obj.getEnumerationsOfProperty(name) != list(choices):
        setattr(obj, name, list(choices))
    if value not in choices:
        setattr(obj, name, fallback)
        warn(obj, _UNKNOWN_VALUE, property=name, value=value, replacement=fallback)
    elif getattr(obj, name) != value:
        setattr(obj, name, value)


def restored_version(obj: DocumentObject) -> int:
    """Version enregistrée de la pièce, 0 si elle est absente. D'un type inattendu, elle est
    supprimée (la migration la recrée) et vaut 0 ; plus récente que l'atelier, elle est gardée.
    Ces deux cas sont signalés par un avertissement."""
    if "Version" not in obj.PropertiesList:
        return 0
    if obj.getTypeIdOfProperty("Version") != TYPE_BY_NAME["Version"]:
        warn(obj, _INVALID_VERSION, value=obj.Version)
        obj.removeProperty("Version")
        return 0
    version: int = obj.Version
    if version > MODEL_VERSION:
        warn(obj, _NEWER_VERSION, version=version, supported=MODEL_VERSION)
    return version
