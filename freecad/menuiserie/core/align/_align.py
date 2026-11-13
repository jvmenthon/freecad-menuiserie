# SPDX-License-Identifier: LGPL-2.1-or-later
"""Amener une face mobile dans le plan d'une face de référence (AL-a, ADR 0054).

Le mouvement est rigide et se fait en deux temps : une **rotation minimale** autour d'un point de
la face mobile qui rend les deux faces parallèles, puis une **translation le long de la normale**
de la référence qui les rend coplanaires. Deux modes : ``FLUSH`` (au ras : normales sortantes de
même sens, les deux faces regardent du même côté) et ``FACING`` (face contre face : normales
opposées, les pièces se touchent). ``AUTO`` prend celui qui demande la plus petite rotation.
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

_IDENTITY: Final[Matrix3] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class AlignError(TemplatedError):
    """Alignement impossible ; message = gabarit français (``QT_TRANSLATE_NOOP``) rempli."""


class AlignMode(Enum):
    """Côté vers lequel regarde la face mobile une fois alignée."""

    AUTO = "auto"  # la plus petite rotation
    FLUSH = "flush"  # au ras : même sens que la référence
    FACING = "facing"  # face contre face : sens opposé


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


def align(fixed: FaceTarget, moving: FaceTarget, mode: AlignMode = AlignMode.AUTO) -> Alignment:
    """Mouvement de la pièce de ``moving`` qui met sa face dans le plan de ``fixed``.

    Le pivot est l'origine du repère de la face mobile (un point du plan mobile : il reste dans le
    plan). Faces non planes : :class:`AlignError`."""
    if not (fixed.planar and moving.planar):
        raise AlignError(NOT_PLANAR, {})
    reference = unit(fixed.frame.z)
    own = unit(moving.frame.z)
    chosen = _mode_of(reference, own, mode)
    wanted = reference if chosen is AlignMode.FLUSH else reference.scaled(-1.0)
    rotation, angle = _rotation_between(own, wanted, unit(moving.frame.x))
    pivot = moving.frame.origin
    offset = dot(fixed.frame.origin - pivot, reference)  # le pivot reste dans le plan mobile
    return Alignment(rotation, pivot, reference.scaled(offset), angle, chosen)
