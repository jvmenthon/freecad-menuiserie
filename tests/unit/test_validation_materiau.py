# SPDX-License-Identifier: LGPL-2.1-or-later
"""Validation de ``Material`` et ``Texture`` à la construction (R1) et bornes alignées (R2)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import (
    MAX_ID_LENGTH,
    MAX_NAME_LENGTH,
    MAX_THICKNESS_MM,
    MAX_THICKNESSES,
    Material,
    MaterialKind,
    Severity,
    Texture,
    load_library,
    parse_materials,
)
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM, Dimensions
from tests.unit.aides import OAK, SOURCE, document

IMAGE = Path(__file__).resolve().parent / "textures" / "chene.png"
VALID_TEXTURE = Texture(IMAGE, (600.0, 200.0))


def material(**changes: object) -> Material:
    """Matériau valide, modifié par ``changes`` (valeurs volontairement non typées)."""
    fields: dict[str, object] = {
        "id": "chene",
        "kind": MaterialKind.SOLID,
        "names": {"fr": "Chêne"},
        "density": 710.0,
        "thicknesses": (18.0, 22.0),
        "color": (184, 135, 90),
        "has_grain": True,
        "texture": None,
        **changes,
    }
    return Material(**fields)  # type: ignore[arg-type]


# --- R1 : un cas refusé par règle (au moins), avec le champ cité --------------------------

REJECTED = [
    pytest.param("id", "Chêne", id="id-accent"),
    pytest.param("id", "a" * (MAX_ID_LENGTH + 1), id="id-65-caracteres"),
    pytest.param("id", "", id="id-vide"),
    pytest.param("id", 12, id="id-nombre"),
    pytest.param("kind", "solid", id="kind-texte"),
    pytest.param("names", {}, id="names-vide"),
    pytest.param("names", "Chêne", id="names-texte"),
    pytest.param("names", {"FR": "Chêne"}, id="names-langue-majuscule"),
    pytest.param("names", {"fra": "Chêne"}, id="names-langue-3-lettres"),
    pytest.param("names", {"fr": "   "}, id="names-libelle-blanc"),
    pytest.param("names", {"fr": "x" * (MAX_NAME_LENGTH + 1)}, id="names-81-caracteres"),
    pytest.param("names", {"fr": "Ch\u202eêne"}, id="names-bidi"),
    pytest.param("names", {"fr": 12}, id="names-libelle-nombre"),
    pytest.param("density", 49.999, id="density-sous-minimum"),
    pytest.param("density", 2000.001, id="density-sur-maximum"),
    pytest.param("density", True, id="density-booleen"),
    pytest.param("density", math.nan, id="density-nan"),
    pytest.param("density", "710", id="density-texte"),
    pytest.param("thicknesses", (), id="ep-vide"),
    pytest.param("thicknesses", (0.05,), id="ep-sous-minimum"),
    pytest.param("thicknesses", (MAX_THICKNESS_MM + 0.001,), id="ep-sur-maximum"),
    pytest.param("thicknesses", (True,), id="ep-booleen"),
    pytest.param("thicknesses", (math.inf,), id="ep-infinie"),
    pytest.param("thicknesses", tuple(range(1, MAX_THICKNESSES + 2)), id="ep-51-valeurs"),
    pytest.param("thicknesses", "18", id="ep-texte"),
    pytest.param("color", (0, 0), id="color-2-composantes"),
    pytest.param("color", (0, 0, 0, 0), id="color-4-composantes"),
    pytest.param("color", (256, 0, 0), id="color-256"),
    pytest.param("color", (-1, 0, 0), id="color-negative"),
    pytest.param("color", (True, 0, 0), id="color-booleen"),
    pytest.param("color", (1.0, 0, 0), id="color-flottant"),
    pytest.param("color", "#B8875A", id="color-texte"),
    pytest.param("has_grain", 1, id="has-grain-entier"),
    pytest.param("has_grain", None, id="has-grain-none"),
    pytest.param("texture", "chene.png", id="texture-texte"),
    # Cas limites complémentaires (revue de test J1b).
    pytest.param("id", "Chene", id="id-majuscule"),
    pytest.param("id", "-chene", id="id-tiret-initial"),
    pytest.param("id", "chene-", id="id-tiret-final"),
    pytest.param("id", "cp--bouleau", id="id-double-tiret"),
    pytest.param("kind", 0, id="kind-entier"),
    pytest.param("names", None, id="names-none"),
    pytest.param("names", {1: "Chêne"}, id="names-langue-entier"),
    pytest.param("names", {"fr": "Ch\x00ne"}, id="names-octet-nul"),
    pytest.param("names", {"fr": "Ch\u200bene"}, id="names-espace-sans-chasse"),
    pytest.param("names", {"fr": "Ch\u2028ene"}, id="names-separateur-de-ligne"),
    pytest.param("density", math.inf, id="density-infinie"),
    pytest.param("density", 10**400, id="density-entier-geant"),
    pytest.param("density", None, id="density-none"),
    pytest.param("thicknesses", (math.nan,), id="ep-nan"),
    pytest.param("thicknesses", None, id="ep-none"),
    pytest.param("thicknesses", (0,), id="ep-zero"),
    pytest.param("thicknesses", (-18,), id="ep-negative"),
    pytest.param("thicknesses", (10**400,), id="ep-entier-geant"),
    pytest.param("color", None, id="color-none"),
    pytest.param("has_grain", "true", id="has-grain-texte"),
]


@pytest.mark.parametrize(("field", "value"), REJECTED)
def test_champ_invalide_refuse(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=f"champ « {field} »"):
        material(**{field: value})


# --- R1 : cas limites acceptés et normalisation -------------------------------------------

ACCEPTED = [
    pytest.param("id", "a" * MAX_ID_LENGTH, "a" * MAX_ID_LENGTH, id="id-64-caracteres"),
    pytest.param("id", "1", "1", id="id-un-chiffre"),
    pytest.param("kind", MaterialKind.MELAMINE, MaterialKind.MELAMINE, id="kind-melamine"),
    pytest.param(
        "names",
        {"fr": " " + "x" * MAX_NAME_LENGTH + "\t"},
        {"fr": "x" * MAX_NAME_LENGTH},
        id="names-80-caracteres-apres-strip",
    ),
    pytest.param("names", {"fr": "Che\u0302ne"}, {"fr": "Ch\u00eane"}, id="names-nfc"),
    pytest.param("names", {"en": "Oak"}, {"en": "Oak"}, id="names-anglais-seul"),
    pytest.param("density", 50, 50.0, id="density-minimum-entier"),
    pytest.param("density", 2000.0, 2000.0, id="density-maximum"),
    pytest.param("thicknesses", [0.1], (0.1,), id="ep-minimum"),
    pytest.param("thicknesses", (MAX_THICKNESS_MM,), (300.0,), id="ep-maximum"),
    pytest.param("thicknesses", (22, 18, 22), (18.0, 22.0), id="ep-triees-dedoublonnees"),
    pytest.param(
        "thicknesses",
        tuple(range(MAX_THICKNESSES, 0, -1)),
        tuple(float(e) for e in range(1, MAX_THICKNESSES + 1)),
        id="ep-50-valeurs",
    ),
    pytest.param("color", [0, 0, 0], (0, 0, 0), id="color-noir-liste"),
    pytest.param("color", (255, 255, 255), (255, 255, 255), id="color-blanc"),
    pytest.param("has_grain", False, False, id="has-grain-faux"),
    pytest.param("texture", VALID_TEXTURE, VALID_TEXTURE, id="texture"),
    pytest.param("texture", None, None, id="texture-absente"),
    # Cas limites complémentaires (revue de test J1b).
    pytest.param("id", "cp-bouleau-2", "cp-bouleau-2", id="id-tirets-internes"),
    pytest.param("names", {"fr": "\u00a0Chêne\u00a0"}, {"fr": "Chêne"}, id="names-insecables"),
    pytest.param(
        "names",
        {"fr": "e\u0302" * MAX_NAME_LENGTH},
        {"fr": "ê" * MAX_NAME_LENGTH},
        id="names-nfc-80",
    ),
    pytest.param("thicknesses", (0.1, 0.1, 300), (0.1, 300.0), id="ep-bornes-doublon"),
]


@pytest.mark.parametrize(("field", "value", "expected"), ACCEPTED)
def test_valeur_limite_acceptee_et_normalisee(field: str, value: object, expected: object) -> None:
    assert getattr(material(**{field: value}), field) == expected


def test_epaisseurs_normalisees_en_flottants() -> None:
    thicknesses = material(thicknesses=(22, 18)).thicknesses
    assert all(type(e) is float for e in thicknesses)


def test_identifiant_cite_dans_le_message() -> None:
    with pytest.raises(ValueError, match="matériau « chene », champ « density »"):
        material(density=0)


# --- R1 : Texture ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "image",
    [Path("textures/chene.png"), str(IMAGE)],
    ids=["relatif", "texte"],
)
def test_texture_image_non_absolue_refusee(image: object) -> None:
    with pytest.raises(ValueError, match="champ « image »"):
        Texture(image, (600.0, 200.0))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "size",
    [(9.99, 200), (600, 10_000.01), (600,), (600, 200, 1), (math.nan, 200), (True, 200), "600"],
)
def test_texture_taille_hors_bornes_refusee(size: object) -> None:
    with pytest.raises(ValueError, match="champ « size »"):
        Texture(IMAGE, size)  # type: ignore[arg-type]


def test_texture_taille_limite_acceptee() -> None:
    assert Texture(IMAGE, [10, 10_000]).size == (10.0, 10_000.0)  # type: ignore[arg-type]


def test_texture_dossier_par_defaut_celui_de_l_image() -> None:
    texture = Texture(IMAGE, (600.0, 200.0))
    assert texture.folder == texture.library_folder == IMAGE.parent


def test_texture_dossier_de_bibliotheque_ancetre_de_l_image() -> None:
    folder = IMAGE.parents[1]
    texture = Texture(IMAGE, (600.0, 200.0), folder)
    assert texture.folder == texture.library_folder == folder


@pytest.mark.parametrize(
    "folder",
    [
        pytest.param(Path("relatif"), id="relatif"),
        pytest.param(str(IMAGE.parent), id="texte"),
        pytest.param(IMAGE, id="image-elle-meme"),
        pytest.param(IMAGE.parent / "autre", id="dossier-voisin"),
    ],
)
def test_texture_dossier_qui_ne_contient_pas_l_image_refuse(folder: object) -> None:
    with pytest.raises(ValueError, match="champ « folder »"):
        Texture(IMAGE, (600.0, 200.0), folder)  # type: ignore[arg-type]


# --- R2 : épaisseur minimale alignée sur la plus petite cote -------------------------------


def test_epaisseur_sous_le_minimum_rejette_l_entree() -> None:
    entry = {**OAK, "thicknesses": [0.05]}
    materials, [issue] = parse_materials(document(entry), SOURCE)
    assert materials == []
    assert issue.severity is Severity.ERROR
    assert issue.params["field"] == "thicknesses"
    assert "0,1" in issue.format()
    assert "300" in issue.format()


def test_epaisseur_minimale_acceptee() -> None:
    entry = {**OAK, "thicknesses": [MIN_DIMENSION_MM]}
    [oak], issues = parse_materials(document(entry), SOURCE)
    assert issues == []
    assert oak.thicknesses == (0.1,)


def test_epaisseurs_integrees_sont_des_cotes_valides() -> None:
    library, issues = load_library(DATA_DIR / "materiaux.json", None)
    assert issues == []
    for builtin in library:
        for thickness in builtin.thicknesses:
            assert Dimensions(800, 200, thickness).thickness == thickness
