# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coplanarité pendant les déplacements, les copies et le redimensionnement (ADR 0058) : cas
limites de l'aimant « au ras » (``far``), faces allumées par ``Dragging.lit`` / ``moved_lit``
(FreeCAD et PySide remplacés par des doublures le temps de l'import) et dessin des guides."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator, Sequence
from typing import Any
from unittest.mock import MagicMock

import pytest

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box, Vec3
from freecad.menuiserie.core.magnet import (
    MAX_COPLANAR,
    DragResult,
    Guide,
    GuideKind,
    MagnetHit,
    MagnetKind,
    PlaneIndex,
    magnet,
)

BOX = Box.from_ranges([(0, 100), (0, 50), (0, 20)])
FAR: list[tuple[float, float]] = [(0, 100), (900, 950), (0, 20)]
NEAR: list[tuple[float, float]] = [(0, 100), (0, 50), (0, 20)]
_STUBS = ("FreeCAD", "FreeCAD.Base", "FreeCADGui", "PySide", "Part", "pivy", "pivy.coin")


def face(axis: int, position: float, ranges: Sequence[tuple[float, float]], sign: int = 1) -> Guide:
    full = list(ranges)
    full[axis] = (position, position)
    return Guide(GuideKind.PLANE, Box.from_ranges(full), axis, sign)


# --- Aimant au ras : cas limites ------------------------------------------------------------


def test_far_face_de_debut_et_plan_en_dessous() -> None:
    """La face de début (0) se met au ras d'un plan à -12, hors de portée sur Y."""
    loin = face(0, -12, FAR, -1)
    result = magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,), far=True)
    assert result.delta == Vec3(-12, 0, 0)
    (hit,) = result.hits
    assert (hit.at_end, hit.kind) == (False, MagnetKind.FLUSH)


def test_far_sens_oppose_donne_un_contact() -> None:
    loin = face(0, 110, FAR, -1)  # sa normale regarde la pièce : la face de fin la touche
    (hit,) = magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,), far=True).hits
    assert hit.kind is MagnetKind.CONTACT


def test_far_ne_touche_que_les_axes_demandes() -> None:
    loin = face(1, 55, FAR)
    assert magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,), far=True).hits == ()
    assert magnet(BOX, [loin], Vec3(0, 0, 0), 15, (1,), far=True).delta == Vec3(0, 5, 0)


def test_far_apres_un_deplacement_demande() -> None:
    """Le delta demandé (80) place la face de fin à 180 ; le plan à 190 la colle : delta 90."""
    loin = face(0, 190, FAR)
    assert magnet(BOX, [loin], Vec3(80, 0, 0), 15, (0,), far=True).delta == Vec3(90, 0, 0)


def test_far_plus_proche_des_deux_plans_hors_de_portee() -> None:
    a, b = face(0, 112, FAR), face(0, 106, FAR)
    result = magnet(BOX, [a, b], Vec3(0, 0, 0), 15, (0,), far=True)
    assert result.delta == Vec3(6, 0, 0)
    assert result.hits[0].guide == 1


def test_far_sans_guide_ne_change_rien() -> None:
    result = magnet(BOX, [], Vec3(7, 0, 0), 15, (0,), far=True)
    assert result == DragResult(Vec3(7, 0, 0))


def test_far_defaut_inchange() -> None:
    """Régression : sans ``far``, un plan à portée aimante comme avant, un plan éloigné non."""
    pres, loin = face(0, 108, NEAR, -1), face(0, 103, FAR, -1)
    assert magnet(BOX, [pres, loin], Vec3(0, 0, 0), 15, (0,)).delta == Vec3(8, 0, 0)
    assert magnet(BOX, [loin], Vec3(0, 0, 0), 15, (0,)).hits == ()


def test_far_a_portee_au_dela_de_la_tolerance_cede_au_plan_lointain() -> None:
    """Le guide à portée est trop loin (30 > 15) : il n'est pas candidat, le plan lointain gagne."""
    pres, loin = face(0, 130, NEAR, -1), face(0, 108, FAR, 1)
    result = magnet(BOX, [pres, loin], Vec3(0, 0, 0), 15, (0,), far=True)
    assert result.delta == Vec3(8, 0, 0)
    assert result.hits[0].guide == 1


# --- Index : tolérance et plafond ----------------------------------------------------------


def test_tolerance_exacte_incluse() -> None:
    index = PlaneIndex([face(2, 20 + CONTACT_TOLERANCE_MM, FAR)])
    assert len(index.at(2, 20)) == 1
    assert index.at(2, 20 - 2 * CONTACT_TOLERANCE_MM) == []


def test_positions_negatives_et_tres_grandes() -> None:
    index = PlaneIndex([face(0, -1e7, FAR), face(0, 1e9, FAR)])
    assert len(index.at(0, -1e7)) == 1
    assert len(index.at(0, 1e9)) == 1
    assert index.at(0, 0) == []


def test_plafond_atteint_exactement_par_les_premieres_faces() -> None:
    """Chaque face a une seule voisine : 2 plans par face, plafond coupé sans erreur."""
    faces = [face(2, 10.0 * i, FAR) for i in range(2 * MAX_COPLANAR)]
    voisines = [face(2, 10.0 * i, [(0, 1), (0, 1), (0, 1)], -1) for i in range(2 * MAX_COPLANAR)]
    found = PlaneIndex(voisines).coplanar(faces)
    assert len(found) == MAX_COPLANAR
    assert found[0] == faces[0]


# --- Faces allumées (Dragging.lit, moved_lit) -------------------------------------------------


@pytest.fixture(scope="module")
def states() -> Iterator[Any]:
    """Module ``gui.drag.states`` importé avec FreeCAD et PySide remplacés par des doublures ;
    les modules importés sont retirés ensuite pour ne pas fausser les autres tests."""
    before = set(sys.modules)
    saved = {name: sys.modules.get(name) for name in _STUBS}
    for name in _STUBS:
        sys.modules[name] = MagicMock()
    try:
        yield importlib.import_module("freecad.menuiserie.gui.drag.states")
    finally:
        for name in set(sys.modules) - before:
            if name.startswith("freecad.menuiserie"):
                del sys.modules[name]
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def gesture(states: Any, guides: Sequence[Guide], box: Box = BOX) -> Any:
    """Geste sans souris : seuls les guides, la boîte et l'index comptent pour ``lit``."""
    drag = states.Dragging.__new__(states.Dragging)
    drag.guides, drag.box, drag.planes = list(guides), box, PlaneIndex(guides)
    return drag


def test_lit_voisine_a_l_ecart_montre_la_face_et_la_voisine(states: Any) -> None:
    voisine = face(2, 20, FAR)
    drag = gesture(states, [voisine])
    lit = drag.lit([], BOX, ((2, True),))
    assert len(lit) == 2
    assert voisine in lit
    assert any(g.extent == BOX.with_range(2, 20, 20) for g in lit)


def test_lit_voisine_qui_recouvre_ne_montre_pas_la_face(states: Any) -> None:
    voisine = face(2, 20, NEAR)
    assert gesture(states, [voisine]).lit([], BOX, ((2, True),)) == [voisine]


def test_lit_rien_sans_coplanarite_et_aimant_conserve(states: Any) -> None:
    touche = face(0, 100, NEAR, -1)
    drag = gesture(states, [face(2, 55, FAR), touche])
    assert drag.lit([touche], BOX, ((2, True),)) == [touche]
    assert drag.lit([], BOX, ((2, False), (2, True))) == []


def test_lit_sans_doublon_avec_le_guide_aimante(states: Any) -> None:
    voisine = face(2, 20, FAR)
    drag = gesture(states, [voisine])
    assert drag.lit([voisine], BOX, ((2, True),)).count(voisine) == 1
    assert len(drag.lit([voisine], BOX, ((2, True),))) == 2


def test_lit_plafonne(states: Any) -> None:
    voisines = [face(2, 20, [(i, i + 1), (900, 950), (0, 0)]) for i in range(5 * MAX_COPLANAR)]
    aimante = face(0, 100, NEAR, -1)
    drag = gesture(states, [aimante, *voisines])
    lit = drag.lit([aimante], BOX, ((2, True),))
    assert len(lit) == 1 + MAX_COPLANAR
    assert lit[0] == aimante


def test_lit_poignee_sans_face_ne_montre_rien(states: Any) -> None:
    assert gesture(states, [face(2, 20, FAR)]).lit([], BOX, ()) == []


def test_moved_lit_suit_la_boite_deplacee(states: Any) -> None:
    """Déplacée de 30 sur Z, la face de fin (50) est au ras du plan voisin à 50, plus la face de
    début (30) au ras de rien ; à 0 de décalage, la face de fin (20) n'est pas au ras de 50."""
    voisine = face(2, 50, FAR)
    drag = gesture(states, [voisine])
    moved = drag.moved_lit(2, DragResult(Vec3(0, 0, 30)))
    assert voisine in moved
    assert len(moved) == 2
    assert drag.moved_lit(2, DragResult(Vec3(0, 0, 0))) == []


def test_moved_lit_garde_les_guides_aimantes_d_abord(states: Any) -> None:
    touche, voisine = face(0, 100, NEAR, -1), face(2, 50, FAR)
    drag = gesture(states, [touche, voisine])
    hit = MagnetHit(0, 0, True, MagnetKind.CONTACT, 100.0)
    moved = drag.moved_lit(2, DragResult(Vec3(0, 0, 30), (hit,)))
    assert moved[0] == touche
    assert voisine in moved


def test_moved_lit_autre_axe_ignore(states: Any) -> None:
    voisine = face(2, 50, FAR)
    assert gesture(states, [voisine]).moved_lit(0, DragResult(Vec3(0, 0, 30))) == []
