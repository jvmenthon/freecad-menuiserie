# SPDX-License-Identifier: LGPL-2.1-or-later
"""Constructeur unique des gabarits (J4d, ADR 0010) : un :class:`Layout` devient des objets
ordinaires du document.

Pièces de bois (``create_wood_part``), assemblages de J3 (``create_joint``), Ensemble
(``create_furniture``) dont les pièces reçoivent le mode et les options « fixe » du gabarit,
puis leurs liaisons. Aucun objet « gabarit » n'est gardé : ``Template`` de l'ensemble n'est
qu'une information. Tout est contrôlé avant la première création (matériaux, ensemble parent,
libellé) ; ni transaction ni recalcul : c'est à l'appelant (``api.py``, commande) de les faire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.furniture import Notice, label_reference
from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.templates import Layout, PieceSpec
from freecad.menuiserie.core.templates.carcass import (
    CarcassParams,
    carcass_layout,
    check_materials,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import create_furniture, writing
from freecad.menuiserie.features.furniture_members import (
    add_members,
    checked_furniture,
    join_with_options,
)
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.joints.dowels import DowelJoint
from freecad.menuiserie.features.joints.factories import create_joint
from freecad.menuiserie.features.joints.rabbet import RabbetJoint
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.wood_part import create_wood_part, validated_arguments

__all__ = ["Built", "build_carcass", "build_layout"]

# Assemblages qu'un gabarit peut demander (ajouts en même temps qu'un gabarit qui s'en sert).
JOINT_CLASSES: Final[dict[JointKind, type[JointFeature]]] = {
    cls.KIND: cls for cls in (DowelJoint, RabbetJoint)
}
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » appartient à un autre document."
)


@dataclass(frozen=True)
class Built:
    """Objets créés par un gabarit : l'ensemble, ses pièces (brutes), leurs pièces usinées
    et les assemblages, avec les avertissements (non traduits)."""

    furniture: DocumentObject
    parts: tuple[DocumentObject, ...]
    machined: tuple[DocumentObject, ...]
    joints: tuple[DocumentObject, ...]
    notices: tuple[Notice, ...]


def _placement(origin: Vec3, transform: RigidTransform) -> object:
    """``Placement`` FreeCAD de ``transform`` décalé de ``origin``."""
    rows = transform.rotation
    base = transform.translation
    return App.Placement(
        App.Matrix(
            *rows[0], base.x + origin.x,
            *rows[1], base.y + origin.y,
            *rows[2], base.z + origin.z,
            0.0, 0.0, 0.0, 1.0,
        )
    )  # fmt: skip


def _checked(doc: Document, layout: Layout, parent: DocumentObject | None) -> DocumentObject | None:
    """Contrôles avant toute création ; renvoie le conteneur commun (celui du parent)."""
    for piece in layout.pieces:
        size = piece.block.dimensions
        validated_arguments(size.length, size.width, size.thickness, piece.material_id)
    with translated_errors():
        label_reference(translated(layout.label))
    if parent is None:
        return None
    checked_furniture(parent)
    if parent.Document != doc:
        raise ValueError(translated(_OTHER_DOCUMENT, {"label": quoted_value(parent.Label)}))
    container: DocumentObject | None = parent.getParentGeoFeatureGroup()
    return container


def _part(
    doc: Document, piece: PieceSpec, origin: Vec3, container: DocumentObject | None
) -> DocumentObject:
    """Pièce de bois de ``piece``, placée dans le repère du conteneur."""
    size = piece.block.dimensions
    obj = create_wood_part(
        doc,
        length=size.length,
        width=size.width,
        thickness=size.thickness,
        material_id=piece.material_id,
    )
    obj.Label = translated(piece.label)
    obj.Placement = _placement(origin, piece.block.placement)
    if container is not None:
        container.addObject(obj)
    return obj


def build_layout(doc: Document, layout: Layout, parent: DocumentObject | None = None) -> Built:
    """Crée les pièces, les assemblages et l'ensemble de ``layout`` dans ``doc`` (dans le
    conteneur de ``parent``, dont le nouvel ensemble devient un sous-ensemble, options par
    défaut vis-à-vis de lui). ``TypeError`` ou ``ValueError`` traduites avant toute création."""
    container = _checked(doc, layout, parent)
    parts = {piece.key: _part(doc, piece, layout.origin, container) for piece in layout.pieces}
    joints = [
        create_joint(
            JOINT_CLASSES[spec.kind], doc, parts[spec.host], parts[spec.guest], spec.params
        )
        for spec in layout.joints
    ]
    furniture = create_furniture(
        doc, layout.box, layout.origin, translated(layout.label), container
    )
    with writing(furniture):
        furniture.Template = layout.template
    entries = [(parts[piece.key], piece.mode, piece.fixed) for piece in layout.pieces]
    notices = join_with_options(furniture, entries)
    if parent is not None:
        notices += add_members(parent, [furniture])
    machined = [machined_part_of(obj) for obj in parts.values()]
    return Built(
        furniture,
        tuple(parts.values()),
        tuple(obj for obj in machined if obj is not None),
        tuple(joints),
        tuple(notices),
    )


def build_carcass(
    doc: Document, params: CarcassParams, parent: DocumentObject | None = None
) -> Built:
    """Caisson (:func:`carcass_layout`) ; matériaux contrôlés dans la bibliothèque."""
    with translated_errors():
        check_materials(params, {material.id for material in get_library()})
    return build_layout(doc, carcass_layout(params), parent)
