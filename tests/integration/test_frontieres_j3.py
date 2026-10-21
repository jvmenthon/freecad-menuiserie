# SPDX-License-Identifier: LGPL-2.1-or-later
"""Frontières entre les sous-lots de J3 (testeur) : pièce reliée par des assemblages de types
différents, suppression / annulation / rétablissement en chaîne, réouverture d'un document qui
contient les quatre types, pièces usinées dans un repère quelconque, expressions sur les cotes
des assemblages, valeurs limites (tourillons sur 40 à 51 mm, pièces de 12 mm)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import STILE_VOLUME, Cadre, touched
from tests.integration.test_assemblages_persistance import snapshot
from tests.integration.types_assemblages import FRAME, RABBET, TONGUE_GROOVE, blanks, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
joints_base = pytest.importorskip("freecad.menuiserie.features.joints.base")

Reopen = Callable[[Any], Any]
HOLE = math.pi * 5**2 * 21  # perçage Ø 10, profondeur 20 + 1 de jeu (cadre, tourillons auto)
MORTISE = 42 * 40 * 7
TENON = 40 * 40 * 7
STILE = 600 * 60 * 22
RAIL = 280 * 60 * 22
# M2 : mortaise (T2) et deux perçages (T1) ; T1 : tenon (M1) et deux perçages (M2).
MIXED_VOLUMES = {
    "M1": STILE_VOLUME,
    "M2": STILE - MORTISE - 2 * HOLE,
    "T1": RAIL + TENON - 2 * HOLE,
    "T2": RAIL + 2 * TENON,
}
TG_VOLUMES = (TONGUE_GROOVE.host_volume, TONGUE_GROOVE.guest_volume)
RABBET_VOLUMES = (RABBET.host_volume, RABBET.guest_volume)


def assemble_mixed(cadre: Cadre) -> dict[str, Any]:
    """Cadre relié par trois tenons-mortaises et des tourillons (M2, T1)."""
    parts = cadre.parts
    return {
        "mt_m1_t1": api.make_mortise_tenon(parts["M1"], parts["T1"]),
        "mt_m1_t2": api.make_mortise_tenon(parts["M1"], parts["T2"]),
        "dw_m2_t1": api.make_dowels(parts["M2"], parts["T1"]),
        "mt_m2_t2": api.make_mortise_tenon(parts["M2"], parts["T2"]),
    }


def volumes(cadre: Cadre) -> dict[str, float]:
    return {mark: cadre.volume(mark) for mark in cadre.parts}


def assert_mixed(cadre: Cadre) -> None:
    assert volumes(cadre) == pytest.approx(MIXED_VOLUMES)
    assert touched(cadre.doc) == []
    for mark in cadre.parts:
        assert len(cadre.machined(mark).Shape.Solids) == 1, mark


def add_tongue_groove_and_rabbet(doc: Any) -> tuple[Any, Any]:
    """Montages rainure-languette et feuillure dans le même document (repère quelconque)."""
    tg = api.make_tongue_groove(*blanks(doc, TONGUE_GROOVE))
    rabbet = api.make_rabbet(*blanks(doc, RABBET))
    return tg, rabbet


def joint_volumes(joint: Any) -> tuple[float, float]:
    return tuple(  # type: ignore[return-value]
        float(api.machined_part_of(blank).Shape.Volume)
        for blank in (joint.HostPart, joint.GuestPart)
    )


# --- Une pièce reliée par des assemblages de types différents ------------------------------


def test_piece_reliee_par_deux_types(cadre: Cadre) -> None:
    joints = assemble_mixed(cadre)
    assert_mixed(cadre)
    m2 = cadre.machined("M2")
    assert set(m2.Joints) == {joints["dw_m2_t1"], joints["mt_m2_t2"]}
    assert set(cadre.machined("T1").Joints) == {joints["mt_m1_t1"], joints["dw_m2_t1"]}
    # Une seule pièce usinée par brute, malgré deux fabriques différentes.
    machined = [obj for obj in cadre.doc.Objects if api.is_machined_part(obj)]
    assert len(machined) == 4


def test_changer_une_cote_recalcule_les_deux_types(cadre: Cadre) -> None:
    joints = assemble_mixed(cadre)
    joints["dw_m2_t1"].Count = 1
    joints["mt_m2_t2"].TenonThickness = 8
    cadre.doc.recompute()
    expected = STILE - 42 * 40 * 8 - HOLE
    assert cadre.volume("M2") == pytest.approx(expected)
    assert touched(cadre.doc) == []


# --- Suppression, annulation, rétablissement en chaîne -------------------------------------


def test_suppressions_annulees_puis_retablies_en_chaine(cadre: Cadre) -> None:
    doc = cadre.doc
    doc.UndoMode = 1
    doc.openTransaction("Créer")
    joints = assemble_mixed(cadre)
    doc.commitTransaction()
    doc.recompute()
    states = [volumes(cadre)]
    doc.openTransaction("Supprimer les tourillons")
    doc.removeObject(joints["dw_m2_t1"].Name)
    doc.commitTransaction()
    doc.recompute()
    states.append(volumes(cadre))
    assert states[-1]["M2"] == pytest.approx(STILE - MORTISE)
    assert states[-1]["T1"] == pytest.approx(RAIL + TENON)
    doc.openTransaction("Modifier")
    joints["mt_m1_t1"].TenonLength = 30
    doc.commitTransaction()
    doc.recompute()
    states.append(volumes(cadre))
    assert states[-1]["T1"] == pytest.approx(RAIL + 30 * 40 * 7)
    doc.openTransaction("Supprimer un tenon")
    doc.removeObject(joints["mt_m2_t2"].Name)
    doc.commitTransaction()
    doc.recompute()
    states.append(volumes(cadre))
    for expected in reversed(states[:-1]):
        doc.undo()
        doc.recompute()
        assert volumes(cadre) == pytest.approx(expected)
        assert touched(doc) == []
    for expected in states[1:]:
        doc.redo()
        doc.recompute()
        assert volumes(cadre) == pytest.approx(expected)
        assert touched(doc) == []
    # Tout annuler : plus aucun assemblage ni pièce usinée, brutes visibles.
    for _ in states:
        doc.undo()
    doc.recompute()
    assert not [obj for obj in doc.Objects if api.is_machined_part(obj)]
    assert all(part.Visibility for part in cadre.parts.values())


def test_supprimer_une_brute_reliee_par_deux_types_puis_annuler(cadre: Cadre) -> None:
    doc = cadre.doc
    doc.UndoMode = 1
    assemble_mixed(cadre)
    doc.recompute()
    t1 = cadre.parts["T1"]
    doc.openTransaction("Supprimer T1")
    doc.removeObject(t1.Name)
    doc.commitTransaction()
    doc.recompute()  # sans exception ; les assemblages de T1 passent en erreur
    doc.undo()
    doc.recompute()
    assert_mixed(cadre)


# --- Réouverture d'un document qui contient les quatre types -------------------------------


def test_reouverture_avec_les_quatre_types(cadre: Cadre, rouvrir: Reopen) -> None:
    joints = assemble_mixed(cadre)
    tg, rabbet = add_tongue_groove_and_rabbet(cadre.doc)
    cadre.doc.recompute()
    names = {key: joint.Name for key, joint in joints.items()}
    tg_name, rabbet_name = tg.Name, rabbet.Name
    m2_name = cadre.parts["M2"].Name
    before = snapshot(cadre.doc)
    doc = rouvrir(cadre.doc)
    assert snapshot(doc) == before
    assert touched(doc) == []
    # Les proxies rouverts recalculent : un paramètre de chaque type modifié.
    doc.getObject(names["dw_m2_t1"]).Count = 1
    doc.getObject(names["mt_m2_t2"]).TenonThickness = 8
    doc.getObject(tg_name).TongueThickness = 8
    doc.getObject(rabbet_name).Through = False
    doc.getObject(rabbet_name).GuestPart.Length = 300
    doc.recompute()
    assert touched(doc) == []
    m2 = api.machined_part_of(doc.getObject(m2_name))
    assert m2.Shape.Volume == pytest.approx(STILE - 42 * 40 * 8 - HOLE)
    assert joint_volumes(doc.getObject(tg_name))[0] == pytest.approx(
        1000 * 100 * 22 - 1000 * 11 * 8
    )
    assert joint_volumes(doc.getObject(rabbet_name))[0] == pytest.approx(
        600 * 300 * 18 - 300 * 10 * 6
    )


# --- Pièces usinées dans un repère quelconque ----------------------------------------------


@pytest.mark.parametrize("factory", ["make_mortise_tenon", "make_dowels"])
def test_pieces_usinees_suivent_les_brutes_dans_un_repere_quelconque(
    document: Any, factory: str
) -> None:
    host = wood(document, "H", (600, 60, 22), (0, 0, 0), FRAME)
    guest = wood(document, "I", (280, 60, 22), (60, 60, 90), FRAME)
    document.recompute()
    getattr(api, factory)(host, guest)
    before = joint_volumes(api.machined_part_of(host).Joints[0])
    move = App.Placement(App.Vector(-300, 50, 7), App.Rotation(App.Vector(3, -1, 2), 71))
    # Q4 : déplacer les deux pièces usinées déplace les brutes ; l'assemblage reste valide.
    document.UndoMode = 1
    document.openTransaction("Déplacer")
    for blank in (host, guest):
        machined = api.machined_part_of(blank)
        machined.Placement = move.multiply(machined.Placement)
    document.commitTransaction()
    document.recompute()
    assert touched(document) == []
    for blank in (host, guest):
        machined = api.machined_part_of(blank)
        assert blank.Placement.isSame(machined.Placement, 1e-9)
        assert machined.Shape.Placement.isSame(blank.Placement, 1e-9)
    assert joint_volumes(api.machined_part_of(host).Joints[0]) == pytest.approx(before)
    document.undo()
    document.recompute()
    assert host.Placement.isSame(FRAME, 1e-9)
    assert touched(document) == []


# --- Expressions sur les cotes des assemblages ---------------------------------------------


def test_expressions_sur_les_cotes_des_tourillons(cadre: Cadre) -> None:
    joint = api.make_dowels(cadre.parts["M1"], cadre.parts["T1"])
    joint.setExpression("Diameter", "<<T1>>.Thickness / 2.75")
    joint.setExpression("DowelLength", "Diameter * 4")
    cadre.doc.recompute()
    resolved = joints_base.resolved_for(joint)
    assert (resolved.diameter, resolved.dowel_length, resolved.count) == (8, 32, 2)
    cadre.parts["T1"].Thickness = 27.5
    cadre.parts["M1"].Thickness = 27.5
    cadre.doc.recompute()
    resolved = joints_base.resolved_for(joint)
    assert (resolved.diameter, resolved.dowel_length) == (10, 40)
    assert touched(cadre.doc) == []


def test_expression_sur_la_languette_suit_l_hote(document: Any) -> None:
    host, guest = blanks(document, TONGUE_GROOVE)
    joint = api.make_tongue_groove(host, guest)
    joint.setExpression("TongueThickness", "<<H>>.Thickness / 2")
    document.recompute()
    assert joint_volumes(joint)[0] == pytest.approx(1000 * 100 * 22 - 1000 * 11 * 11)
    host.Thickness = 18
    guest.Thickness = 18
    document.recompute()
    assert joint_volumes(joint)[0] == pytest.approx(1000 * 100 * 18 - 1000 * 11 * 9)
    assert touched(document) == []


# --- Valeurs limites -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "positions"),
    [
        (40, (20.0,)),
        (45, (22.5,)),
        (50, (25.0,)),
        (51, (20.0, 31.0)),
    ],
)
def test_tourillons_sur_une_traverse_etroite(
    document: Any, width: float, positions: tuple[float, ...]
) -> None:
    host = wood(document, "H", (600, 60, 22), (0, 0, 0), FRAME)
    guest = wood(document, "I", (280, width, 22), (width, 60, 90), FRAME)
    document.recompute()
    joint = api.make_dowels(host, guest)
    resolved = joints_base.resolved_for(joint)
    assert resolved.positions == pytest.approx(positions)
    assert len(joint.Shape.Solids) == len(positions)
    assert joint_volumes(joint)[1] == pytest.approx(280 * width * 22 - len(positions) * HOLE)
    assert touched(document) == []


@pytest.mark.parametrize("factory", ["make_mortise_tenon", "make_tongue_groove", "make_dowels"])
def test_pieces_de_12_mm(document: Any, factory: str) -> None:
    host = wood(document, "H", (600, 60, 12), (0, 0, 0), FRAME)
    guest = wood(document, "I", (280, 60, 12), (60, 60, 90), FRAME)
    document.recompute()
    joint = getattr(api, factory)(host, guest)
    assert touched(document) == []
    for blank in (host, guest):
        shape = api.machined_part_of(blank).Shape
        assert shape.isValid()
        assert len(shape.Solids) == 1
    resolved = joints_base.resolved_for(joint)
    thickness = getattr(resolved, "diameter", None) or resolved.thickness
    assert thickness == (6 if factory == "make_dowels" else 4)
    # Juste en dessous de 12 mm : tourillons en erreur, jamais d'exception ni de forme partielle.
    host.Thickness = guest.Thickness = 11.99
    document.recompute()
    if factory == "make_dowels":
        assert "trop minces" in joint.getStatusString()
        assert "Invalid" in joint.State
    else:
        assert touched(document) == []


# --- D1 (J3) : pièces d'un assemblage modifiées par un script ------------------------------

PARTS_MISMATCH = "ne correspondent plus à ses pièces usinées"


def joints_consistent(doc: Any) -> list[str]:
    """Écarts entre les liens des assemblages valides et les ``Joints`` des pièces usinées."""
    problems = []
    for obj in doc.Objects:
        if api.is_machined_part(obj):
            for joint in obj.Joints:
                if obj.Base not in (joint.HostPart, joint.GuestPart):
                    problems.append(f"{obj.Label} liste {joint.Label} sans en être une pièce")
        elif hasattr(obj, "HostPart") and "Invalid" not in obj.State:
            for blank in (obj.HostPart, obj.GuestPart):
                machined = api.machined_part_of(blank)
                if machined is None or obj not in machined.Joints:
                    problems.append(f"{obj.Label} absent des usinages de {blank.Label}")
    return problems


def test_changer_la_piece_hote_d_un_assemblage(cadre: Cadre) -> None:
    joints = assemble_mixed(cadre)
    joint = joints["mt_m1_t1"]
    assert joint.getEditorMode("HostPart") == ["ReadOnly"]
    assert joint.getEditorMode("GuestPart") == ["ReadOnly"]
    joint.HostPart = cadre.parts["M2"]  # T1 touche aussi M2 par son autre bout
    cadre.doc.recompute()
    assert "Invalid" in joint.State
    assert PARTS_MISMATCH in joint.getStatusString()
    machined = cadre.machined("M1")
    with pytest.raises(ValueError, match=PARTS_MISMATCH):
        machined.Proxy.execute(machined)
    # Jamais de forme partielle : les pièces usinées gardent leurs formes précédentes.
    assert volumes(cadre) == pytest.approx(MIXED_VOLUMES)
    joint.HostPart = cadre.parts["M1"]
    cadre.doc.recompute()
    assert_mixed(cadre)
    assert joints_consistent(cadre.doc) == []
