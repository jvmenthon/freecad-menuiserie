# SPDX-License-Identifier: LGPL-2.1-or-later
"""Taille initiale d'une pièce limitée par la collision : géométrie pure (cotes par défaut)."""

from __future__ import annotations

from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import limit_dimensions

DEFAULT = Dimensions(1000, 100, 20)


def test_libre_cotes_inchangees() -> None:
    assert limit_dimensions(DEFAULT, lambda _d: True) == DEFAULT


def test_longueur_limitee_au_voisin() -> None:
    """Une pièce voisine à x = 640 : la longueur s'arrête à 640."""
    assert limit_dimensions(DEFAULT, lambda d: d.length <= 640) == Dimensions(640, 100, 20)


def test_longueur_limitee_en_premier() -> None:
    free = lambda d: d.length <= 300 or d.width <= 50  # noqa: E731
    assert limit_dimensions(DEFAULT, free) == Dimensions(300, 100, 20)


def test_deja_en_collision_au_minimum_laisse_la_cote() -> None:
    assert limit_dimensions(DEFAULT, lambda _d: False) == DEFAULT
