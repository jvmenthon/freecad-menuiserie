# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets valeur des ensembles (J4a, critère F1)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core import furniture
from freecad.menuiserie.core.furniture import (
    Anchor,
    Binding,
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    Notice,
    NoticeKind,
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
    ("edge", "axis", "at_end", "anchor"),
    [
        (Edge.LEFT, FurnitureAxis.WIDTH, False, Anchor.START),
        (Edge.RIGHT, FurnitureAxis.WIDTH, True, Anchor.END),
        (Edge.FRONT, FurnitureAxis.DEPTH, False, Anchor.START),
        (Edge.BACK, FurnitureAxis.DEPTH, True, Anchor.END),
        (Edge.BOTTOM, FurnitureAxis.HEIGHT, False, Anchor.START),
        (Edge.TOP, FurnitureAxis.HEIGHT, True, Anchor.END),
    ],
)
def test_proprietes_des_bords(
    edge: Edge, axis: FurnitureAxis, at_end: bool, anchor: Anchor
) -> None:
    assert (edge.axis, edge.at_end, edge.anchor) == (axis, at_end, anchor)
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


def test_regle_limites() -> None:
    rule = FollowRule(FurnitureAxis.DEPTH, Anchor.START, Anchor.END, "Width")
    assert rule.local == "Width"
    thickness = FollowRule(FurnitureAxis.WIDTH, Anchor.RATIO, Anchor.RATIO, None)
    assert thickness.local is None


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (("Width", Anchor.START, Anchor.END, "Width"), "FollowRule.axis"),
        ((FurnitureAxis.WIDTH, "Start", Anchor.END, "Width"), "FollowRule.start"),
        ((FurnitureAxis.WIDTH, Anchor.START, Anchor.END, "Thickness"), "FollowRule.local"),
        ((FurnitureAxis.WIDTH, Anchor.START, Anchor.END, ""), "FollowRule.local"),
        ((FurnitureAxis.WIDTH, Anchor.START, Anchor.END, None), "une seule ancre"),
    ],
)
def test_regle_refusee(args: tuple[object, ...], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        FollowRule(*args)  # type: ignore[arg-type]


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
