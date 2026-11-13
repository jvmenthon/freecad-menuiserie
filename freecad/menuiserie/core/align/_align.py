# SPDX-License-Identifier: LGPL-2.1-or-later
"""Amener une face mobile dans le plan d'une face de référence (AL-a, ADR 0054).

Le mouvement est rigide et se fait en deux temps : une **rotation minimale** autour d'un point de
la face mobile qui rend les deux faces parallèles, puis une **translation le long de la normale**
de la référence qui les rend coplanaires. Trois modes : ``FLUSH`` (au ras : normales sortantes de
même sens), ``FACING`` (face contre face : normales opposées, les pièces se touchent) et
``PERPENDICULAR`` (faces d'équerre : la rotation s'arrête à 90°). ``AUTO`` prend au ras ou face
contre face, selon la plus petite rotation. Un décalage facultatif se règle sur les trois axes de
la face de référence.
Convention : ``align(fixed, moving)`` — le premier élément est la référence, le second celui de
la pièce qui bouge. Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Matrix3, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.snap import FaceTarget
from freecad.menuiserie.core.vectors import cross, dot, norm, unit

NOT_PLANAR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les deux faces doivent être planes pour être alignées."
)

NOT_PARALLEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Sur un axe, la pièce ne tourne pas : les deux faces doivent déjà être parallèles "
    "(choisissez « Libre »).",
)
AXIS_IN_PLANE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cet axe est parallèle aux faces : un déplacement sur cet axe ne les met pas dans le même "
    "plan. Choisissez un autre axe.",
)
NO_OFFSET: Final = Vec3(0.0, 0.0, 0.0)
_IDENTITY: Final[Matrix3] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class AlignError(TemplatedError):
    """Alignement impossible ; message = gabarit français (``QT_TRANSLATE_NOOP``) rempli."""


class AlignMode(Enum):
    """Position de la face mobile une fois alignée : au ras, contre, ou d'équerre."""

    AUTO = "auto"  # la plus petite rotation
    FLUSH = "flush"  # au ras : même sens que la référence
    FACING = "facing"  # face contre face : sens opposé
    PERPENDICULAR = "perpendicular"  # faces d'équerre : normales à 90°


@dataclass(frozen=True)
class Alignment:
    """Mouvement rigide global qui aligne : ``point ↦ rotation·(point - pivot) + pivot + shift``.

    ``angle`` : angle de la rotation en degrés (0 si les faces sont déjà parallèles) ;
    ``mode`` : mode retenu (jamais ``AUTO``)."""

    rotation: Matrix3
    pivot: Vec3
    shift: Vec3
    angle: float
    mode: AlignMode


def _rotation_between(source: Vec3, target: Vec3, spare: Vec3) -> tuple[Matrix3, float]:
    """Rotation minimale qui amène le vecteur unitaire ``source`` sur ``target`` (Rodrigues) et
    son angle en degrés. Vecteurs opposés : demi-tour autour de ``spare`` (unitaire, perpendiculaire
    à ``source``)."""
    axis = cross(source, target)
    sine, cosine = norm(axis), dot(source, target)
    if sine <= ANGLE_TOLERANCE:
        if cosine > 0:
            return _IDENTITY, 0.0
        axis, sine = spare, 0.0
    else:
        axis = axis.scaled(1.0 / sine)
    angle = math.atan2(sine, cosine)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = axis.x, axis.y, axis.z
    t = 1.0 - c
    rows: Matrix3 = (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )
    return rows, math.degrees(angle)


def _turned(matrix: Matrix3, vector: Vec3) -> Vec3:
    return Vec3.of([sum(r * vector.component(j) for j, r in enumerate(row)) for row in matrix])


def _mode_of(fixed_normal: Vec3, moving_normal: Vec3, mode: AlignMode) -> AlignMode:
    if mode is not AlignMode.AUTO:
        return mode
    # À 90° exacts : au ras, sans dépendre du signe du bruit numérique.
    flush = dot(fixed_normal, moving_normal) >= -ANGLE_TOLERANCE
    return AlignMode.FLUSH if flush else AlignMode.FACING


def _wanted_normal(reference: Vec3, own: Vec3, chosen: AlignMode, spare: Vec3) -> Vec3:
    """Normale que la face mobile doit avoir : celle de la référence (au ras), son opposée (face
    contre face) ou, d'équerre, la composante de ``own`` perpendiculaire à la référence (rotation
    minimale ; normales parallèles : ``spare``, perpendiculaire à la référence)."""
    if chosen is AlignMode.FLUSH:
        return reference
    if chosen is AlignMode.FACING:
        return reference.scaled(-1.0)
    side = own - reference.scaled(dot(own, reference))
    return spare if norm(side) <= ANGLE_TOLERANCE else unit(side)


def _along_axis(
    fixed: FaceTarget, moving: FaceTarget, mode: AlignMode, gap_offset: float, axis: Vec3
) -> Alignment:
    """Translation seule, le long de ``axis`` (unitaire), qui amène la face mobile dans le plan
    de la référence (plus ``gap_offset`` le long de sa normale)."""
    reference = unit(fixed.frame.z)
    own = unit(moving.frame.z)
    if norm(cross(reference, own)) > ANGLE_TOLERANCE:
        raise AlignError(NOT_PARALLEL, {})
    slope = dot(axis, reference)
    if abs(slope) <= ANGLE_TOLERANCE:
        raise AlignError(AXIS_IN_PLANE, {})
    pivot = moving.frame.origin
    gap = dot(fixed.frame.origin - pivot, reference) + gap_offset
    chosen = _mode_of(reference, own, AlignMode.AUTO if mode is AlignMode.PERPENDICULAR else mode)
    return Alignment(_IDENTITY, pivot, axis.scaled(gap / slope), 0.0, chosen)


def align(
    fixed: FaceTarget,
    moving: FaceTarget,
    mode: AlignMode = AlignMode.AUTO,
    offset: Vec3 = NO_OFFSET,
    axis: Vec3 | None = None,
) -> Alignment:
    """Mouvement de la pièce de ``moving`` qui met sa face dans le plan de ``fixed``.

    Le pivot est l'origine du repère de la face mobile (un point du plan mobile : il reste dans le
    plan). ``offset`` (mm) : décalage de plus dans le repère de la face de référence (x, y dans
    son plan, z le long de sa normale : le « 3e axe »). ``axis`` (vecteur global) : alignement
    **sur un axe** seulement, sans rotation ; les faces doivent être parallèles, l'axe ne doit pas
    être dans leur plan, et seul ``offset.z`` (écart le long de la normale) compte. Faces non
    planes : :class:`AlignError`."""
    if not (fixed.planar and moving.planar):
        raise AlignError(NOT_PLANAR, {})
    reference = unit(fixed.frame.z)
    own = unit(moving.frame.z)
    if axis is not None:
        return _along_axis(fixed, moving, mode, offset.z, unit(axis))
    chosen = _mode_of(reference, own, mode)
    wanted = _wanted_normal(reference, own, chosen, unit(fixed.frame.x))
    rotation, angle = _rotation_between(own, wanted, unit(moving.frame.x))
    pivot = moving.frame.origin
    gap = dot(fixed.frame.origin - pivot, reference)  # le pivot reste dans le plan de la référence
    frame = fixed.frame
    shift = (
        reference.scaled(gap)
        + frame.x.scaled(offset.x)
        + frame.y.scaled(offset.y)
        + reference.scaled(offset.z)
    )
    return Alignment(rotation, pivot, shift, angle, chosen)
