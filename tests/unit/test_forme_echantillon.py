# SPDX-License-Identifier: LGPL-2.1-or-later
"""Échantillon d'une forme et plafonds de taille (A1, § 4.9 de la spécification de PD-a)."""

from __future__ import annotations

import dataclasses
import math

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.shaped import (
    MAX_COORDINATE_MM,
    MAX_EDGES,
    MAX_FACES,
    MAX_POINTS,
    Axes,
    ShapeSample,
    principal_axes,
)
from tests.unit.aides_forme import X, Y, Z, about_z, box_sample

ORIGIN = Vec3(0, 0, 0)


def test_echantillon_valide_et_gele() -> None:
    sample = box_sample(800, 400, 22)
    assert not sample.exceeds_limits
    assert len(sample.points) == 8
    with pytest.raises(dataclasses.FrozenInstanceError):
        sample.points = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"points": ()}, "points"),
        ({"points": (Vec3(0, math.nan, 0),)}, r"points\[0\]"),
        ({"points": (ORIGIN, Vec3(math.inf, 0, 0))}, r"points\[1\]"),
        ({"points": (Vec3(2 * MAX_COORDINATE_MM, 0, 0),)}, r"points\[0\]"),
        ({"points": (ORIGIN,), "planar_faces": ((ORIGIN, 1.0),)}, r"planar_faces\[0\]"),
        ({"points": (ORIGIN,), "planar_faces": ((Z, 0.0),)}, r"planar_faces\[0\]"),
        ({"points": (ORIGIN,), "planar_faces": ((Z, 1.0), (Z, -2.0))}, r"planar_faces\[1\]"),
        ({"points": (ORIGIN,), "planar_faces": ((Z, math.nan),)}, r"planar_faces\[0\]"),
        ({"points": (ORIGIN,), "planar_faces": ((Vec3(math.nan, 0, 1), 1.0),)}, "planar_faces"),
        ({"points": (ORIGIN,), "straight_edges": ((ORIGIN, 1.0),)}, r"straight_edges\[0\]"),
        ({"points": (ORIGIN,), "straight_edges": ((X, 0.0),)}, r"straight_edges\[0\]"),
        (
            {"points": (ORIGIN,), "straight_edges": ((X, 1.0), (Y, math.inf))},
            r"straight_edges\[1\]",
        ),
    ],
)
def test_valeurs_invalides_citent_le_champ(kwargs: dict[str, object], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        ShapeSample(**kwargs)  # type: ignore[arg-type]


def test_plafonds_exposes() -> None:
    assert (MAX_FACES, MAX_EDGES, MAX_POINTS) == (5_000, 5_000, 20_000)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"points": (ORIGIN,) * (MAX_POINTS + 1)},
        {"points": (ORIGIN,), "planar_faces": ((Z, 1.0),) * (MAX_FACES + 1)},
        {"points": (ORIGIN,), "straight_edges": ((X, 1.0),) * (MAX_EDGES + 1)},
    ],
)
def test_au_dela_des_plafonds_l_echantillon_se_declare_trop_gros(
    kwargs: dict[str, object],
) -> None:
    assert ShapeSample(**kwargs).exceeds_limits  # type: ignore[arg-type]


def test_au_plafond_exact_l_echantillon_reste_valide() -> None:
    sample = ShapeSample((ORIGIN,) * MAX_POINTS, ((Z, 1.0),) * MAX_FACES, ((X, 1.0),) * MAX_EDGES)
    assert not sample.exceeds_limits


def test_trop_gros_les_elements_ne_sont_pas_parcourus() -> None:
    # Valeur invalide (aire nulle) au-delà du plafond : pas d'exception, pas de boucle.
    sample = ShapeSample((ORIGIN,), ((Z, 0.0),) * (MAX_FACES + 1))
    assert sample.exceeds_limits


def test_trop_gros_les_axes_de_la_source_sont_renvoyes() -> None:
    big = ShapeSample(
        tuple(about_z(30)(p) for p in box_sample(800, 400, 22).points) * 2_600,
        box_sample(800, 400, 22, about_z(30)).planar_faces,
    )
    assert big.exceeds_limits
    assert principal_axes(big) == Axes.identity()
    source = Axes(Y, Vec3(-1, 0, 0), Z)
    assert principal_axes(big, source) == source
