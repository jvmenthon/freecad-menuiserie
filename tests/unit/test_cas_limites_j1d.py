# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de la projection des textures et du choix couleur / texture (lot J1d, D1, D2).

Un défaut constaté serait marqué ``xfail(strict=True)`` et numéroté (D1, D2…) ; aucun à ce jour.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from freecad.menuiserie.core.appearance import (
    Appearance,
    TextureMapping,
    Vector3,
    part_appearance,
    texture_mapping,
)
from freecad.menuiserie.core.materials import (
    MAX_TEXTURE_SIZE_MM,
    MIN_TEXTURE_SIZE_MM,
    Texture,
)
from freecad.menuiserie.core.part_model import GrainDirection
from tests.unit.aides import make_material

IMAGE = Path("/bibliotheque/textures/erable.png").resolve()
EXTREMES = [MIN_TEXTURE_SIZE_MM, MAX_TEXTURE_SIZE_MM]
PLAIN = make_material("erable", "Érable")


def dot(direction: Vector3, point: Vector3) -> float:
    return sum(d * p for d, p in zip(direction, point, strict=True))


def on_axis(index: int, value: float) -> Vector3:
    """Point du repère local à ``value`` mm sur l'axe ``index`` (0 = X, 1 = Y, 2 = Z)."""
    x, y, z = (value if i == index else 0.0 for i in range(3))
    return x, y, z


def grain_axis(grain: GrainDirection) -> int:
    """Indice de l'axe local du fil : Y pour ``WIDTH``, X sinon."""
    return 1 if grain is GrainDirection.WIDTH else 0


@pytest.mark.parametrize("grain", list(GrainDirection))
@pytest.mark.parametrize("width", EXTREMES)
@pytest.mark.parametrize("height", EXTREMES)
def test_projection_aux_tailles_extremes(
    grain: GrainDirection, width: float, height: float
) -> None:
    """10 mm et 10 000 mm : une répétition de l'image tous les ``width`` mm le long du fil et
    tous les ``height`` mm en travers (largeur et épaisseur)."""
    mapping = texture_mapping((width, height), grain)
    along = on_axis(grain_axis(grain), width)
    across = on_axis(1 - grain_axis(grain), height)
    thickness = on_axis(2, height)
    assert dot(mapping.direction_s, along) == pytest.approx(1.0)
    assert dot(mapping.direction_t, along) == 0
    assert dot(mapping.direction_t, across) == pytest.approx(1.0)
    assert dot(mapping.direction_s, across) == 0
    assert dot(mapping.direction_t, thickness) == pytest.approx(1.0)
    assert dot(mapping.direction_s, thickness) == 0


@pytest.mark.parametrize(
    ("size", "length", "repetitions"),
    [((10.0, 10.0), 10_000.0, 1000.0), ((10_000.0, 10.0), 10.0, 0.001), ((600.0, 200.0), 0.0, 0)],
)
def test_repetitions_sur_grandes_et_petites_pieces(
    size: tuple[float, float], length: float, repetitions: float
) -> None:
    """Nombre d'images le long du fil sur une pièce de 10 m, de 10 mm, ou au point d'origine."""
    mapping = texture_mapping(size, GrainDirection.LENGTH)
    assert dot(mapping.direction_s, (length, 2_000.0, 100.0)) == pytest.approx(repetitions)


@pytest.mark.parametrize(
    "size",
    [
        (math.inf, 200.0),
        (600.0, math.inf),
        (-math.inf, 200.0),
        (600.0, -0.0),
        (-600.0, -200.0),
        (math.nan, math.nan),
    ],
)
def test_tailles_non_finies_ou_negatives_refusees(size: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="taille de texture"):
        texture_mapping(size, GrainDirection.WIDTH)


def test_taille_minuscule_mais_valide_sans_division_par_zero() -> None:
    """``texture_mapping`` n'impose pas la borne de 10 mm de la bibliothèque : seule une taille
    nulle, négative ou non finie est refusée."""
    mapping = texture_mapping((1e-300, 1e300), GrainDirection.LENGTH)
    assert all(math.isfinite(value) for value in mapping.direction_s + mapping.direction_t)


def test_fil_en_long_et_en_travers_echangent_x_et_y() -> None:
    long = texture_mapping((600.0, 200.0), GrainDirection.LENGTH)
    cross = texture_mapping((600.0, 200.0), GrainDirection.WIDTH)
    swap = (1, 0, 2)
    assert tuple(long.direction_s[i] for i in swap) == cross.direction_s
    assert tuple(long.direction_t[i] for i in swap) == cross.direction_t


def test_resultats_immuables() -> None:
    mapping = texture_mapping((600.0, 200.0), GrainDirection.LENGTH)
    appearance = Appearance((1, 2, 3), Texture(IMAGE, (600.0, 200.0)), mapping)
    with pytest.raises(FrozenInstanceError):
        mapping.direction_s = (0.0, 0.0, 0.0)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        appearance.texture = None  # type: ignore[misc]


@pytest.mark.parametrize("size", [(MIN_TEXTURE_SIZE_MM,) * 2, (MAX_TEXTURE_SIZE_MM,) * 2])
@pytest.mark.parametrize("grain", list(GrainDirection))
def test_part_appearance_aux_tailles_extremes(
    size: tuple[float, float], grain: GrainDirection
) -> None:
    texture = Texture(IMAGE, size)
    textured = replace(PLAIN, texture=texture)
    appearance = part_appearance(textured, grain, lambda _texture: True)
    assert appearance == Appearance(PLAIN.color, texture, texture_mapping(size, grain))
    assert appearance.image == IMAGE


def test_texture_vers_sans_texture_et_inverse() -> None:
    """Le choix ne garde aucun état : changer de matériau dans un sens puis dans l'autre redonne
    exactement les mêmes apparences."""
    textured = replace(PLAIN, texture=Texture(IMAGE, (600.0, 200.0)))
    first = part_appearance(textured, GrainDirection.WIDTH, lambda _texture: True)
    plain = part_appearance(PLAIN, GrainDirection.WIDTH, lambda _texture: True)
    again = part_appearance(textured, GrainDirection.WIDTH, lambda _texture: True)
    assert plain == Appearance(PLAIN.color)
    assert first == again
    assert first.mapping == TextureMapping((0.0, 1 / 600, 0.0), (1 / 200, 0.0, 1 / 200))


def test_controle_qui_leve_une_exception_n_est_pas_masque() -> None:
    """``part_appearance`` ne rattrape rien : c'est au contrôle fourni de ne jamais lever (D3)."""
    textured = replace(PLAIN, texture=Texture(IMAGE, (600.0, 200.0)))

    def broken(_texture: Texture) -> bool:
        raise OSError("disque")

    with pytest.raises(OSError, match="disque"):
        part_appearance(textured, GrainDirection.LENGTH, broken)
