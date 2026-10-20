# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de la pièce de bois dans un vrai document FreeCAD (lot J1b, critères B1 à B14).

Les défauts constatés sont marqués ``xfail(strict=True)`` et numérotés (D1, D2…) : le test
passera au vert, et devra alors perdre son marqueur, quand le code de production sera corrigé.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
library = pytest.importorskip("freecad.menuiserie.features.library")
part_model = pytest.importorskip("freecad.menuiserie.core.part_model")
api = pytest.importorskip("freecad.menuiserie.api")

Reopen = Callable[[Any], Any]
MAPLE = {
    "id": "erable",
    "kind": "solid",
    "name": {"fr": "Érable", "en": "Maple"},
    "density": 650,
    "thicknesses": [22],
    "color": "#E8D2A8",
}


def board(doc: Any, material_id: str = "chene") -> Any:
    """Pièce de 800 x 200 x 22 mm du matériau donné, recalculée."""
    obj = wood_part.create_wood_part(doc, material_id=material_id)
    doc.recompute()
    return obj


def material_state(obj: Any) -> tuple[object, ...]:
    """Matériau, catégorie, fil, surcotes et masse volumique (arrondie) de la pièce."""
    return (
        obj.Material,
        obj.MaterialId,
        obj.Category,
        obj.GrainDirection,
        obj.LengthAllowance.Value,
        obj.WidthAllowance.Value,
        obj.ThicknessAllowance.Value,
        round(float(obj.Density.getValueAs("kg/m^3")), 6),
    )


def touched(doc: Any) -> list[str]:
    return [o.Name for o in doc.Objects if "Touched" in o.State]


# --- B3, B6 : cotes extrêmes --------------------------------------------------------------


@pytest.mark.parametrize("name", ["Length", "Width", "Thickness"])
@pytest.mark.parametrize("value", [0.1, 20_000])
def test_cote_aux_bornes_acceptee(document: Any, name: str, value: float) -> None:
    obj = board(document)
    setattr(obj, name, value)
    document.recompute()
    assert obj.isValid()
    size = {"Length": 800.0, "Width": 200.0, "Thickness": 22.0, name: value}
    assert obj.Shape.Volume == pytest.approx(size["Length"] * size["Width"] * size["Thickness"])


@pytest.mark.parametrize("name", ["Length", "Width", "Thickness"])
@pytest.mark.parametrize("value", [0.09, 20_000.001, 1e9, float("inf")])
def test_cote_hors_bornes_en_erreur_puis_reparee(document: Any, name: str, value: float) -> None:
    obj = board(document)
    placement = App.Placement(App.Vector(5, -7, 9), App.Rotation(15, 30, 45))
    obj.Placement = placement
    document.recompute()
    setattr(obj, name, value)
    document.recompute()
    assert not obj.isValid()
    assert "cote invalide" in obj.getStatusString().lower()
    setattr(obj, name, 100)
    document.recompute()
    assert obj.isValid()
    assert obj.Placement.isSame(placement, 1e-9)


def test_cote_negative_par_expression_met_en_erreur(document: Any) -> None:
    obj = board(document)
    obj.setExpression("Length", "Width - 1000 mm")
    document.recompute()
    assert not obj.isValid()
    assert "cote invalide" in obj.getStatusString().lower()
    obj.setExpression("Length", None)
    obj.Length = 800
    document.recompute()
    assert obj.isValid()


@pytest.mark.xfail(
    strict=True,
    reason="D1 : une expression écrit une cote négative (-800 mm) dans la propriété ; "
    "B6 exige qu'une valeur négative ne soit jamais retenue",
)
def test_cote_negative_par_expression_jamais_retenue(document: Any) -> None:
    obj = board(document)
    obj.setExpression("Length", "Width - 1000 mm")
    document.recompute()
    assert obj.Length.Value >= 0


# --- B4, B7 : expressions -----------------------------------------------------------------


def test_expression_entre_deux_pieces(document: Any) -> None:
    source, target = board(document), board(document)
    target.setExpression("Length", f"{source.Name}.Width * 2")
    source.Width = 300
    document.recompute()
    assert target.Length.Value == pytest.approx(600)
    assert target.isValid()


def test_expression_conservee_a_la_reouverture(document: Any, rouvrir: Reopen) -> None:
    obj = board(document)
    obj.setExpression("Length", "Width * 4")
    obj.Placement = App.Placement(App.Vector(1, 2, 3), App.Rotation(10, 20, 30))
    document.recompute()
    placement, name = obj.Placement, obj.Name
    reopened = rouvrir(document)
    restored = reopened.getObject(name)
    assert restored.ExpressionEngine == [("Length", "Width * 4")]
    assert restored.Placement.isSame(placement, 1e-9)
    assert touched(reopened) == []
    restored.Width = 300
    reopened.recompute()
    assert restored.Length.Value == pytest.approx(1200)
    assert restored.Shape.Volume == pytest.approx(1200 * 300 * 22)


# --- Recalcul après chaque propriété ------------------------------------------------------

EDITS = [
    ("Mark", "M1 « é » " + "x" * 300),
    ("GrainDirection", "Width"),
    ("LengthAllowance", 35),
    ("WidthAllowance", 0),
    ("ThicknessAllowance", 2),
    ("Material", "Frêne"),
]


@pytest.mark.parametrize(("name", "value"), EDITS, ids=[name for name, _ in EDITS])
def test_recalcul_apres_modification(document: Any, name: str, value: object) -> None:
    obj = board(document)
    setattr(obj, name, value)
    document.recompute()
    assert obj.isValid()
    assert touched(document) == []
    assert obj.Shape.Volume == pytest.approx(3_520_000)
    assert getattr(obj, name) == value or getattr(obj, name).Value == value
    assert wood_part.record_of(obj).finished == part_model.Dimensions(800, 200, 22)


def test_surcote_negative_jamais_retenue(document: Any) -> None:
    obj = board(document)
    obj.LengthAllowance = -5
    assert obj.LengthAllowance.Value >= 0


# --- B5 : changements de matériau en chaîne -----------------------------------------------

CHAIN = [
    ("MDF", ("MDF", "mdf", "MDF", "None", 0.0, 0.0, 0.0, 750.0)),
    ("Chêne", ("Chêne", "chene", "Solid", "Length", 20.0, 5.0, 0.0, 710.0)),
    ("Contreplaqué bouleau", ("Contreplaqué bouleau", "cp-bouleau", "Plywood", "Length")),
    ("Mélaminé blanc", ("Mélaminé blanc", "melamine-blanc", "Melamine", "None", 0.0, 0.0)),
    ("Hêtre", ("Hêtre", "hetre", "Solid", "Length", 20.0, 5.0, 0.0, 720.0)),
]


def test_changements_de_materiau_en_chaine(document: Any) -> None:
    obj = board(document)
    for label, expected in CHAIN:
        obj.Material = label
        assert material_state(obj)[: len(expected)] == expected, label
        assert (obj.Length.Value, obj.Width.Value, obj.Thickness.Value) == (800, 200, 22)
    document.recompute()
    assert obj.isValid()


def test_materiau_choisi_par_son_rang(document: Any) -> None:
    obj = board(document)
    labels = obj.getEnumerationsOfProperty("Material")
    obj.Material = labels.index("Noyer")
    assert (obj.Material, obj.MaterialId) == ("Noyer", "noyer")


def test_surcotes_choisies_sur_panneau_conservees_en_revenant_au_massif(document: Any) -> None:
    obj = board(document, "mdf")
    obj.LengthAllowance = 3
    wood_part.set_material(obj, "chene")
    assert (obj.LengthAllowance.Value, obj.WidthAllowance.Value) == (3, 0)
    assert obj.GrainDirection == "Length"


def test_meme_materiau_reselectionne_sans_effet(document: Any) -> None:
    obj = board(document)
    obj.LengthAllowance = 30
    obj.GrainDirection = "Width"
    document.recompute()
    before = material_state(obj)
    wood_part.set_material(obj, "chene")
    assert material_state(obj) == before


# --- B10 : annuler / rétablir chaque modification -----------------------------------------

UNDOABLE = [
    ("Width", 250),
    ("Thickness", 27),
    ("Mark", "M7"),
    ("GrainDirection", "Width"),
    ("LengthAllowance", 40),
    ("WidthAllowance", 1),
    ("ThicknessAllowance", 2),
]


@pytest.mark.parametrize(("name", "value"), UNDOABLE, ids=[name for name, _ in UNDOABLE])
def test_annuler_retablir_chaque_propriete(document: Any, name: str, value: object) -> None:
    document.UndoMode = 1
    obj = board(document)
    before = str(getattr(obj, name))
    document.openTransaction("Modifier")
    setattr(obj, name, value)
    document.commitTransaction()
    after = str(getattr(obj, name))
    document.undo()
    assert str(getattr(obj, name)) == before
    document.redo()
    assert str(getattr(obj, name)) == after
    document.recompute()
    assert obj.isValid()


def test_annuler_retablir_set_material(document: Any) -> None:
    document.UndoMode = 1
    obj = board(document)
    before = material_state(obj)
    document.openTransaction("Matériau")
    wood_part.set_material(obj, "cp-bouleau")
    document.commitTransaction()
    after = material_state(obj)
    document.undo()
    assert material_state(obj) == before
    document.redo()
    assert material_state(obj) == after


def test_annuler_une_cote_invalide_rend_la_piece_valide(document: Any) -> None:
    document.UndoMode = 1
    obj = board(document)
    document.openTransaction("Cote nulle")
    obj.Length = 0
    document.commitTransaction()
    document.recompute()
    assert not obj.isValid()
    document.undo()
    document.recompute()
    assert obj.isValid()
    assert obj.Length.Value == 800


def test_annuler_retablir_la_suppression(document: Any) -> None:
    document.UndoMode = 1
    obj = board(document)
    obj.Material = "Noyer"
    document.recompute()
    name, before = obj.Name, material_state(obj)
    document.openTransaction("Supprimer")
    document.removeObject(name)
    document.commitTransaction()
    document.undo()
    restored = document.getObject(name)
    assert wood_part.is_wood_part(restored)
    assert material_state(restored) == before
    document.recompute()
    assert restored.isValid()
    document.redo()
    assert document.getObject(name) is None


# --- B7, B8 : réouverture et bibliothèque modifiée ----------------------------------------


def test_deux_reouvertures_successives_stables(document: Any, rouvrir: Reopen) -> None:
    obj = board(document, "cp-bouleau")
    obj.Mark = "P1"
    document.recompute()
    name, before = obj.Name, material_state(obj)
    once = rouvrir(document)
    twice = rouvrir(once)
    restored = twice.getObject(name)
    assert material_state(restored) == before
    assert restored.Mark == "P1"
    assert touched(twice) == []


def test_reouverture_avec_un_materiau_utilisateur_present(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    bibliotheque_temporaire.installer(MAPLE)
    obj = board(document, "erable")
    vue_rapport.messages.clear()
    name = obj.Name
    reopened = rouvrir(document)
    assert reopened.getObject(name).Material == "Érable"
    assert touched(reopened) == []
    assert vue_rapport.messages == []


def test_reouverture_sans_le_materiau_puis_autre_choix_et_annulation(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any
) -> None:
    bibliotheque_temporaire.installer(MAPLE)
    name = board(document, "erable").Name
    bibliotheque_temporaire.retirer()
    reopened = rouvrir(document)
    obj = reopened.getObject(name)
    before = material_state(obj)
    reopened.UndoMode = 1
    reopened.openTransaction("Matériau")
    obj.Material = "Hêtre"
    reopened.commitTransaction()
    assert obj.MaterialId == "hetre"
    assert "Érable" not in obj.getEnumerationsOfProperty("Material")
    reopened.undo()
    assert material_state(obj) == before
    assert "Érable" in obj.getEnumerationsOfProperty("Material")
    record = wood_part.record_of(obj)
    assert (record.material_id, record.material_name) == ("erable", "Érable")
    assert record.density == pytest.approx(650)


def test_reouverture_sans_le_materiau_un_avertissement_par_piece(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    bibliotheque_temporaire.installer(MAPLE)
    first, second = board(document, "erable"), board(document, "erable")
    labels = first.Label, second.Label
    bibliotheque_temporaire.retirer()
    vue_rapport.messages.clear()
    reopened = rouvrir(document)
    warnings = vue_rapport.de_niveau("Warning")
    assert len(warnings) == 2
    assert all(sum(f"« {label} »" in w for w in warnings) == 1 for label in labels)
    reopened.recompute()
    assert all(o.isValid() for o in reopened.Objects)


def test_reouverture_avec_bibliotheque_corrompue(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    bibliotheque_temporaire.installer(MAPLE)
    name = board(document, "erable").Name
    bibliotheque_temporaire.path.write_text("{corrompu", encoding="utf-8")
    vue_rapport.messages.clear()
    library.reload_library()
    restored = rouvrir(document).getObject(name)
    [error] = vue_rapport.de_niveau("Error")
    assert "JSON" in error
    [warning] = vue_rapport.de_niveau("Warning")
    assert "erable" in warning
    assert (restored.MaterialId, restored.Material) == ("erable", "Érable")
    assert float(restored.Density.getValueAs("kg/m^3")) == pytest.approx(650)


def test_reouverture_avec_un_materiau_renomme_garde_l_instantane(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    name = board(document).Name
    renamed = {**MAPLE, "id": "chene", "name": "Chêne massif", "density": 800}
    bibliotheque_temporaire.installer(renamed)
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert (restored.MaterialId, restored.Material) == ("chene", "Chêne massif")
    assert float(restored.Density.getValueAs("kg/m^3")) == pytest.approx(710)
    assert vue_rapport.de_niveau("Warning") == []


# --- B9 : migration -----------------------------------------------------------------------


def test_version_plus_recente_non_retrogradee(document: Any, rouvrir: Reopen) -> None:
    obj = board(document)
    obj.Version = 2
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert restored.Version == 2
    restored.Document.recompute()
    assert restored.isValid()


def test_migration_garde_les_proprietes_presentes(document: Any, rouvrir: Reopen) -> None:
    obj = board(document, "mdf")
    obj.ThicknessAllowance = 3
    obj.LengthAllowance = 7
    obj.removeProperty("Version")
    obj.removeProperty("WidthAllowance")
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert restored.Version == 1
    assert (restored.ThicknessAllowance.Value, restored.LengthAllowance.Value) == (3, 7)
    assert restored.WidthAllowance.Value == 0  # panneau : surcote par défaut nulle
    assert (restored.MaterialId, restored.Material) == ("mdf", "MDF")


@pytest.mark.xfail(
    strict=True,
    reason="D2 : la migration recrée Category et GrainDirection d'après le matériau par "
    "défaut de la bibliothèque (chêne) et non d'après MaterialId",
)
def test_migration_deduit_categorie_et_fil_du_materiau(document: Any, rouvrir: Reopen) -> None:
    obj = board(document, "mdf")
    for prop in ("Version", "Category", "GrainDirection"):
        obj.removeProperty(prop)
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert (restored.MaterialId, restored.Category, restored.GrainDirection) == (
        "mdf",
        "MDF",
        "None",
    )
    assert wood_part.record_of(restored).kind.value == "mdf"


@pytest.mark.xfail(
    strict=True,
    reason="D3 : bibliothèque vide (intégrée absente) : la migration lève "
    "UnknownMaterialError, avalée par FreeCAD ; Version et propriétés manquantes non recréées",
)
def test_migration_avec_bibliotheque_vide(
    document: Any, rouvrir: Reopen, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obj = board(document)
    obj.removeProperty("Version")
    obj.removeProperty("ThicknessAllowance")
    name = obj.Name
    monkeypatch.setattr(library, "builtin_library_path", lambda: tmp_path / "absente.json")
    assert len(library.reload_library()) == 0
    restored = rouvrir(document).getObject(name)
    assert restored.Version == 1
    assert restored.ThicknessAllowance.Value == 0
    assert wood_part.record_of(restored).material_id == "chene"


def test_reouverture_avec_bibliotheque_vide_garde_la_piece(
    document: Any, rouvrir: Reopen, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = board(document, "noyer").Name
    monkeypatch.setattr(library, "builtin_library_path", lambda: tmp_path / "absente.json")
    library.reload_library()
    with pytest.raises(KeyError):
        wood_part.create_wood_part(document)
    restored = rouvrir(document).getObject(name)
    assert (restored.MaterialId, restored.Material) == ("noyer", "Noyer")
    restored.Document.recompute()
    assert restored.isValid()


# --- B11, B12 : contrat et reconnaissance -------------------------------------------------


def test_copie_d_une_piece(document: Any) -> None:
    obj = board(document, "noyer")
    copy = document.copyObject(obj)
    document.recompute()
    assert wood_part.is_wood_part(copy)
    assert copy.Proxy is not obj.Proxy
    assert material_state(copy) == material_state(obj)
    assert copy.isValid()
    copy.Material = "Hêtre"
    assert (copy.MaterialId, obj.MaterialId) == ("hetre", "noyer")


def test_loads_accepte_l_etat_vide(document: Any) -> None:
    proxy = board(document).Proxy
    assert proxy.loads(None) is None


def test_feature_python_etrangere_n_est_pas_une_piece(document: Any) -> None:
    other = document.addObject("Part::FeaturePython", "Autre")
    assert not wood_part.is_wood_part(other)
    assert not wood_part.is_wood_part("WoodPart")
    with pytest.raises(TypeError):
        wood_part.set_material(other, "chene")


def test_is_wood_part_sur_un_objet_supprime(document: Any) -> None:
    obj = board(document)
    document.removeObject(obj.Name)
    assert not wood_part.is_wood_part(obj)


def test_record_of_d_une_piece_invalide_leve(document: Any) -> None:
    obj = board(document)
    obj.Thickness = 0
    with pytest.raises(part_model.InvalidDimensionsError):
        wood_part.record_of(obj)


def test_record_of_suit_le_materiau(document: Any) -> None:
    obj = board(document)
    obj.Material = "Contreplaqué bouleau"
    record = wood_part.record_of(obj)
    assert (record.material_id, record.kind.value, record.density) == ("cp-bouleau", "plywood", 680)
    assert record.allowances == part_model.Allowances(0, 0, 0)


# --- Documents multiples ------------------------------------------------------------------


def test_pieces_dans_deux_documents_independantes(document: Any, rouvrir: Reopen) -> None:
    other = App.newDocument("TestPieceDeBoisAutre")
    try:
        first, second = board(document), board(other)
        assert first.Name == second.Name
        wood_part.set_material(first, "mdf")
        second.Length = 1000
        document.recompute()
        other.recompute()
        assert (first.MaterialId, first.Length.Value) == ("mdf", 800)
        assert (second.MaterialId, second.Length.Value) == ("chene", 1000)
        name = first.Name
        reopened = rouvrir(document)
        assert reopened.getObject(name).MaterialId == "mdf"
        assert second.MaterialId == "chene"
        assert touched(other) == []
    finally:
        App.closeDocument(other.Name)


# --- B13 : façade api ---------------------------------------------------------------------


def test_make_wood_part_materiau_inconnu_sans_objet(document: Any) -> None:
    with pytest.raises(KeyError):
        api.make_wood_part(material_id="inconnu", doc=document)
    with pytest.raises(part_model.InvalidDimensionsError):
        api.make_wood_part(-1, doc=document)
    assert document.Objects == []


def test_make_wood_part_annulable_par_l_appelant(document: Any) -> None:
    document.UndoMode = 1
    document.openTransaction("Créer")
    obj = api.make_wood_part(doc=document)
    document.commitTransaction()
    name = obj.Name
    document.undo()
    assert document.getObject(name) is None
    document.redo()
    assert document.getObject(name).isValid()


def test_make_wood_part_invalide_ne_cree_pas_de_document() -> None:
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    try:
        with pytest.raises(part_model.InvalidDimensionsError):
            api.make_wood_part(0)
        assert App.listDocuments() == {}
    finally:
        for name in list(App.listDocuments()):
            App.closeDocument(name)


# --- B14 : bibliothèque utilisateur corrompue ---------------------------------------------


@pytest.mark.parametrize(
    "content", [b"{corrompu", b"\xff\xfe{}", b'{"format": 99, "materials": []}'], ids=str
)
def test_bibliotheque_corrompue_signalee_une_fois(
    document: Any,
    rouvrir: Reopen,
    bibliotheque_temporaire: Any,
    vue_rapport: Any,
    content: bytes,
) -> None:
    bibliotheque_temporaire.path.write_bytes(content)
    vue_rapport.messages.clear()
    library.reload_library()
    for _ in range(3):
        library.get_library()
    obj = wood_part.create_wood_part(document, material_id="noyer")
    document.recompute()
    name = obj.Name
    reopened = rouvrir(document)
    reopened.recompute()
    second = board(reopened, "hetre")
    [error] = vue_rapport.de_niveau("Error")
    assert str(bibliotheque_temporaire.path) in error
    assert re.search(r"\{[a-z_]+\}", error) is None
    assert vue_rapport.de_niveau("Warning") == []
    assert reopened.getObject(name).isValid()
    assert second.isValid()
