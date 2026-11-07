# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fonctions de perçage pour les coulisses de tiroir.

Ce module contient les fonctions de création des trous et du corps de la coulisse.
"""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import Box, Vec3

from ._params import (
    FIRST_HOLE_MM,
    HOLE_STEP_MM,
    MIN_BOTTOM_MM,
    CONTACT_TOLERANCE_MM,
)


def _holes(length: float, count: int) -> tuple[float, ...]:
    """Calcule les positions des trous au pas du système 32.

    Les trous sont placés :
    - Le premier à 37 mm de l'avant
    - Les suivants répartis par multiples de 32 mm
    - Jusqu'à 37 mm du bout

    Args:
        length: Longueur de la coulisse
        count: Nombre de trous

    Returns:
        tuple[float, ...]: Positions des trous depuis l'avant de la coulisse
    """
    step = HOLE_STEP_MM * max(
        1,
        math.floor((length - 2 * FIRST_HOLE_MM) / (HOLE_STEP_MM * (count - 1))),
    )
    return tuple(FIRST_HOLE_MM + index * step for index in range(count))


def _front(frame: "_Frame", params: "SlideParams") -> tuple[float, int]:
    """Calcule la coordonnée de l'avant de la coulisse sur l'axe de longueur.

    Args:
        frame: Le cadre de référence
        params: Les paramètres de la coulisse

    Returns:
        tuple[float, int]: (coordonnée, sens vers l'arrière)
    """
    from ._params import _Frame, SlideParams

    box = frame.overlap
    if params.reversed:
        return box.hi(frame.length_axis) - params.front_setback, -1
    return box.lo(frame.length_axis) + params.front_setback, 1


def _along(frame: "_Frame", params: "SlideParams", distance: float) -> Vec3:
    """Calcule un point sur l'axe de la coulisse.

    Args:
        frame: Le cadre de référence
        params: Les paramètres de la coulisse
        distance: Distance depuis l'avant de la coulisse

    Returns:
        Vec3: Point à mi-hauteur de la coulisse
    """
    from ._params import _Frame, SlideParams

    start, direction = _front(frame, params)
    point = Vec3(0.0, 0.0, 0.0).with_component(frame.length_axis, start + direction * distance)
    middle = frame.overlap.center(frame.height_axis) + params.height_offset
    return point.with_component(frame.height_axis, middle)


def _depth(thickness: float, wanted: float) -> float:
    """Calcule la profondeur effective d'un trou.

    Args:
        thickness: Épaisseur de la pièce
        wanted: Profondeur souhaitée

    Returns:
        float: Profondeur effective

    Raises:
        JointError: Si le trou serait trop profond
    """
    from freecad.menuiserie.core.geometry import JointError
    from freecad.menuiserie.core.i18n import mm_text
    from ._params import HOLE_TOO_DEEP, MIN_BOTTOM_MM

    if wanted > thickness - MIN_BOTTOM_MM + CONTACT_TOLERANCE_MM:
        text = {
            "depth": mm_text(wanted),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)
    return wanted


def _body(frame: "_Frame", params: "SlideParams", values: "SlideValues") -> Box:
    """Crée le corps de la coulisse.

    La coulisse est une boîte collée au côté du caisson, de toute son épaisseur.
    Elle déborde dans le côté du tiroir si le jeu manque.

    Args:
        frame: Le cadre de référence
        params: Les paramètres de la coulisse
        values: Les valeurs calculées

    Returns:
        Box: La boîte représentant le corps de la coulisse
    """
    from ._params import _Frame, SlideParams, SlideValues

    start, direction = _front(frame, params)
    end = start + direction * values.length

    # Position verticale de la coulisse
    middle = frame.overlap.center(frame.height_axis) + params.height_offset

    # Plan extérieur de la coulisse
    far = frame.host_plane + frame.sign * params.thickness

    # Créer la boîte de la coulisse
    box = frame.overlap.with_range(frame.length_axis, min(start, end), max(start, end))
    box = box.with_range(
        frame.height_axis,
        middle - params.slide_height / 2,
        middle + params.slide_height / 2,
    )
    return box.with_range(frame.normal, min(frame.host_plane, far), max(frame.host_plane, far))
