# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce de bois paramétrique : proxy ``WoodPart`` du FeaturePython et fonctions utilitaires.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``WoodPart``,
les noms des propriétés et les valeurs des énumérations sont écrits dans les documents ; ils
ne changent jamais. Toute évolution passe par ``Version`` et :meth:`WoodPart._migrate`.

Les propriétés et leurs valeurs par défaut sont décrites dans :mod:`.wood_part_schema`, les
contrôles de la réouverture dans :mod:`.wood_part_restore`.
"""

from __future__ import annotations

from typing import ClassVar, Final

import Part

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.features.freecad_types import Document, DocumentObject, proxy_is
from freecad.menuiserie.features.furniture import MEMBER_OPTIONS, remember_before_change
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.part_labels import make_label_unique
from freecad.menuiserie.features.part_names import label_of_mark
from freecad.menuiserie.features.schema import warn
from freecad.menuiserie.features.wood_material import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    GRAIN_DIRECTIONS,
    UnsupportedPartError,
    allowances_of,
)
from freecad.menuiserie.features.wood_material import shows_grain as material_shows_grain
from freecad.menuiserie.features.wood_material_proxy import MaterialProxy
from freecad.menuiserie.features.wood_part_record import dimensions_of, record_of
from freecad.menuiserie.features.wood_part_restore import (
    EMPTY_LIBRARY_MIGRATION,
    migration_material,
    remove_mistyped_properties,
    restore_enumerations,
    restore_material_choices,
    restored_version,
)
from freecad.menuiserie.features.wood_part_schema import (
    DEFAULT_DIMENSIONS,
    MODEL_VERSION,
    add_missing_properties,
    apply_editor_modes,
    is_from_newer_version,
)

__all__ = [
    "CATEGORIES",
    "CATEGORY_BY_KIND",
    "GRAIN_DIRECTIONS",
    "OBJECT_NAME",
    "UnsupportedPartError",
    "WoodPart",
    "allowances_of",
    "create_wood_part",
    "dimensions_of",
    "is_wood_part",
    "record_of",
    "set_material",
    "shows_grain",
    "validated_arguments",
]

OBJECT_NAME: Final = "WoodPart"

_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois."
)


class WoodPart(MaterialProxy):
    """Proxy du FeaturePython « pièce de bois ». Chemin de module figé (ADR 0003).

    Le proxy ne porte aucun état : tout est dans les propriétés de l'objet. Matériau, fil, repère
    et libellé sont gérés par :class:`.MaterialProxy`, partagé avec la pièce en bois.
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

    def library(self) -> MaterialLibrary:
        """Bibliothèque de matériaux de la session."""
        return get_library()

    def language(self) -> str:
        """Langue des libellés de matériaux."""
        return display_language()

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, énumérations canoniques, migration, modes
        d'édition (``Material`` en lecture seule si le document est plus récent), puis liste des
        matériaux de la bibliothèque locale ; propriétés de membre d'un ensemble contrôlées de
        même (J4)."""
        library = get_library()
        with self._synchronizing():
            version = restored_version(obj)
            mistyped = remove_mistyped_properties(obj)
            restore_enumerations(obj, library, keep_unknown=version > self.VERSION)
            self._migrate(obj, library, version, repair=bool(mistyped))
            apply_editor_modes(
                obj,
                show_grain=material_shows_grain(obj, library),
                material_read_only=is_from_newer_version(obj),
            )
            restore_material_choices(obj, library)
        from freecad.menuiserie.features.furniture_restore import restore_member

        restore_member(obj)  # membre d'un ensemble (J4) ; sans effet sinon
        make_label_unique(obj)  # copie, duplication, fusion (J6, L5 bis)

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Matériau, fil, repère et libellé : voir :meth:`.MaterialProxy.onChanged`. Réglage ou
        épaisseur d'un membre d'ensemble : tout l'ensemble est relié (ADR 0019). Pièce d'un
        document plus récent (``Version`` > ``MODEL_VERSION``) : le choix du matériau n'est pas
        suivi (R1)."""
        super().onChanged(obj, prop)
        if (prop in MEMBER_OPTIONS or prop == "Thickness") and self._follows_user_changes(obj):
            from freecad.menuiserie.features.furniture_edits import member_changed

            member_changed(obj, prop)  # membre d'un ensemble (J4)

    def unsetupObject(self, obj: DocumentObject) -> None:
        """Pièce supprimée : ses voisines d'ensemble sont reliées sans elle (même transaction)."""
        from freecad.menuiserie.features.furniture_relink import member_removed

        member_removed(obj)

    def onBeforeChange(self, obj: DocumentObject, prop: str) -> None:
        """Épaisseur d'un membre d'ensemble avant une saisie, pour :meth:`onChanged`."""
        remember_before_change(obj, prop)

    def execute(self, obj: DocumentObject) -> None:
        """Reconstruit la forme depuis les seules cotes, sans toucher au ``Placement``."""
        with translated_errors():
            dimensions = dimensions_of(obj)
        placement = obj.Placement
        obj.Shape = Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)
        obj.Placement = placement

    def _migrate(
        self, obj: DocumentObject, library: MaterialLibrary, from_version: int, *, repair: bool
    ) -> None:
        """Version 0 (absente) ou 1 → 2 : ajoute les propriétés manquantes avec leurs défauts,
        déduits du matériau de la pièce (``MaterialId``), dont ``PreferredGrainDirection``
        d'après le fil (ADR 0005). Aboutit même si la bibliothèque est vide.

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
    proxy.select_material(obj, material)
    obj.Length = dimensions.length
    obj.Width = dimensions.width
    obj.Thickness = dimensions.thickness
    with proxy.synchronizing():  # le libellé est celui du repère (J6b), posé une seule fois
        obj.Mark = mark
        obj.Label = label_of_mark(obj, mark)
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
    return proxy_is(obj, WoodPart)


def set_material(obj: DocumentObject, material_id: str) -> None:
    """Change le matériau de la pièce (``UnknownMaterialError`` si l'identifiant est inconnu)."""
    if not is_wood_part(obj):
        raise TypeError(translated(_NOT_A_WOOD_PART, {"label": str(obj.Label)}))
    obj.Proxy.select_material(obj, get_library().get(material_id))


def shows_grain(obj: DocumentObject) -> bool:
    """Vrai si le fil de la pièce est visible : son matériau (ou, inconnu localement, sa
    famille) a un fil."""
    return material_shows_grain(obj, get_library())
