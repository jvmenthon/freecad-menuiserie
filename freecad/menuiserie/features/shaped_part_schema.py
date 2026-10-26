# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma de la pièce en bois : propriétés propres, valeurs par défaut et modes d'édition.

La pièce en bois (``ShapedPart``, ADR 0020) enveloppe la forme d'un corps FreeCAD. Elle porte les
propriétés de menuiserie de la pièce de bois (:data:`.wood_material.MATERIAL_PROPERTIES`, mêmes
noms, types et énumérations) et les siennes : la forme liée (``Source``), le repère de la pièce
dans le repère de la source (``SourceAxes``), l'épaisseur du profil d'une esquisse, l'indice et
l'empreinte du solide d'une forme importée, et ses trois cotes d'encombrement, en sortie. Les
noms et valeurs écrits dans les documents relèvent du contrat de persistance (ADR 0003).
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    EDITABLE,
    HIDDEN,
    READ_ONLY,
    DocumentObject,
)
from freecad.menuiserie.features.schema import LENGTH, PropertySpec
from freecad.menuiserie.features.wood_material import (
    MATERIAL_PROPERTIES,
    VERSION_SPEC,
    apply_material_modes,
    is_newer_version,
    material_default_values,
    material_enumerations,
)

__all__ = [
    "DEFAULT_PROFILE_THICKNESS",
    "DIMENSION_NAMES",
    "MODEL_VERSION",
    "NOUN",
    "PROPERTIES",
    "add_missing_properties",
    "apply_editor_modes",
    "is_from_newer_version",
]

DEFAULT_PROFILE_THICKNESS: Final = 22.0
# Version du modèle de données (propriété ``Version``).
MODEL_VERSION: Final = 1
# Cotes d'encombrement, écrites par ``execute()`` (exception documentée de CONTRIBUTING).
DIMENSION_NAMES: Final = ("Length", "Width", "Thickness")
# Statut des propriétés que ``execute()`` écrit : FreeCAD ne remet pas l'objet à recalculer.
OUTPUT_STATUS: Final = "Output"
# Genre de l'objet cité par les avertissements de la réouverture.
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce en bois")

_SHAPE_PROPERTIES: Final = (
    PropertySpec(
        "Source",
        "App::PropertyLink",
        "Forme",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Corps, forme ou esquisse dessiné avec les outils de FreeCAD, dont la pièce reprend "
            "la forme. Il n'est jamais modifié par l'atelier.",
        ),
    ),
    PropertySpec(
        "SourceAxes",
        "App::PropertyPlacement",
        "Forme",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Repère de la pièce (longueur, largeur, épaisseur) dans le repère de la source. Il est "
            "calculé à la conversion puis gardé quand le dessin change.",
        ),
        mode=HIDDEN,
    ),
    PropertySpec(
        "ProfileThickness",
        LENGTH,
        "Forme",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Épaisseur de la pièce tirée d'une esquisse fermée, mesurée selon la normale de "
            "l'esquisse.",
        ),
        mode=HIDDEN,
    ),
    PropertySpec(
        "SolidIndex",
        "App::PropertyInteger",
        "Forme",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Rang du solide de la source converti en cette pièce (forme importée à plusieurs "
            "solides) ; -1 si la source n'a qu'un solide.",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "SolidSignature",
        "App::PropertyString",
        "Forme",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Empreinte (volume, aire, inertie, centre de masse) du solide converti, contrôlée à "
            "chaque recalcul pour ne jamais prendre un solide pour un autre.",
        ),
        mode=HIDDEN,
    ),
)
_DIMENSIONS: Final = (
    PropertySpec(
        "Length",
        LENGTH,
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Longueur de l'encombrement de la pièce selon l'axe X local, déduite du dessin "
            "(lecture seule).",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Width",
        LENGTH,
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Largeur de l'encombrement de la pièce selon l'axe Y local, déduite du dessin "
            "(lecture seule).",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Thickness",
        LENGTH,
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Épaisseur de l'encombrement de la pièce selon l'axe Z local, déduite du dessin "
            "(lecture seule).",
        ),
        mode=READ_ONLY,
    ),
)
_VERSION: Final = (VERSION_SPEC,)
# Toutes les propriétés, dans l'ordre d'ajout : forme, cotes, matériau et repère, version.
PROPERTIES: Final = (*_SHAPE_PROPERTIES, *_DIMENSIONS, *MATERIAL_PROPERTIES, *_VERSION)
# Propriétés au mode d'édition fixe (les autres dépendent de la pièce, cf. apply_editor_modes).
_FIXED_MODES: Final = (
    *(spec for spec in _SHAPE_PROPERTIES if spec.name not in ("ProfileThickness", "SolidIndex")),
    *_DIMENSIONS,
    *_VERSION,
)


def _default_values(obj: DocumentObject, material: Material | None) -> dict[str, object]:
    """Valeurs par défaut : celles du matériau (:func:`.wood_material.material_default_values`),
    repère de la source neutre, épaisseur de profil de 22 mm, aucun solide désigné."""
    return {
        **material_default_values(obj, material),
        "SourceAxes": App.Placement(),
        "ProfileThickness": DEFAULT_PROFILE_THICKNESS,
        "SolidIndex": -1,
        "Version": MODEL_VERSION,
    }


def add_missing_properties(
    obj: DocumentObject, library: MaterialLibrary, material: Material | None
) -> None:
    """Ajoute les propriétés absentes de ``obj``, à leur valeur par défaut (cf.
    :func:`_default_values`) ; les cotes d'encombrement reçoivent le statut ``Output``."""
    schema.add_missing_properties(
        obj, PROPERTIES, _default_values(obj, material), material_enumerations(library)
    )
    mark_outputs(obj)


def mark_outputs(obj: DocumentObject) -> None:
    """Statut ``Output`` des cotes d'encombrement présentes (écrit seulement s'il manque) : leur
    écriture par ``execute()`` ne remet pas l'objet à recalculer."""
    for name in DIMENSION_NAMES:
        if name in obj.PropertiesList and OUTPUT_STATUS not in obj.getPropertyStatus(name):
            obj.setPropertyStatus(name, OUTPUT_STATUS)


def apply_editor_modes(
    obj: DocumentObject,
    *,
    show_grain: bool = True,
    material_read_only: bool = False,
    profile: bool = False,
) -> None:
    """Modes d'édition des propriétés présentes, ceux du schéma sauf trois cas qui dépendent de
    la pièce : ``GrainDirection`` masquée si ``show_grain`` est faux, ``Material`` en lecture
    seule si ``material_read_only`` est vrai, ``ProfileThickness`` modifiable si ``profile`` (la
    source est une esquisse) et masquée sinon, ``SolidIndex`` en lecture seule s'il désigne un
    solide et masqué sinon. Une propriété absente est ignorée ; ``setEditorMode`` n'est appelé
    que si le mode change."""
    schema.apply_editor_modes(obj, _FIXED_MODES)
    apply_material_modes(obj, show_grain=show_grain, material_read_only=material_read_only)
    mark_outputs(obj)
    if "ProfileThickness" in obj.PropertiesList:
        schema.set_editor_mode(obj, "ProfileThickness", EDITABLE if profile else HIDDEN)
    if "SolidIndex" in obj.PropertiesList:
        indexed = obj.SolidIndex >= 0
        schema.set_editor_mode(obj, "SolidIndex", READ_ONLY if indexed else HIDDEN)


def is_from_newer_version(obj: DocumentObject) -> bool:
    """Vrai si ``Version`` de la pièce dépasse ``MODEL_VERSION`` : document créé par une version
    plus récente de l'atelier, dont le matériau n'est pas modifiable ici."""
    return is_newer_version(obj, MODEL_VERSION)
