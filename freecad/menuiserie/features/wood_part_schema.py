# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma de la pièce de bois : propriétés, énumérations et valeurs par défaut.

Spécifications des propriétés (type, groupe, mode d'édition, infobulle), valeurs stockées des
énumérations, valeurs par défaut déduites du matériau, ajout des propriétés manquantes et modes
d'édition. Les noms et valeurs écrits dans les documents relèvent du contrat de persistance
(ADR 0003). Les propriétés de matériau, de fil, de repère et de surcotes sont partagées avec la
pièce en bois (ADR 0020) : elles sont définies dans :mod:`.wood_material`, ré-exportées ici.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import HIDDEN, DocumentObject
from freecad.menuiserie.features.schema import LENGTH, PropertySpec
from freecad.menuiserie.features.wood_material import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    DENSITY_DECIMALS,
    DENSITY_UNIT,
    GRAIN_DIRECTIONS,
    KIND_BY_CATEGORY,
    MATERIAL_PROPERTIES,
    PREFERRED_GRAIN_DIRECTIONS,
    apply_material_modes,
    default_grain,
    density_kg_m3,
    density_quantity,
    is_newer_version,
    material_choices,
    material_default_values,
    material_enumerations,
    material_kind,
    part_kind,
    preferred_grain_default,
    select_label,
    show_grain_direction,
)

__all__ = [
    "CATEGORIES",
    "CATEGORY_BY_KIND",
    "DEFAULT_DIMENSIONS",
    "DENSITY_DECIMALS",
    "DENSITY_UNIT",
    "GRAIN_DIRECTIONS",
    "KIND_BY_CATEGORY",
    "MODEL_VERSION",
    "NOUN",
    "PREFERRED_GRAIN_DIRECTIONS",
    "PROPERTIES",
    "add_missing_properties",
    "apply_editor_modes",
    "default_grain",
    "density_kg_m3",
    "density_quantity",
    "is_from_newer_version",
    "material_choices",
    "material_kind",
    "part_kind",
    "preferred_grain_default",
    "select_label",
    "show_grain_direction",
]

DEFAULT_DIMENSIONS: Final = Dimensions(800.0, 200.0, 22.0)
# Version du modèle de données (propriété ``Version``), cf. :meth:`WoodPart._migrate`.
MODEL_VERSION: Final = 2

_DIMENSIONS: Final = (
    PropertySpec(
        "Length",
        LENGTH,
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property", "Longueur finie de la pièce, mesurée selon l'axe X local."
        ),
    ),
    PropertySpec(
        "Width",
        LENGTH,
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property", "Largeur finie de la pièce, mesurée selon l'axe Y local."
        ),
    ),
    PropertySpec(
        "Thickness",
        LENGTH,
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property", "Épaisseur finie de la pièce, mesurée selon l'axe Z local."
        ),
    ),
)
_VERSION: Final = (
    PropertySpec(
        "Version",
        "App::PropertyInteger",
        "Base",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers.",
        ),
        mode=HIDDEN,
    ),
)
# Toutes les propriétés, dans l'ordre d'ajout : cotes, matériau et repère, version.
PROPERTIES: Final = (*_DIMENSIONS, *MATERIAL_PROPERTIES, *_VERSION)
# Genre de l'objet cité par les avertissements de la réouverture.
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce")


def _default_values(obj: DocumentObject, material: Material | None) -> dict[str, object]:
    """Valeurs par défaut des propriétés : cotes de 800 x 200 x 22 mm, puis celles du matériau
    (:func:`.wood_material.material_default_values`)."""
    return {
        **material_default_values(obj, material),
        "Length": DEFAULT_DIMENSIONS.length,
        "Width": DEFAULT_DIMENSIONS.width,
        "Thickness": DEFAULT_DIMENSIONS.thickness,
        "Version": MODEL_VERSION,
    }


def add_missing_properties(
    obj: DocumentObject, library: MaterialLibrary, material: Material | None
) -> None:
    """Ajoute les propriétés absentes de ``obj``, à leur valeur par défaut (cf.
    :func:`_default_values`)."""
    schema.add_missing_properties(
        obj, PROPERTIES, _default_values(obj, material), material_enumerations(library)
    )


def apply_editor_modes(
    obj: DocumentObject, *, show_grain: bool = True, material_read_only: bool = False
) -> None:
    """Modes d'édition des propriétés présentes, ceux du schéma (``PROPERTIES``), sauf deux
    cas qui dépendent de la pièce : ``GrainDirection`` est masquée si ``show_grain`` est faux
    (matériau sans fil) et ``Material`` est en lecture seule si ``material_read_only`` est vrai
    (pièce d'un document plus récent, :func:`is_from_newer_version`). Une propriété absente est
    ignorée ; ``setEditorMode`` n'est appelé que si le mode change."""
    schema.apply_editor_modes(obj, [*_DIMENSIONS, *_VERSION])
    apply_material_modes(obj, show_grain=show_grain, material_read_only=material_read_only)


def is_from_newer_version(obj: DocumentObject) -> bool:
    """Vrai si ``Version`` de la pièce dépasse ``MODEL_VERSION`` : document créé par une version
    plus récente de l'atelier, dont le matériau n'est pas modifiable ici (issue #13)."""
    return is_newer_version(obj, MODEL_VERSION)
