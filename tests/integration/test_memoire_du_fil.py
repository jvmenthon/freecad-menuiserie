# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mémoire et visibilité du sens du fil dans un vrai document (critères C10 et C11, I).

La pièce mémorise son dernier sens du fil (``PreferredGrainDirection``, ADR 0005) et le
retrouve en revenant à un matériau avec fil ; ``GrainDirection`` est masquée dans l'éditeur de
propriétés tant que le matériau n'a pas de fil.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.aides import Board

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

Reopen = Callable[[Any], Any]
HIDDEN = ["Hidden"]
EDITABLE: list[str] = []
GREY_MDF = {
    "id": "mdf-gris",
    "kind": "mdf",
    "name": {"fr": "MDF gris", "en": "Grey MDF"},
    "density": 760,
    "thicknesses": [19],
    "color": "#8A8A8A",
}


def grain(obj: Any) -> tuple[str, str]:
    """Fil de la pièce et sens mémorisé."""
    return obj.GrainDirection, obj.PreferredGrainDirection


def grain_mode(obj: Any) -> list[str]:
    mode: list[str] = obj.getEditorMode("GrainDirection")
    return mode


def in_transaction(doc: Any, change: Callable[[], None]) -> None:
    doc.openTransaction("Étape")
    change()
    doc.commitTransaction()


# --- C10 (1) : tous les chemins ------------------------------------------------------------


def test_set_material_retrouve_le_sens_memorise(document: Any, board: Board) -> None:
    obj = board(document, grain="Width")
    assert obj.PreferredGrainDirection == "Width"
    wood_part.set_material(obj, "mdf")
    assert grain(obj) == ("None", "Width")
    wood_part.set_material(obj, "chene")
    assert grain(obj) == ("Width", "Width")


def test_editeur_de_proprietes_retrouve_le_sens_memorise(document: Any, board: Board) -> None:
    obj = board(document, grain="Width")
    obj.Material = "MDF"
    assert grain(obj) == ("None", "Width")
    obj.Material = "Chêne"
    assert grain(obj) == ("Width", "Width")


def test_passage_par_un_autre_materiau_avec_fil(document: Any, board: Board) -> None:
    obj = board(document, grain="Width")
    wood_part.set_material(obj, "mdf")
    wood_part.set_material(obj, "cp-bouleau")
    assert grain(obj) == ("Width", "Width")


def test_sans_fil_n_efface_pas_la_memoire(document: Any, board: Board) -> None:
    obj = board(document, grain="Width")
    obj.GrainDirection = "None"
    assert grain(obj) == ("None", "Width")
    obj.GrainDirection = "Length"
    assert obj.PreferredGrainDirection == "Length"


def test_piece_creee_en_mdf(document: Any, board: Board) -> None:
    obj = board(document, "mdf", grain="None")
    assert grain(obj) == ("None", "Length")
    wood_part.set_material(obj, "chene")
    assert grain(obj) == ("Length", "Length")


# --- C10 (2) et (3) : réouverture, annulation ----------------------------------------------


def test_memoire_enregistree(document: Any, rouvrir: Reopen, board: Board) -> None:
    obj = board(document, grain="Width")
    wood_part.set_material(obj, "mdf")
    document.recompute()
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert restored.PreferredGrainDirection == "Width"
    assert [o.Name for o in restored.Document.Objects if "Touched" in o.State] == []
    wood_part.set_material(restored, "chene")
    assert restored.GrainDirection == "Width"


def test_la_memoire_suit_l_annulation(document: Any, board: Board) -> None:
    document.UndoMode = 1
    obj = board(document)
    steps = (
        lambda: setattr(obj, "GrainDirection", "Width"),
        lambda: wood_part.set_material(obj, "mdf"),
        lambda: wood_part.set_material(obj, "chene"),
    )
    for step in steps:
        in_transaction(document, step)
    assert grain(obj) == ("Width", "Width")
    expected_after_undo = [("None", "Width"), ("Width", "Width"), ("Length", "Length")]
    for expected in expected_after_undo:
        document.undo()
        assert grain(obj) == expected
    for _step in steps:
        document.redo()
    assert grain(obj) == ("Width", "Width")


# --- C10 (4) : migration 1 → 2 -------------------------------------------------------------


def as_version_1(obj: Any) -> None:
    obj.removeProperty("PreferredGrainDirection")
    obj.Version = 1


def test_migration_1_vers_2_d_une_piece_en_largeur(
    document: Any, rouvrir: Reopen, board: Board
) -> None:
    obj = board(document, grain="Width")
    as_version_1(obj)
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert (restored.Version, restored.PreferredGrainDirection) == (2, "Width")
    assert restored.getEditorMode("PreferredGrainDirection") == HIDDEN
    wood_part.set_material(restored, "mdf")
    wood_part.set_material(restored, "chene")
    assert restored.GrainDirection == "Width"


@pytest.mark.parametrize("version", [0, 1])
def test_migration_d_une_piece_en_mdf(
    document: Any, rouvrir: Reopen, version: int, board: Board
) -> None:
    obj = board(document, "mdf", grain="None")
    as_version_1(obj)
    if version == 0:
        obj.removeProperty("Version")
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert (restored.Version, grain(restored)) == (2, ("None", "Length"))


# --- C10 (5) : contrôles de la réouverture -------------------------------------------------


def with_unknown_preference(obj: Any) -> None:
    obj.PreferredGrainDirection = ["Length", "Width", "Diagonal"]
    obj.PreferredGrainDirection = "Diagonal"


def preference_warnings(vue_rapport: Any) -> list[str]:
    warnings: list[str] = vue_rapport.de_niveau("Warning")
    return [w for w in warnings if "PreferredGrainDirection" in w]


@pytest.mark.parametrize(("grain_value", "expected"), [("Width", "Width"), ("None", "Length")])
def test_valeur_inconnue_remplacee(
    document: Any, rouvrir: Reopen, vue_rapport: Any, grain_value: str, expected: str, board: Board
) -> None:
    obj = board(document, "mdf" if grain_value == "None" else "chene", grain=grain_value)
    with_unknown_preference(obj)
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.PreferredGrainDirection == expected
    assert restored.getEnumerationsOfProperty("PreferredGrainDirection") == ["Length", "Width"]
    assert len(preference_warnings(vue_rapport)) == 1


def test_valeur_inconnue_gardee_dans_un_document_plus_recent(
    document: Any, rouvrir: Reopen, vue_rapport: Any, board: Board
) -> None:
    obj = board(document, grain="Width")
    obj.Version = wood_part.WoodPart.VERSION + 1
    with_unknown_preference(obj)
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.PreferredGrainDirection == "Diagonal"
    assert len(preference_warnings(vue_rapport)) == 1
    restored.GrainDirection = "None"
    wood_part.set_material(restored, "mdf")
    wood_part.set_material(restored, "chene")
    assert restored.GrainDirection == "Length"  # sens mémorisé illisible : Length
    assert restored.PreferredGrainDirection == "Diagonal"  # « Sans fil » ne l'efface pas


def test_type_inattendu_recree(
    document: Any, rouvrir: Reopen, vue_rapport: Any, board: Board
) -> None:
    obj = board(document, grain="Width")
    obj.removeProperty("PreferredGrainDirection")
    obj.addProperty("App::PropertyString", "PreferredGrainDirection")
    obj.PreferredGrainDirection = "Largeur"
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.getTypeIdOfProperty("PreferredGrainDirection") == "App::PropertyEnumeration"
    assert restored.PreferredGrainDirection == "Width"
    assert len(preference_warnings(vue_rapport)) == 1


# --- C11 : fil masqué pour un matériau sans fil --------------------------------------------


def test_fil_masque_a_la_creation(document: Any, board: Board) -> None:
    oak = board(document)
    mdf = board(document, "mdf", grain="None")
    assert grain_mode(oak) == EDITABLE
    assert grain_mode(mdf) == HIDDEN
    assert oak.getEditorMode("PreferredGrainDirection") == HIDDEN
    assert wood_part.shows_grain(oak)
    assert not wood_part.shows_grain(mdf)


def test_fil_masque_puis_affiche(document: Any, board: Board) -> None:
    obj = board(document)
    wood_part.set_material(obj, "mdf")
    assert grain_mode(obj) == HIDDEN
    obj.Material = "Chêne"
    assert grain_mode(obj) == EDITABLE


def test_le_masquage_suit_l_annulation(document: Any, board: Board) -> None:
    document.UndoMode = 1
    obj = board(document)
    in_transaction(document, lambda: wood_part.set_material(obj, "mdf"))
    document.undo()
    assert (obj.MaterialId, grain_mode(obj)) == ("chene", EDITABLE)
    document.redo()
    assert (obj.MaterialId, grain_mode(obj)) == ("mdf", HIDDEN)


def test_masquage_apres_reouverture(document: Any, rouvrir: Reopen, board: Board) -> None:
    names = (board(document, "mdf", grain="None").Name, board(document).Name)
    restored = rouvrir(document)
    modes = [grain_mode(restored.getObject(name)) for name in names]
    assert modes == [HIDDEN, EDITABLE]


def test_materiau_inconnu_localement_de_categorie_mdf(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any, board: Board
) -> None:
    bibliotheque_temporaire.installer(GREY_MDF)
    name = board(document, "mdf-gris", grain="None").Name
    bibliotheque_temporaire.retirer()
    restored = rouvrir(document).getObject(name)
    assert restored.MaterialId == "mdf-gris"
    assert not wood_part.shows_grain(restored)
    assert grain_mode(restored) == HIDDEN
