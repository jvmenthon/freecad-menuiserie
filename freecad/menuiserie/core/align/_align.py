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
from freecad.menuiserie.core.vectors import cross, dot, is_finite, norm, unit

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
PERPENDICULAR_ON_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Sur un axe, la pièce ne tourne pas : elle ne peut pas être mise d'équerre."
)
INVALID_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'axe de déplacement doit être un vecteur fini et non nul."
)
SKEWED_AXES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les axes de centrage doivent être perpendiculaires entre eux."
)
INVALID_OFFSET: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les décalages doivent être des nombres finis."
)
# Pente minimale de l'axe sur la normale (sin ≈ 3°) : en deçà, le trajet (écart / pente) devient
# démesuré pour un axe presque dans le plan des faces ; refusé comme un axe dans le plan.
MIN_AXIS_SLOPE: Final = 0.05
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
    fixed: FaceTarget, moving: FaceTarget, normals: tuple[Vec3, Vec3], gap_offset: float, axis: Vec3
) -> Alignment:
    """Translation seule, le long de ``axis`` (unitaire), qui amène la face mobile dans le plan
    de la référence (plus ``gap_offset`` le long de sa normale). ``normals`` : normales unitaires
    de la référence et de la face mobile."""
    reference, own = normals
    if norm(cross(reference, own)) > ANGLE_TOLERANCE:
        raise AlignError(NOT_PARALLEL, {})
    slope = dot(axis, reference)
    if not abs(slope) >= MIN_AXIS_SLOPE:  # NaN compris
        raise AlignError(AXIS_IN_PLANE, {})
    pivot = moving.frame.origin
    gap = dot(fixed.frame.origin - pivot, reference) + gap_offset
    chosen = _mode_of(reference, own, AlignMode.AUTO)  # sans rotation : le sens réel
    return Alignment(_IDENTITY, pivot, axis.scaled(gap / slope), 0.0, chosen)


def face_center(face: FaceTarget) -> Vec3:
    """Centre du rectangle englobant de ``face`` : son repère part d'un coin, axes vers
    l'intérieur, étendue le long de ces axes."""
    frame = face.frame
    return frame.origin + frame.x.scaled(face.extent[0] / 2) + frame.y.scaled(face.extent[1] / 2)


def _turned_point(motion: Alignment, point: Vec3) -> Vec3:
    return _turned(motion.rotation, point - motion.pivot) + motion.pivot + motion.shift


def _centering(
    motion: Alignment, fixed: FaceTarget, moving: FaceTarget, centered: tuple[Vec3, ...]
) -> Vec3:
    """Translation de plus qui, sur chaque axe de ``centered`` (vecteurs globaux unitaires, deux
    à deux perpendiculaires), amène le centre de la face mobile (placée par ``motion``, sans
    décalage) sur celui de la référence, ramenée dans le plan de la référence : le centrage ne
    sort jamais la face de ce plan (le 3e axe reste au décalage le long de la normale)."""
    delta = face_center(fixed) - _turned_point(motion, face_center(moving))
    extra = NO_OFFSET
    for axis in centered:
        extra = extra + axis.scaled(dot(delta, axis))
    normal = unit(fixed.frame.z)
    return extra - normal.scaled(dot(extra, normal))


def align(
    fixed: FaceTarget,
    moving: FaceTarget,
    mode: AlignMode = AlignMode.AUTO,
    offset: Vec3 = NO_OFFSET,
    axis: Vec3 | None = None,
    centered: tuple[Vec3, ...] = (),
) -> Alignment:
    """:func:`plane_motion` puis, pour chaque axe de ``centered`` (axes X, Y, Z globaux du
    conteneur, unitaires et perpendiculaires), le centre de la face mobile amené sur celui de la
    référence le long de cet axe, **dans le plan de la référence** ; avec les trois axes, les
    deux centres se confondent dans ce plan. Le décalage ``offset`` s'ajoute après le centrage.
    Axe de ``centered`` non fini, nul, ou non perpendiculaire aux autres : :class:`AlignError`."""
    for item in centered:
        if not is_finite(item) or norm(item) <= ANGLE_TOLERANCE:
            raise AlignError(INVALID_AXIS, {})
    axes = tuple(unit(item) for item in centered)
    if any(abs(dot(a, b)) > ANGLE_TOLERANCE for i, a in enumerate(axes) for b in axes[i + 1 :]):
        raise AlignError(SKEWED_AXES, {})
    motion = plane_motion(fixed, moving, mode, offset, axis)
    if not centered:
        return motion
    bare = plane_motion(fixed, moving, mode, NO_OFFSET, axis)
    extra = _centering(bare, fixed, moving, axes)
    if not is_finite(extra):
        raise AlignError(INVALID_OFFSET, {})
    return Alignment(motion.rotation, motion.pivot, motion.shift + extra, motion.angle, motion.mode)


def plane_motion(
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
    être dans leur plan (ni presque : :data:`MIN_AXIS_SLOPE`), le mode d'équerre est refusé, et
    seul ``offset.z`` (écart le long de la normale) compte. Refus (:class:`AlignError`) :
    faces non planes, décalage ou axe non fini."""
    if not (fixed.planar and moving.planar):
        raise AlignError(NOT_PLANAR, {})
    if not is_finite(offset):
        raise AlignError(INVALID_OFFSET, {})
    reference = unit(fixed.frame.z)
    own = unit(moving.frame.z)
    if axis is not None:
        if not is_finite(axis) or norm(axis) <= ANGLE_TOLERANCE:
            raise AlignError(INVALID_AXIS, {})
        if mode is AlignMode.PERPENDICULAR:
            raise AlignError(PERPENDICULAR_ON_AXIS, {})
        return _along_axis(fixed, moving, (reference, own), offset.z, unit(axis))
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
