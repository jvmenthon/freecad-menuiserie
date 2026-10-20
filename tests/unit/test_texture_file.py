# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ouverture unique et confinée du fichier image d'une texture (audit de sécurité J1d, point 2).

Le fichier est ouvert une fois (liens résolus, confinement au dossier de la bibliothèque,
``O_NOFOLLOW`` sur la cible), contrôlé sur son descripteur et lu au plus une fois.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from freecad.menuiserie.core.appearance import MAX_TEXTURE_FILE_BYTES
from freecad.menuiserie.core.materials import Texture, parse_materials
from freecad.menuiserie.core.texture_file import (
    OUTSIDE_LIBRARY,
    UNUSABLE_FILE,
    TextureFile,
    TextureRefusedError,
    confined_image,
)
from tests.unit.aides import OAK, SOURCE, document, requires_symlinks

CONTENT = b"\x89PNG\r\n\x1a\n" + bytes(56)
SIZE = (600.0, 200.0)
OPEN_FILES = Path("/proc/self/fd")


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """Dossier résolu de la bibliothèque, avec un sous-dossier ``textures``."""
    folder = (tmp_path / "bibliotheque").resolve()
    (folder / "textures").mkdir(parents=True)
    return folder


def image_file(path: Path, content: bytes = CONTENT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def sparse_file(path: Path, size: int) -> Path:
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


def texture_in(library: Path, relative: str = "textures/erable.png") -> Texture:
    return Texture(library / relative, SIZE, library)


def refusal(texture: Texture) -> str:
    """Raison du refus de ``texture`` (l'ouverture doit échouer)."""
    with pytest.raises(TextureRefusedError) as raised:
        TextureFile(texture).close()
    return raised.value.reason


def read_all(texture: Texture) -> bytes:
    with TextureFile(texture) as opened:
        return opened.read()


@pytest.fixture
def no_descriptor_leak() -> Iterator[None]:
    """Vérifie, sous Linux, qu'aucun descripteur ne reste ouvert après le test."""
    if not OPEN_FILES.is_dir():
        yield
        return
    before = len(list(OPEN_FILES.iterdir()))
    yield
    assert len(list(OPEN_FILES.iterdir())) == before


# --- Fichiers acceptés ---------------------------------------------------------------------


def test_fichier_ordinaire_lu_une_fois(library: Path, no_descriptor_leak: None) -> None:
    image_file(library / "textures" / "erable.png")
    assert read_all(texture_in(library)) == CONTENT


def test_fichier_de_16_mio_accepte(library: Path) -> None:
    sparse_file(library / "textures" / "erable.png", MAX_TEXTURE_FILE_BYTES)
    assert len(read_all(texture_in(library))) == MAX_TEXTURE_FILE_BYTES


def test_cle_identifie_le_contenu(library: Path) -> None:
    image = image_file(library / "textures" / "erable.png")
    with TextureFile(texture_in(library)) as opened:
        status = image.stat()
        assert opened.key == (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns)


def test_liens_physiques_meme_cle(library: Path) -> None:
    image = image_file(library / "textures" / "erable.png")
    os.link(image, library / "textures" / "copie.png")
    copy = texture_in(library, "textures/copie.png")
    with TextureFile(texture_in(library)) as first, TextureFile(copy) as second:
        assert first.key == second.key


def test_fichier_reecrit_change_de_cle(library: Path) -> None:
    image = image_file(library / "textures" / "erable.png")
    with TextureFile(texture_in(library)) as opened:
        before = opened.key
    image.write_bytes(CONTENT * 2)
    with TextureFile(texture_in(library)) as opened:
        assert opened.key != before


@requires_symlinks
def test_lien_interne_au_dossier_accepte(library: Path) -> None:
    target = image_file(library / "images" / "vraie.png")
    (library / "textures" / "erable.png").symlink_to(target)
    texture = texture_in(library)
    assert confined_image(texture) == target
    assert read_all(texture) == CONTENT


@requires_symlinks
def test_dossier_de_bibliotheque_lien_vers_sa_cible(tmp_path: Path, library: Path) -> None:
    """Bibliothèque lue par un lien vers son dossier : la texture garde la cible résolue, où
    l'image est ouverte."""
    (tmp_path / "lien").symlink_to(library)
    image_file(library / "textures" / "erable.png")
    entry = {**OAK, "texture": {"image": "textures/erable.png", "size": list(SIZE)}}
    [material], issues = parse_materials(document(entry), SOURCE, tmp_path / "lien")
    assert issues == []
    assert material.texture is not None
    assert material.texture.library_folder == library
    assert read_all(material.texture) == CONTENT


# --- Fichiers refusés ----------------------------------------------------------------------


def test_fichier_absent(library: Path, no_descriptor_leak: None) -> None:
    assert refusal(texture_in(library)) == UNUSABLE_FILE


@pytest.mark.parametrize("size", [0, MAX_TEXTURE_FILE_BYTES + 1])
def test_fichier_vide_ou_trop_gros(library: Path, size: int, no_descriptor_leak: None) -> None:
    sparse_file(library / "textures" / "erable.png", size)
    assert refusal(texture_in(library)) == UNUSABLE_FILE


def test_dossier(library: Path, no_descriptor_leak: None) -> None:
    (library / "textures" / "erable.png").mkdir()
    assert refusal(texture_in(library)) == UNUSABLE_FILE


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="tubes nommés indisponibles")
def test_tube_nomme_refuse_sans_blocage(library: Path, no_descriptor_leak: None) -> None:
    os.mkfifo(library / "textures" / "erable.png")
    assert refusal(texture_in(library)) == UNUSABLE_FILE


def test_fichier_sans_droit_de_lecture(library: Path) -> None:
    image = image_file(library / "textures" / "erable.png")
    os.chmod(image, 0)
    try:
        if os.access(image, os.R_OK):  # administrateur : la lecture reste permise
            assert read_all(texture_in(library)) == CONTENT
        else:
            assert refusal(texture_in(library)) == UNUSABLE_FILE
    finally:
        os.chmod(image, 0o600)


@requires_symlinks
def test_lien_vers_l_exterieur_cree_apres_le_chargement(tmp_path: Path, library: Path) -> None:
    secret = image_file(tmp_path / "secret.png")
    (library / "textures" / "erable.png").symlink_to(secret)
    assert refusal(texture_in(library)) == OUTSIDE_LIBRARY


@requires_symlinks
def test_lien_vers_un_peripherique(library: Path) -> None:
    (library / "textures" / "erable.png").symlink_to(os.devnull)
    assert refusal(texture_in(library)) == OUTSIDE_LIBRARY


@requires_symlinks
def test_dossier_intermediaire_remplace_par_un_lien(tmp_path: Path, library: Path) -> None:
    image_file(tmp_path / "ailleurs" / "erable.png")
    (library / "textures").rmdir()
    (library / "textures").symlink_to(tmp_path / "ailleurs")
    assert refusal(texture_in(library)) == OUTSIDE_LIBRARY


@requires_symlinks
def test_lien_vers_le_dossier_lui_meme(library: Path) -> None:
    (library / "textures" / "erable.png").symlink_to(library)
    assert refusal(texture_in(library)) == OUTSIDE_LIBRARY


@requires_symlinks
def test_boucle_de_liens(library: Path) -> None:
    loop = library / "textures" / "erable.png"
    loop.symlink_to(loop)
    assert refusal(texture_in(library)) == UNUSABLE_FILE


def test_octet_nul_dans_le_chemin(library: Path) -> None:
    assert refusal(texture_in(library, "textures/era\0ble.png")) == UNUSABLE_FILE


@requires_symlinks
@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW indisponible")
def test_lien_substitue_entre_resolution_et_ouverture(
    tmp_path: Path, library: Path, monkeypatch: pytest.MonkeyPatch, no_descriptor_leak: None
) -> None:
    """Course simulée : la résolution rend un chemin dont le dernier composant est devenu un
    lien vers l'extérieur ; ``O_NOFOLLOW`` fait échouer l'ouverture."""
    link = library / "textures" / "erable.png"
    link.symlink_to(image_file(tmp_path / "secret.png"))
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: self)
    assert refusal(texture_in(library)) == UNUSABLE_FILE


# --- Lecture bornée ------------------------------------------------------------------------


def test_fichier_agrandi_apres_l_ouverture(library: Path, no_descriptor_leak: None) -> None:
    image = image_file(library / "textures" / "erable.png")
    with TextureFile(texture_in(library)) as opened:
        with image.open("r+b") as handle:
            handle.truncate(MAX_TEXTURE_FILE_BYTES + 1)
        with pytest.raises(TextureRefusedError) as raised:
            opened.read()
    assert raised.value.reason == UNUSABLE_FILE


def test_fichier_vide_apres_l_ouverture(library: Path) -> None:
    image = image_file(library / "textures" / "erable.png")
    with TextureFile(texture_in(library)) as opened:
        image.write_bytes(b"")
        with pytest.raises(TextureRefusedError):
            opened.read()


def test_fermeture_idempotente(library: Path, no_descriptor_leak: None) -> None:
    image_file(library / "textures" / "erable.png")
    opened = TextureFile(texture_in(library))
    opened.close()
    opened.close()


def test_raison_et_parametres() -> None:
    error = TextureRefusedError("{n} balayages", {"n": "3"})
    assert (error.reason, error.params) == ("{n} balayages", {"n": "3"})
    assert TextureRefusedError(UNUSABLE_FILE).params == {}
