# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apparence d'une pièce : projection de la texture et choix couleur / texture (D1, D2)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from freecad.menuiserie.core.appearance import (
    MAX_TEXTURE_FILE_BYTES,
    MAX_TEXTURE_PIXELS,
    TEXTURE_BASE_COLOR,
    Appearance,
    TextureMapping,
    Vector3,
    part_appearance,
    texture_mapping,
)
from freecad.menuiserie.core.materials import Texture
from freecad.menuiserie.core.part_model import GrainDirection
from tests.unit.aides import make_material

IMAGE = Path("/bibliotheque/textures/erable.png").resolve()
SIZE = (600.0, 200.0)
PLAIN = make_material("erable", "Érable")
TEXTURE = Texture(IMAGE, SIZE)
TEXTURED = replace(PLAIN, texture=TEXTURE)


def coordinate(direction: Vector3, point: Vector3) -> float:
    """Coordonnée de texture d'un point du repère local (produit scalaire)."""
    return sum(d * p for d, p in zip(direction, point, strict=True))


class ImageUsable:
    """Contrôle du fichier image simulé, qui retient les textures demandées."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.calls: list[Texture] = []

    def __call__(self, texture: Texture) -> bool:
        self.calls.append(texture)
        return self.answer


# --- D1 : projection ---------------------------------------------------------------------


def test_constantes_de_l_adr() -> None:
    assert TEXTURE_BASE_COLOR == (255, 255, 255)
    assert MAX_TEXTURE_FILE_BYTES == 16 * 1024 * 1024
    assert MAX_TEXTURE_PIXELS == 4096


def test_projection_fil_en_long() -> None:
    mapping = texture_mapping(SIZE, GrainDirection.LENGTH)
    assert mapping.direction_s == pytest.approx((1 / 600, 0, 0))
    assert mapping.direction_t == pytest.approx((0, 1 / 200, 1 / 200))


def test_projection_fil_en_travers() -> None:
    mapping = texture_mapping(SIZE, GrainDirection.WIDTH)
    assert mapping.direction_s == pytest.approx((0, 1 / 600, 0))
    assert mapping.direction_t == pytest.approx((1 / 200, 0, 1 / 200))


def test_sans_fil_comme_fil_en_long() -> None:
    assert texture_mapping(SIZE, GrainDirection.NONE) == texture_mapping(
        SIZE, GrainDirection.LENGTH
    )


@pytest.mark.parametrize("width", [200.0, 22.0, 1000.0])
def test_deux_repetitions_sur_1200_mm(width: float) -> None:
    """Une planche de 1 200 mm montre deux images le long du fil, quelle que soit sa largeur."""
    mapping = texture_mapping(SIZE, GrainDirection.LENGTH)
    assert coordinate(mapping.direction_s, (0.0, width, 22.0)) == 0
    assert coordinate(mapping.direction_s, (1200.0, width, 22.0)) == pytest.approx(2.0)


def test_echelle_reelle_en_travers_du_fil() -> None:
    """T avance d'une image tous les 200 mm, sur la largeur comme sur l'épaisseur."""
    mapping = texture_mapping(SIZE, GrainDirection.WIDTH)
    assert coordinate(mapping.direction_s, (0.0, 600.0, 0.0)) == pytest.approx(1.0)
    assert coordinate(mapping.direction_t, (200.0, 0.0, 0.0)) == pytest.approx(1.0)
    assert coordinate(mapping.direction_t, (0.0, 0.0, 200.0)) == pytest.approx(1.0)


@pytest.mark.parametrize("size", [(0.0, 200.0), (600.0, -1.0), (float("nan"), 1.0)])
def test_taille_invalide_refusee(size: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="taille de texture"):
        texture_mapping(size, GrainDirection.LENGTH)


# --- D2 : couleur ou texture -------------------------------------------------------------


def test_materiau_sans_texture_sans_controle_du_fichier() -> None:
    usable = ImageUsable(True)
    assert part_appearance(PLAIN, GrainDirection.LENGTH, usable) == Appearance(
        color=PLAIN.color, texture=None, mapping=None
    )
    assert usable.calls == []


@pytest.mark.parametrize("grain", list(GrainDirection))
def test_texture_utilisable(grain: GrainDirection) -> None:
    usable = ImageUsable(True)
    appearance = part_appearance(TEXTURED, grain, usable)
    assert appearance == Appearance(PLAIN.color, TEXTURE, texture_mapping(SIZE, grain))
    assert appearance.image == IMAGE
    assert usable.calls == [TEXTURE]


def test_texture_inutilisable_comme_sans_texture() -> None:
    usable = ImageUsable(False)
    assert part_appearance(TEXTURED, GrainDirection.WIDTH, usable) == Appearance(PLAIN.color)
    assert usable.calls == [TEXTURE]


@pytest.mark.parametrize(
    ("texture", "mapping"),
    [(TEXTURE, None), (None, TextureMapping((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))],
)
def test_texture_et_projection_vont_ensemble(
    texture: Texture | None, mapping: TextureMapping | None
) -> None:
    with pytest.raises(ValueError, match="ensemble"):
        Appearance((1, 2, 3), texture, mapping)


def test_couleur_seule_sans_image() -> None:
    assert Appearance((1, 2, 3)).image is None
