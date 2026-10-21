# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaisons du bureau de référence et formules de l'utilisateur (J4a, critères F8, F9)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Linear,
    Member,
    NoticeKind,
    bindings_for,
    bound_by_workshop,
    driven_properties,
    expression_text,
    follow_rules,
    is_driven,
    label_reference,
    same_binding,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_ensembles import BOX, FREE_BACK, desk, with_options

DESK = {
    ("P", "Length"): "<<Bureau>>.Width",
    ("P", "Width"): "<<Bureau>>.Depth",
    ("P", "Placement.Base.z"): "<<Bureau>>.Origin.z + <<Bureau>>.Height - 30 mm",
    ("JG", "Length"): "<<Bureau>>.Height - 30 mm",
    ("JG", "Width"): "<<Bureau>>.Depth - 40 mm",
    ("JD", "Length"): "<<Bureau>>.Height - 30 mm",
    ("JD", "Width"): "<<Bureau>>.Depth - 40 mm",
    ("JD", "Placement.Base.x"): "<<Bureau>>.Origin.x + <<Bureau>>.Width",
    ("V", "Length"): "<<Bureau>>.Width - 44 mm",
    ("V", "Width"): "<<Bureau>>.Height - 350 mm",
    ("V", "Placement.Base.y"): "<<Bureau>>.Origin.y + <<Bureau>>.Depth - 141 mm",
}


def bindings(
    members: list[Member], label: str = "Bureau", *, nested: bool = False
) -> dict[tuple[str, str], str]:
    rules, _ = follow_rules(BOX, members)
    found, _ = bindings_for(label, BOX, members, rules, nested=nested)
    result = {(b.key, b.prop): b.expression for b in found}
    assert len(result) == len(found), "une seule liaison par propriété"
    return result


# --- F8 : expressions exactes -------------------------------------------------------------


def test_bureau_options_par_defaut() -> None:
    assert bindings(with_options(desk())) == DESK


def test_bureau_arriere_des_joues_decoche() -> None:
    expected = {k: v for k, v in DESK.items() if k not in {("JG", "Width"), ("JD", "Width")}}
    assert bindings(with_options(desk(), FREE_BACK)) == expected


def test_voile_en_proportion() -> None:
    members = with_options(desk(V=InteriorMode.PROPORTIONAL), {"V": frozenset({Edge.BACK})})
    found = bindings(members)
    assert found[("V", "Placement.Base.y")] == (
        "<<Bureau>>.Origin.y + <<Bureau>>.Depth * 0.75 + 9 mm"
    )
    assert found[("V", "Width")] == "<<Bureau>>.Height - 350 mm"  # le bas reste fixe
    assert ("V", "Placement.Base.z") not in found


def test_ensemble_imbrique_lie_toutes_les_positions() -> None:
    found = bindings(with_options(desk()), nested=True)
    assert found[("P", "Placement.Base.x")] == "<<Bureau>>.Origin.x"
    assert found[("JG", "Placement.Base.x")] == "<<Bureau>>.Origin.x + 22 mm"
    assert found[("V", "Placement.Base.z")] == "<<Bureau>>.Origin.z + 320 mm"
    assert found[("JD", "Placement.Base.x")] == DESK[("JD", "Placement.Base.x")]
    assert len(found) == len(DESK) + 12 - 3


@pytest.mark.parametrize(
    ("linear", "expected"),
    [
        (Linear(1.0, 0.0), "<<B>>.Depth"),
        (Linear(1.0, -40.0), "<<B>>.Depth - 40 mm"),
        (Linear(0.5, 12.25), "<<B>>.Depth * 0.5 + 12.25 mm"),
        (Linear(1 / 3, 1e-7), "<<B>>.Depth * 0.333333333"),
        (Linear(1.0000000001, -1e-7), "<<B>>.Depth"),
        (Linear(2.0, 0.1234567), "<<B>>.Depth * 2 + 0.123457 mm"),
        (Linear(0.0, -3.0), "-3 mm"),
    ],
)
def test_format_des_nombres(linear: Linear, expected: str) -> None:
    assert expression_text("<<B>>", FurnitureAxis.DEPTH, linear) == expected


@pytest.mark.parametrize(
    ("linear", "expected"),
    [
        (Linear(0.0, 0.0), "<<B>>.Origin.y"),
        (Linear(0.0, 22.0), "<<B>>.Origin.y + 22 mm"),
        (Linear(0.75, 9.0), "<<B>>.Origin.y + <<B>>.Depth * 0.75 + 9 mm"),
        (Linear(1.0, -141.0), "<<B>>.Origin.y + <<B>>.Depth - 141 mm"),
    ],
)
def test_position_relative_a_l_origine(linear: Linear, expected: str) -> None:
    assert expression_text("<<B>>", FurnitureAxis.DEPTH, linear, from_origin=True) == expected


@pytest.mark.parametrize("label", ["", "a>>b", "Bureau <bis>", "a\nb", "Bur\\'eau", "a\\", None])
def test_libelle_refuse(label: object) -> None:
    with pytest.raises(FurnitureError, match="Libellé d'ensemble"):
        label_reference(label)  # type: ignore[arg-type]


def test_libelle_accepte() -> None:
    assert label_reference("Bureau (bis) <") == "<<Bureau (bis) <>>"
    assert bindings(with_options(desk()), label="Mon bureau")[("P", "Length")] == (
        "<<Mon bureau>>.Width"
    )


def test_sous_ensemble_lie_par_origin_et_cotes() -> None:
    caisson = Member(
        "C",
        box=FurnitureBox(600, 520, 720),
        origin=Vec3(22, 0, 0),
        fixed=frozenset({Edge.FRONT, Edge.BACK}),
        mode=InteriorMode.PROPORTIONAL,
        label="Caisson",
    )
    found = bindings([caisson])
    assert found[("C", "Depth")] == "<<Bureau>>.Depth - 80 mm"
    assert found[("C", "Width")] == "<<Bureau>>.Width * 0.5"
    assert found[("C", "Origin.x")] == "<<Bureau>>.Origin.x + <<Bureau>>.Width * 0.018333333"
    assert found[("C", "Height")] == "<<Bureau>>.Height * 0.96"
    assert ("C", "Origin.y") not in found


# --- F9 : formules de l'utilisateur -------------------------------------------------------


def test_formule_de_l_utilisateur_jamais_remplacee() -> None:
    members = with_options(desk())
    members = [
        replace(m, driven=frozenset({"Width", "Placement.Base.y", "Thickness"}))
        if m.key == "JG"
        else m
        for m in members
    ]
    rules, _ = follow_rules(BOX, members)
    found, notices = bindings_for("Bureau", BOX, members, rules)
    assert ("JG", "Width") not in {(b.key, b.prop) for b in found}
    assert [(n.kind, n.params["member"], n.params["property"]) for n in notices] == [
        (NoticeKind.USER_FORMULA, "Joue gauche", "Placement.Base.y"),
        (NoticeKind.USER_FORMULA, "Joue gauche", "Width"),
    ]
    assert "Joue gauche" in notices[1].message


def test_placement_pilote_bloque_ses_sous_chemins() -> None:
    members = [
        replace(m, driven=frozenset({"Placement"})) if m.key == "JD" else m
        for m in with_options(desk())
    ]
    assert ("JD", "Placement.Base.x") not in bindings(members)
    assert is_driven(members[2], "Placement.Base.x")
    assert not is_driven(members[2], "PlacementBis")


def test_liaison_reecrite_traitee_comme_formule() -> None:
    recorded = {"Width": "<<Bureau>>.Depth - 40 mm", "Length": "<<Bureau>>.Height - 30 mm"}
    current = {
        "Width": "<<Bureau>>.Depth - 40 mm",
        "Length": "<<Bureau>>.Height - 31 mm",
        "Placement.Base.y": "<<Bureau>>.Depth - 141 mm",
    }
    assert driven_properties(current, recorded) == {"Length", "Placement.Base.y"}
    # Liaison effacée par l'utilisateur : non pilotée, « Relier » la remet.
    assert driven_properties({}, recorded) == frozenset()


def test_avertissement_seulement_pour_les_proprietes_liees() -> None:
    caisson = Member(
        "C",
        box=FurnitureBox(600, 520, 720),
        origin=Vec3(0, 0, 0),
        fixed=frozenset(),
        driven=frozenset({"Depth", "Origin.y", "Label", "Thickness"}),
    )
    _, notices = bindings_for("Bureau", BOX, [caisson], {})
    assert [n.params["property"] for n in notices] == ["Depth", "Origin.y"]
    assert bound_by_workshop(caisson, "Height")
    assert not bound_by_workshop(caisson, "Length")


@pytest.mark.parametrize(
    "current",
    [
        "<<Bureau>>.Depth - 40 mm",
        "<<Nouveau>>.Depth - 40 mm",  # ensemble renommé : FreeCAD réécrit la référence
        "<<Bureau d\\'angle>>.Depth - 40 mm",  # apostrophe échappée par FreeCAD
        '<<Meuble \\"TV\\">>.Depth - 40 mm',  # guillemets échappés
        "<<Bureau001>>.Depth - 40 mm",  # copie du document
    ],
)
def test_liaison_reconnue_au_libelle_pres(current: str) -> None:
    recorded = {"Width": "<<Bureau>>.Depth - 40 mm"}
    assert same_binding(current, recorded["Width"])
    assert driven_properties({"Width": current}, recorded) == frozenset()


@pytest.mark.parametrize(
    ("current", "recorded"),
    [
        ("<<Bureau>>.Depth - 41 mm", "<<Bureau>>.Depth - 40 mm"),
        ("<<Bureau>>.Width - 40 mm", "<<Bureau>>.Depth - 40 mm"),
        ("Depth - 40 mm", "<<Bureau>>.Depth - 40 mm"),
        ("<<Bureau>>.Depth - 40 mm", None),
    ],
)
def test_formule_differente_pilotee(current: str, recorded: str | None) -> None:
    assert not same_binding(current, recorded)
