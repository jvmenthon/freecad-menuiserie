# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture, annulation, libellés réécrits par FreeCAD (J4b', N12, N13, N15, risque R2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.bureau import EXPRESSIONS, LAYOUT, Bureau, build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

Reopen = Callable[[Any], Any]
UNCOMPARABLE = ("Density",)  # relue en kg/mm³, arrondie (cf. J1b)


def snapshot(doc: Any) -> dict[str, dict[str, str]]:
    """Propriétés (textes) et expressions de chaque objet ; adresses mémoire ignorées."""
    result = {}
    for obj in doc.Objects:
        texts = {name: str(obj.getPropertyByName(name)) for name in obj.PropertiesList}
        values = {k: v for k, v in texts.items() if k not in UNCOMPARABLE and " at 0x" not in v}
        values["(types)"] = str([obj.getTypeIdOfProperty(name) for name in obj.PropertiesList])
        result[obj.Name] = values
    return result


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


# --- N12 : enregistrer, fermer, rouvrir ------------------------------------------------------


def test_reouverture_a_l_identique(bureau: Bureau, rouvrir: Reopen) -> None:
    bureau.parts["V"].FixedBack = False
    bureau.parts["V"].PositionMode = "Proportional"
    bureau.doc.recompute()
    before = snapshot(bureau.doc)
    name, voile = bureau.furniture.Name, bureau.parts["V"].Name
    doc = rouvrir(bureau.doc)
    assert snapshot(doc) == before
    assert stale_or_invalid(doc) == []
    furniture = doc.getObject(name)
    proxy = type(furniture.Proxy)
    assert (proxy.__module__, proxy.__name__) == (
        "freecad.menuiserie.features.furniture",
        "Furniture",
    )
    assert proxy.TYPE == "Menuiserie::Furniture"
    assert furniture.Proxy.dumps() is None
    assert furniture.Version == 1
    furniture.Depth = 800
    doc.recompute()
    assert doc.getObject(voile).Shape.BoundBox.YMin == pytest.approx(591)
    assert stale_or_invalid(doc) == []


def test_version_absente_ou_mal_typee(bureau: Bureau, rouvrir: Reopen, vue_rapport: Any) -> None:
    furniture = bureau.furniture
    furniture.removeProperty("Version")
    furniture.addProperty("App::PropertyString", "Version")
    furniture.Version = "un"
    furniture.removeProperty("Template")
    name = furniture.Name
    doc = rouvrir(bureau.doc)
    restored = doc.getObject(name)
    assert restored.getTypeIdOfProperty("Version") == "App::PropertyInteger"
    assert restored.Version == 1
    assert restored.Template == ""
    assert any("version du modèle illisible" in w for w in vue_rapport.de_niveau("Warning"))
    doc.recompute()  # migration : l'ensemble est à recalculer, comme en J3
    assert stale_or_invalid(doc) == []


def test_version_plus_recente(bureau: Bureau, rouvrir: Reopen, vue_rapport: Any) -> None:
    bureau.furniture.Version = 2
    bureau.furniture.removeProperty("Template")
    name = bureau.furniture.Name
    doc = rouvrir(bureau.doc)
    restored = doc.getObject(name)
    assert restored.Version == 2
    assert "Template" not in restored.PropertiesList
    warnings = [w for w in vue_rapport.de_niveau("Warning") if "version plus récente" in w]
    assert len(warnings) == 1
    assert warnings[0].startswith("Menuiserie : Ensemble « Bureau » : document créé par")


def test_proprietes_de_membre_mal_typees(bureau: Bureau, rouvrir: Reopen, vue_rapport: Any) -> None:
    plateau, joue = bureau.parts["P"], bureau.parts["JG"]
    plateau.removeProperty("FixedTop")
    plateau.addProperty("App::PropertyInteger", "FixedTop", "Ensemble")
    plateau.FixedTop = 0
    joue.removeProperty("PositionMode")
    joue.addProperty("App::PropertyString", "PositionMode", "Ensemble")
    joue.PositionMode = "Proportional"
    engines = {mark: engine(part) for mark, part in bureau.parts.items()}
    names = {mark: part.Name for mark, part in bureau.parts.items()}
    doc = rouvrir(bureau.doc)
    plateau, joue = doc.getObject(names["P"]), doc.getObject(names["JG"])
    assert plateau.getTypeIdOfProperty("FixedTop") == "App::PropertyBool"
    assert plateau.FixedTop is True  # option par défaut (F3)
    assert joue.getTypeIdOfProperty("PositionMode") == "App::PropertyEnumeration"
    assert joue.PositionMode == "Stay"
    assert joue.getEnumerationsOfProperty("PositionMode") == ["Stay", "Proportional"]
    assert {mark: engine(doc.getObject(n)) for mark, n in names.items()} == engines
    warnings = " ".join(vue_rapport.de_niveau("Warning"))
    assert "Membre d'ensemble « Plateau » : propriété FixedTop d'un type inattendu" in warnings
    assert "propriété PositionMode d'un type inattendu" in warnings
    doc.recompute()  # propriétés recréées : pièces à recalculer, comme en J1 et J3
    assert stale_or_invalid(doc) == []
    assert {mark: engine(doc.getObject(n)) for mark, n in names.items()} == engines


# --- N13 : annuler / rétablir --------------------------------------------------------------------


def undone_and_redone(doc: Any, action: Callable[[], object]) -> None:
    """``action`` dans une transaction : ``undo()`` rétablit tout, ``redo()`` la refait."""
    doc.UndoMode = 1
    doc.recompute()
    before = snapshot(doc)
    count = doc.UndoCount
    doc.openTransaction("Ensemble")
    action()
    doc.commitTransaction()
    doc.recompute()
    after = snapshot(doc)
    assert doc.UndoCount == count + 1
    doc.undo()
    doc.recompute()
    assert snapshot(doc) == before
    doc.redo()
    doc.recompute()
    assert snapshot(doc) == after
    assert stale_or_invalid(doc) == []


def test_annuler_la_creation(document: Any) -> None:
    bureau = build_parts(document)
    undone_and_redone(
        document, lambda: api.make_furniture(list(bureau.parts.values()), label="Bureau")
    )
    assert engine(bureau.parts["JG"]) == EXPRESSIONS["JG"]


@pytest.mark.parametrize(
    "action",
    [
        "ajout",
        "retrait",
        "mode",
        "option",
        "redimensionnement",
        "relier",
    ],
)
def test_annuler_une_operation(document: Any, action: str) -> None:
    bureau = build_parts(document)
    parts = bureau.parts
    furniture, _ = api.make_furniture([parts["P"], parts["JG"], parts["JD"]], label="Bureau")
    actions: dict[str, Callable[[], object]] = {
        "ajout": lambda: api.add_to_furniture(furniture, [parts["V"]]),
        "retrait": lambda: api.remove_from_furniture([parts["JG"]]),
        "mode": lambda: api.set_member_options(parts["JG"], mode="Proportional"),
        "option": lambda: setattr(parts["JG"], "FixedBack", False),
        "redimensionnement": lambda: api.resize_furniture(furniture, depth=800, height=800),
        "relier": lambda: api.rebind_furniture(furniture),
    }
    if action == "relier":
        parts["P"].setExpression("Width", None)
    undone_and_redone(document, actions[action])


# --- N15 : documents J1 et J3, liste de débit -----------------------------------------------------


def test_record_of_inchange_pour_un_membre(document: Any) -> None:
    bureau = build_parts(document)
    before = {mark: wood_part.record_of(part) for mark, part in bureau.parts.items()}
    api.make_furniture(list(bureau.parts.values()), label="Bureau")
    assert {mark: wood_part.record_of(part) for mark, part in bureau.parts.items()} == before


def test_document_j3_sans_propriete_ajoutee(cadre_assemble: Any, rouvrir: Reopen) -> None:
    before = snapshot(cadre_assemble.doc)
    doc = rouvrir(cadre_assemble.doc)
    assert snapshot(doc) == before
    assert stale_or_invalid(doc) == []
    assert not any("Furniture" in obj.PropertiesList for obj in doc.Objects)


# --- R2 : libellés réécrits par FreeCAD ------------------------------------------------------


@pytest.mark.parametrize("label", ["Bureau d'angle", 'Meuble "TV"', "Bu'r\"eau"])
def test_libelle_avec_apostrophe_et_guillemets(
    document: Any, rouvrir: Reopen, vue_rapport: Any, label: str
) -> None:
    bureau = build_parts(document)
    furniture, notices = api.make_furniture(list(bureau.parts.values()), label=label)
    assert notices == ()
    escaped = label.replace("'", "\\'").replace('"', '\\"')
    assert engine(bureau.parts["JG"])["Width"] == f"<<{escaped}>>.Depth - 40 mm"
    assert dict(bureau.parts["JG"].FurnitureBindings) == engine(bureau.parts["JG"])
    names = {mark: part.Name for mark, part in bureau.parts.items()}
    name = furniture.Name
    doc = rouvrir(document)
    parts = {mark: doc.getObject(part) for mark, part in names.items()}
    furniture = doc.getObject(name)
    assert api.set_member_options(parts["V"], fixed={"Back": True}) == ()
    assert api.rebind_furniture(furniture) == ()
    furniture.Depth = 800
    doc.recompute()
    assert parts["JG"].Width.Value == pytest.approx(760)
    assert vue_rapport.de_niveau("Warning") == []


def test_ensemble_renomme(bureau: Bureau, rouvrir: Reopen) -> None:
    bureau.furniture.Label = "Bureau d'angle"
    expected = "<<Bureau d\\'angle>>.Depth - 40 mm"
    assert engine(bureau.parts["JG"])["Width"] == expected
    assert api.set_member_options(bureau.parts["JG"], mode="Proportional") == ()
    assert api.rebind_furniture(bureau.furniture) == ()
    assert dict(bureau.parts["JD"].FurnitureBindings)["Width"] == expected
    names = [bureau.parts[mark].Name for mark in LAYOUT]
    name = bureau.furniture.Name
    doc = rouvrir(bureau.doc)
    assert api.rebind_furniture(doc.getObject(name)) == ()
    assert engine(doc.getObject(names[1]))["Width"] == expected
