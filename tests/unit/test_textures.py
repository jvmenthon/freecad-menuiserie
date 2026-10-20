# SPDX-License-Identifier: LGPL-2.1-or-later
"""Textures facultatives des matériaux (critère A10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import (
    MAX_TEXTURE_PATH_LENGTH,
    MAX_TEXTURE_SIZE_MM,
    MIN_TEXTURE_SIZE_MM,
    LibraryIssue,
    Material,
    Severity,
    Texture,
    load_library,
    parse_materials,
    read_materials_file,
)
from tests.unit.aides import OAK, SOURCE, requires_symlinks


def entry(texture: object) -> dict[str, object]:
    """Entrée valide « erable » munie de la texture donnée."""
    return {
        "id": "erable",
        "kind": "solid",
        "name": "Érable",
        "density": 650,
        "thicknesses": [22],
        "color": "#E8D2A8",
        "texture": texture,
    }


def texture(image: object = "textures/erable.jpg", size: object = (600, 200)) -> dict[str, object]:
    return {"image": image, "size": list(size) if isinstance(size, tuple) else size}


def parse(raw_texture: object, folder: Path | None) -> tuple[list[Material], list[LibraryIssue]]:
    """Analyse ``OAK`` suivi de l'érable texturé ; ``OAK`` doit toujours rester chargé."""
    document = {"format": 1, "materials": [OAK, entry(raw_texture)]}
    materials, issues = parse_materials(document, SOURCE, folder)
    assert materials[0].id == "chene"
    return materials[1:], issues


def rejected_field(raw_texture: object, folder: Path) -> str:
    """Champ cité par l'unique erreur ; l'entrée texturée doit être rejetée."""
    materials, issues = parse(raw_texture, folder)
    assert materials == []
    [issue] = [i for i in issues if i.severity is Severity.ERROR]
    assert issue.material_id == "erable"
    assert SOURCE in issue.format()
    return issue.params["field"]


# --- Textures acceptées ----------------------------------------------------------------


def test_texture_resolue_dans_le_dossier_du_fichier(tmp_path: Path) -> None:
    [material], issues = parse(texture(), tmp_path)
    assert issues == []
    assert material.texture == Texture(
        (tmp_path / "textures" / "erable.jpg").resolve(), (600.0, 200.0), tmp_path.resolve()
    )
    assert material.texture.image.is_absolute()
    assert not material.texture.image.exists()  # l'existence n'est pas vérifiée par core/


def test_materiau_sans_texture(tmp_path: Path) -> None:
    document = {"format": 1, "materials": [OAK]}
    [material], issues = parse_materials(document, SOURCE, tmp_path)
    assert issues == []
    assert material.texture is None


@pytest.mark.parametrize(
    "image",
    [
        "erable.png",
        "textures/erable.jpeg",
        "textures/ERABLE.JPG",
        "./textures/erable.png",
        "textures/bois clair/érable.png",
        "a" * (MAX_TEXTURE_PATH_LENGTH - 4) + ".png",
    ],
)
def test_chemin_d_image_accepte(tmp_path: Path, image: str) -> None:
    [material], issues = parse(texture(image=image), tmp_path)
    assert issues == []
    assert material.texture is not None
    assert material.texture.image == (tmp_path / image).resolve()


@pytest.mark.parametrize("size", [(MIN_TEXTURE_SIZE_MM, MAX_TEXTURE_SIZE_MM), (600.5, 1e3)])
def test_taille_aux_bornes_acceptee(tmp_path: Path, size: tuple[float, float]) -> None:
    [material], issues = parse(texture(size=size), tmp_path)
    assert issues == []
    assert material.texture is not None
    assert material.texture.size == (float(size[0]), float(size[1]))


@requires_symlinks
def test_lien_symbolique_interne_accepte(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "textures").symlink_to(tmp_path / "images")
    [material], issues = parse(texture(), tmp_path)
    assert issues == []
    assert material.texture is not None
    assert material.texture.image == (tmp_path / "images" / "erable.jpg").resolve()
    assert material.texture.folder == tmp_path.resolve()


@requires_symlinks
def test_dossier_de_bibliotheque_lien_resolu_vers_sa_cible(tmp_path: Path) -> None:
    (tmp_path / "vrai").mkdir()
    (tmp_path / "lien").symlink_to(tmp_path / "vrai")
    [material], issues = parse(texture(), tmp_path / "lien")
    assert issues == []
    assert material.texture is not None
    assert material.texture.folder == (tmp_path / "vrai").resolve()
    assert material.texture.image == (tmp_path / "vrai" / "textures" / "erable.jpg").resolve()


def test_cle_inconnue_dans_la_texture_signalee_sans_rejet(tmp_path: Path) -> None:
    raw = {**texture(), "rotation": 90}
    [material], [issue] = parse(raw, tmp_path)
    assert material.texture is not None
    assert issue.severity is Severity.WARNING
    assert issue.params["keys"] == "« texture.rotation »"


def test_materiau_texture_hachable(tmp_path: Path) -> None:
    [material], _ = parse(texture(), tmp_path)
    assert len({material, material}) == 1


# --- Textures refusées : entrée rejetée, champ cité ---------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("textures/erable.jpg", id="chaine"),
        pytest.param(None, id="null"),
        pytest.param(["textures/erable.jpg", [600, 200]], id="liste"),
    ],
)
def test_texture_qui_n_est_pas_un_objet(tmp_path: Path, raw: object) -> None:
    assert rejected_field(raw, tmp_path) == "texture"


@pytest.mark.parametrize("key", ["image", "size"])
def test_cle_obligatoire_de_texture_absente(tmp_path: Path, key: str) -> None:
    raw = texture()
    del raw[key]
    assert rejected_field(raw, tmp_path) == f"texture.{key}"


@pytest.mark.parametrize(
    "image",
    [
        pytest.param("", id="vide"),
        pytest.param("a" * (MAX_TEXTURE_PATH_LENGTH - 3) + ".png", id="256-caracteres"),
        pytest.param(42, id="nombre"),
        pytest.param(None, id="null"),
        pytest.param("/textures/erable.png", id="absolu-posix"),
        pytest.param("C:/textures/erable.png", id="absolu-windows"),
        pytest.param("C:erable.png", id="lecteur-windows"),
        pytest.param("\\\\serveur\\partage\\erable.png", id="chemin-unc"),
        pytest.param("textures\\erable.png", id="separateur-windows"),
        pytest.param("../erable.png", id="parent"),
        pytest.param("textures/../erable.png", id="parent-interne"),
        pytest.param("textures/../../erable.png", id="parent-hors-dossier"),
        pytest.param("textures/erable.gif", id="extension-gif"),
        pytest.param("textures/erable.svg", id="extension-svg"),
        pytest.param("textures/erable", id="sans-extension"),
        pytest.param("textures/.png", id="fichier-cache-sans-extension"),
        pytest.param("textures/erable.png/", id="dossier"),
        pytest.param("textures/erable\x00.png", id="octet-nul"),
        pytest.param("textures/\u202eerable.png", id="inversion-bidi"),
        pytest.param("textures/erable.png\n", id="saut-de-ligne"),
    ],
)
def test_chemin_d_image_refuse(tmp_path: Path, image: object) -> None:
    assert rejected_field(texture(image=image), tmp_path) == "texture.image"


@pytest.mark.parametrize(
    "size",
    [
        pytest.param([MIN_TEXTURE_SIZE_MM - 0.01, 100], id="largeur-trop-petite"),
        pytest.param([100, MAX_TEXTURE_SIZE_MM + 0.01], id="hauteur-trop-grande"),
        pytest.param([0, 100], id="nulle"),
        pytest.param([-600, 200], id="negative"),
        pytest.param([600], id="une-valeur"),
        pytest.param([600, 200, 1], id="trois-valeurs"),
        pytest.param([], id="liste-vide"),
        pytest.param("600x200", id="chaine"),
        pytest.param({"width": 600, "height": 200}, id="objet"),
        pytest.param([True, 200], id="booleen"),
        pytest.param(["600", 200], id="nombre-en-texte"),
        pytest.param([10**400, 200], id="entier-geant"),
        pytest.param([float("nan"), 200], id="nan"),
        pytest.param([float("inf"), 200], id="infini"),
        pytest.param(None, id="null"),
    ],
)
def test_taille_refusee(tmp_path: Path, size: object) -> None:
    assert rejected_field(texture(size=size), tmp_path) == "texture.size"


@requires_symlinks
def test_lien_symbolique_vers_l_exterieur_refuse(tmp_path: Path) -> None:
    library = tmp_path / "bibliotheque"
    outside = tmp_path / "ailleurs"
    library.mkdir()
    outside.mkdir()
    (library / "textures").symlink_to(outside)
    assert rejected_field(texture(), library) == "texture.image"


@requires_symlinks
def test_image_lien_vers_l_exterieur_refusee(tmp_path: Path) -> None:
    library = tmp_path / "bibliotheque"
    (library / "textures").mkdir(parents=True)
    (library / "textures" / "erable.jpg").symlink_to(tmp_path / "secret.jpg")
    assert rejected_field(texture(), library) == "texture.image"


@requires_symlinks
def test_image_lien_vers_le_dossier_lui_meme_refusee(tmp_path: Path) -> None:
    (tmp_path / "erable.png").symlink_to(tmp_path)
    assert rejected_field(texture(image="erable.png"), tmp_path) == "texture.image"


def test_resolution_impossible_refusee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_resolve(self: Path, strict: bool = False) -> Path:
        raise OSError(40, "Trop de niveaux de liens symboliques")

    monkeypatch.setattr(Path, "resolve", failing_resolve)
    assert rejected_field(texture(), tmp_path) == "texture.image"


def test_texture_sans_dossier_de_reference_refusee() -> None:
    materials, [issue] = parse(texture(), None)
    assert materials == []
    assert issue.params["field"] == "texture.image"
    assert "dossier du fichier de bibliothèque inconnu" in issue.format()


# --- Lecture depuis un fichier et bibliothèque intégrée ---------------------------------------


def test_texture_relative_au_fichier_utilisateur(tmp_path: Path) -> None:
    folder = tmp_path / "Menuiserie"
    folder.mkdir()
    path = folder / "materiaux.json"
    replacement = {**OAK, "name": "Chêne texturé", "texture": texture("textures/chene.jpg")}
    path.write_text(json.dumps({"format": 1, "materials": [replacement]}), encoding="utf-8")
    library, issues = load_library(DATA_DIR / "materiaux.json", path)
    assert [i.severity for i in issues] == [Severity.INFO]
    oak_texture = library.get("chene").texture
    assert oak_texture is not None
    assert oak_texture.image == (folder / "textures" / "chene.jpg").resolve()


def test_bibliotheque_integree_sans_texture_pour_l_instant() -> None:
    materials, issues = read_materials_file(DATA_DIR / "materiaux.json")
    assert issues == []
    assert all(material.texture is None for material in materials)


def test_message_de_chemin_refuse_explicite(tmp_path: Path) -> None:
    _, [issue] = parse(texture(image="../erable.png"), tmp_path)
    message = issue.format()
    assert f"1 à {MAX_TEXTURE_PATH_LENGTH} caractères" in message
    assert ".png, .jpg, .jpeg" in message
