# SPDX-License-Identifier: LGPL-2.1-or-later
"""Étendue des membres et distances aux bords dans le repère de l'ensemble (J4a, critère F2).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, NamedTuple, cast

from freecad.menuiserie.core.furniture._messages import NOT_SQUARE
from freecad.menuiserie.core.furniture._model import (
    PIECE_AXES,
    THICKNESS,
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    Member,
)
from freecad.menuiserie.core.geometry import (
    JointError,
    PlacedBlock,
    RigidTransform,
    Vec3,
    moved_box,
    relative_axes,
)
from freecad.menuiserie.core.part_model import Dimensions

_REFERENCE: Final = PlacedBlock(Dimensions(1.0, 1.0, 1.0), RigidTransform.identity())


class Span(NamedTuple):
    """Étendue d'un membre sur un axe de l'ensemble et axe local qui lui est aligné.

    ``reversed`` : l'axe local est orienté vers le début de l'axe de l'ensemble (l'origine
    locale de la pièce est alors à ``hi``).
    """

    lo: float
    hi: float
    local: str
    reversed: bool = False

    @property
    def size(self) -> float:
        """Étendue ``hi - lo``."""
        return self.hi - self.lo

    @property
    def stretchable(self) -> bool:
        """Faux sur l'axe de l'épaisseur d'une pièce, qui n'est jamais étiré."""
        return self.local != THICKNESS

    @property
    def origin(self) -> float:
        """Coordonnée de l'origine locale du membre sur cet axe."""
        return self.hi if self.reversed else self.lo


Spans = Mapping[FurnitureAxis, Span]


def _piece_spans(member: Member, block: PlacedBlock) -> Spans:
    try:
        axes = relative_axes(_REFERENCE, block)
    except JointError as error:
        raise FurnitureError(NOT_SQUARE, {"member": member.name}) from error
    bounds = moved_box(block.local_box(), block.placement)
    return {
        FurnitureAxis.of(axis.index): Span(
            bounds.lo(axis.index), bounds.hi(axis.index), PIECE_AXES[local], axis.sign < 0
        )
        for local, axis in enumerate(axes)
    }


def _furniture_spans(box: FurnitureBox, origin: Vec3) -> Spans:
    return {
        axis: Span(
            origin.component(axis.index), origin.component(axis.index) + box.size(axis), axis.value
        )
        for axis in FurnitureAxis
    }


def member_spans(member: Member) -> Spans:
    """Étendue du membre sur X, Y et Z de l'ensemble, avec l'axe local aligné sur chacun.

    Pièce : ``Length``, ``Width`` ou ``Thickness`` (``relative_axes`` de J3) ; sous-ensemble :
    ``Width``, ``Depth``, ``Height``. Lève :class:`FurnitureError` (gabarit ``NOT_SQUARE``)
    pour une pièce qui n'est pas d'équerre avec l'ensemble.
    """
    if member.block is not None:
        return _piece_spans(member, member.block)
    # Member garantit box et origin quand block est absent.
    return _furniture_spans(cast(FurnitureBox, member.box), cast(Vec3, member.origin))


def square_spans(member: Member) -> Spans | None:
    """Étendues du membre, ou ``None`` s'il n'est pas d'équerre avec l'ensemble."""
    try:
        return member_spans(member)
    except FurnitureError:
        return None


def distances(spans: Spans, box: FurnitureBox) -> Mapping[Edge, float]:
    """Distance de chaque face au bord de l'ensemble de son côté."""
    result: dict[Edge, float] = {}
    for axis, span in spans.items():
        result[Edge.of(axis, False)] = span.lo
        result[Edge.of(axis, True)] = box.size(axis) - span.hi
    return {edge: result[edge] for edge in Edge}


def edge_distances(member: Member, box: FurnitureBox) -> Mapping[Edge, float]:
    """Distance de chaque face du membre au bord de son côté (gauche = début de X… haut = fin
    de Z) ; :class:`FurnitureError` si le membre n'est pas d'équerre."""
    return distances(member_spans(member), box)


def frame_block(spans: Spans) -> PlacedBlock:
    """Boîte du membre dans le repère de l'ensemble, sans rotation (pour ``classify``)."""
    ordered = [spans[axis] for axis in FurnitureAxis]
    translation = Vec3.of([span.lo for span in ordered])
    placement = RigidTransform(RigidTransform.identity().rotation, translation)
    return PlacedBlock(Dimensions(*(span.size for span in ordered)), placement)
