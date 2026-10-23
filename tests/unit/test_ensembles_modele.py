# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets valeur des ensembles (J4a, critère F1)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core import furniture
from freecad.menuiserie.core.furniture import (
    Binding,
    BlockedRowError,
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Linear,
    Member,
    Notice,
    NoticeKind,
    Row,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_ensembles import BLOCKS

ORIGIN = Vec3(0.0, 0.0, 0.0)
CUBE = FurnitureBox(100.0, 100.0, 100.0)


# --- Énumérations enregistrées : valeurs et ordre figés ----------------------------------


def test_valeurs_stables_des_modes() -> None:
    assert [mode.value for mode in InteriorMode] == ["Stay", "Proportional"]


def test_valeurs_stables_des_bords() -> None:
    assert [edge.value for edge in Edge] == ["Left", "Right", "Front", "Back", "Bottom", "Top"]


@pytest.mark.parametrize(
    ("edge", "axis", "at_end"),
    [
        (Edge.LEFT, FurnitureAxis.WIDTH, False),
        (Edge.RIGHT, FurnitureAxis.WIDTH, True),
        (Edge.FRONT, FurnitureAxis.DEPTH, False),
        (Edge.BACK, FurnitureAxis.DEPTH, True),
        (Edge.BOTTOM, FurnitureAxis.HEIGHT, False),
        (Edge.TOP, FurnitureAxis.HEIGHT, True),
    ],
)
def test_proprietes_des_bords(edge: Edge, axis: FurnitureAxis, at_end: bool) -> None:
    assert (edge.axis, edge.at_end) == (axis, at_end)
    assert Edge.of(axis, at_end) is edge
    assert edge.opposite().axis is axis
    assert edge.opposite().at_end is not at_end


def test_axes_de_l_ensemble() -> None:
    assert [axis.index for axis in FurnitureAxis] == [0, 1, 2]
    assert FurnitureAxis.of(1) is FurnitureAxis.DEPTH


# --- FurnitureBox -------------------------------------------------------------------------


def test_boite_limites_acceptees() -> None:
    box = FurnitureBox(0.1, 20_000, 600)
    assert (box.width, box.depth, box.height) == (0.1, 20_000.0, 600.0)
    assert isinstance(box.depth, float)
    assert box.size(FurnitureAxis.HEIGHT) == 600.0


@pytest.mark.parametrize(
    ("values", "field", "shown"),
    [
        ((0.09, 600, 750), "largeur", "0,09"),
        ((1200, 20_000.5, 750), "profondeur", "20000,5"),
        ((1200, 600, math.nan), "hauteur", "nan"),
        ((1200, 600, True), "hauteur", "True"),
        ((1200, "600", 750), "profondeur", "600"),
    ],
)
def test_boite_refusee(values: tuple[object, object, object], field: str, shown: str) -> None:
    with pytest.raises(FurnitureError) as caught:
        FurnitureBox(*values)  # type: ignore[arg-type]
    assert caught.value.params["field"] == field
    assert caught.value.params["value"] == shown
    assert isinstance(caught.value, ValueError)
    assert field in str(caught.value)


# --- Member -------------------------------------------------------------------------------


def test_membre_piece_et_sous_ensemble() -> None:
    piece = Member("P", block=BLOCKS["P"])
    assert piece.name == "P"
    assert piece.mode is InteriorMode.STAY
    assert piece.fixed is None
    assert piece.driven == frozenset()
    assert piece.locked is False
    furniture = Member("C", box=CUBE, origin=ORIGIN, fixed=frozenset(), label="Caisson")
    assert furniture.name == "Caisson"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"key": ""}, "Member.key"),
        ({"label": None}, "Member.label"),
        ({"box": CUBE}, "Member.block"),
        ({"block": None}, "Member.block"),
        ({"mode": "Stay"}, "Member.mode"),
        ({"fixed": {Edge.LEFT}}, "Member.fixed"),
        ({"fixed": frozenset({"Left"})}, "Member.fixed"),
        ({"driven": frozenset({1})}, "Member.driven"),
        ({"locked": 1}, "Member.locked"),
    ],
)
def test_membre_refuse(changes: dict[str, object], field: str) -> None:
    values: dict[str, object] = {"key": "P", "block": BLOCKS["P"], **changes}
    with pytest.raises(ValueError, match=field):
        Member(**values)  # type: ignore[arg-type]


def test_sous_ensemble_sans_origine_refuse() -> None:
    with pytest.raises(ValueError, match=r"Member\.block"):
        Member("C", box=CUBE)


# --- FollowRule, Binding, Notice ----------------------------------------------------------


ROW = Row(FurnitureAxis.DEPTH, ("A",), ())


def test_regle_limites() -> None:
    rule = FollowRule(FurnitureAxis.DEPTH, "Width", Linear(1.0, -40.0), Linear(1.0, -40.0), ROW)
    assert rule.local == "Width"
    thickness = FollowRule(FurnitureAxis.WIDTH, None, Linear(0.0, 5.0), None, ROW)
    assert thickness.size is None


@pytest.mark.parametrize(
    ("local", "size"),
    [("Width", None), (None, Linear(1.0, 0.0))],
    ids=["cote étirée sans propriété", "propriété sans cote étirée"],
)
def test_regle_refusee(local: str | None, size: Linear | None) -> None:
    with pytest.raises(ValueError, match="FollowRule"):
        FollowRule(FurnitureAxis.WIDTH, local, Linear(0.0, 0.0), size, ROW)


def test_refus_de_rangee_bloquee() -> None:
    error = BlockedRowError(
        "{members} / {locked}",
        {"members": "a", "locked": "b"},
        locked=("V",),
        members=("JG", "V"),
    )
    assert isinstance(error, FurnitureError)
    assert (error.locked, error.members, str(error)) == (("V",), ("JG", "V"), "a / b")


def test_fonction_affine() -> None:
    linear = Linear.of(1.0, -44.0, {"JG": -1.0, "JD": -1.0, "V": 1e-12})
    assert linear.thickness == (("JD", -1.0), ("JG", -1.0))  # triée, terme négligeable retiré
    assert linear.keys == {"JD", "JG"}
    assert linear.at(1400.0, {"JG": 25.0, "JD": 22.0}) == 1400.0 - 44.0 - 47.0
    assert not linear.constant
    assert Linear.of(1e-12, 5.0).constant
    assert not Linear(0.0, 5.0, (("JG", 1.0),)).constant
    assert Linear(0.4, 0.0).proportional
    assert not Linear(1.0, 0.0).proportional
    assert not Linear(0.0, 3.0).proportional
    assert Linear(0.5, 1.0).scaled(2.0) == Linear(1.0, 2.0)
    assert Linear(1.0, 2.0).minus(Linear(0.0, 2.0, (("A", 1.0),))) == Linear(
        1.0, 0.0, (("A", -1.0),)
    )
    with pytest.raises(KeyError):
        linear.at(1200.0)


def test_liaison() -> None:
    binding = Binding("P", "Length", "<<Bureau>>.Width")
    assert binding.expression == "<<Bureau>>.Width"
    with pytest.raises(ValueError, match=r"Binding\.prop"):
        Binding("P", "", "<<Bureau>>.Width")
    with pytest.raises(ValueError, match=r"Binding\.expression"):
        Binding("P", "Length", None)  # type: ignore[arg-type]


def test_avertissement() -> None:
    notice = Notice(NoticeKind.NOT_SQUARE, {"member": "Voile"})
    assert notice.message == (
        "« Voile » n'est pas d'équerre avec l'ensemble : il ne suit pas ses cotes."
    )
    assert "{member}" in notice.template
    assert hash(notice) == hash(Notice(NoticeKind.NOT_SQUARE, {"member": "Voile"}))
    assert [kind.value for kind in NoticeKind] == [
        "UserFormula",
        "NotSquare",
        "ThicknessKept",
        "OutsideBox",
    ]
    with pytest.raises(ValueError, match=r"Notice\.kind"):
        Notice("NotSquare", {})  # type: ignore[arg-type]


# --- F12 : façade -------------------------------------------------------------------------


def test_facade_sans_logique() -> None:
    assert sorted(furniture.__all__) == furniture.__all__
    # Rules : alias de type ; Notice : type commun, défini dans core.notice
    for name in set(furniture.__all__) - {"Rules", "Notice"}:
        assert getattr(furniture, name).__module__.startswith("freecad.menuiserie.core.furniture._")
