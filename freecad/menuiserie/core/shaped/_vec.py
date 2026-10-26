# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opérations vectorielles minimales sur :class:`Vec3` (module privé de ``core/shaped``)."""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import Vec3


def dot(a: Vec3, b: Vec3) -> float:
    """Produit scalaire."""
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Produit vectoriel ``a`` puis ``b``."""
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def norm(a: Vec3) -> float:
    """Longueur du vecteur."""
    return math.sqrt(dot(a, a))


def scaled(a: Vec3, factor: float) -> Vec3:
    """Vecteur multiplié par ``factor``."""
    return Vec3(a.x * factor, a.y * factor, a.z * factor)


def added(a: Vec3, b: Vec3) -> Vec3:
    """Somme de deux vecteurs."""
    return Vec3(a.x + b.x, a.y + b.y, a.z + b.z)


def subtracted(a: Vec3, b: Vec3) -> Vec3:
    """Différence ``a - b``."""
    return Vec3(a.x - b.x, a.y - b.y, a.z - b.z)


def unit(a: Vec3, minimum: float = 1e-12) -> Vec3 | None:
    """Vecteur normé, ou ``None`` s'il est (presque) nul."""
    length = norm(a)
    return None if length <= minimum else scaled(a, 1.0 / length)


def is_finite(a: Vec3) -> bool:
    """Vrai si les trois coordonnées sont finies."""
    return math.isfinite(a.x) and math.isfinite(a.y) and math.isfinite(a.z)
