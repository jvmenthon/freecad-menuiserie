# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de l'apparence d'une pièce dans un vrai document FreeCAD (lot J1d, D3).

Fichiers piégés, bibliothèque modifiée entre deux sessions, recalcul après chaque propriété,
annuler / rétablir, réouverture et documents multiples, sans interface. Un défaut constaté
serait marqué ``xfail(strict=True)`` et numéroté (D1, D2…) ; aucun à ce jour.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core import appearance as core_appearance
from freecad.menuiserie.core import materials, part_model
from tests.integration.test_apparence import (
    IMAGE,
    MAPLE_RGB,
    TEXTURED_MAPLE,
    install_textured_maple,
    sized_file,
    texture_at,
)

pytestmark = pytest.mark.integration

Library = Any  # fixture bibliotheque_temporaire (conftest.BibliothequeTemporaire)
Reopen = Callable[[Any], Any]

App = pytest.importorskip("FreeCAD")
appearance = pytest.importorskip("freecad.menuiserie.features.appearance")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

OAK_RGB = (184, 135, 90)


def mapping(size: tuple[float, float], grain: str) -> Any:
    return core_appearance.texture_mapping(size, part_model.GrainDirection(grain))


def textured(image: Path, size: tuple[float, float] = (600.0, 200.0)) -> Any:
    """Apparence texturée de l'érable (image sous ``textures/`` de la bibliothèque)."""
    texture = materials.Texture(image, size, image.parents[1])
    return core_appearance.Appearance(MAPLE_RGB, texture, mapping(size, "Length"))


def maple(**texture: object) -> dict[str, object]:
    """Érable de la bibliothèque, texture remplacée par ``texture`` (supprimée si vide)."""
    entry = {key: value for key, value in TEXTURED_MAPLE.items() if key != "texture"}
    if texture:
        entry["texture"] = texture
    return entry


def board(doc: Any, material_id: str = "erable") -> Any:
    obj = wood_part.create_wood_part(doc, material_id=material_id)
    doc.recompute()
    return obj


def touched(doc: Any) -> list[str]:
    return [o.Name for o in doc.Objects if "Touched" in o.State]


# --- usable_texture_file : fichiers piégés -----------------------------------------------


def test_tube_nomme_png_refuse_sans_blocage(tmp_path: Path) -> None:
    """Un tube nommé est ouvert sans blocage (``O_NONBLOCK``) puis refusé par ``fstat``."""
    fifo = tmp_path / "tube.png"
    os.mkfifo(fifo)
    assert not appearance.usable_texture_file(texture_at(fifo))


def test_lien_vers_un_peripherique_refuse(tmp_path: Path) -> None:
    link = tmp_path / "zero.png"
    link.symlink_to("/dev/zero")
    assert not appearance.usable_texture_file(texture_at(link))
    assert not appearance.usable_texture_file(texture_at(Path("/dev/null")))


def test_lien_vers_un_fichier_ordinaire_suivi(tmp_path: Path) -> None:
    target = sized_file(tmp_path / "vraie.png", 10)
    link = tmp_path / "lien.png"
    link.symlink_to(target)
    assert appearance.usable_texture_file(texture_at(link))


def test_lien_vers_un_fichier_trop_gros_refuse(tmp_path: Path) -> None:
    """La taille contrôlée est celle de la cible, pas celle du lien."""
    link = tmp_path / "lien.png"
    link.symlink_to(sized_file(tmp_path / "enorme.png", core_appearance.MAX_TEXTURE_FILE_BYTES + 1))
    assert not appearance.usable_texture_file(texture_at(link))


def test_chemins_impossibles_refuses_sans_exception(tmp_path: Path) -> None:
    loop = tmp_path / "boucle.png"
    loop.symlink_to(loop)
    to_folder = tmp_path / "dossier.png"
    to_folder.symlink_to(tmp_path)
    regular = sized_file(tmp_path / "fichier.png", 10)
    refused = [
        loop,
        to_folder,
        regular / "sous.png",  # un composant du chemin est un fichier (ENOTDIR)
        tmp_path / ("x" * 300 + ".png"),  # nom trop long (ENAMETOOLONG)
    ]
    assert [path for path in refused if appearance.usable_texture_file(texture_at(path))] == []
    with pytest.raises(ValueError, match="image"):
        texture_at(Path("relative/absente.png"))


# --- appearance_of : recalcul, annuler / rétablir ----------------------------------------


@pytest.mark.parametrize(
    ("prop", "value"),
    [
        ("Length", 10_000.0),
        ("Width", 1.0),
        ("Thickness", 300.0),
        ("LengthAllowance", 5.0),
        ("WidthAllowance", 3.0),
        ("ThicknessAllowance", 2.0),
        ("Mark", "A1"),
        ("Placement", None),
    ],
)
def test_apparence_independante_des_cotes(
    document: Any, bibliotheque_temporaire: Library, prop: str, value: object
) -> None:
    image = install_textured_maple(bibliotheque_temporaire)
    obj = board(document)
    if value is None:
        value = App.Placement(App.Vector(1e6, -2e5, 30), App.Rotation(30, 45, 60))
    setattr(obj, prop, value)
    document.recompute()
    assert appearance.appearance_of(obj) == textured(image)
    assert touched(document) == []


def test_annuler_retablir_fil_et_materiau(document: Any, bibliotheque_temporaire: Library) -> None:
    image = install_textured_maple(bibliotheque_temporaire)
    document.UndoMode = 1
    obj = board(document)
    document.openTransaction("Fil")
    obj.GrainDirection = "Width"
    document.commitTransaction()
    document.openTransaction("Matériau")
    wood_part.set_material(obj, "chene")
    document.commitTransaction()
    document.recompute()
    assert appearance.appearance_of(obj) == core_appearance.Appearance(OAK_RGB)
    document.undo()
    expected = core_appearance.Appearance(
        MAPLE_RGB, textured(image).texture, mapping((600.0, 200.0), "Width")
    )
    assert appearance.appearance_of(obj) == expected
    document.undo()
    assert appearance.appearance_of(obj) == textured(image)
    document.redo()
    document.redo()
    assert appearance.appearance_of(obj) == core_appearance.Appearance(OAK_RGB)


def test_texture_vers_sans_texture_et_inverse(
    document: Any, bibliotheque_temporaire: Library
) -> None:
    image = install_textured_maple(bibliotheque_temporaire)
    obj = board(document, "chene")
    for material_id, expected in [
        ("erable", textured(image)),
        ("mdf", core_appearance.Appearance((169, 139, 109))),
        ("erable", textured(image)),
    ]:
        wood_part.set_material(obj, material_id)
        document.recompute()
        assert appearance.appearance_of(obj).image == expected.image
        assert appearance.appearance_of(obj).color == expected.color


# --- bibliothèque modifiée, image remplacée, réouverture ---------------------------------


@pytest.mark.parametrize("size", [(10.0, 10.0), (10_000.0, 10_000.0), (10.0, 10_000.0)])
def test_tailles_extremes_de_la_bibliotheque(
    document: Any, bibliotheque_temporaire: Library, size: tuple[float, float]
) -> None:
    install_textured_maple(bibliotheque_temporaire)
    bibliotheque_temporaire.installer(maple(image=IMAGE, size=list(size)))
    obj = board(document)
    obj.GrainDirection = "Width"
    assert appearance.appearance_of(obj).mapping == mapping(size, "Width")


def test_bibliotheque_modifiee_entre_deux_sessions(
    document: Any, bibliotheque_temporaire: Library, rouvrir: Reopen
) -> None:
    """Rien de la texture n'est enregistré : la réouverture suit la bibliothèque du moment."""
    image = install_textured_maple(bibliotheque_temporaire)
    name = board(document).Name
    bibliotheque_temporaire.installer(maple(image=IMAGE, size=[300, 100]))
    doc = rouvrir(document)
    assert appearance.appearance_of(doc.getObject(name)) == textured(image, (300.0, 100.0))
    bibliotheque_temporaire.installer(maple())
    doc = rouvrir(doc)
    assert appearance.appearance_of(doc.getObject(name)) == core_appearance.Appearance(MAPLE_RGB)
    install_textured_maple(bibliotheque_temporaire)
    doc = rouvrir(doc)
    obj = doc.getObject(name)
    assert appearance.appearance_of(obj) == textured(image)
    assert obj.Version == 1
    assert touched(doc) == []


def test_image_remplacee_ou_supprimee_sur_le_disque(
    document: Any, bibliotheque_temporaire: Library
) -> None:
    image = install_textured_maple(bibliotheque_temporaire)
    obj = board(document)
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(4096))
    assert appearance.appearance_of(obj) == textured(image)
    image.unlink()
    assert appearance.appearance_of(obj) == core_appearance.Appearance(MAPLE_RGB)
    image.symlink_to(sized_file(image.with_name("autre.png"), 10))
    assert appearance.appearance_of(obj) == textured(image)  # lien interne au dossier
    image.unlink()
    image.symlink_to(sized_file(image.parents[2] / "dehors.png", 10))
    assert appearance.appearance_of(obj) == core_appearance.Appearance(MAPLE_RGB)


def test_lien_de_la_bibliotheque_resolu_vers_sa_cible(
    document: Any, bibliotheque_temporaire: Library
) -> None:
    """Un lien symbolique dans le dossier de la bibliothèque est résolu au chargement : la pièce
    pointe vers la cible, toujours dans le dossier."""
    folder = bibliotheque_temporaire.path.parent
    (folder / "textures").mkdir()
    target = sized_file(folder / "textures" / "vraie.png", 10)
    (folder / IMAGE).symlink_to(target)
    bibliotheque_temporaire.installer(TEXTURED_MAPLE)
    obj = board(document)
    assert appearance.appearance_of(obj) == textured(target.resolve())


def test_documents_multiples_independants(document: Any, bibliotheque_temporaire: Library) -> None:
    image = install_textured_maple(bibliotheque_temporaire)
    other = App.newDocument("TestPieceDeBoisAutre")
    other_name = other.Name
    try:
        first, second = board(document), board(other)
        second.GrainDirection = "Width"
        assert appearance.appearance_of(first) == textured(image)
        assert appearance.appearance_of(second).mapping == mapping((600.0, 200.0), "Width")
        App.closeDocument(other_name)
        assert appearance.appearance_of(first) == textured(image)
    finally:
        if other_name in App.listDocuments():
            App.closeDocument(other_name)
