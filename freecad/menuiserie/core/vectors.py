# SPDX-License-Identifier: LGPL-2.1-or-later
"""Calcul vectoriel partagé sur :class:`Vec3` (produits, longueur, vecteur normé).

Somme, différence, opposé et produit par un réel sont des opérateurs et méthodes de
:class:`Vec3` (``a + b``, ``a - b``, ``-a``, ``a.scaled(k)``).
"""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import Vec3

__all__ = ["cross", "dot", "is_finite", "norm", "unit", "unit_or_none"]


def dot(a: Vec3, b: Vec3) -> float:
    """Produit scalaire."""
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Produit vectoriel ``a`` puis ``b``."""
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def norm(a: Vec3) -> float:
    """Longueur du vecteur."""
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3:
    """Vecteur normé (``a`` non nul)."""
    return a.scaled(1.0 / norm(a))


def unit_or_none(a: Vec3, minimum: float = 1e-12) -> Vec3 | None:
    """Vecteur normé, ou ``None`` si sa longueur est inférieure ou égale à ``minimum``."""
    length = norm(a)
    return None if length <= minimum else a.scaled(1.0 / length)


def is_finite(a: Vec3) -> bool:
    """Vrai si les trois coordonnées sont finies."""
    return all(math.isfinite(value) for value in (a.x, a.y, a.z))
