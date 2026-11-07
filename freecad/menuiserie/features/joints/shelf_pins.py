# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 du document : proxy ``ShelfPinsJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et des propriétés
figés. Le perçage concerne **un seul** côté debout : ``HostPart`` et ``GuestPart`` sont la même
pièce (le côté est percé, les taquets sont les pièces rapportées de la forme).
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any, ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointError, JointKind
from freecad.menuiserie.core.joints.shelf_pins import Neighbor, ShelfPinsParams, facing_side
from freecad.menuiserie.core.part_model import InvalidDimensionsError
from freecad.menuiserie.features.freecad_types import HIDDEN, DocumentObject
from freecad.menuiserie.features.joints.base import (
    JointFeature,
    is_joint,
    params_from,
    placed_blank,
    resolved_for,
)
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.schema import LENGTH, PropertySpec
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["ShelfPinsJoint", "opposite_drilling"]

_GROUP: Final = "Perçage LR32"
_DEFAULTS: Final = ShelfPinsParams()
_MAX_ROWS: Final = 50


def timber_blanks_around(part: DocumentObject) -> list[DocumentObject]:
    """Pièces de bois du document de ``part``, sauf elle-même (voisines possibles du côté)."""
    return [obj for obj in part.Document.Objects if obj is not part and is_timber(obj)]


def _assembled_with(part: DocumentObject, other: DocumentObject) -> bool:
    """Vrai si un assemblage (autre que des perçages LR32) relie ``other`` à ``part``."""
    machined = machined_part_of(part)
    for joint in getattr(machined, "Joints", ()):
        other_kind = is_joint(joint) and joint.Proxy.KIND is not JointKind.SHELF_PINS
        if other_kind and other in (joint.HostPart, joint.GuestPart):
            return True
    return False


def opposite_drilling(joint: DocumentObject) -> tuple[DocumentObject, dict[str, object]] | None:
    """Côté debout en face de la face percée par ``joint`` (montant opposé du caisson) et
    réglages de son perçage en miroir (mêmes cotes, face tournée vers ``joint``, même zone) ;
    ``None`` s'il n'y en a pas, s'il est déjà percé ou si le perçage est impossible."""
    part = joint.HostPart
    try:
        face = resolved_for(joint).face  # type: ignore[attr-defined]
        host = placed_blank(part)
    except (ValueError, InvalidDimensionsError):
        return None
    candidates, blocks = [], []
    for other in timber_blanks_around(part):
        try:
            blocks.append(placed_blank(other))
        except (ValueError, InvalidDimensionsError):
            continue
        candidates.append(other)
    try:
        found = facing_side(host, face, tuple(blocks))
    except JointError:
        return None
    if found is None or _has_shelf_pins(candidates[found[0]]):
        return None
    index, other_face, low = found
    params = params_from(joint, ShelfPinsParams)
    settings: dict[str, object] = {
        field.name: getattr(params, field.name)
        for field in fields(params)
        if field.name not in {"neighbors", "face", "zone_height"}
    }
    zone = params.zone_height
    settings["face"] = other_face
    settings["zone_height"] = max(zone - low, 0.0) if zone else 0.0
    return candidates[index], settings


def _has_shelf_pins(part: DocumentObject) -> bool:
    machined = machined_part_of(part)
    joints = getattr(machined, "Joints", ())
    return any(is_joint(item) and item.Proxy.KIND is JointKind.SHELF_PINS for item in joints)


class ShelfPinsJoint(JointFeature):
    """Perçage au pas de 32 mm dans un côté debout, taquets de tablette rapportés."""

    KIND: ClassVar[JointKind] = JointKind.SHELF_PINS
    TYPE: ClassVar[str] = "Menuiserie::ShelfPins"
    OBJECT_NAME: ClassVar[str] = "ShelfPins"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Perçage LR32")
    PARAMS: ClassVar[type[ShelfPinsParams]] = ShelfPinsParams
    INVERT_TIP: ClassVar[str] = QT_TRANSLATE_NOOP(
        "Menuiserie", "Perce l'autre face du côté (les trous et les taquets changent de face)."
    )

    def invert(self, obj: DocumentObject) -> None:
        """« Inverser » : l'autre face du côté est percée."""
        try:
            current = resolved_for(obj).face  # type: ignore[attr-defined]
        except ValueError:
            current = "minus" if obj.Face == "plus" else "plus"
        obj.Face = "minus" if current == "plus" else "plus"

    def params(self, obj: DocumentObject) -> Any:
        """Réglages des propriétés, plus les pièces voisines du côté dans le document : celles
        qui lui sont assemblées bornent la zone percée, les autres (tablettes) reçoivent un
        taquet sous elles."""
        neighbors = []
        for other in timber_blanks_around(obj.HostPart):
            try:
                block = placed_blank(other)
            except (ValueError, InvalidDimensionsError):
                continue
            neighbors.append(Neighbor(block, _assembled_with(obj.HostPart, other)))
        return replace(params_from(obj, ShelfPinsParams), neighbors=tuple(neighbors))

    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Neighbors",
            "App::PropertyLinkList",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Pièces du document qui bornent le perçage ou reposent sur ses taquets : leur "
                "déplacement recalcule le perçage.",
            ),
            mode=HIDDEN,
        ),
        PropertySpec(
            "HoleDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Diamètre des trous (taquets à tige). 0 : automatique (5 mm)."
            ),
            default=_DEFAULTS.hole_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des trous"),
            resolved="hole_diameter",
        ),
        PropertySpec(
            "HoleDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Profondeur des trous dans le côté. 0 : automatique (12 mm)."
            ),
            default=_DEFAULTS.hole_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des trous"),
            resolved="hole_depth",
        ),
        PropertySpec(
            "Pitch",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Pas entre deux trous d'une colonne (32 mm)."),
            default=_DEFAULTS.pitch,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Pas"),
        ),
        PropertySpec(
            "EdgeDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance des deux colonnes aux bords avant et arrière du côté. 0 : automatique "
                "(37 mm).",
            ),
            default=_DEFAULTS.edge_distance,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance au bord"),
            resolved="edge_distance",
        ),
        PropertySpec(
            "EndMargin",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance du premier et du dernier trou aux pièces assemblées au côté (fond, "
                "dessus) ou à ses bouts. 0 : automatique (64 mm).",
            ),
            default=_DEFAULTS.end_margin,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Marge aux pièces assemblées"),
            resolved="end_margin",
        ),
        PropertySpec(
            "Rows",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de trous par colonne. 0 : automatique, autant que la zone libre entre les "
                "pièces assemblées au côté en reçoit.",
            ),
            default=(_DEFAULTS.rows, 0, _MAX_ROWS, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Trous par colonne"),
            resolved="rows",
        ),
        PropertySpec(
            "WithPins",
            "App::PropertyBool",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Poser les taquets : sous chaque tablette posée contre le côté, ou dans le rang "
                "choisi.",
            ),
            default=_DEFAULTS.with_pins,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Poser les taquets"),
        ),
        PropertySpec(
            "PinRow",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Rang des taquets, compté depuis le bas de la zone percée (1 : le plus bas). 0 : "
                "automatique, un rang sous chaque tablette posée contre le côté.",
            ),
            default=(_DEFAULTS.pin_row, 0, _MAX_ROWS, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Rang des taquets"),
            resolved="pin_row",
        ),
        PropertySpec(
            "PinProjection",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Saillie du taquet hors de la face du côté."),
            default=_DEFAULTS.pin_projection,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Saillie des taquets"),
        ),
        PropertySpec(
            "ZoneHeight",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Hauteur, depuis le bas du côté, d'un point de la zone à percer (entre deux pièces "
                "assemblées au côté) : celle du clic à la création. 0 : automatique, la plus "
                "grande zone libre.",
            ),
            default=_DEFAULTS.zone_height,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Hauteur de la zone percée"),
            resolved="zone_height",
        ),
        PropertySpec(
            "Face",
            "App::PropertyEnumeration",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Face percée du côté. Automatique : la face intérieure, celle contre laquelle sont "
                "posées des pièces et qui regarde l'autre côté.",
            ),
            default=_DEFAULTS.face,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Face percée"),
            choices=(
                ("auto", QT_TRANSLATE_NOOP("Menuiserie", "Automatique (face intérieure)")),
                ("plus", QT_TRANSLATE_NOOP("Menuiserie", "Face +Z de la pièce")),
                ("minus", QT_TRANSLATE_NOOP("Menuiserie", "Face -Z de la pièce")),
            ),
        ),
    )
