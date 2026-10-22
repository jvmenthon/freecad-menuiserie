# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce de bois dans un vrai document FreeCAD, sans interface (critères B1 à B12)."""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
part_model = pytest.importorskip("freecad.menuiserie.core.part_model")

Reopen = Callable[[Any], Any]
OAK_LABEL = "Chêne"
MAPLE = {
    "id": "erable",
    "kind": "solid",
    "name": {"fr": "Érable", "en": "Maple"},
    "density": 650,
    "thicknesses": [22, 27],
    "color": "#E8D2A8",
}

# Propriétés du tableau du § 4.4.2 : type, groupe, mode d'édition, infobulle.
PROPERTIES = [
    (
        "Length",
        "App::PropertyLength",
        "Dimensions",
        [],
        "Longueur finie de la pièce, mesurée selon l'axe X local.",
    ),
    (
        "Width",
        "App::PropertyLength",
        "Dimensions",
        [],
        "Largeur finie de la pièce, mesurée selon l'axe Y local.",
    ),
    (
        "Thickness",
        "App::PropertyLength",
        "Dimensions",
        [],
        "Épaisseur finie de la pièce, mesurée selon l'axe Z local.",
    ),
    (
        "Material",
        "App::PropertyEnumeration",
        "Matériau",
        [],
        "Essence ou panneau, choisi dans la bibliothèque de matériaux.",
    ),
    (
        "MaterialId",
        "App::PropertyString",
        "Matériau",
        ["ReadOnly"],
        "Identifiant stable du matériau dans la bibliothèque. C'est lui qui est enregistré et "
        "utilisé par les calculs.",
    ),
    (
        "Category",
        "App::PropertyEnumeration",
        "Matériau",
        ["ReadOnly"],
        "Type de matériau, déduit du matériau choisi : massif ou panneau (contreplaqué, MDF, "
        "mélaminé).",
    ),
    (
        "Density",
        "App::PropertyDensity",
        "Matériau",
        ["ReadOnly"],
        "Masse volumique recopiée de la bibliothèque au choix du matériau ; sert au calcul de "
        "la masse.",
    ),
    (
        "GrainDirection",
        "App::PropertyEnumeration",
        "Matériau",
        [],
        "Sens du fil par rapport aux cotes de la pièce : le long de la longueur, de la "
        "largeur, ou sans fil (MDF, mélaminé uni).",
    ),
    (
        "PreferredGrainDirection",
        "App::PropertyEnumeration",
        "Matériau",
        ["Hidden"],
        "Dernier sens du fil choisi pour la pièce, repris quand elle revient à un matériau "
        "avec fil.",
    ),
    (
        "Mark",
        "App::PropertyString",
        "Débit",
        [],
        "Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 ») ; c'est aussi "
        "son nom dans l'arborescence. Des pièces identiques peuvent partager le même repère.",
    ),
    (
        "LengthAllowance",
        "App::PropertyLength",
        "Débit",
        [],
        "Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit.",
    ),
    (
        "WidthAllowance",
        "App::PropertyLength",
        "Débit",
        [],
        "Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit.",
    ),
    (
        "ThicknessAllowance",
        "App::PropertyLength",
        "Débit",
        [],
        "Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit.",
    ),
    (
        "Version",
        "App::PropertyInteger",
        "Base",
        ["Hidden"],
        "Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers.",
    ),
]
PROPERTY_NAMES = [name for name, *_ in PROPERTIES]


def oak_board(doc: Any) -> Any:
    """Planche de chêne de 800 x 200 x 22 mm, recalculée."""
    obj = wood_part.create_wood_part(doc, length=800, width=200, thickness=22, material_id="chene")
    doc.recompute()
    return obj


def values(obj: Any) -> dict[str, object]:
    """Valeurs comparables des propriétés de la pièce (quantités en texte)."""
    return {name: str(getattr(obj, name)) for name in [*PROPERTY_NAMES, "Label"]}


def density(obj: Any) -> float:
    return float(obj.Density.getValueAs("kg/m^3"))


def allowances(obj: Any) -> tuple[float, float, float]:
    return (
        obj.LengthAllowance.Value,
        obj.WidthAllowance.Value,
        obj.ThicknessAllowance.Value,
    )


# --- B1 : création ------------------------------------------------------------------------


def test_creation_planche_de_chene(document: Any) -> None:
    obj = oak_board(document)
    assert obj.isValid()
    assert obj.Shape.Volume == pytest.approx(3_520_000)
    box = obj.Shape.BoundBox
    assert (box.XMin, box.YMin, box.ZMin) == pytest.approx((0, 0, 0))
    assert (box.XLength, box.YLength, box.ZLength) == pytest.approx((800, 200, 22))
    assert obj.MaterialId == "chene"
    assert obj.Material == OAK_LABEL
    assert obj.Category == "Solid"
    assert density(obj) == pytest.approx(710)
    assert obj.GrainDirection == "Length"
    assert obj.PreferredGrainDirection == "Length"
    assert obj.Version == wood_part.WoodPart.VERSION == 2
    assert allowances(obj) == (20, 5, 0)
    assert obj.Label.startswith("Pièce de bois")


def test_creation_refuse_cote_et_materiau_invalides(document: Any) -> None:
    with pytest.raises(part_model.InvalidDimensionsError):
        wood_part.create_wood_part(document, length=0)
    with pytest.raises(KeyError):
        wood_part.create_wood_part(document, material_id="inconnu")
    assert document.Objects == []


# --- B2 : propriétés ----------------------------------------------------------------------


@pytest.mark.parametrize(("name", "type_id", "group", "mode", "tooltip"), PROPERTIES)
def test_propriete_declaree(
    document: Any, name: str, type_id: str, group: str, mode: list[str], tooltip: str
) -> None:
    obj = oak_board(document)
    assert obj.getTypeIdOfProperty(name) == type_id
    assert obj.getGroupOfProperty(name) == group
    assert obj.getEditorMode(name) == mode
    assert obj.getDocumentationOfProperty(name) == tooltip


def test_valeurs_des_enumerations_figees(document: Any) -> None:
    obj = oak_board(document)
    assert obj.getEnumerationsOfProperty("Category") == ["Solid", "Plywood", "MDF", "Melamine"]
    assert obj.getEnumerationsOfProperty("GrainDirection") == ["Length", "Width", "None"]
    assert obj.getEnumerationsOfProperty("PreferredGrainDirection") == ["Length", "Width"]
    labels = obj.getEnumerationsOfProperty("Material")
    assert labels[0] == OAK_LABEL
    assert len(labels) == 12


# --- B3, B4 : cotes, placement et expressions ---------------------------------------------


@pytest.mark.parametrize(
    ("name", "value", "volume"),
    [("Length", 1000, 4_400_000), ("Width", 250, 4_400_000), ("Thickness", 27, 4_320_000)],
)
def test_cote_modifiee_placement_conserve(
    document: Any, name: str, value: float, volume: float
) -> None:
    obj = oak_board(document)
    placement = App.Placement(App.Vector(10, 20, 30), App.Rotation(App.Vector(1, 1, 0), 30))
    obj.Placement = placement
    document.recompute()
    setattr(obj, name, value)
    document.recompute()
    assert obj.isValid()
    assert obj.Shape.Volume == pytest.approx(volume)
    assert obj.Placement.isSame(placement, 1e-9)


def test_expression_sur_une_cote(document: Any) -> None:
    obj = oak_board(document)
    obj.setExpression("Length", "Width * 4")
    document.recompute()
    assert obj.Length.Value == pytest.approx(800)
    obj.Width = 250
    document.recompute()
    assert obj.Length.Value == pytest.approx(1000)
    assert obj.Shape.Volume == pytest.approx(1000 * 250 * 22)


# --- B5 : changement de matériau ----------------------------------------------------------


def test_changement_de_materiau(document: Any) -> None:
    obj = oak_board(document)
    obj.Material = "Hêtre"
    assert (obj.MaterialId, obj.Category) == ("hetre", "Solid")
    assert density(obj) == pytest.approx(720)
    assert (obj.Length.Value, obj.Width.Value, obj.Thickness.Value) == (800, 200, 22)
    obj.Material = "MDF"
    assert (obj.MaterialId, obj.Category, obj.GrainDirection) == ("mdf", "MDF", "None")
    assert allowances(obj) == (0, 0, 0)
    assert (obj.Length.Value, obj.Width.Value, obj.Thickness.Value) == (800, 200, 22)


def test_surcotes_choisies_conservees(document: Any) -> None:
    obj = oak_board(document)
    obj.LengthAllowance = 30
    obj.GrainDirection = "Width"
    wood_part.set_material(obj, "cp-bouleau")
    assert (obj.Material, obj.Category) == ("Contreplaqué bouleau", "Plywood")
    assert allowances(obj) == (30, 5, 0)
    assert obj.GrainDirection == "Width"


def test_set_material_refuse_un_identifiant_inconnu(document: Any) -> None:
    obj = oak_board(document)
    with pytest.raises(KeyError):
        wood_part.set_material(obj, "inconnu")
    with pytest.raises(TypeError):
        wood_part.set_material(document.addObject("Part::Box", "Boite"), "chene")
    assert obj.MaterialId == "chene"


# --- B6 : cote invalide -------------------------------------------------------------------


def test_cote_nulle_met_la_piece_en_erreur(document: Any) -> None:
    obj = oak_board(document)
    other = oak_board(document)
    obj.Length = 0
    document.recompute()
    assert not obj.isValid()
    assert "cote invalide" in obj.getStatusString().lower()
    assert "longueur" in obj.getStatusString()
    assert other.isValid()
    obj.Length = 900
    document.recompute()
    assert obj.isValid()
    assert obj.Shape.Volume == pytest.approx(900 * 200 * 22)


def test_cote_negative_jamais_retenue(document: Any) -> None:
    obj = oak_board(document)
    obj.Width = -5
    assert obj.Width.Value >= 0
    document.recompute()
    assert not obj.isValid()


# --- B7 à B9 : enregistrement, bibliothèque changée, migration ----------------------------


def test_enregistrer_et_rouvrir(document: Any, rouvrir: Reopen) -> None:
    obj = oak_board(document)
    obj.Mark = "M1"
    obj.Material = "Noyer"
    obj.GrainDirection = "Width"
    document.recompute()
    before = values(obj)
    name = obj.Name
    reopened = rouvrir(document)
    restored = reopened.getObject(name)
    assert values(restored) == before
    assert restored.isValid()
    assert restored.Shape.Volume == pytest.approx(3_520_000)
    assert [o.Name for o in reopened.Objects if "Touched" in o.State] == []
    assert restored.getEditorMode("MaterialId") == ["ReadOnly"]


def test_rouvrir_sans_le_materiau(
    document: Any, rouvrir: Reopen, bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    bibliotheque_temporaire.installer(MAPLE)
    obj = wood_part.create_wood_part(document, material_id="erable")
    document.recompute()
    bibliotheque_temporaire.retirer()
    vue_rapport.messages.clear()
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert restored.MaterialId == "erable"
    assert restored.Material == "Érable"
    assert density(restored) == pytest.approx(650)
    assert restored.isValid()
    [warning] = vue_rapport.de_niveau("Warning")
    assert "erable" in warning
    assert vue_rapport.de_niveau("Error") == []
    assert "Érable" in restored.getEnumerationsOfProperty("Material")


def test_migration_d_un_ancien_fichier(document: Any, rouvrir: Reopen) -> None:
    obj = oak_board(document)
    obj.ThicknessAllowance = 3
    obj.removeProperty("Version")
    obj.removeProperty("ThicknessAllowance")
    obj.removeProperty("PreferredGrainDirection")
    name = obj.Name
    restored = rouvrir(document).getObject(name)
    assert restored.Version == wood_part.WoodPart.VERSION
    assert restored.ThicknessAllowance.Value == 0
    assert restored.PreferredGrainDirection == "Length"
    assert restored.getEditorMode("Version") == ["Hidden"]
    assert restored.getGroupOfProperty("ThicknessAllowance") == "Débit"
    restored.Document.recompute()
    assert restored.isValid()


# --- B10 : annuler / rétablir -------------------------------------------------------------


def test_annuler_retablir_la_creation(document: Any) -> None:
    document.UndoMode = 1
    document.openTransaction("Créer une pièce de bois")
    obj = oak_board(document)
    name = obj.Name
    document.commitTransaction()
    document.undo()
    assert document.getObject(name) is None
    document.redo()
    restored = document.getObject(name)
    assert wood_part.is_wood_part(restored)
    assert (restored.MaterialId, restored.Length.Value) == ("chene", 800)
    document.recompute()
    assert restored.isValid()


@pytest.mark.parametrize(
    ("name", "value", "check"),
    [
        ("Length", 1000, lambda obj: obj.Length.Value),
        ("Material", "MDF", lambda obj: (obj.MaterialId, obj.GrainDirection, allowances(obj))),
    ],
    ids=["Length", "Material"],
)
def test_annuler_retablir_une_modification(
    document: Any, name: str, value: object, check: Callable[[Any], object]
) -> None:
    document.UndoMode = 1
    obj = oak_board(document)
    before = check(obj)
    document.openTransaction("Modifier une pièce de bois")
    setattr(obj, name, value)
    document.commitTransaction()
    after = check(obj)
    document.undo()
    assert check(obj) == before
    document.redo()
    assert check(obj) == after


# --- B11, B12 : contrat de persistance et enregistrement de débit -------------------------


def test_contrat_de_persistance(document: Any, tmp_path: Path) -> None:
    obj = oak_board(document)
    proxy = obj.Proxy
    assert type(proxy).__module__ == "freecad.menuiserie.features.wood_part"
    assert type(proxy).__qualname__ == "WoodPart"
    assert proxy.dumps() is None
    path = tmp_path / "contrat.FCStd"
    document.saveAs(str(path))
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("Document.xml").decode("utf-8")
    assert 'module="freecad.menuiserie.features.wood_part"' in xml
    assert 'class="WoodPart"' in xml


def test_enregistrement_de_debit(document: Any) -> None:
    obj = oak_board(document)
    obj.Mark = "M1"
    record = wood_part.record_of(obj)
    assert record.mark == "M1"
    assert (record.material_id, record.material_name) == ("chene", OAK_LABEL)
    assert record.kind.value == "solid"
    assert record.finished == part_model.Dimensions(800, 200, 22)
    assert record.allowances == part_model.Allowances(20, 5, 0)
    assert record.grain is part_model.GrainDirection.LENGTH
    assert record.density == pytest.approx(710)
    assert record.volume_m3() == pytest.approx(0.00352)
    assert record.mass_kg() == pytest.approx(2.4992)
    assert record.rough == part_model.Dimensions(820, 205, 22)


def test_reconnaissance_d_une_piece(document: Any) -> None:
    obj = oak_board(document)
    box = document.addObject("Part::Box", "Boite")
    assert wood_part.is_wood_part(obj)
    assert not wood_part.is_wood_part(box)
    assert not wood_part.is_wood_part(None)
