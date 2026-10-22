# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opérations vectorielles élémentaires sur :class:`Vec3` (module privé de ``core/snap/``)."""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import Vec3


def add(a: Vec3, b: Vec3) -> Vec3:
    """Somme ``a + b``."""
    return Vec3(a.x + b.x, a.y + b.y, a.z + b.z)


def sub(a: Vec3, b: Vec3) -> Vec3:
    """Différence ``a - b``."""
    return Vec3(a.x - b.x, a.y - b.y, a.z - b.z)


def scale(a: Vec3, factor: float) -> Vec3:
    """Vecteur ``a`` multiplié par ``factor``."""
    return Vec3(a.x * factor, a.y * factor, a.z * factor)


def dot(a: Vec3, b: Vec3) -> float:
    """Produit scalaire."""
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Produit vectoriel ``a ∧ b``."""
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def norm(a: Vec3) -> float:
    """Longueur du vecteur."""
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3:
    """Vecteur normé (``a`` non nul)."""
    return scale(a, 1.0 / norm(a))


def is_finite(a: Vec3) -> bool:
    """Vrai si les trois coordonnées sont finies."""
    return all(math.isfinite(value) for value in (a.x, a.y, a.z))
