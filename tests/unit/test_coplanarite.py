# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faces coplanaires pendant un déplacement, une copie ou une répétition (ADR 0058) : règles
pures de ``core/magnet/_coplanar.py`` et aimant « au ras » d'un plan hors de portée."""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box, Vec3
from freecad.menuiserie.core.magnet import (
    MAX_COPLANAR,
    Guide,
    GuideKind,
    MagnetKind,
    PlaneIndex,
    box_faces,
    magnet,
    overlaps,
)

BOX = Box.from_ranges([(0, 100), (0, 50), (0, 20)])


def face(axis: int, position: float, ranges: Sequence[tuple[float, float]], sign: int = 1) -> Guide:
    """Plan normal à ``axis`` à ``position``, d'étendue ``ranges`` sur les autres axes."""
    full = list(ranges)
    full[axis] = (position, position)
    return Guide(GuideKind.PLANE, Box.from_ranges(full), axis, sign)


# Étendue d'un autre meuble, loin sur Y.
FAR: list[tuple[float, float]] = [(0, 100), (900, 950), (0, 20)]
NEAR: list[tuple[float, float]] = [(0, 100), (0, 50), (0, 20)]


# --- Faces d'une boîte ------------------------------------------------------------------------


def test_faces_d_une_boite_et_leur_normale() -> None:
    debut, fin = box_faces(BOX, ((2, False), (2, True)))
    assert (debut.axis, debut.sign, debut.position(2)) == (2, -1, 0)
    assert (fin.axis, fin.sign, fin.position(2)) == (2, 1, 20)
    assert fin.extent.ranges()[:2] == [(0, 100), (0, 50)]


def test_aucune_face_demandee() -> None:
    assert box_faces(BOX, ()) == ()


# --- Index des plans voisins ------------------------------------------------------------------


def test_plans_a_une_position_a_la_tolerance_pres() -> None:
    dessus = face(2, 20, FAR)
    presque = face(2, 20 + CONTACT_TOLERANCE_MM / 2, FAR)
    a_cote = face(2, 20 + 2 * CONTACT_TOLERANCE_MM, FAR)
    index = PlaneIndex([dessus, presque, a_cote])
    assert index.at(2, 20) == [dessus, presque]
    assert index.at(2, 21) == []
    assert index.at(0, 20) == []  # autre axe


def test_droites_et_sommets_ignores() -> None:
    droite = Guide(GuideKind.LINE, Box.from_ranges([(0, 100), (5, 5), (20, 20)]), 0)
    sommet = Guide(GuideKind.POINT, Box(Vec3(0, 0, 20), Vec3(0, 0, 20)))
    assert PlaneIndex([droite, sommet]).at(2, 20) == []


def test_coplanaires_face_puis_voisines_sans_doublon() -> None:
    voisine = face(2, 20, FAR)
    index = PlaneIndex([voisine, voisine, face(2, 30, FAR)])
    dessus = box_faces(BOX, ((2, True),))[0]
    assert index.coplanar([dessus, dessus]) == (dessus, voisine)


def test_coplanaires_seulement_sur_les_axes_demandes() -> None:
    index = PlaneIndex([face(2, 20, FAR)])
    dessus = box_faces(BOX, ((2, True),))[0]
    assert index.coplanar([dessus], axes=(0, 1)) == ()
    assert index.coplanar([dessus], axes=(2,)) == (dessus, face(2, 20, FAR))


def test_une_face_sans_voisine_n_est_pas_montree() -> None:
    index = PlaneIndex([face(2, 25, FAR)])
    assert index.coplanar(box_faces(BOX, ((2, False), (2, True)))) == ()


def test_coplanaires_plafonnees() -> None:
    voisines = [face(2, 20, [(i, i + 1), (900, 950), (0, 0)]) for i in range(3 * MAX_COPLANAR)]
    dessus = box_faces(BOX, ((2, True),))[0]
    found = PlaneIndex(voisines).coplanar([dessus])
    assert len(found) == MAX_COPLANAR
    assert found[0] == dessus


def test_recouvrement_sur_les_autres_axes() -> None:
    dessus = box_faces(BOX, ((2, True),))[0]
    assert overlaps(dessus, face(2, 20, NEAR))
    assert overlaps(dessus, face(2, 20, [(100, 200), (0, 50), (0, 0)]))  # bord à bord
    assert not overlaps(dessus, face(2, 20, FAR))


# --- Aimant au ras d'un plan hors de portée -----------------------------------------------------


def test_plan_hors_de_portee_ignore_sans_far() -> None:
    loin = face(0, 110, FAR, -1)
    assert magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,)).hits == ()


def test_plan_hors_de_portee_aimante_avec_far() -> None:
    """La face de fin (100) se met au ras de la face d'un autre meuble (110), même sens."""
    loin = face(0, 110, FAR, 1)
    result = magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,), far=True)
    assert result.delta == Vec3(10, 0, 0)
    (hit,) = result.hits
    assert (hit.at_end, hit.kind, hit.position) == (True, MagnetKind.FLUSH, 110)


def test_un_guide_a_portee_garde_la_priorite() -> None:
    loin = face(0, 102, FAR, 1)  # plus proche, mais hors de portée
    pres = face(0, 108, NEAR, -1)
    result = magnet(BOX, [loin, pres], Vec3(0, 0, 0), 15, (0,), far=True)
    assert result.delta == Vec3(8, 0, 0)
    assert result.hits[0].guide == 1


def test_droite_ou_sommet_hors_de_portee_n_aimante_pas() -> None:
    droite = Guide(GuideKind.LINE, Box.from_ranges([(103, 103), (900, 900), (0, 20)]), 2)
    sommet = Guide(GuideKind.POINT, Box(Vec3(103, 900, 0), Vec3(103, 900, 0)))
    assert magnet(BOX, [droite, sommet], Vec3(0, 0, 0), 15, (0,), far=True).hits == ()


def test_plan_hors_de_portee_au_dela_de_la_tolerance() -> None:
    loin = face(0, 130, FAR, 1)
    assert magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,), far=True).hits == ()
