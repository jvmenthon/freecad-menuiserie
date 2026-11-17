# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarit « Fermer le caisson » (ADR 0064, spécification ``docs/specs/fermer-le-caisson.md``).

Le menuisier a déjà dessiné le dessous (ou le dessus) de son meuble : cette **ancre** n'est ni
recréée, ni déplacée, ni redimensionnée. Le gabarit décrit les autres pièces dans le repère du
caisson, qui est celui de l'ancre (tourné autour de Z de ``front_turns`` quarts de tour pour
choisir l'avant) : X = largeur, Y = profondeur (avant en 0), Z = celui de l'ancre, qui occupe
``[0, largeur] x [0, profondeur] x [0, e]``. Le caisson monte (ancre = dessous) ou descend
(ancre = dessus) depuis l'ancre ; sa hauteur ``H`` est hors tout, ancre comprise.

Notations : ``t`` épaisseur des côtés (et de l'avant et du fond épais), ``tt`` celle de la pièce
opposée, ``e`` celle de l'ancre, ``r`` profondeur de la feuillure du fond. L'ancre et la pièce
opposée filent d'un bout à l'autre ; les côtés sont posés sur l'ancre, sous la pièce opposée
(``u`` : hauteur depuis la face extérieure de l'ancre). Le ``Layout`` rend les blocs **relatifs à
``Origin``**, le coin (avant, gauche, bas) de l'ensemble, qui vaut le coin de l'ancre sauf quand
le caisson descend.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import replace
from enum import Enum
from typing import Final, TypeVar

from freecad.menuiserie.core.furniture import Edge, FurnitureBox
from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.joints import strategy_for
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.templates import Layout, PieceSpec
from freecad.menuiserie.core.templates.closing_joints import joint_specs
from freecad.menuiserie.core.templates.closing_params import (
    GROOVE_SETBACK_MM,
    BackJoinery,
    ClosingJoinery,
    ClosingParams,
    ClosingRole,
    Element,
)

__all__ = [
    "ANCHOR_KEY",
    "CLOSING_TEMPLATE",
    "back_availability",
    "check_feasible",
    "closing_layout",
    "joinery_availability",
    "nearest_front",
    "wanted_extents",
]

CLOSING_TEMPLATE: Final = "ClosedCarcass"  # valeur de ``Template`` (enregistrée, figée)
CLOSING_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Caisson")
ANCHOR_KEY: Final = "anchor"
LABELS: Final = {
    "left": QT_TRANSLATE_NOOP("Menuiserie", "Côté gauche"),
    "right": QT_TRANSLATE_NOOP("Menuiserie", "Côté droit"),
    "bottom": QT_TRANSLATE_NOOP("Menuiserie", "Dessous"),
    "top": QT_TRANSLATE_NOOP("Menuiserie", "Dessus"),
    "back": QT_TRANSLATE_NOOP("Menuiserie", "Fond"),
    "front": QT_TRANSLATE_NOOP("Menuiserie", "Avant"),
    "opposite": QT_TRANSLATE_NOOP("Menuiserie", "Pièce opposée"),  # dessus ou dessous : légende
}

_C = TypeVar("_C", bound=Enum)
Span = tuple[float, float]
Spans = tuple[Span, Span, Span]
# Axes (indice de l'axe du caisson, sens) des axes locaux L, l, e d'une pièce.
Axes = tuple[tuple[int, int], tuple[int, int], tuple[int, int]]
_FLAT: Final[Axes] = ((0, 1), (1, 1), (2, 1))  # L selon X, l selon Y, e selon Z
_UPRIGHT: Final[Axes] = ((2, 1), (1, 1), (0, -1))  # côté : L selon Z, e selon -X
_STANDING: Final[Axes] = ((2, 1), (0, 1), (1, 1))  # fond mince : L selon Z, l selon X, e selon Y
_ACROSS: Final[Axes] = (
    (0, 1),
    (2, 1),
    (1, -1),
)  # avant, fond épais : L selon X, l selon Z, e selon -Y

_ALL_EDGES: Final = frozenset(Edge)


# --- Repère et blocs --------------------------------------------------------------------------


def _z_span(params: ClosingParams, low: float, high: float) -> Span:
    """Étendue sur Z d'une pièce entre les hauteurs ``low`` et ``high`` (``u``) : vers +Z quand
    le caisson monte, vers -Z (à partir de la face extérieure, en ``e``) quand il descend."""
    if params.role is ClosingRole.BOTTOM:
        return (low, high)
    top = params.anchor.thickness
    return (top - high, top - low)


def _origin(params: ClosingParams) -> Vec3:
    """Coin (avant, gauche, bas) du caisson dans le repère du caisson."""
    return Vec3(0.0, 0.0, _z_span(params, 0.0, params.height)[0])


def _block(spans: Spans, axes: Axes, origin: Vec3) -> PlacedBlock:
    """Pièce occupant ``spans`` (repère du caisson) avec les axes locaux ``axes``, relative à
    ``origin``. La base est le coin de la pièce d'où partent ses axes (début ou fin d'une étendue
    selon le sens de l'axe)."""
    size = [
        round(spans[axis][1] - spans[axis][0], 6) for axis, _sign in axes
    ]  # sans bruit flottant
    rows = [[0.0, 0.0, 0.0, 0.0] for _ in range(3)]
    for column, (axis, sign) in enumerate(axes):
        rows[axis][column] = float(sign)
        rows[axis][3] = spans[axis][0] if sign > 0 else spans[axis][1]
    for axis, shift in enumerate((origin.x, origin.y, origin.z)):
        rows[axis][3] -= shift
    return PlacedBlock(Dimensions(*size), RigidTransform.from_matrix([*rows, [0, 0, 0, 1]]))


def _anchor_block(params: ClosingParams, origin: Vec3) -> PlacedBlock:
    """L'ancre dans le repère du caisson : tournée de ``front_turns`` quarts de tour autour de Z
    (l'avant est le bord ``Y = 0`` du caisson), sa face intérieure en ``Z = 0``."""
    length, width = params.anchor.length, params.anchor.width
    plan = {  # lignes X et Y de la matrice, par quart de tour
        0: ((1, 0, 0, 0), (0, 1, 0, 0)),
        1: ((0, 1, 0, 0), (-1, 0, 0, length)),
        2: ((-1, 0, 0, length), (0, -1, 0, width)),
        3: ((0, -1, 0, width), (1, 0, 0, 0)),
    }[params.front_turns]
    rows = [[float(value) for value in row] for row in (*plan, (0, 0, 1, 0))]
    for axis, shift in enumerate((origin.x, origin.y, origin.z)):
        rows[axis][3] -= shift
    return PlacedBlock(params.anchor, RigidTransform.from_matrix([*rows, [0, 0, 0, 1]]))


# --- Étendues des pièces (repère du caisson, avant la mise en bloc) -----------------------


def _without(*edges: Edge) -> frozenset[Edge]:
    return _ALL_EDGES - frozenset(edges)


def _facing_edges(params: ClosingParams) -> tuple[Edge, Edge]:
    """Bords de l'ensemble (côté de l'ancre, côté de la pièce opposée)."""
    if params.role is ClosingRole.BOTTOM:
        return Edge.BOTTOM, Edge.TOP
    return Edge.TOP, Edge.BOTTOM


def _top_u(params: ClosingParams) -> float:
    """Hauteur ``u`` jusqu'où montent les côtés : sous la pièce opposée, ou hors tout."""
    height = params.height
    return height - params.opposite_t if params.has(Element.OPPOSITE) else height


def _side_spans(params: ClosingParams, left: bool) -> Spans:
    """Côté posé sur l'ancre (en onglet : de la face extérieure de l'ancre à la hauteur hors
    tout, il chevauche l'ancre et la pièce opposée)."""
    t = params.side_t
    start = 0.0 if params.joinery is ClosingJoinery.MITER else params.anchor.thickness
    end = params.height if params.joinery is ClosingJoinery.MITER else _top_u(params)
    x = (0.0, t) if left else (params.width - t, params.width)
    return (x, (0.0, params.depth), _z_span(params, start, end))


def _between_x(params: ClosingParams, inset: float) -> Span:
    """Étendue sur X entre les côtés présents (``inset`` de plus de chaque côté absent)."""
    t = params.side_t
    low = t - inset if params.has(Element.LEFT) else 0.0
    high = params.width - (t - inset) if params.has(Element.RIGHT) else params.width
    return (low, high)


def _front_spans(params: ClosingParams) -> Spans:
    """Avant : panneau entre les côtés, au ras de l'avant."""
    z = _z_span(params, params.anchor.thickness, _top_u(params))
    return (_between_x(params, 0.0), (0.0, params.side_t), z)


def _back_spans(params: ClosingParams) -> Spans:
    """Fond : épais, il est entre les côtés et l'ancre, à fleur de l'arrière ; mince, il est
    en feuillure (prolongé de ``r`` dans les pièces qui le reçoivent), reculé dans une rainure,
    ou posé entre les pièces."""
    depth, e = params.depth, params.anchor.thickness
    if params.thick_back or params.back_joinery is not BackJoinery.RABBET:
        setback = 0.0
        if not params.thick_back and params.back_joinery is BackJoinery.GROOVE:
            setback = GROOVE_SETBACK_MM
        y = (depth - setback - params.back_t, depth - setback)
        return (_between_x(params, 0.0), y, _z_span(params, e, _top_u(params)))
    r = params.rabbet_depth
    top = params.height - params.opposite_t + r if params.has(Element.OPPOSITE) else params.height
    return (_between_x(params, r), (depth - params.back_t, depth), _z_span(params, e - r, top))


def _opposite_spans(params: ClosingParams) -> Spans:
    return (
        (0.0, params.width),
        (0.0, params.depth),
        _z_span(params, params.height - params.opposite_t, params.height),
    )


# --- Pièces -------------------------------------------------------------------------------


def _piece(
    key: str,
    block: PlacedBlock,
    material_id: str,
    fixed: frozenset[Edge],
    label: str | None = None,
) -> PieceSpec:
    return PieceSpec(key, label or LABELS[key], block, material_id, fixed)


def _anchor_piece(params: ClosingParams, origin: Vec3) -> PieceSpec:
    """L'ancre telle qu'elle est ; fixe sur tous ses bords sauf sa face intérieure."""
    _near, far = _facing_edges(params)  # libre du côté de la pièce opposée seulement
    own = "bottom" if params.role is ClosingRole.BOTTOM else "top"
    return _piece(
        ANCHOR_KEY,
        _anchor_block(params, origin),
        params.anchor_material_id,
        _without(far),
        LABELS[own],
    )


def _created(params: ClosingParams, origin: Vec3) -> list[PieceSpec]:
    """Pièces à créer : côtés, avant, fond, pièce opposée (selon ``elements``)."""
    near, _far = _facing_edges(params)
    pieces: list[PieceSpec] = []
    material = params.material_id or params.anchor_material_id
    for left, key, other in ((True, "left", Edge.RIGHT), (False, "right", Edge.LEFT)):
        if params.has(Element(key)):
            block = _block(_side_spans(params, left), _UPRIGHT, origin)
            pieces.append(_piece(key, block, material, _without(other)))
    if params.has(Element.FRONT):
        block = _block(_front_spans(params), _ACROSS, origin)
        pieces.append(_piece("front", block, material, _without(Edge.BACK)))
    if params.has(Element.BACK):
        block = _block(_back_spans(params), _ACROSS if params.thick_back else _STANDING, origin)
        back_material = material if params.thick_back else params.back_material_id
        pieces.append(_piece("back", block, back_material or material, _without(Edge.FRONT)))
    if params.has(Element.OPPOSITE):
        block = _block(_opposite_spans(params), _FLAT, origin)
        opposite = "top" if params.role is ClosingRole.BOTTOM else "bottom"
        pieces.append(
            _piece(
                "opposite",
                block,
                params.opposite_material_id or params.anchor_material_id,
                _without(near),
                LABELS[opposite],
            )
        )
    return pieces


def closing_layout(params: ClosingParams) -> Layout:
    """Ancre, pièces à créer et assemblages du caisson fermé (fonction pure, ADR 0064)."""
    origin = _origin(params)
    box = FurnitureBox(params.width, params.depth, params.height)
    pieces = (_anchor_piece(params, origin), *_created(params, origin))
    return Layout(
        CLOSING_TEMPLATE,
        CLOSING_LABEL,
        box,
        origin,
        pieces,
        joint_specs(params),
        anchor=ANCHOR_KEY,
    )


# --- Choix impossibles --------------------------------------------------------------------


def _absolute(piece: PieceSpec, origin: Vec3) -> PlacedBlock:
    """Bloc de ``piece`` dans le repère du caisson (le bloc est relatif à ``origin``)."""
    shift = RigidTransform(RigidTransform.identity().rotation, origin)
    return PlacedBlock(piece.block.dimensions, shift.compose(piece.block.placement))


def check_feasible(layout: Layout) -> None:
    """Refuse (``JointError``, ``ValueError``) si un assemblage du gabarit est impossible avec
    ces cotes : chaque stratégie de J3 calcule son plan sur les pièces du gabarit."""
    blocks = {piece.key: _absolute(piece, layout.origin) for piece in layout.pieces}
    for spec in layout.joints:
        strategy_for(spec.kind).plan(blocks[spec.host], blocks[spec.guest], spec.params)


def _availability(
    choices: Iterable[_C], build: Callable[[_C], ClosingParams]
) -> dict[_C, TemplatedError | None]:
    """Pour chaque choix : ``None`` s'il est réalisable (les paramètres et chaque assemblage se
    calculent), la raison (erreur traduisible) sinon."""
    result: dict[_C, TemplatedError | None] = {}
    for choice in choices:
        try:
            check_feasible(closing_layout(build(choice)))
            result[choice] = None
        except TemplatedError as error:
            result[choice] = error
    return result


def joinery_availability(params: ClosingParams) -> dict[ClosingJoinery, TemplatedError | None]:
    """Réalisabilité de chaque assemblage des côtés avec les autres choix de ``params``."""
    return _availability(ClosingJoinery, lambda choice: replace(params, joinery=choice))


def back_availability(params: ClosingParams) -> dict[BackJoinery, TemplatedError | None]:
    """Réalisabilité de chaque assemblage du fond mince avec les autres choix de ``params``."""
    return _availability(BackJoinery, lambda choice: replace(params, back_joinery=choice))


def wanted_extents(layout: Layout, key: str) -> tuple[Span, Span, Span]:
    """Étendues (X, Y, Z, repère du caisson) de la pièce ``key`` : bloc relatif à ``Origin``
    ramené dans le repère du caisson ; utile aux tests et au schéma."""
    block = _absolute(layout.piece(key), layout.origin)
    box = block.local_box()
    corners = [
        block.placement.apply(Vec3(x, y, z))
        for x in (box.lo(0), box.hi(0))
        for y in (box.lo(1), box.hi(1))
        for z in (box.lo(2), box.hi(2))
    ]

    def extent(axis: int) -> Span:
        values = [corner.component(axis) for corner in corners]
        return (round(min(values), 6), round(max(values), 6))

    return (extent(0), extent(1), extent(2))


# --- Avant du caisson ---------------------------------------------------------------------


def nearest_front(anchor: Dimensions, viewer: Vec3) -> int:
    """Quarts de tour de l'avant (0 à 3) pour un observateur en ``viewer`` (repère local de
    l'ancre) : le grand chant de l'ancre le plus proche de lui. Les grands chants sont ceux de
    la longueur (``Y = 0`` et ``Y = largeur``) si la longueur est au moins la largeur, ceux de la
    largeur sinon ; à distance égale, le premier (``Y = 0`` ou ``X = longueur``)."""
    length, width = anchor.length, anchor.width
    middles = {  # quarts de tour → milieu du chant
        0: (length / 2, 0.0),
        1: (length, width / 2),
        2: (length / 2, width),
        3: (0.0, width / 2),
    }
    long_edges = (0, 2) if length >= width else (1, 3)
    return min(long_edges, key=lambda turns: math.dist(middles[turns], (viewer.x, viewer.y)))
