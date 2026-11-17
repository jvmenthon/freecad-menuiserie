# SPDX-License-Identifier: LGPL-2.1-or-later
"""Disposition de la face mobile dans le plan de la référence (ADR 0054, grille choisie par jv
le 2026-11-16).

Après le mouvement de :func:`plane_motion`, la pièce peut tourner dans le plan pour que son grand
côté soit **parallèle** à un axe choisi, puis se placer au **début**, au **centre** ou à la
**fin** de la face de référence le long d'axes choisis (axes X, Y, Z du conteneur, en vecteurs
globaux). Un axe qui suit la normale des faces est refusé : la distance entre les faces se règle
par le mode et le 3e décalage. Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Final

from freecad.menuiserie.core.align._align import (
    INVALID_OFFSET,
    MIN_AXIS_SLOPE,
    NO_OFFSET,
    NOT_PLANAR,
    AlignError,
    Alignment,
    AlignMode,
    checked_axis,
    is_square,
    long_side,
    plane_motion,
    product,
    rotated,
    rotation_between,
    turned_point,
)
from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import FaceTarget
from freecad.menuiserie.core.vectors import cross, dot, is_finite, norm, unit

SKEWED_AXES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les axes d'alignement doivent être perpendiculaires entre eux."
)
AXIS_ACROSS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cet axe traverse les faces (il suit leur normale) : la pièce ne peut pas y être rendue "
    "parallèle ni alignée. La distance entre les faces se règle avec « Position » et le 3e "
    "décalage.",
)
PARALLEL_ON_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Sur un axe, la pièce ne tourne pas : elle ne peut pas être rendue parallèle à un axe "
    "(choisissez « Libre »).",
)


class Anchor(Enum):
    """Où la face mobile se place le long d'un axe, par rapport à la face de référence."""

    START = "start"  # bords du côté « moins » de l'axe sur la même ligne
    CENTER = "center"  # centres sur la même ligne
    END = "end"  # bords du côté « plus » de l'axe sur la même ligne


@dataclass(frozen=True)
class Layout:
    """Disposition de la face mobile dans le plan de la référence (vecteurs globaux).

    ``parallel`` : axe auquel le grand côté de la face mobile devient parallèle (d'équerre : sa
    normale), ``None`` pour ne pas tourner dans le plan. ``anchors`` : pour chaque axe (deux à
    deux perpendiculaires), où la face mobile se place le long de cet axe."""

    parallel: Vec3 | None = None
    anchors: tuple[tuple[Vec3, Anchor], ...] = ()


NO_LAYOUT: Final = Layout()


def _in_plane(axis: Vec3, normal: Vec3) -> Vec3 | None:
    """Part de ``axis`` (unitaire) dans le plan de normale ``normal``, rendue unitaire ; ``None``
    si l'axe suit presque la normale (part plus courte que :data:`MIN_AXIS_SLOPE`)."""
    flat = axis - normal.scaled(dot(axis, normal))
    if not norm(flat) >= MIN_AXIS_SLOPE:  # NaN compris
        return None
    return unit(flat)


def crosses_faces(axis: Vec3, fixed: FaceTarget) -> bool:
    """Vrai si ``axis`` (vecteur global non nul) suit presque la normale de ``fixed`` : la pièce
    ne peut alors ni y être rendue parallèle ni s'y aligner (le panneau grise cette ligne)."""
    return _in_plane(checked_axis(axis), unit(fixed.frame.z)) is None


def _paralleled(motion: Alignment, fixed: FaceTarget, moving: FaceTarget, axis: Vec3) -> Alignment:
    """``motion`` complété d'un tour dans le plan de la référence (autour de sa normale, par le
    pivot déplacé) qui rend le grand côté de la face mobile parallèle à ``axis`` (le plus petit
    des deux sens ; des quatre quarts de tour si la face mobile est carrée). D'équerre, c'est la
    normale de la face mobile (couchée dans le plan) qui devient parallèle à ``axis``."""
    normal = unit(fixed.frame.z)
    along = _in_plane(axis, normal)
    if along is None:
        raise AlignError(AXIS_ACROSS, {})
    across = cross(normal, along)
    perpendicular = motion.mode is AlignMode.PERPENDICULAR
    own = unit(moving.frame.z) if perpendicular else long_side(moving)
    turned = rotated(motion.rotation, own)
    flat = turned - normal.scaled(dot(turned, normal))
    if norm(flat) <= ANGLE_TOLERANCE:
        return motion
    flat = unit(flat)
    current = math.atan2(dot(flat, across), dot(flat, along))
    step = math.pi / 2 if not perpendicular and is_square(moving) else math.pi
    target = round(current / step) * step
    wanted = along.scaled(math.cos(target)) + across.scaled(math.sin(target))
    turn, _angle = rotation_between(flat, unit(wanted), normal)
    return replace(motion, rotation=product(turn, motion.rotation))


def _corners(face: FaceTarget) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Les quatre coins du rectangle englobant de ``face``."""
    frame = face.frame
    width, height = frame.x.scaled(face.extent[0]), frame.y.scaled(face.extent[1])
    return (
        frame.origin,
        frame.origin + width,
        frame.origin + height,
        frame.origin + width + height,
    )


def _anchored(span: tuple[float, float], other: tuple[float, float], anchor: Anchor) -> float:
    """Écart, le long d'un axe, qui amène l'étendue ``other`` (min, max) au début, au centre ou
    à la fin de l'étendue ``span``."""
    if anchor is Anchor.START:
        return span[0] - other[0]
    if anchor is Anchor.END:
        return span[1] - other[1]
    return (span[0] + span[1] - other[0] - other[1]) / 2


def _placing(
    motion: Alignment,
    fixed: FaceTarget,
    moving: FaceTarget,
    anchors: tuple[tuple[Vec3, Anchor], ...],
) -> Vec3:
    """Translation de plus qui, sur chaque axe de ``anchors`` (vecteurs globaux unitaires, deux à
    deux perpendiculaires), place le rectangle de la face mobile (placée par ``motion``, sans
    décalage) au début, au centre ou à la fin de celui de la référence, ramenée dans le plan de
    la référence : elle ne sort jamais la face de ce plan (le 3e axe reste au décalage)."""
    placed = tuple(turned_point(motion, corner) for corner in _corners(moving))
    reference = _corners(fixed)
    extra = NO_OFFSET
    for axis, anchor in anchors:
        span = [dot(point, axis) for point in reference]
        other = [dot(point, axis) for point in placed]
        delta = _anchored((min(span), max(span)), (min(other), max(other)), anchor)
        extra = extra + axis.scaled(delta)
    normal = unit(fixed.frame.z)
    return extra - normal.scaled(dot(extra, normal))


def _checked_layout(
    layout: Layout, normal: Vec3
) -> tuple[Vec3 | None, tuple[tuple[Vec3, Anchor], ...]]:
    """Axes de ``layout`` rendus unitaires ; :class:`AlignError` si un axe n'est pas fini, est
    nul, suit la normale ``normal`` des faces, ou si les axes d'ancrage ne sont pas
    perpendiculaires entre eux."""
    anchors = tuple((checked_axis(axis), anchor) for axis, anchor in layout.anchors)
    axes = [axis for axis, _anchor in anchors]
    if any(abs(dot(a, b)) > ANGLE_TOLERANCE for i, a in enumerate(axes) for b in axes[i + 1 :]):
        raise AlignError(SKEWED_AXES, {})
    parallel = None if layout.parallel is None else checked_axis(layout.parallel)
    checked = axes if parallel is None else [*axes, parallel]
    if any(_in_plane(axis, normal) is None for axis in checked):
        raise AlignError(AXIS_ACROSS, {})
    return parallel, anchors


def align(
    fixed: FaceTarget,
    moving: FaceTarget,
    mode: AlignMode = AlignMode.AUTO,
    offset: Vec3 = NO_OFFSET,
    axis: Vec3 | None = None,
    layout: Layout = NO_LAYOUT,
) -> Alignment:
    """:func:`plane_motion` puis la disposition ``layout`` : la pièce tourne dans le plan de la
    référence pour que son grand côté soit parallèle à ``layout.parallel`` (refusé sur un axe,
    où rien ne tourne), puis, pour chaque axe de ``layout.anchors``, le rectangle de la face
    mobile se place au début, au centre ou à la fin de celui de la référence le long de cet axe,
    **dans le plan de la référence** (centres sur les deux axes du plan : centres confondus). Le
    décalage ``offset`` s'ajoute après. Axe non fini, nul, qui suit la normale des faces, ou axes
    d'ancrage non perpendiculaires entre eux : :class:`AlignError`."""
    if not (fixed.planar and moving.planar):
        raise AlignError(NOT_PLANAR, {})
    parallel, anchors = _checked_layout(layout, unit(fixed.frame.z))
    if parallel is not None and axis is not None:
        raise AlignError(PARALLEL_ON_AXIS, {})
    motion = plane_motion(fixed, moving, mode, offset, axis)
    if parallel is not None:
        motion = _paralleled(motion, fixed, moving, parallel)
    if not anchors:
        return motion
    # Placement mesuré sans décalage (sur un axe, le décalage allonge le trajet le long de l'axe :
    # ce n'est pas une simple translation), puis ajouté au mouvement décalé.
    bare = replace(plane_motion(fixed, moving, mode, NO_OFFSET, axis), rotation=motion.rotation)
    extra = _placing(bare, fixed, moving, anchors)
    if not is_finite(extra):
        raise AlignError(INVALID_OFFSET, {})
    return Alignment(motion.rotation, motion.pivot, motion.shift + extra, motion.angle, motion.mode)
