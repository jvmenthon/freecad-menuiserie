# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coupe d'un profil sur une arête quelconque (ADR 0063). Module privé, Python pur.

Une arête d'une pièce dessinée n'est plus l'une des 12 d'une boîte : ``features/`` lit la forme
FreeCAD et décrit l'arête par des nombres (:class:`EdgeFrame`) ; ce module en tire la section
enlevée, balayée le long de l'arête. À angle droit, la coupe est celle d'une boîte (ADR 0029).

Repère de la section : origine sur l'arête, ``u`` le long de la première face (vers l'intérieur
de la face), ``v`` perpendiculaire à ``u`` du côté de la seconde face ; la seconde face part
dans la direction ``(cos t, sin t)``, ``t`` étant l'angle de la matière entre les deux faces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core._extrusion import Extrusion
from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.edges._cut import MAX_SIZE_RATIO, OVERSHOOT_MM, resolved_sizes
from freecad.menuiserie.core.edges._families import FAMILIES, EdgeFamily, family_for
from freecad.menuiserie.core.edges._ids import EdgeError
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.vectors import cross, dot, norm, unit

__all__ = [
    "ANGLED_FAMILIES",
    "MAX_ANGLE_DEG",
    "MIN_ANGLE_DEG",
    "RIGHT_ANGLE_TOLERANCE_DEG",
    "EdgeFrame",
    "edge_cut_in_frame",
    "frame_refusal",
]

MIN_ANGLE_DEG: Final = 30.0  # angle de matière le plus aigu accepté
MAX_ANGLE_DEG: Final = 150.0  # le plus ouvert (au-delà, l'arête est presque plate)
RIGHT_ANGLE_TOLERANCE_DEG: Final = 0.5  # angle « droit » à ce jeu près
_ANGLE_SLACK_DEG: Final = 1e-6  # arrondis du calcul de l'angle aux bornes

# Familles calculées à tout angle (lu dans le registre) ; les autres exigent un angle droit.
ANGLED_FAMILIES: Final = frozenset(family for family, s in FAMILIES.items() if s.any_angle)

_CONCAVE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Arête {edge} rentrante : il n'y a pas de matière à enlever."
)
_BAD_ANGLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Arête {edge} : ses faces forment un angle de {angle}°, il doit être entre {minimum}° et "
    "{maximum}°.",
)
_RIGHT_ONLY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Arête {edge} à {angle}° : ce profil exige une arête à angle droit (chanfrein, quart de rond "
    "et gorge acceptent les autres angles).",
)
_TOO_BIG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Profil de l'arête {edge} trop grand : il peut occuper au plus {first} mm sur la première "
    "face et {second} mm sur la seconde.",
)


@dataclass(frozen=True)
class EdgeFrame:
    """Arête droite entre deux faces planes, lue sur la forme par ``features/``.

    ``start`` est un bout de l'arête, ``direction`` (unitaire) va vers l'autre, ``length`` mm plus
    loin. ``first`` et ``second`` sont les directions unitaires, perpendiculaires à l'arête, qui
    partent de l'arête dans chacune des deux faces. ``convex`` : la matière est dans l'angle
    entre ``first`` et ``second`` (arête saillante). ``room_first`` et ``room_second`` : largeur
    de chaque face mesurée perpendiculairement à l'arête. ``extend_start`` / ``extend_end`` : le
    prolongement de l'arête sort du solide à ce bout (dépassement franc autorisé). ``name`` :
    nom affiché dans les messages (« Edge7 »).
    """

    name: str
    start: Vec3
    direction: Vec3
    length: float
    first: Vec3
    second: Vec3
    convex: bool
    room_first: float
    room_second: float
    extend_start: bool = True
    extend_end: bool = True

    def __post_init__(self) -> None:
        numbers = (self.length, self.room_first, self.room_second)
        if not all(isinstance(n, int | float) and math.isfinite(n) for n in numbers):
            raise ValueError("repère d'arête : nombres finis attendus")
        if self.length <= 0:
            raise ValueError("repère d'arête : longueur > 0 attendue")
        for axis in (self.direction, self.first, self.second):
            if abs(norm(axis) - 1.0) > 1e-6:
                raise ValueError("repère d'arête : directions unitaires attendues")
        if abs(dot(self.first, self.direction)) > 1e-6 or abs(dot(self.second, self.direction)) > (
            1e-6
        ):
            raise ValueError("repère d'arête : faces perpendiculaires à l'arête attendues")

    @property
    def angle(self) -> float:
        """Angle entre les deux faces, en degrés, dans ``[0, 180]``."""
        cosine = max(-1.0, min(1.0, dot(self.first, self.second)))
        return math.degrees(math.acos(cosine))

    @property
    def right_angled(self) -> bool:
        """Vrai si les deux faces sont d'équerre (au jeu près)."""
        return abs(self.angle - 90.0) <= RIGHT_ANGLE_TOLERANCE_DEG


def _degrees(value: float) -> str:
    return decimal_text(round(value, 1))


def frame_refusal(frame: EdgeFrame, family: EdgeFamily | str) -> EdgeError | None:
    """Raison pour laquelle ``family`` ne peut pas profiler l'arête ``frame`` (``None`` sinon) :
    arête rentrante, angle hors bornes, famille qui exige un angle droit."""
    if not frame.convex:
        return EdgeError(_CONCAVE, {"edge": frame.name})
    angle = frame.angle
    if not MIN_ANGLE_DEG - _ANGLE_SLACK_DEG <= angle <= MAX_ANGLE_DEG + _ANGLE_SLACK_DEG:
        return EdgeError(
            _BAD_ANGLE,
            {
                "edge": frame.name,
                "angle": _degrees(angle),
                "minimum": _degrees(MIN_ANGLE_DEG),
                "maximum": _degrees(MAX_ANGLE_DEG),
            },
        )
    if not frame.right_angled and not family_for(family).any_angle:
        return EdgeError(_RIGHT_ONLY, {"edge": frame.name, "angle": _degrees(angle)})
    return None


def edge_cut_in_frame(
    frame: EdgeFrame, family: EdgeFamily | str, a: float, b: float = 0.0
) -> Extrusion:
    """Section du profil balayée le long de l'arête ``frame`` (dans le repère de la forme).

    À angle droit, mêmes section et encombrement que :func:`~._cut.edge_cut` ; sinon chanfrein,
    quart de rond (``b`` ignorée : arc de rayon ``a``) et gorge. Le balayage dépasse l'arête de
    :data:`OVERSHOOT_MM` aux bouts où son prolongement sort du solide. ``EdgeError`` si l'arête
    est refusée (:func:`frame_refusal`), si une cote est trop petite ou si l'encombrement dépasse
    la moitié d'une face voisine.
    """
    family = EdgeFamily(family)
    refusal = frame_refusal(frame, family)
    if refusal is not None:
        raise refusal
    strategy = family_for(family)
    a, b = resolved_sizes(family, a, b, frame.name)
    if frame.right_angled:
        section = strategy.section(a, b)
        extent = strategy.extent(a, b)
    else:
        angle = math.radians(frame.angle)
        section = strategy.angled_section(a, b, angle)
        extent = strategy.angled_extent(a, b, angle)
    room = (MAX_SIZE_RATIO * frame.room_first, MAX_SIZE_RATIO * frame.room_second)
    if extent[0] > room[0] + 1e-9 or extent[1] > room[1] + 1e-9:
        raise EdgeError(
            _TOO_BIG,
            {
                "edge": frame.name,
                "first": decimal_text(round(room[0], 2)),
                "second": decimal_text(round(room[1], 2)),
            },
        )
    u_axis = frame.first
    v_axis = unit(frame.second - u_axis.scaled(dot(frame.second, u_axis)))
    direction = unit(cross(u_axis, v_axis))
    v_axis = unit(cross(direction, u_axis))  # exactement orthonormé, aux arrondis près
    before = OVERSHOOT_MM if frame.extend_start else 0.0
    after = OVERSHOOT_MM if frame.extend_end else 0.0
    sign = 1.0 if dot(direction, frame.direction) > 0 else -1.0
    origin = frame.start - frame.direction.scaled(before)
    if sign < 0:  # le balayage part de l'autre bout, toujours dans le sens de ``direction``
        origin = frame.start + frame.direction.scaled(frame.length + after)
    return Extrusion(
        section=section,
        origin=origin,
        u_axis=u_axis,
        v_axis=v_axis,
        direction=direction,
        length=frame.length + before + after,
    )
