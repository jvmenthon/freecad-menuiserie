# SPDX-License-Identifier: LGPL-2.1-or-later
"""Onglet (J4g, critères A1 à A3) : coupe par le coin extérieur et le coin intérieur, angles,
volumes enlevés et refus."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from freecad.menuiserie.core.geometry import (
    CUT_OVERRUN_MM,
    PlacedBlock,
    Prism,
    RigidTransform,
    Solid,
    Vec3,
    moved,
    relative_transform,
)
from freecad.menuiserie.core.joints import JointKind, JointPlan, guess_roles, strategy_for
from freecad.menuiserie.core.joints.miter import MiterParams, MiterValues
from tests.unit.aides_assemblages import (
    block,
    matrix,
    miter_corner,
    placed,
    rotation_y,
    rotation_z,
)

MITER = strategy_for(JointKind.MITER)
Pair = tuple[PlacedBlock, PlacedBlock]
Point2 = tuple[float, float]
OVERLAP = "dessinez les deux pièces à leur longueur hors tout"
CORNER = "doivent s'arrêter au même coin"
FLUSH = "à fleur"


def values(pair: Pair) -> MiterValues:
    result: MiterValues = MITER.resolve(*pair, MiterParams())
    return result


def refused(pair: Pair, text: str) -> None:
    with pytest.raises(ValueError, match=text):
        MITER.plan(*pair, MiterParams())


def carcass_corner() -> Pair:
    """Coin de caisson (A2) : côté 720 x 400 x 18 debout (épaisseur selon X), dessus
    600 x 400 x 18 à plat posé sur toute l'épaisseur du côté ; chevauchement 18 x 400 x 18."""
    side = placed((720.0, 400.0, 18.0), rotation_y(-90.0), (18.0, 0.0, 0.0))
    return side, block((600.0, 400.0, 18.0), (0.0, 0.0, 702.0))


# --- Volume d'un prisme dans une pièce (polygone découpé par un rectangle) -----------------


def _clip(polygon: list[Point2], axis: int, bound: float, keep_above: bool) -> list[Point2]:
    """Sutherland-Hodgman : partie du polygone du bon côté de ``coordonnée[axis] = bound``."""

    def inside(point: Point2) -> bool:
        return point[axis] >= bound if keep_above else point[axis] <= bound

    result: list[Point2] = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if inside(end) != inside(start):
            ratio = (bound - start[axis]) / (end[axis] - start[axis])
            result.append(
                (start[0] + ratio * (end[0] - start[0]), start[1] + ratio * (end[1] - start[1]))
            )
        if inside(end):
            result.append(end)
    return result


def _area(polygon: list[Point2]) -> float:
    pairs = zip(polygon, polygon[1:] + polygon[:1], strict=True)
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in pairs)) / 2


def as_prism(solid: Solid) -> Prism:
    assert isinstance(solid, Prism)
    return solid


def removed(solid: Solid, part: PlacedBlock) -> float:
    """Volume du prisme (extrudé selon un axe du repère local) dans la boîte de la pièce."""
    prism = as_prism(solid)
    box = part.local_box()
    edge = next(i for i in range(3) if prism.extrusion.component(i))
    u, v = (i for i in range(3) if i != edge)
    polygon = [(p.component(u), p.component(v)) for p in prism.points]
    for index, axis in enumerate((u, v)):
        polygon = _clip(polygon, index, box.lo(axis), keep_above=True)
        polygon = _clip(polygon, index, box.hi(axis), keep_above=False)
    start = prism.points[0].component(edge)
    span = sorted((start, start + prism.extrusion.component(edge)))
    length = min(span[1], box.hi(edge)) - max(span[0], box.lo(edge))
    return _area(polygon) * max(length, 0.0)


def lost(pair: Pair) -> tuple[float, float]:
    """Volumes enlevés à l'hôte et à l'invitée."""
    result = values(pair)
    return removed(result.host_cut, pair[0]), removed(result.guest_cut, pair[1])


# --- A1 : paramètres, coupe ---------------------------------------------------------------


def test_parametres_sans_champ() -> None:
    params = MiterParams()
    assert fields(params) == ()
    assert params == MiterParams()
    with pytest.raises(FrozenInstanceError):
        params.reinforcement = 1  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        MiterParams(reinforcement=1)  # type: ignore[call-arg]


def test_cadre_a_45_degres() -> None:
    """A2 : deux traverses 500 x 60 x 20 qui se chevauchent de 60 x 60 au coin."""
    pair = miter_corner()
    result = values(pair)
    assert (result.host_angle, result.guest_angle) == (45.0, 45.0)
    assert lost(pair) == pytest.approx((36_000, 36_000))
    plan = MITER.plan(*pair, MiterParams())
    assert plan == JointPlan(host_cuts=(result.host_cut,), guest_cuts=(result.guest_cut,))


def test_coupe_par_le_coin_exterieur_et_le_coin_interieur() -> None:
    """Hypoténuse de (0, 0) à (60, 60), prolongée au-delà ; l'hôte (selon X) perd le triangle
    du côté de l'invitée (coin (0, 60)), l'invitée celui du côté de l'hôte (coin (60, 0))."""
    host, guest = miter_corner()
    result = values((host, guest))
    margin = CUT_OVERRUN_MM / 60
    low, high = -60 * margin, 60 * (1 + margin)
    expected_host = (Vec3(low, low, -0.1), Vec3(high, high, -0.1), Vec3(low, high, -0.1))
    host_cut = as_prism(result.host_cut)
    assert _close(host_cut.points, expected_host)
    assert _close((host_cut.extrusion,), (Vec3(0.0, 0.0, 20.2),))
    guest_cut = as_prism(moved(result.guest_cut, relative_transform(host, guest)))
    assert _close(guest_cut.points[:2], expected_host[:2])  # même plan de coupe
    assert _close(guest_cut.points[2:], (Vec3(high, low, -0.1),))


def test_largeurs_differentes() -> None:
    """A2 : hôte large de 60, invitée de 40 → 33,69° et 56,31° ; chacune perd la moitié de C."""
    pair = miter_corner(host_width=60.0, guest_width=40.0)
    result = values(pair)
    assert (result.host_angle, result.guest_angle) == (33.69, 56.31)
    assert lost(pair) == pytest.approx((24_000, 24_000))
    swapped = values((pair[1], pair[0]))
    assert (swapped.host_angle, swapped.guest_angle) == (56.31, 33.69)


def test_coin_de_caisson() -> None:
    """A2 : axe commun = profondeur ; chacun perd 18 x 18 / 2 x 400 = 64 800 mm³."""
    pair = carcass_corner()
    result = values(pair)
    assert (result.host_angle, result.guest_angle) == (45.0, 45.0)
    assert lost(pair) == pytest.approx((64_800, 64_800))
    assert lost((pair[1], pair[0])) == pytest.approx((64_800, 64_800))
    assert as_prism(result.host_cut).extrusion.component(1) == pytest.approx(400.2)


@pytest.mark.parametrize("corner", [0, 90, 180, 270])
def test_les_quatre_coins_d_un_cadre(corner: int) -> None:
    """Le même angle tourné autour du cadre, dans un repère quelconque : mêmes pertes."""
    frame = RigidTransform.from_matrix(matrix(rotation_z(30.0), (100.0, -40.0, 7.0)))
    turn = RigidTransform.from_matrix(matrix(rotation_z(corner), (0.0, 0.0, 0.0)))
    host, guest = (
        PlacedBlock(part.dimensions, frame.compose(turn).compose(part.placement))
        for part in miter_corner(guest_width=40.0)
    )
    assert lost((host, guest)) == pytest.approx((24_000, 24_000))
    assert values((host, guest)).host_angle == 33.69


def test_roles_ordre_de_selection() -> None:
    """Épaisseurs égales : la première pièce sélectionnée est l'hôte."""
    host, guest = miter_corner()
    assert guess_roles(host, guest) == (0, 1)
    assert guess_roles(guest, host) == (0, 1)


# --- A3 : refus ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "guest",
    [
        block((500.0, 60.0, 20.0), (60.0, 60.0, 0.0), 90.0),  # bout contre le chant
        block((500.0, 60.0, 20.0), (60.0, 70.0, 0.0), 90.0),  # écartée
        block((500.0, 60.0, 20.0), (60.0, 0.0, 20.0), 90.0),  # posée dessus
    ],
    ids=["contact", "écart", "dessus"],
)
def test_refus_sans_chevauchement(guest: PlacedBlock) -> None:
    refused((block((500.0, 60.0, 20.0)), guest), OVERLAP)


@pytest.mark.parametrize(
    "guest",
    [
        block((500.0, 60.0, 20.0), (300.0, 0.0, 0.0), 90.0),  # T : bout au milieu de l'hôte
        block((500.0, 60.0, 20.0), (300.0, -200.0, 0.0), 90.0),  # croix
        block((500.0, 60.0, 20.0), (60.0, -100.0, 0.0), 90.0),  # l'invitée dépasse le coin
        block((500.0, 60.0, 20.0), (400.0, 0.0, 0.0)),  # bout à bout, alignées
        block((60.0, 60.0, 20.0)),  # dans l'hôte, sans se prolonger
    ],
    ids=["T", "croix", "dépasse", "alignées", "incluse"],
)
def test_refus_pas_au_meme_coin(guest: PlacedBlock) -> None:
    refused((block((500.0, 60.0, 20.0)), guest), CORNER)


@pytest.mark.parametrize(
    "guest",
    [
        block((500.0, 60.0, 22.0), (60.0, 0.0, 0.0), 90.0),  # plus épaisse
        block((500.0, 60.0, 20.0), (60.0, 0.0, 5.0), 90.0),  # décalée
        block((500.0, 60.0, 24.0), (60.0, 0.0, -2.0), 90.0),  # plus épaisse et centrée
    ],
    ids=["épaisseurs", "décalée", "centrée"],
)
def test_refus_pas_a_fleur(guest: PlacedBlock) -> None:
    refused((block((500.0, 60.0, 20.0)), guest), FLUSH)


def test_refus_pas_d_equerre() -> None:
    refused(
        (block((500.0, 60.0, 20.0)), block((500.0, 60.0, 20.0), (60.0, 0.0, 0.0), 60.0)),
        "d'équerre",
    )


def test_tolerance_de_contact() -> None:
    """Invitée plus épaisse de 0,005 mm : à fleur à la tolérance près, coupe acceptée."""
    host = block((500.0, 60.0, 20.0))
    guest = block((500.0, 60.0, 20.005), (60.0, 0.0, 0.0), 90.0)
    assert values((host, guest)).host_angle == 45.0


def _close(points: tuple[Vec3, ...], expected: tuple[Vec3, ...]) -> bool:
    return len(points) == len(expected) and all(
        abs(a.component(i) - b.component(i)) <= 1e-9
        for a, b in zip(points, expected, strict=True)
        for i in range(3)
    )


def test_boite_commune_coupee_en_deux() -> None:
    """Les deux enlèvements, ramenés dans le repère de l'hôte, se partagent la boîte commune."""
    host, guest = miter_corner(guest_width=40.0)
    result = values((host, guest))
    common = PlacedBlock(block((40.0, 60.0, 20.0)).dimensions, host.placement)
    guest_cut = moved(result.guest_cut, relative_transform(host, guest))
    halves = removed(result.host_cut, common) + removed(guest_cut, common)
    assert halves == pytest.approx(40 * 60 * 20)


def test_invitee_retournee() -> None:
    """Invitée retournée (épaisseur vers le bas), mêmes faces : même coupe, mêmes pertes."""
    flipped = [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]
    host = block((500.0, 60.0, 20.0))
    guest = placed((500.0, 60.0, 20.0), flipped, (0.0, 0.0, 20.0))
    result = values((host, guest))
    assert (result.host_angle, result.guest_angle) == (45.0, 45.0)
    assert lost((host, guest)) == pytest.approx((36_000, 36_000))
