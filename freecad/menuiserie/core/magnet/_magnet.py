# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aimantation par axe, redimensionnement, saisie en pixels et tolérance (A3 à A8)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box, Vec3
from freecad.menuiserie.core.magnet._model import (
    MIN_SIZE_MM,
    DragResult,
    Guide,
    Handle,
    MagnetHit,
    MagnetKind,
    PixelTarget,
    ResizeResult,
)

HANDLE_RADIUS_PX = 8.0
_TIE = 9  # décimales au-delà desquelles deux distances sont à égalité
Face = tuple[bool, float]  # (face de fin ?, position de la face sur l'axe)
Point2 = tuple[float, float]


def _in_reach(box: Box, guide: Guide, axis: int, tolerance: float) -> bool:
    """Vrai si le guide recouvre la boîte, à ``tolerance`` près, sur les deux autres axes."""
    return all(
        guide.extent.lo(i) <= box.hi(i) + tolerance and guide.extent.hi(i) >= box.lo(i) - tolerance
        for i in range(3)
        if i != axis
    )


def _kind(guide: Guide, at_end: bool) -> MagnetKind:
    """Contact si les normales sont opposées ; affleurement si elles ont le même sens.

    Une droite ou un point n'a pas de normale : la face les touche (contact)."""
    face_sign = 1 if at_end else -1
    return MagnetKind.FLUSH if guide.sign == face_sign else MagnetKind.CONTACT


def _candidates(
    box: Box, guides: Sequence[Guide], axis: int, faces: Sequence[Face], tolerance: float
) -> list[tuple[tuple[float, float, int], MagnetHit, float]]:
    """Aimantations possibles sur ``axis`` : (clé de tri, résultat, correction à ajouter)."""
    found = []
    for index, guide in enumerate(guides):
        if axis not in guide.magnetic_axes() or not _in_reach(box, guide, axis, tolerance):
            continue
        position = guide.position(axis)
        for at_end, face in faces:
            gap = position - face
            if abs(gap) <= tolerance:
                key = (round(abs(gap), _TIE), round(abs(position - box.center(axis)), _TIE), index)
                found.append(
                    (key, MagnetHit(axis, index, at_end, _kind(guide, at_end), position), gap)
                )
    return found


def _snap_axis(
    box: Box, guides: Sequence[Guide], axis: int, faces: Sequence[Face], tolerance: float
) -> tuple[MagnetHit, float] | None:
    """Meilleure aimantation sur ``axis`` : la face la plus proche d'un guide ; à égalité, le guide
    le plus proche du centre de la boîte (que le curseur tient), puis le premier."""
    found = _candidates(box, guides, axis, faces, tolerance)
    if not found:
        return None
    _, hit, gap = min(found, key=lambda item: item[0])
    return hit, gap


def _check_tolerance(tolerance: float) -> None:
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance : valeur positive ou nulle attendue")


def _shifted(box: Box, delta: Vec3) -> Box:
    low, high = box.min, box.max
    return Box(
        Vec3(low.x + delta.x, low.y + delta.y, low.z + delta.z),
        Vec3(high.x + delta.x, high.y + delta.y, high.z + delta.z),
    )


def magnet(
    box: Box, guides: Sequence[Guide], delta: Vec3, tolerance: float, axes: Sequence[int]
) -> DragResult:
    """Déplacement ``delta`` de ``box`` corrigé pour coller une face à un guide (A3 à A5).

    Chaque axe de ``axes`` est traité seul : la face de début ou de fin de la boîte déplacée la
    plus proche d'un guide à moins de ``tolerance`` s'y colle. Un guide hors de portée de la boîte
    sur les autres axes est ignoré ; sans guide à portée, ``delta`` est inchangé.
    """
    _check_tolerance(tolerance)
    if not set(axes) <= {0, 1, 2}:
        raise ValueError("magnet : axes inclus dans {0, 1, 2} attendus")
    moved = _shifted(box, delta)
    values = [delta.x, delta.y, delta.z]
    hits = []
    for axis in dict.fromkeys(axes):
        faces = ((False, moved.lo(axis)), (True, moved.hi(axis)))
        best = _snap_axis(moved, guides, axis, faces, tolerance)
        if best is not None:
            values[axis] += best[1]
            hits.append(best[0])
    return DragResult(Vec3.of(values), tuple(hits))


def resize(
    box: Box,
    handle: Handle,
    delta: float,
    guides: Sequence[Guide],
    tolerance: float,
    minimum: float = MIN_SIZE_MM,
) -> ResizeResult:
    """Redimensionne ``box`` : la face de ``handle`` est tirée de ``delta`` mm sur son axe (A6).

    Seule cette face bouge, aimantée aux guides ; la cote reste au moins ``minimum``. Les trois
    axes sont permis, y compris l'épaisseur (axe Z) : savoir si la pièce a une poignée dessus est
    l'affaire de l'appelant (massif seulement). ``origin_shift`` vaut la translation de l'origine
    (non nulle seulement pour la poignée de début).
    """
    _check_tolerance(tolerance)
    if not math.isfinite(delta) or not math.isfinite(minimum) or minimum <= 0:
        raise ValueError("resize : delta fini et minimum strictement positif attendus")
    axis, low, high = handle.axis, box.lo(handle.axis), box.hi(handle.axis)
    face = (high if handle.at_end else low) + delta
    best = _snap_axis(box, guides, axis, ((handle.at_end, face),), tolerance)
    hit = None
    if best is not None:
        hit, face = best[0], face + best[1]
    if handle.at_end:
        new_low, new_high = low, max(face, low + minimum)
    else:
        new_low, new_high = min(face, high - minimum), high
    final = new_high if handle.at_end else new_low
    if hit is not None and abs(final - hit.position) > CONTACT_TOLERANCE_MM:
        hit = None  # la borne de 1 mm l'a emporté sur l'aimant
    shift = [0.0, 0.0, 0.0]
    shift[axis] = new_low - low
    return ResizeResult(new_high - new_low, Vec3.of(shift), hit)


def _segment_distance(point: Point2, start: Point2, end: Point2) -> float | None:
    """Distance d'un point à un segment ; ``None`` si le segment est un point (flèche de bout)."""
    sx, sy = end[0] - start[0], end[1] - start[1]
    squared = sx * sx + sy * sy
    if squared < 1.0:
        return None
    t = ((point[0] - start[0]) * sx + (point[1] - start[1]) * sy) / squared
    t = min(1.0, max(0.0, t))
    return math.hypot(point[0] - start[0] - t * sx, point[1] - start[1] - t * sy)


def _pixel_distance(target: PixelTarget, cursor: Point2) -> float | None:
    if target.end is None:
        return math.hypot(cursor[0] - target.start[0], cursor[1] - target.start[1])
    return _segment_distance(cursor, target.start, target.end)


def handle_at(
    handles_px: Sequence[PixelTarget], cursor_px: Point2, radius: float = HANDLE_RADIUS_PX
) -> str | None:
    """Clé de la flèche (segment projeté) ou de la poignée la plus proche du curseur, à moins de
    ``radius`` pixels, sinon ``None`` (A7). À égalité, la poignée l'emporte, puis la première.

    Une flèche vue de bout (segment réduit à un point) n'est pas saisissable. Un curseur ou un
    rayon non fini est refusé (``ValueError``).
    """
    if not all(math.isfinite(v) for v in (*cursor_px, radius)):
        raise ValueError("handle_at : curseur et rayon finis attendus")
    best: tuple[tuple[float, bool, int], str] | None = None
    for index, target in enumerate(handles_px):
        distance = _pixel_distance(target, cursor_px)
        if distance is None or distance > radius:
            continue
        key = (round(distance, _TIE), target.end is not None, index)
        if best is None or key < best[0]:
            best = (key, target.key)
    return None if best is None else best[1]


def mm_per_pixel(p0: Vec3, p1: Vec3, px: float) -> float:
    """Longueur en mm de ``px`` pixels, d'après deux points ``p0`` et ``p1`` (mm) qui se
    projettent à un pixel d'écart ; jamais nulle ni négative (A8).

    Un résultat trop petit (points confondus, ``px`` nul) est ramené à ``CONTACT_TOLERANCE_MM``.
    """
    if not all(math.isfinite(v) for v in (p0.x, p0.y, p0.z, p1.x, p1.y, p1.z, px)):
        raise ValueError("mm_per_pixel : valeurs non finies")
    distance = math.dist((p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z))
    return max(distance * abs(px), CONTACT_TOLERANCE_MM)
