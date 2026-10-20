# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apparence d'une pièce d'après la bibliothèque locale, sans interface (critère D3).

Chaque test installe sa bibliothèque temporaire ; aucune texture intégrée n'est utilisée.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

Library = Any  # fixture bibliotheque_temporaire (conftest.BibliothequeTemporaire)

App = pytest.importorskip("FreeCAD")
appearance = pytest.importorskip("freecad.menuiserie.features.appearance")
core_appearance = pytest.importorskip("freecad.menuiserie.core.appearance")
materials = pytest.importorskip("freecad.menuiserie.core.materials")
part_model = pytest.importorskip("freecad.menuiserie.core.part_model")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

LIMIT = 16 * 1024 * 1024
IMAGE = "textures/erable.png"
SIZE = (600.0, 200.0)
MAPLE_RGB = (232, 210, 168)
TEXTURED_MAPLE = {
    "id": "erable",
    "kind": "solid",
    "name": "Érable",
    "density": 650,
    "thicknesses": [22],
    "color": "#E8D2A8",
    "texture": {"image": IMAGE, "size": list(SIZE)},
}


def texture_at(image: Path, folder: Path | None = None) -> Any:
    """Texture de ``image`` (taille ``SIZE``) confinée à ``folder`` (par défaut son dossier)."""
    return materials.Texture(image, SIZE, folder)


def maple_texture(image: Path) -> Any:
    """Texture de l'érable telle que chargée : image sous ``textures/`` du dossier résolu de la
    bibliothèque."""
    return texture_at(image, image.parents[1])


def sized_file(path: Path, size: int) -> Path:
    """Fichier de ``size`` octets (creux au-delà du premier octet : rien n'est écrit)."""
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


def install_textured_maple(library: Library, *, with_image: bool = True) -> Path:
    """Installe l'érable texturé ; l'image (octets quelconques : rien ne la décode ici) est
    écrite si ``with_image``. Renvoie son chemin résolu."""
    image: Path = (library.path.parent / IMAGE).resolve()
    if with_image:
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(64))
    library.installer(TEXTURED_MAPLE)
    return image


def touched(obj: Any) -> bool:
    return "Touched" in obj.State


# --- usable_texture_file -----------------------------------------------------------------


@pytest.mark.parametrize("size", [1, LIMIT])
def test_fichier_utilisable(tmp_path: Path, size: int) -> None:
    assert appearance.usable_texture_file(texture_at(sized_file(tmp_path / "image.png", size)))


def test_limite_partagee_avec_core() -> None:
    assert core_appearance.MAX_TEXTURE_FILE_BYTES == LIMIT


def test_fichiers_inutilisables(tmp_path: Path) -> None:
    broken = tmp_path / "lien.png"
    broken.symlink_to(tmp_path / "disparue.png")
    folder = tmp_path / "dossier.png"
    folder.mkdir()
    refused = [
        tmp_path / "absente.png",
        folder,
        sized_file(tmp_path / "vide.png", 0),
        sized_file(tmp_path / "enorme.png", LIMIT + 1),
        broken,
        Path("/nul\0.png"),
    ]
    assert [path for path in refused if appearance.usable_texture_file(texture_at(path))] == []


def test_fichier_illisible_sans_exception(tmp_path: Path) -> None:
    """Le fichier est ouvert (sans être lu) : sans droit de lecture, il est refusé, sauf pour
    l'administrateur, à qui la lecture reste permise."""
    image = sized_file(tmp_path / "secrete.png", 10)
    os.chmod(image, 0)
    try:
        assert appearance.usable_texture_file(texture_at(image)) == os.access(image, os.R_OK)
    finally:
        os.chmod(image, 0o600)


def test_lien_vers_l_exterieur_apres_le_chargement(tmp_path: Path) -> None:
    """Le confinement au dossier de la bibliothèque est revérifié à chaque ouverture."""
    folder = tmp_path / "dossier"
    folder.mkdir()
    link = folder / "erable.png"
    link.symlink_to(sized_file(tmp_path / "secret.png", 10))
    assert not appearance.usable_texture_file(texture_at(link, folder))


# --- appearance_of -----------------------------------------------------------------------


def test_texture_dans_le_sens_du_fil(document: Any, bibliotheque_temporaire: Library) -> None:
    image = install_textured_maple(bibliotheque_temporaire)
    obj = wood_part.create_wood_part(document, material_id="erable")
    document.recompute()
    grain = part_model.GrainDirection
    expected = core_appearance.Appearance(
        MAPLE_RGB, maple_texture(image), core_appearance.texture_mapping(SIZE, grain.LENGTH)
    )
    assert appearance.appearance_of(obj) == expected
    assert not touched(obj)
    obj.GrainDirection = "Width"
    document.recompute()
    assert appearance.appearance_of(obj).mapping == core_appearance.texture_mapping(
        SIZE, grain.WIDTH
    )
    assert not touched(obj)


def test_image_absente_couleur_seule(document: Any, bibliotheque_temporaire: Library) -> None:
    install_textured_maple(bibliotheque_temporaire, with_image=False)
    obj = wood_part.create_wood_part(document, material_id="erable")
    assert appearance.appearance_of(obj) == core_appearance.Appearance(MAPLE_RGB)


def test_controle_injecte(document: Any, bibliotheque_temporaire: Library) -> None:
    """L'interface fournit son propre contrôle (décodage) : un refus donne la couleur."""
    image = install_textured_maple(bibliotheque_temporaire)
    obj = wood_part.create_wood_part(document, material_id="erable")
    asked: list[Any] = []

    def refuse(texture: Any) -> bool:
        asked.append(texture)
        return False

    assert appearance.appearance_of(obj, refuse) == core_appearance.Appearance(MAPLE_RGB)
    assert asked == [maple_texture(image)]


def test_materiau_inconnu_localement(document: Any, bibliotheque_temporaire: Library) -> None:
    install_textured_maple(bibliotheque_temporaire)
    obj = wood_part.create_wood_part(document, material_id="erable")
    document.recompute()
    bibliotheque_temporaire.retirer()
    assert appearance.appearance_of(obj) is None
    assert not touched(obj)


def test_materiau_sans_texture(document: Any) -> None:
    obj = wood_part.create_wood_part(document, material_id="chene")
    assert appearance.appearance_of(obj) == core_appearance.Appearance((184, 135, 90))
