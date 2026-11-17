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

from collections.abc import Mapping
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
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_container import (
    create_with_std_part,
    is_std_part,
    std_part_of,
)
from freecad.menuiserie.features.furniture_detach import detach_members
from freecad.menuiserie.features.furniture_entry import taken_along
from freecad.menuiserie.features.furniture_members import (
    add_members,
    checked_furniture,
    join_with_options,
)
from freecad.menuiserie.features.furniture_plan import chain_of, plan_entry, split_creation
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.joints.dovetail import DovetailJoint
from freecad.menuiserie.features.joints.dowels import DowelJoint
from freecad.menuiserie.features.joints.factories import create_joint
from freecad.menuiserie.features.joints.miter import MiterJoint
from freecad.menuiserie.features.joints.rabbet import RabbetJoint
from freecad.menuiserie.features.joints.tongue_groove import TongueGrooveJoint
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import blank_of, machined_part_of
from freecad.menuiserie.features.wood_part import create_wood_part, validated_arguments

__all__ = ["Built", "build_carcass", "build_layout"]

# Assemblages qu'un gabarit peut demander (ajouts en même temps qu'un gabarit qui s'en sert).
JOINT_CLASSES: Final[dict[JointKind, type[JointFeature]]] = {
    cls.KIND: cls for cls in (DowelJoint, RabbetJoint, DovetailJoint, MiterJoint, TongueGrooveJoint)
}
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » appartient à un autre document."
)
_NO_ANCHOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ce gabarit ne part d'aucune pièce existante : rien à lui donner."
)
_MISSING_ANCHOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ce gabarit part d'une pièce existante, et d'une seule : elle manque."
)
_ANCHOR_CONTAINER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est dans « {container} » (corps ou autre conteneur) : sortez-la d'abord à la "
    "racine ou dans une pièce (Std Part).",
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


@dataclass(frozen=True)
class _Anchor:
    """Pièce déjà dans le document que le gabarit entoure (ADR 0064) : sa brute, l'ensemble
    qu'elle quitte (``None`` si elle est libre) et si elle avait déjà une pièce usinée."""

    obj: DocumentObject
    furniture: DocumentObject | None
    machined: bool


def _anchor_of(layout: Layout, existing: Mapping[str, DocumentObject] | None) -> _Anchor | None:
    """Ancre du gabarit parmi les pièces ``existing`` (clé → objet) ; ``TypeError`` ou
    ``ValueError`` traduites si elle manque ou si ``existing`` n'est pas attendu."""
    if layout.anchor is None:
        if existing:
            raise ValueError(translated(_NO_ANCHOR))
        return None
    obj = (existing or {}).get(layout.anchor)
    if obj is None or len(existing or {}) != 1:
        raise ValueError(translated(_MISSING_ANCHOR))
    blank = blank_of(obj)
    return _Anchor(blank, furniture_of(blank), machined_part_of(blank) is not None)


def _created(layout: Layout) -> list[PieceSpec]:
    """Pièces que le gabarit crée : toutes, sauf l'ancre."""
    return [piece for piece in layout.pieces if piece.key != layout.anchor]


def _anchor_container(doc: Document, anchor: _Anchor) -> DocumentObject | None:
    """Conteneur de l'ancre, où les pièces et l'ensemble sont créés : la racine, un Std Part ou
    le Std Part de son ensemble ; ``ValueError`` traduite avant toute création pour un autre
    conteneur (corps), un autre document, ou une ancre assemblée à une pièce qui reste ailleurs."""
    obj = anchor.obj
    if obj.Document != doc:
        raise ValueError(translated(_OTHER_DOCUMENT, {"label": quoted_value(obj.Label)}))
    container: DocumentObject | None = obj.getParentGeoFeatureGroup()
    if container is not None and not is_std_part(container):
        params = {"label": quoted_value(obj.Label), "container": quoted_value(container.Label)}
        raise ValueError(translated(_ANCHOR_CONTAINER, params))
    wanted = ("", *chain_of(anchor.furniture))
    split_creation(plan_entry([obj], wanted), wanted, anchor.furniture)
    return container


def _checked(
    doc: Document, layout: Layout, parent: DocumentObject | None, anchor: _Anchor | None
) -> DocumentObject | None:
    """Contrôles avant toute création ; renvoie le conteneur commun (celui du parent, ou de
    l'ancre)."""
    for piece in _created(layout):
        size = piece.block.dimensions
        validated_arguments(size.length, size.width, size.thickness, piece.material_id)
    with translated_errors():
        label_reference(translated(layout.label))
    if anchor is not None:
        return _anchor_container(doc, anchor)
    if parent is None:
        return None
    checked_furniture(parent)
    if parent.Document != doc:
        raise ValueError(translated(_OTHER_DOCUMENT, {"label": quoted_value(parent.Label)}))
    container: DocumentObject | None = parent.getParentGeoFeatureGroup()
    return container


def _frame(layout: Layout, anchor: _Anchor | None) -> App.Placement:
    """Placement du repère du gabarit dans le conteneur : neutre sans ancre ; avec une ancre,
    celui qui la laisse où elle est (``Placement`` de l'ancre ``A``, position ``M`` de son bloc
    dans le gabarit : repère = ``A · M⁻¹``). Une ancre tournée donne un repère tourné."""
    if anchor is None or layout.anchor is None:
        return App.Placement()
    held = _placement(layout.origin, layout.piece(layout.anchor).block.placement)
    return App.Placement(anchor.obj.Placement).multiply(held.inverse())


def _part(
    doc: Document,
    piece: PieceSpec,
    frame: App.Placement,
    origin: Vec3,
    container: DocumentObject | None,
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
    obj.Placement = frame.multiply(_placement(origin, piece.block.placement))
    if container is not None:
        container.addObject(obj)
    return obj


def _leave_ensemble(anchor: _Anchor) -> None:
    """L'ancre n'est plus membre de son ensemble (propriétés gardées : Ctrl+Z les rétablit) ;
    elle entre dans le nouvel ensemble, qui devient un sous-ensemble du premier (ADR 0037)."""
    if anchor.furniture is not None:
        detach_members([anchor.obj], keep_properties=True)


def build_layout(
    doc: Document,
    layout: Layout,
    parent: DocumentObject | None = None,
    existing: Mapping[str, DocumentObject] | None = None,
) -> Built:
    """Crée les pièces, les assemblages et l'ensemble de ``layout`` dans ``doc`` (dans le
    conteneur de ``parent``, dont le nouvel ensemble devient un sous-ensemble, options par
    défaut vis-à-vis de lui). Avec ``layout.anchor``, ``existing`` donne la pièce déjà dans le
    document (``{clé: objet}``) : elle n'est ni recréée, ni déplacée ; le repère du gabarit est le
    sien, et si elle est membre d'un ensemble elle en sort et le nouvel ensemble devient un
    sous-ensemble de celui-ci (``parent`` est alors ignoré). ``TypeError`` ou ``ValueError``
    traduites avant toute création."""
    anchor = _anchor_of(layout, existing)
    container = _checked(doc, layout, parent, anchor)
    frame = _frame(layout, anchor)
    taken: list[
        Notice
    ] = []  # pièces libres liées à l'ancre, rangées avec elle (avant nos assemblages)
    if anchor is not None:
        parent = anchor.furniture
        taken = taken_along([anchor.obj])
        _leave_ensemble(anchor)
    created = {
        piece.key: _part(doc, piece, frame, layout.origin, container) for piece in _created(layout)
    }
    parts = {**created, **({layout.anchor: anchor.obj} if anchor and layout.anchor else {})}
    joints = [
        create_joint(
            JOINT_CLASSES[spec.kind], doc, parts[spec.host], parts[spec.guest], spec.params
        )
        for spec in layout.joints
    ]
    furniture = create_with_std_part(
        doc, layout.box, layout.origin, translated(layout.label), container
    )
    if anchor is not None:
        std_part_of(furniture).Placement = frame  # type: ignore[union-attr]
    with writing(furniture):
        furniture.Template = layout.template
    entries = [(parts[piece.key], piece.mode, piece.fixed) for piece in layout.pieces]
    notices = [*taken, *join_with_options(furniture, entries)]
    if parent is not None:
        notices += add_members(parent, [furniture])
    machined = [
        machined_part_of(obj)
        for key, obj in parts.items()
        if not (anchor and key == layout.anchor and anchor.machined)
    ]
    return Built(
        furniture,
        tuple(created.values()),
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
