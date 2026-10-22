# SPDX-License-Identifier: LGPL-2.1-or-later
"""Queue d'aronde traversante (J4f, critères D1 à D4) : prisme, paramètres, plan et refus."""

from __future__ import annotations

import math
import typing

import pytest

from freecad.menuiserie.core.geometry import (
    CUT_OVERRUN_MM,
    Box,
    Cylinder,
    JointError,
    PlacedBlock,
    Prism,
    RigidTransform,
    Solid,
    Vec3,
    moved,
)
from freecad.menuiserie.core.joints import JointKind, guess_roles, strategy_for
from freecad.menuiserie.core.joints.dovetail import DovetailParams, DovetailValues
from tests.unit.aides_assemblages import (
    block,
    dovetail_corner,
    matrix,
    placed,
    rotation_y,
    rotation_z,
)

DOVETAIL = strategy_for(JointKind.DOVETAIL)
NOT_FLUSH = "doit arriver à fleur de la face extérieure"
Pair = tuple[PlacedBlock, PlacedBlock]
SQUARE = (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(1.0, 1.0, 0.0), Vec3(0.0, 1.0, 0.0))
UP = Vec3(0.0, 0.0, 1.0)
DEFAULT_ANGLE = 10.0  # degrés, angle automatique
FLANK = math.tan(math.radians(DEFAULT_ANGLE))  # retrait par mm de profondeur
# Trois queues de 42 mm côté pointe sur 18 mm de profondeur et d'épaisseur.
TAILS_VOLUME = 3 * (42.0 - 18.0 * FLANK) * 18.0 * 18.0


def values(pair: Pair, params: DovetailParams | None = None) -> DovetailValues:
    result: DovetailValues = DOVETAIL.resolve(*pair, params or DovetailParams())
    return result


def refused(pair: Pair, text: str, **params: object) -> JointError:
    with pytest.raises(JointError, match=text) as error:
        DOVETAIL.plan(*pair, DovetailParams(**params))  # type: ignore[arg-type]
    return error.value


def prisms(solids: tuple[Solid, ...]) -> list[Prism]:
    assert all(isinstance(solid, Prism) for solid in solids)
    return typing.cast(list[Prism], list(solids))


def bounds(prism: Prism) -> list[tuple[float, float]]:
    """Étendue du prisme (sommets et sommets extrudés) sur X, Y et Z."""
    ends = [*prism.points]
    ends += [
        Vec3(p.x + prism.extrusion.x, p.y + prism.extrusion.y, p.z + prism.extrusion.z)
        for p in prism.points
    ]
    return [
        (min(p.component(i) for p in ends), max(p.component(i) for p in ends)) for i in range(3)
    ]


def volume(prism: Prism) -> float:
    """Volume du prisme : aire du polygone (formule de Newell) x extrusion selon sa normale."""
    total = [0.0, 0.0, 0.0]
    points = prism.points
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        total[0] += (a.y - b.y) * (a.z + b.z)
        total[1] += (a.z - b.z) * (a.x + b.x)
        total[2] += (a.x - b.x) * (a.y + b.y)
    extrusion = prism.extrusion
    return abs(total[0] * extrusion.x + total[1] * extrusion.y + total[2] * extrusion.z) / 2


# --- D1 : le solide Prism -------------------------------------------------------------------


def test_prisme_valide_et_type_solide() -> None:
    prism = Prism(SQUARE, Vec3(0.0, 0.0, 2.0))
    assert volume(prism) == pytest.approx(2.0)
    assert Prism(SQUARE[:3], Vec3(1.0, 1.0, -3.0)).points == SQUARE[:3]  # extrusion oblique
    assert set(typing.get_args(Solid)) == {Box, Cylinder, Prism}


def test_prisme_transporte() -> None:
    """Rotation quelconque (pas d'équerre) : sommets et vecteur transformés."""
    transform = RigidTransform.from_matrix(matrix(rotation_z(30), (10.0, 0.0, 5.0)))
    prism = Prism(SQUARE, Vec3(0.0, 0.0, 2.0))
    turned = moved(prism, transform)
    assert isinstance(turned, Prism)
    assert turned.points == tuple(transform.apply(p) for p in SQUARE)
    assert turned.extrusion == transform.rotate(prism.extrusion)
    assert volume(turned) == pytest.approx(2.0)
    back = moved(turned, transform.inverse())
    assert isinstance(back, Prism)
    assert all(
        math.isclose(a.component(i), b.component(i), abs_tol=1e-9)
        for a, b in zip(back.points, SQUARE, strict=True)
        for i in range(3)
    )


@pytest.mark.parametrize(
    ("points", "extrusion"),
    [
        (SQUARE[:2], UP),
        ((SQUARE[0], SQUARE[1], SQUARE[1], SQUARE[2]), UP),
        ((SQUARE[0], SQUARE[1], Vec3(2.0, 0.0, 0.0)), UP),
        ((*SQUARE[:3], Vec3(0.0, 1.0, 0.5)), UP),
        (SQUARE, Vec3(0.0, 0.0, 0.0)),
        (SQUARE, Vec3(1.0, 1.0, 0.0)),
        ((SQUARE[0], SQUARE[2], SQUARE[1], SQUARE[3]), UP),
        ((SQUARE[0], Vec3(2.0, 0.0, 0.0), SQUARE[1], Vec3(1.0, 1.0, 0.0)), UP),
        ((SQUARE[0], SQUARE[1], Vec3(math.nan, 1.0, 0.0)), UP),
        (SQUARE, Vec3(0.0, 0.0, math.inf)),
    ],
    ids=[
        "2 sommets",
        "sommets confondus",
        "alignés",
        "non coplanaires",
        "extrusion nulle",
        "extrusion dans le plan",
        "polygone croisé",
        "côtés qui se replient",
        "NaN",
        "extrusion infinie",
    ],
)
def test_prisme_refuse(points: tuple[Vec3, ...], extrusion: Vec3) -> None:
    with pytest.raises(ValueError, match=r"prisme|coordonnées"):
        Prism(points, extrusion)


# --- D2 : paramètres et valeurs automatiques ------------------------------------------------


def test_parametres_par_defaut_et_normalises() -> None:
    params = DovetailParams()
    assert (params.tail_count, params.pin_width, params.angle) == (0, 0.0, 0.0)
    assert isinstance(DovetailParams(angle=8).angle, float)
    assert isinstance(DovetailParams(pin_width=5).pin_width, float)


@pytest.mark.parametrize("angle", [30.01, 45.0, -6.0, math.inf, math.nan, True, "10"])
def test_angle_refuse(angle: object) -> None:
    with pytest.raises(JointError, match="angle") as error:
        DovetailParams(angle=angle)  # type: ignore[arg-type]
    assert "en degrés" in str(error.value)
    assert "d'au plus 30" in str(error.value)


@pytest.mark.parametrize("angle", [0, 0.5, 7.5, 30])
def test_angle_accepte(angle: float) -> None:
    assert DovetailParams(angle=angle).angle == angle


@pytest.mark.parametrize(
    ("field", "value"), [("tail_count", 51), ("tail_count", 2.0), ("pin_width", -1.0)]
)
def test_autres_parametres_refuses(field: str, value: object) -> None:
    with pytest.raises(JointError, match=field):
        DovetailParams(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("size", "count", "pin"),
    [
        ((400.0, 150.0, 18.0), 3, 6.0),
        ((400.0, 200.0, 18.0), 4, 6.0),  # D7 : tiroir de 200 mm de haut
        ((400.0, 100.0, 22.0), 2, 7.0),  # 100 / 66 + 0,5 = 2,02 ; 22 / 3 = 7,33
        ((400.0, 40.0, 18.0), 1, 6.0),  # au moins une queue
    ],
)
def test_valeurs_automatiques(size: tuple[float, float, float], count: int, pin: float) -> None:
    result = values(dovetail_corner(size))
    assert (result.tail_count, result.pin_width, result.angle) == (count, pin, DEFAULT_ANGLE)


def test_valeurs_saisies_gardees() -> None:
    result = values(dovetail_corner(), DovetailParams(tail_count=2, pin_width=10, angle=8))
    assert (result.tail_count, result.pin_width, result.angle) == (2, 10.0, 8.0)
    assert result.tail_width == pytest.approx(60.0)  # (150 - 3 x 10) / 2
    assert result.tail_base == pytest.approx(60.0 - 2 * 18 * math.tan(math.radians(8)))


# --- D3 : queues et logements ---------------------------------------------------------------


def test_planches_de_reference() -> None:
    result = values(dovetail_corner())
    assert result.tail_base == pytest.approx(42.0 - 36.0 * FLANK)
    assert result == DovetailValues(
        tail_count=3,
        pin_width=6.0,
        angle=DEFAULT_ANGLE,
        tail_width=42.0,
        tail_base=result.tail_base,
        tails=((6.0, 48.0), (54.0, 96.0), (102.0, 144.0)),
    )


def test_queues_ajoutees_a_l_invitee() -> None:
    plan = DOVETAIL.plan(*dovetail_corner(), DovetailParams())
    tails = prisms(plan.guest_additions)
    assert plan.guest_cuts == plan.host_additions == plan.inserts == ()
    # Repère de l'invitée : bout en x = 0, vers l'hôte selon -X ; largeur selon Y.
    expected = (
        Vec3(0.0, 6.0 + 18.0 * FLANK, 0.0),
        Vec3(0.0, 48.0 - 18.0 * FLANK, 0.0),
        Vec3(-18.0, 48.0, 0.0),
        Vec3(-18.0, 6.0, 0.0),
    )
    assert [(p.x, p.y, p.z) for p in tails[0].points] == pytest.approx(
        [(p.x, p.y, p.z) for p in expected]
    )
    assert tails[0].extrusion == Vec3(0.0, 0.0, 18.0)
    assert [bounds(tail)[1] for tail in tails] == [(6.0, 48.0), (54.0, 96.0), (102.0, 144.0)]
    assert sum(volume(tail) for tail in tails) == pytest.approx(TAILS_VOLUME)


def test_logements_traversants_prolonges_hors_de_la_matiere() -> None:
    plan = DOVETAIL.plan(*dovetail_corner(), DovetailParams())
    sockets = prisms(plan.host_cuts)
    overrun = CUT_OVERRUN_MM
    first = bounds(sockets[0])
    # Repère de l'hôte : bout en x = 0 (face extérieure de l'invitée), faces z = 0 et z = 18.
    assert first[0] == pytest.approx((-overrun, 18.0))
    assert first[2] == pytest.approx((-overrun, 18.0 + overrun))
    # Flancs prolongés : côté pointe (z = 0) plus large de overrun x tan(angle) de chaque côté.
    assert first[1] == pytest.approx((6.0 - overrun * FLANK, 48.0 + overrun * FLANK))
    # Largeur moyenne des queues (42 mm - 18 tan) gardée : prolongé en profondeur et épaisseur.
    expected = 3 * (18.0 + 2 * overrun) * (42.0 - 18.0 * FLANK) * (18.0 + overrun)
    assert sum(volume(socket) for socket in sockets) == pytest.approx(expected)


def test_face_exterieure_de_l_autre_cote() -> None:
    """Invitée sous l'hôte, à son autre bout : sa face Z = e est à fleur du bout x = 400."""
    host = block((400.0, 150.0, 18.0))
    guest = placed((400.0, 150.0, 18.0), rotation_y(90.0), (382.0, 0.0, 0.0))
    assert values((host, guest)).tails == ((6.0, 48.0), (54.0, 96.0), (102.0, 144.0))
    plan = DOVETAIL.plan(host, guest, DovetailParams())
    assert bounds(prisms(plan.host_cuts)[0])[0] == pytest.approx((382.0, 400.0 + CUT_OVERRUN_MM))
    assert bounds(prisms(plan.guest_additions)[0])[2] == pytest.approx((0.0, 18.0))


def test_tiroir_sur_chant() -> None:
    """Côté et façade debout (largeur selon Z du document), façade hors tout."""
    on_edge = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]  # +90° autour de X
    front = placed((400.0, 150.0, 18.0), on_edge, (0.0, 18.0, 0.0))
    side_rotation = [
        [sum(rotation_z(90)[i][k] * on_edge[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]
    side = placed((300.0, 150.0, 18.0), side_rotation, (0.0, 18.0, 0.0))
    assert values((front, side)).tail_count == 3
    plan = DOVETAIL.plan(front, side, DovetailParams())
    assert sum(volume(tail) for tail in prisms(plan.guest_additions)) == pytest.approx(TAILS_VOLUME)


def test_roles_devines() -> None:
    host, guest = dovetail_corner()
    assert guess_roles(host, guest) == (0, 1)
    assert guess_roles(guest, host) == (1, 0)


# --- D4 : refus -------------------------------------------------------------------------------


def test_refus_contact_par_la_face() -> None:
    host = block((400.0, 150.0, 18.0))
    refused((host, block((400.0, 150.0, 18.0), (0.0, 0.0, 18.0))), "par une face")


def test_refus_contact_par_le_chant() -> None:
    host = block((400.0, 150.0, 18.0))
    refused((host, block((400.0, 150.0, 18.0), (0.0, 150.0, 0.0))), "pas sur son chant")


@pytest.mark.parametrize("x", [23.0, 13.0], ids=["hôte qui dépasse", "hôte trop court"])
def test_refus_hote_pas_a_fleur(x: float) -> None:
    guest = placed((400.0, 150.0, 18.0), rotation_y(-90.0), (x, 0.0, 18.0))
    refused((block((400.0, 150.0, 18.0)), guest), NOT_FLUSH)


def test_refus_hote_aussi_large_que_l_epaisseur() -> None:
    """Hôte qui couvre juste l'épaisseur de l'invitée : ses griffes seraient détachées."""
    host = block((18.0, 150.0, 18.0))
    guest = placed((400.0, 150.0, 18.0), rotation_y(-90.0), (18.0, 0.0, 18.0))
    refused((host, guest), NOT_FLUSH)


def test_a_fleur_a_la_tolerance_pres() -> None:
    guest = placed((400.0, 150.0, 18.0), rotation_y(-90.0), (18.005, 0.0, 18.0))
    assert values((block((400.0, 150.0, 18.0)), guest)).tail_count == 3


@pytest.mark.parametrize(
    ("params", "count", "pin"),
    [({"tail_count": 20}, "20", "6"), ({"pin_width": 50}, "3", "50")],
    ids=["b < 1 mm", "t <= 0"],
)
def test_refus_queues_trop_etroites(params: dict[str, object], count: str, pin: str) -> None:
    error = refused(dovetail_corner(), "Queues trop étroites", **params)
    assert error.params == {"count": count, "width": "150", "pin": pin, "angle": "10"}


def test_queue_de_un_mm_a_l_epaulement_acceptee() -> None:
    """b = t - 2 L tan(angle) = 1 mm tout juste : accepté (angle de la pente 1:3)."""
    angle = math.degrees(math.atan(1 / 3))
    params = DovetailParams(tail_count=1, pin_width=68.5, angle=angle)
    result = values(dovetail_corner(), params)
    assert (result.tail_width, result.tail_base) == pytest.approx((13.0, 1.0))
    refused(dovetail_corner(), "Queues trop étroites", tail_count=1, pin_width=69, angle=angle)


def test_refus_pieces_pas_d_equerre() -> None:
    guest = placed((400.0, 150.0, 18.0), rotation_y(-60.0), (18.0, 0.0, 18.0))
    refused((block((400.0, 150.0, 18.0)), guest), "d'équerre")
