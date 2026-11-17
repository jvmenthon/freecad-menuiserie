# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sections enlevées par les profils d'arête (ADR 0029). Module privé, Python pur.

Repère de la section : l'origine est sur l'arête ; ``p`` court le long de la première face, à
partir de l'arête (distance ``a``), ``q`` le long de la seconde (distance ``b``). La matière est
du côté ``p ≥ 0``, ``q ≥ 0``. Chaque contour tourne dans le sens direct et reste dans le
rectangle ``[0, étendue p] x [0, étendue q]``.
"""

from __future__ import annotations

import math

from freecad.menuiserie.core._extrusion import Arc, Section, Segment

__all__ = ["beak", "chamfer", "cove", "ogee", "round_corner"]

_RIGHT = math.pi / 2


def chamfer(a: float, b: float) -> Section:
    """Triangle ``(0,0) (a,0) (0,b)`` : ``a`` sur la première face, ``b`` sur la seconde."""
    return Section(
        (
            Segment((0.0, 0.0), (a, 0.0)),
            Segment((a, 0.0), (0.0, b)),
            Segment((0.0, b), (0.0, 0.0)),
        )
    )


def round_corner(a: float, b: float) -> Section:
    """Quart de rond (convexe) : le rectangle ``a x b`` moins le quart d'ellipse de centre
    ``(a, b)``. Aire ``(1 - π/4)·a·b`` ; cercle de rayon ``a`` si ``b == a``."""
    return Section(
        (
            Segment((0.0, 0.0), (a, 0.0)),
            Arc((a, b), a, b, -_RIGHT, -2 * _RIGHT),
            Segment((0.0, b), (0.0, 0.0)),
        )
    )


def cove(radius: float) -> Section:
    """Gorge (concave) : quart de disque de rayon ``radius`` centré sur l'arête. Aire ``π r²/4``."""
    return Section(
        (
            Segment((0.0, 0.0), (radius, 0.0)),
            Arc((0.0, 0.0), radius, radius, 0.0, _RIGHT),
            Segment((0.0, radius), (0.0, 0.0)),
        )
    )


def beak(radius: float, shoulder: float) -> Section:
    """Bec-de-corbin : épaulement droit de hauteur ``shoulder`` le long de la première face,
    surmonté d'un quart de rond de rayon ``radius``. Étendue ``radius x (radius + shoulder)``.
    Aire ``radius·shoulder + (1 - π/4)·radius²``."""
    return Section(
        (
            Segment((0.0, 0.0), (radius, 0.0)),
            Segment((radius, 0.0), (radius, shoulder)),
            Arc((radius, shoulder + radius), radius, radius, -_RIGHT, -2 * _RIGHT),
            Segment((0.0, shoulder + radius), (0.0, 0.0)),
        )
    )


def ogee(width: float, height: float) -> Section:
    """Doucine : deux quarts d'ellipse tangents en S, un cavet (concave) près de la première face
    puis un quart de rond (convexe) tangent à la seconde. Étendue ``width x height``, aire
    ``width·height / 2``."""
    half_w, half_h = width / 2, height / 2
    return Section(
        (
            Segment((0.0, 0.0), (width, 0.0)),
            Arc((half_w, 0.0), half_w, half_h, 0.0, _RIGHT),
            Arc((half_w, height), half_w, half_h, -_RIGHT, -2 * _RIGHT),
            Segment((0.0, height), (0.0, 0.0)),
        )
    )
