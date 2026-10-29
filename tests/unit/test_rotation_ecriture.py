# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture d'une rotation libre (RO-b, B1 à B5), sans FreeCAD : le ``Placement`` est simulé par
une ``RigidTransform`` de ``core``, l'écriture note ce qu'elle reçoit."""

from __future__ import annotations

import math
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.rotation import angles_of, matrix_of
from tests.unit.aides_freecad import simulated_freecad

START = RigidTransform(matrix_of((0.0, 0.0, 0.0)), Vec3(100.0, 200.0, 300.0))
CENTER = Vec3(500.0, 50.0, 20.0)  # (L, l, e) = (1000, 100, 40)


@pytest.fixture
def rotate(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import part_rotate

        monkeypatch.setattr(part_rotate, "rigid_transform", lambda placement: placement)
        monkeypatch.setattr(part_rotate, "to_placement", lambda transform: transform)
        size = SimpleNamespace(length=1000.0, width=100.0, thickness=40.0)
        monkeypatch.setattr(part_rotate, "dimensions_of", lambda obj: size)
        monkeypatch.setattr(part_rotate, "placement_expression", lambda obj: obj.expression)
        yield part_rotate


class Writes:
    """Écritures de ``write_placement`` : (brute, placement)."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, raw: Any, placement: Any) -> None:
        self.calls.append((raw, placement))
        raw.Placement = placement


def part(expression: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(Placement=START, expression=expression)


@pytest.fixture
def writes(rotate: ModuleType, monkeypatch: pytest.MonkeyPatch) -> Writes:
    writer = Writes()
    monkeypatch.setattr(rotate, "write_placement", writer)
    monkeypatch.setattr(rotate, "raw_part", lambda obj: getattr(obj, "blank", obj))
    return writer


def center_of(transform: RigidTransform) -> Vec3:
    return transform.apply(CENTER)


def test_b1_rotate_to_ecrit_les_angles_absolus_autour_du_centre(
    rotate: ModuleType, writes: Writes
) -> None:
    obj = part()
    assert rotate.rotate_to(obj, (90.0, 30.0, -45.0)) is True
    [(_, written)] = writes.calls
    assert angles_of(written.rotation) == pytest.approx((90.0, 30.0, -45.0), abs=1e-9)
    after, before = center_of(written), center_of(START)
    assert (after.x, after.y, after.z) == pytest.approx((before.x, before.y, before.z), abs=1e-9)


def test_b1_rotate_to_est_absolu_et_idempotent(rotate: ModuleType, writes: Writes) -> None:
    obj = part()
    rotate.rotate_to(obj, (10.0, 20.0, 30.0))
    first = obj.Placement
    rotate.rotate_to(obj, (10.0, 20.0, 30.0))
    assert obj.Placement.translation == pytest.approx(first.translation)
    assert angles_of(obj.Placement.rotation) == pytest.approx((10.0, 20.0, 30.0), abs=1e-9)


def test_b1_expression_sur_le_placement_rien_n_est_ecrit(
    rotate: ModuleType, writes: Writes
) -> None:
    obj = part("Placement.Base.x")
    assert rotate.rotate_to(obj, (0.0, 0.0, 45.0)) is False
    assert writes.calls == []
    assert obj.Placement is START


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_angle_non_fini_refuse_sans_ecrire(rotate: ModuleType, writes: Writes, bad: float) -> None:
    with pytest.raises(ValueError, match="finis"):
        rotate.rotate_to(part(), (0.0, bad, 0.0))
    assert writes.calls == []


def test_b2_une_piece_usinee_ou_un_assemblage_ecrit_la_brute(
    rotate: ModuleType, writes: Writes
) -> None:
    blank = part()
    wrapper = SimpleNamespace(blank=blank, Placement=START, expression=None)
    assert rotate.rotate_to(wrapper, (0.0, 0.0, 90.0)) is True
    [(written_in, _)] = writes.calls
    assert written_in is blank


def test_b2_l_expression_de_la_brute_compte_pour_la_piece_usinee(
    rotate: ModuleType, writes: Writes
) -> None:
    wrapper = SimpleNamespace(blank=part("Placement"), expression=None)
    assert rotate.rotate_to(wrapper, (0.0, 0.0, 90.0)) is False
    assert writes.calls == []


def memento(**changes: Any) -> SimpleNamespace:
    values: dict[str, Any] = {"part": part(), "placement": START, "aside": {}}
    return SimpleNamespace(**{**values, **changes})


def test_b3_le_geste_part_toujours_du_placement_du_debut(
    rotate: ModuleType, writes: Writes
) -> None:
    start = memento()
    for angle in (10.0, 20.0, 30.0):  # trois mouvements : rien ne s'accumule
        assert rotate.rotate_by(start, 2, angle) is True
    assert angles_of(start.part.Placement.rotation) == pytest.approx((0.0, 0.0, 30.0), abs=1e-9)
    assert len(writes.calls) == 3
    after, before = center_of(start.part.Placement), center_of(START)
    assert (after.x, after.y, after.z) == pytest.approx((before.x, before.y, before.z), abs=1e-9)


def test_b3_le_geste_tourne_a_partir_de_l_orientation_courante(
    rotate: ModuleType, writes: Writes
) -> None:
    oriented = RigidTransform(matrix_of((90.0, 0.0, 0.0)), Vec3(0.0, 0.0, 0.0))
    start = memento(placement=oriented, part=SimpleNamespace(Placement=oriented, expression=None))
    rotate.rotate_by(start, 2, 90.0)  # lacet autour de Z fixe : R' = Rz(90) · R
    assert angles_of(start.part.Placement.rotation) == pytest.approx((90.0, 0.0, 90.0), abs=1e-9)


def test_b3_geste_refuse_si_une_liaison_pilotait_le_placement(
    rotate: ModuleType, writes: Writes
) -> None:
    """``begin_drag`` met les liaisons de l'atelier de côté : le mémento s'en souvient."""
    start = memento(aside={"Placement.Base.x": "Cadre.Placement.Base.x"})
    assert rotate.rotate_by(start, 0, 15.0) is False
    assert writes.calls == []
    assert rotate.rotate_by(memento(part=part("Placement")), 0, 15.0) is False
    assert writes.calls == []


def test_b3_geste_axe_ou_angle_invalide(rotate: ModuleType, writes: Writes) -> None:
    with pytest.raises(ValueError, match="axis"):
        rotate.rotate_by(memento(), 3, 15.0)
    with pytest.raises(ValueError, match="fini"):
        rotate.rotate_by(memento(), 0, math.nan)
    assert writes.calls == []


def test_b4_la_fin_de_rotation_est_celle_du_glissement(
    rotate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[Any, Any]] = []

    def end_drag(start: Any, choose: Any) -> list[str]:
        seen.append((start, choose))
        return ["message"]

    monkeypatch.setattr(rotate, "end_drag", end_drag)
    start, choose = memento(), object()
    assert rotate.end_rotation(start, choose) == ["message"]
    assert seen == [(start, choose)]


@pytest.mark.parametrize("angles", [(361.0, 0.0, 0.0), (0.0, -360.5, 0.0), (0.0, 0.0, 1e9)])
def test_rotate_to_refuse_un_angle_hors_de_360_sans_ecrire(
    rotate: ModuleType, writes: Writes, angles: tuple[float, float, float]
) -> None:
    """Spécification § 4.6 : angles bornés avant écriture."""
    with pytest.raises(ValueError, match="360"):
        rotate.rotate_to(part(), angles)
    assert writes.calls == []


@pytest.mark.parametrize("angles", [(360.0, 0.0, 0.0), (0.0, -360.0, 360.0)])
def test_rotate_to_accepte_les_bornes(
    rotate: ModuleType, writes: Writes, angles: tuple[float, float, float]
) -> None:
    assert rotate.rotate_to(part(), angles) is True


def test_rotate_to_compte_les_liaisons_mises_de_cote(rotate: ModuleType, writes: Writes) -> None:
    """Comme ``rotate_by`` : une liaison de l'atelier sur le ``Placement`` mise de côté par
    ``begin_drag`` interdit encore la rotation."""
    aside = {"Placement.Base.x": "Bureau.Placement.Base.x"}
    assert rotate.rotate_to(part(), (0.0, 0.0, 45.0), aside) is False
    assert writes.calls == []
    assert rotate.rotate_to(part(), (0.0, 0.0, 45.0), {"Length": "Bureau.Length"}) is True
