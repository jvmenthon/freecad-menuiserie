# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes d'un ensemble recalées sur l'enveloppe de ses membres (ADR 0048).

Après un déplacement ou une rotation d'un sous-ensemble, les cotes de l'ensemble parent
deviennent la boîte qui enveloppe ses membres (pièces et sous-ensembles, rotation comprise). Rien
ne bouge : seuls ``Origin`` et les cotes du parent sont écrits, puis ses liaisons sont recalculées
d'après la géométrie actuelle (``furniture_drag._relink``).

Seul un ensemble de plus haut niveau est recalé : la position d'un sous-ensemble est portée par le
``Placement`` de son Std Part avec un ``Origin`` nul (ADR 0038), qu'un recalage décalerait. Un
parent dont une formule de l'utilisateur pilote ``Origin`` ou une cote n'est pas recalé non plus.
"""

from __future__ import annotations

from itertools import product
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Box, PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import furniture_of, is_furniture, origin_of, writing
from freecad.menuiserie.features.furniture_bindings import members_of, workshop_expressions
from freecad.menuiserie.features.furniture_container import std_part_of
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["FurnitureFrame", "frame_of", "member_envelope", "reframe", "restore_frame"]

TOLERANCE_MM: Final = 1e-6
_FRAME_PROPERTIES: Final = ("Origin", "Width", "Depth", "Height")

FurnitureFrame = tuple[Vec3, Vec3]  # Origin et cotes (largeur, profondeur, hauteur)


def _corners(box: Box, transform: RigidTransform) -> list[Vec3]:
    return [
        transform.apply(Vec3(*(box.hi(i) if bits[i] else box.lo(i) for i in range(3))))
        for bits in product((0, 1), repeat=3)
    ]


def _member_corners(obj: DocumentObject) -> list[Vec3]:
    """Coins de ``obj`` dans le repère de son ensemble (celui de son ``Origin``)."""
    if is_furniture(obj):
        origin = origin_of(obj)
        size = Vec3(obj.Width.Value, obj.Depth.Value, obj.Height.Value)
        part = std_part_of(obj)
        transform = RigidTransform.identity() if part is None else rigid_transform(part.Placement)
        return _corners(Box(origin, origin + size), transform)
    transform = rigid_transform(obj.Placement)
    return _corners(PlacedBlock(dimensions_of(obj), transform).local_box(), transform)


def member_envelope(furniture: DocumentObject) -> Box | None:
    """Boîte qui enveloppe les membres de ``furniture`` dans le repère de son ``Origin`` ;
    ``None`` sans membre."""
    points = [point for obj in members_of(furniture) for point in _member_corners(obj)]
    if not points:
        return None
    return Box(
        Vec3(*(min(p.component(i) for p in points) for i in range(3))),
        Vec3(*(max(p.component(i) for p in points) for i in range(3))),
    )


def _driven(furniture: DocumentObject) -> bool:
    """Vrai si une formule de l'utilisateur pilote ``Origin`` ou une cote."""
    workshop = workshop_expressions(furniture)
    return any(
        path.lstrip(".").split(".")[0] in _FRAME_PROPERTIES and path not in workshop
        for path in expressions_of(furniture)
    )


def frame_of(furniture: DocumentObject) -> FurnitureFrame:
    """``Origin`` et cotes actuels de ``furniture``."""
    size = Vec3(furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value)
    return origin_of(furniture), size


def restore_frame(furniture: DocumentObject, frame: FurnitureFrame) -> None:
    """Remet ``Origin`` et les cotes lus par :func:`frame_of` (refus de la liaison)."""
    origin, size = frame
    with writing(furniture):
        furniture.Origin = App.Vector(origin.x, origin.y, origin.z)
        furniture.Width, furniture.Depth, furniture.Height = size.x, size.y, size.z


def reframe(furniture: DocumentObject) -> bool:
    """Recale ``Origin`` et les cotes de ``furniture`` sur l'enveloppe de ses membres, sans
    recalcul ni liaison (l'appelant relie ensuite les membres). Faux, sans rien écrire, pour un
    sous-ensemble, un ensemble piloté par une formule, sans membre ou déjà à l'enveloppe."""
    if furniture_of(furniture) is not None or _driven(furniture):
        return False
    envelope = member_envelope(furniture)
    if envelope is None:
        return False
    origin, size = frame_of(furniture)
    target = (envelope.min, Vec3(*(envelope.size(i) for i in range(3))))
    if all(
        abs(a.component(i) - b.component(i)) <= TOLERANCE_MM
        for a, b in zip((origin, size), target, strict=True)
        for i in range(3)
    ):
        return False
    restore_frame(furniture, target)
    return True
