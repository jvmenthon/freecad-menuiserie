# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce de bois paramétrique : proxy ``WoodPart`` du FeaturePython et fonctions utilitaires.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``WoodPart``,
les noms des propriétés et les valeurs des énumérations sont écrits dans les documents ; ils
ne changent jamais. Toute évolution passe par ``Version`` et :meth:`WoodPart._migrate`.

Les propriétés et leurs valeurs par défaut sont décrites dans :mod:`.wood_part_schema`, les
contrôles de la réouverture dans :mod:`.wood_part_restore`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, ClassVar, Final

import Part

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.part_model import (
    Allowances,
    Dimensions,
    GrainDirection,
    InvalidDimensionsError,
    PartRecord,
    allowances_after_material_change,
    grain_after_material_change,
)
from freecad.menuiserie.features.library import display_language, get_library, translated
from freecad.menuiserie.features.wood_part_restore import (
    EMPTY_LIBRARY_MIGRATION,
    migration_material,
    remove_mistyped_properties,
    restore_enumerations,
    restore_material_choices,
    restored_version,
    warn,
)
from freecad.menuiserie.features.wood_part_schema import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    DEFAULT_DIMENSIONS,
    GRAIN_DIRECTIONS,
    KIND_BY_CATEGORY,
    MODEL_VERSION,
    add_missing_properties,
    apply_editor_modes,
    density_kg_m3,
    density_quantity,
    material_choices,
    select_label,
)

__all__ = [
    "CATEGORIES",
    "CATEGORY_BY_KIND",
    "GRAIN_DIRECTIONS",
    "OBJECT_NAME",
    "WoodPart",
    "allowances_of",
    "create_wood_part",
    "dimensions_of",
    "is_wood_part",
    "record_of",
    "set_material",
    "validated_arguments",
]

DocumentObject = Any  # objets FreeCAD, sans annotations de type
Document = Any

OBJECT_NAME: Final = "WoodPart"

_DEFAULT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce de bois")
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois."
)


class WoodPart:
    """Proxy du FeaturePython « pièce de bois ». Chemin de module figé (ADR 0003).

    Le proxy ne porte aucun état : tout est dans les propriétés de l'objet. Le drapeau de
    resynchronisation ``_syncing`` est lu avec ``getattr`` car ``__init__`` n'est pas rappelé
    à la réouverture d'un document.
    """

    TYPE: ClassVar[str] = "Menuiserie::WoodPart"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la pièce, aux valeurs du matériau par défaut de la
        bibliothèque. :func:`create_wood_part` valide cotes et matériau avant de l'appeler.

        Appelé directement avec une bibliothèque vide, il lève ``UnknownMaterialError`` (une
        ``KeyError``) : ``obj.Proxy`` est déjà assigné mais aucune propriété n'est ajoutée,
        l'objet est inutilisable et c'est à l'appelant de le supprimer du document.
        """
        obj.Proxy = self
        library = get_library()
        with self._synchronizing():
            add_missing_properties(obj, library, library.default_material())
            apply_editor_modes(obj)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, énumérations canoniques, migration, modes
        d'édition, puis liste des matériaux de la bibliothèque locale."""
        library = get_library()
        with self._synchronizing():
            version = restored_version(obj)
            mistyped = remove_mistyped_properties(obj)
            restore_enumerations(obj, library, keep_unknown=version > self.VERSION)
            self._migrate(obj, library, version, repair=bool(mistyped))
            apply_editor_modes(obj)
            restore_material_choices(obj, library)

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

    def _migrate(
        self, obj: DocumentObject, library: MaterialLibrary, from_version: int, *, repair: bool
    ) -> None:
        """Version 0 (absente) → 1 : ajoute les propriétés manquantes avec leurs défauts, déduits
        du matériau de la pièce (``MaterialId``). Aboutit même si la bibliothèque est vide.

        ``repair`` : à toute version, recrée de même les propriétés supprimées à la réouverture
        (type inattendu), sans changer la ``Version``."""
        outdated = from_version < self.VERSION
        if not (outdated or repair):
            return
        if not len(library):
            warn(obj, EMPTY_LIBRARY_MIGRATION)
        add_missing_properties(obj, library, migration_material(obj, library))
        if outdated:
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
        density=density_kg_m3(obj),
    )


def _dimension_message(error: InvalidDimensionsError) -> str:
    """Message traduit d'une cote refusée, nom de la cote compris."""
    params = dict(error.params)
    params["field"] = translated(params["field"])
    return translated(error.template, params)


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
