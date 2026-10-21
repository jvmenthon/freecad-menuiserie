# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture, annulation, suppression et déplacement des pièces assemblées (J3b, O8 à O12)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import RAIL_VOLUME, STILE_VOLUME, Cadre, placement, stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

Reopen = Callable[[Any], Any]
# Masse volumique relue en kg/mm³ (arrondi, cf. J1b) ; les textes qui citent une adresse
# mémoire (Shape, Proxy, ShapeMaterial en 1.1) sont ignorés aussi.
UNCOMPARABLE = ("Density",)
MACHINED_PROXY = ("freecad.menuiserie.features.machined_part", "MachinedPart")
JOINT_PROXY = ("freecad.menuiserie.features.joints.mortise_tenon", "MortiseTenonJoint")


def snapshot(doc: Any) -> dict[str, tuple[float, dict[str, str]]]:
    """Volume et propriétés (textes) de chaque objet de l'atelier."""
    result = {}
    for obj in doc.Objects:
        texts = {name: str(obj.getPropertyByName(name)) for name in obj.PropertiesList}
        values = {
            name: text
            for name, text in texts.items()
            if name not in UNCOMPARABLE and " at 0x" not in text
        }
        volume = 0.0 if obj.Shape.isNull() else float(obj.Shape.Volume)
        result[obj.Name] = (round(volume, 3), values)
    return result


def by_name(doc: Any, name: str) -> Any:
    return doc.getObject(name)


# --- O8 : enregistrer, fermer, rouvrir ---------------------------------------------------


def test_reouverture_a_l_identique(cadre_assemble: Cadre, rouvrir: Reopen) -> None:
    before = snapshot(cadre_assemble.doc)
    joint_name = cadre_assemble.joints["M1", "T1"].Name
    machined_name = cadre_assemble.machined("M1").Name
    doc = rouvrir(cadre_assemble.doc)
    after = snapshot(doc)
    differences = [
        (name, prop, values[prop], after[name][1].get(prop))
        for name, (_, values) in before.items()
        for prop in values
        if values[prop] != after[name][1].get(prop)
    ]
    assert differences == []
    assert {name: volume for name, (volume, _) in after.items()} == {
        name: volume for name, (volume, _) in before.items()
    }
    assert stale_or_invalid(doc) == []
    for name, (module, cls) in ((machined_name, MACHINED_PROXY), (joint_name, JOINT_PROXY)):
        obj = by_name(doc, name)
        assert (type(obj.Proxy).__module__, type(obj.Proxy).__name__) == (module, cls)
        assert obj.Proxy.dumps() is None
        assert obj.Version == 1
    doc.recompute()
    assert by_name(doc, machined_name).Shape.Volume == pytest.approx(STILE_VOLUME)


# --- O9 : réouverture contrôlée ----------------------------------------------------------


def test_version_absente_migree(cadre_assemble: Cadre, rouvrir: Reopen) -> None:
    joint = cadre_assemble.joints["M1", "T1"]
    machined = cadre_assemble.machined("M1")
    for obj in (joint, machined):
        obj.removeProperty("Version")
    joint.removeProperty("MortiseClearance")
    names = (joint.Name, machined.Name)
    doc = rouvrir(cadre_assemble.doc)
    for name in names:
        assert by_name(doc, name).Version == 1
    assert by_name(doc, names[0]).MortiseClearance.Value == pytest.approx(2)


def test_version_plus_recente_non_migree(
    cadre_assemble: Cadre, rouvrir: Reopen, vue_rapport: Any
) -> None:
    joint = cadre_assemble.joints["M1", "T1"]
    joint.Version = 2
    joint.removeProperty("MortiseClearance")
    name = joint.Name
    doc = rouvrir(cadre_assemble.doc)
    restored = by_name(doc, name)
    assert restored.Version == 2
    assert "MortiseClearance" not in restored.PropertiesList
    warnings = [text for text in vue_rapport.de_niveau("Warning") if "version plus récente" in text]
    assert len(warnings) == 1
    assert warnings[0].startswith("Menuiserie : Assemblage « Tenon-mortaise")


def test_propriete_d_un_type_inattendu(
    cadre_assemble: Cadre, rouvrir: Reopen, vue_rapport: Any
) -> None:
    machined = cadre_assemble.machined("T1")
    joint = cadre_assemble.joints["M1", "T1"]
    joint.removeProperty("TenonThickness")
    joint.addProperty("App::PropertyString", "TenonThickness")
    joint.TenonThickness = "épais"
    machined.removeProperty("Version")
    machined.addProperty("App::PropertyString", "Version")
    names = (joint.Name, machined.Name)
    doc = rouvrir(cadre_assemble.doc)
    restored_joint, restored_machined = (by_name(doc, name) for name in names)
    assert restored_joint.getTypeIdOfProperty("TenonThickness") == "App::PropertyLength"
    assert restored_joint.TenonThickness.Value == 0
    assert restored_machined.getTypeIdOfProperty("Version") == "App::PropertyInteger"
    assert restored_machined.Version == 1
    warnings = " ".join(vue_rapport.de_niveau("Warning"))
    assert "propriété TenonThickness d'un type inattendu" in warnings
    assert "Pièce usinée « T" in warnings
    doc.recompute()
    assert restored_machined.Shape.Volume == pytest.approx(RAIL_VOLUME)


# --- O10 : annuler / rétablir ------------------------------------------------------------


def test_annuler_retablir_la_creation(cadre: Cadre) -> None:
    doc = cadre.doc
    doc.UndoMode = 1
    count = len(doc.Objects)
    doc.openTransaction("Créer un assemblage tenon-mortaise")
    api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"])
    doc.commitTransaction()
    assert len(doc.Objects) == count + 3
    doc.undo()
    assert len(doc.Objects) == count
    assert cadre.parts["M1"].Visibility is True
    assert cadre.parts["T1"].Visibility is True
    doc.redo()
    doc.recompute()
    assert len(doc.Objects) == count + 3
    assert cadre.parts["M1"].Visibility is False
    assert cadre.volume("T1") == pytest.approx(280 * 60 * 22 + 40 * 40 * 7)
    assert cadre.volume("M1") == pytest.approx(600 * 60 * 22 - 42 * 40 * 7)


def test_annuler_une_modification(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    doc.UndoMode = 1
    joint = cadre_assemble.joints["M1", "T1"]
    doc.openTransaction("Modifier un assemblage")
    joint.TenonThickness = 8
    doc.commitTransaction()
    doc.recompute()
    doc.undo()
    doc.recompute()
    assert joint.TenonThickness.Value == 0
    assert cadre_assemble.volume("T1") == pytest.approx(RAIL_VOLUME)


# --- O11 : suppression -------------------------------------------------------------------


def test_supprimer_un_assemblage(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    doc.removeObject(cadre_assemble.joints["M1", "T1"].Name)
    doc.recompute()
    assert stale_or_invalid(doc) == []
    assert cadre_assemble.volume("M1") == pytest.approx(600 * 60 * 22 - 42 * 40 * 7)
    assert cadre_assemble.volume("T1") == pytest.approx(280 * 60 * 22 + 40 * 40 * 7)


def test_supprimer_une_piece_usinee_sans_assemblage(cadre_assemble: Cadre) -> None:
    doc, blank = cadre_assemble.doc, cadre_assemble.parts["M1"]
    machined = cadre_assemble.machined("M1")
    with pytest.raises(ValueError, match="porte encore des assemblages"):
        api.remove_machined_part(machined)
    for pair in (("M1", "T1"), ("M1", "T2")):
        doc.removeObject(cadre_assemble.joints[pair].Name)
    count = len(doc.Objects)
    api.remove_machined_part(machined)
    assert len(doc.Objects) == count - 1
    assert api.machined_part_of(blank) is None
    assert blank.Visibility is True
    with pytest.raises(TypeError):
        api.remove_machined_part(blank)


def test_supprimer_une_brute(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    machined = cadre_assemble.machined("T2")
    doc.removeObject(cadre_assemble.parts["T2"].Name)
    doc.recompute()
    for pair in (("M1", "T2"), ("M2", "T2")):
        assert not cadre_assemble.joints[pair].isValid()
    # Dépendante d'assemblages invalides, la pièce usinée n'est pas recalculée (comme en O6).
    assert "Invalid" in machined.State or "Touched" in machined.State
    assert cadre_assemble.machined("T1").isValid()


# --- O12 : documents J1 et liste de débit -------------------------------------------------


def test_document_j1_inchange(document: Any, rouvrir: Reopen) -> None:
    obj = api.make_wood_part(600, 60, 22, "chene", doc=document)
    name = obj.Name
    doc = rouvrir(document)
    restored = by_name(doc, name)
    assert restored.Version == 2
    assert stale_or_invalid(doc) == []
    assert [o.Name for o in doc.Objects] == [name]


def test_record_of_inchange(cadre: Cadre) -> None:
    before = {mark: wood_part.record_of(part) for mark, part in cadre.parts.items()}
    cadre.assemble()
    assert {mark: wood_part.record_of(part) for mark, part in cadre.parts.items()} == before


# --- Q4 : déplacer la pièce usinée déplace sa brute --------------------------------------


def test_deplacer_la_piece_usinee(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    doc.UndoMode = 1
    machined, blank = cadre_assemble.machined("T1"), cadre_assemble.parts["T1"]
    doc.openTransaction("Déplacer")
    moved = placement(60, 60, 90)
    moved.Base.z = 30
    machined.Placement = moved
    doc.commitTransaction()
    assert blank.Placement == machined.Placement
    doc.recompute()
    assert blank.Placement == machined.Placement
    assert "Invalid" in cadre_assemble.joints["M1", "T1"].State
    doc.undo()
    doc.recompute()
    assert blank.Placement == placement(60, 60, 90)
    assert stale_or_invalid(doc) == []
    assert cadre_assemble.volume("T1") == pytest.approx(RAIL_VOLUME)
