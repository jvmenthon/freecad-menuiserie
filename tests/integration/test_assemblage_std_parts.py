# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage entre deux pièces rangées dans des Std Part imbriqués (issue #209, ADR 0054)."""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.features.joints.frames import touch_framed_joints
from tests.integration.cadre import RAIL_VOLUME, Cadre, api

App = pytest.importorskip("FreeCAD")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
drag_joints = pytest.importorskip("freecad.menuiserie.features.drag_joints")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
snap = pytest.importorskip("freecad.menuiserie.core.snap")

SHIFT = 100.0


def _nested(cadre: Cadre) -> Any:
    """M1 dans un Std Part parent, T1 dans un Std Part enfant décalé de ``SHIFT`` en x ; la place
    globale des pièces ne change pas."""
    doc = cadre.doc
    parent = doc.addObject("App::Part", "Parent")
    child = doc.addObject("App::Part", "Enfant")
    parent.addObject(child)
    child.Placement = App.Placement(App.Vector(SHIFT, 0, 0), App.Rotation())
    parent.addObject(cadre.parts["M1"])
    t1 = cadre.parts["T1"]
    t1_global = t1.Placement
    child.addObject(t1)
    t1.Placement = child.Placement.inverse() * t1_global
    doc.recompute()
    return child


def test_assemblage_entre_std_parts_imbriques(cadre: Cadre) -> None:
    _nested(cadre)
    joint = api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"])
    cadre.doc.recompute()
    assert joint.getParentGeoFeatureGroup() == cadre.parts["M1"].getParentGeoFeatureGroup()
    assert cadre.volume("T1") == pytest.approx(RAIL_VOLUME - 40 * 40 * 7)


def test_assemblage_suit_le_std_part_deplace(cadre: Cadre) -> None:
    child = _nested(cadre)
    joint = api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"])
    cadre.doc.recompute()
    child.Placement = App.Placement(App.Vector(SHIFT, 0, 500), App.Rotation())
    touch_framed_joints(child)  # fait par l'observateur de gui/drag quand l'atelier est actif
    cadre.doc.recompute()
    assert "Invalid" in joint.State  # les pièces ne se touchent plus : l'assemblage a été recalculé


def test_piece_libre_et_piece_de_std_part(cadre: Cadre) -> None:
    """Pièce à la racine face à une pièce d'un Std Part décalé (cas de jv : planche libre entre
    deux caissons)."""
    child = cadre.doc.addObject("App::Part", "Caisson")
    child.Placement = App.Placement(App.Vector(SHIFT, 0, 0), App.Rotation())
    t1 = cadre.parts["T1"]
    t1_global = t1.Placement
    child.addObject(t1)
    t1.Placement = child.Placement.inverse() * t1_global
    cadre.doc.recompute()
    api.make_mortise_tenon(cadre.parts["M1"], t1)
    cadre.doc.recompute()
    assert cadre.volume("T1") == pytest.approx(RAIL_VOLUME - 40 * 40 * 7)


def test_refus_corps_et_autre_conteneur(cadre: Cadre) -> None:
    """Corps PartDesign : même conteneur seulement (ADR 0054)."""
    body = cadre.doc.addObject("PartDesign::Body", "Corps")
    t1 = cadre.parts["T1"]
    body.addObject(t1)
    assert t1.getParentGeoFeatureGroup() == body
    before = len(cadre.doc.Objects)
    with pytest.raises(ValueError) as raised:
        api.make_mortise_tenon(cadre.parts["M1"], t1)
    assert str(raised.value)
    assert len(cadre.doc.Objects) == before


# Gestes sur une pièce assemblée rangée dans un Std Part **tourné** (le repère local de la pièce
# n'est plus celui de l'hôte) : épaisseur suivie, glissement et rotation contrôlés au relâchement.
TILT = App.Rotation(App.Vector(1, 0, 0), 90)


class Chooser:
    """Fonction de choix de test : note les libellés proposés, répond ``answer``."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[list[str]] = []

    def __call__(self, labels: Any) -> bool:
        self.asked.append(list(labels))
        return self.answer


def _tilted_pair(document: Any) -> tuple[Any, Any, Any]:
    """Traverse à la racine (600 x 100 x 30) ; montant dressé dessus (tenon en bas) rangé dans
    un Std Part tourné de 90° autour de X, à la même place globale ; tenon-mortaise entre eux."""
    host = api.make_wood_part(600, 100, 30, doc=document)
    guest = api.make_wood_part(400, 100, 30, doc=document)
    guest.Placement = App.Placement(App.Vector(300, 0, 30), App.Rotation(App.Vector(0, 1, 0), -90))
    holder = document.addObject("App::Part", "Tourne")
    holder.Placement = App.Placement(App.Vector(0, 50, 0), TILT)
    seen = guest.Placement
    holder.addObject(guest)
    guest.Placement = holder.Placement.inverse() * seen
    document.recompute()
    joint = api.make_mortise_tenon(host, guest)
    document.recompute()
    assert "Invalid" not in joint.State
    return host, guest, joint


def test_epaisseur_suivie_dans_un_std_part_tourne(document: Any) -> None:
    host, guest, joint = _tilted_pair(document)
    host.Thickness = 22
    document.recompute()
    base = guest.getGlobalPlacement().Base
    assert (base.x, base.y, base.z) == pytest.approx((300, 0, 22))
    assert "Invalid" not in joint.State


def test_glisser_sans_bouger_ne_defait_rien(document: Any) -> None:
    """Repère juste : la pièce en place n'est pas prise pour un assemblage défait."""
    _host, guest, joint = _tilted_pair(document)
    choose = Chooser(False)
    memento = drag.begin_drag(guest)
    drag.move_part(memento, geometry.Vec3(0, 0, 0))
    drag.end_drag(memento, choose)
    assert choose.asked == []
    assert "Invalid" not in joint.State


def test_glisser_loin_propose_puis_annule(document: Any) -> None:
    _host, guest, joint = _tilted_pair(document)
    start = App.Placement(guest.Placement)
    choose = Chooser(False)
    memento = drag.begin_drag(guest)
    drag.move_part(memento, geometry.Vec3(1000, 0, 0))
    with pytest.raises(drag.DragCancelledError):
        drag.end_drag(memento, choose)
    assert choose.asked == [["« " + joint.Label + " »"]]
    assert guest.Placement == start


def test_rotation_qui_defait_est_annulee(document: Any) -> None:
    _host, guest, joint = _tilted_pair(document)
    start = App.Placement(guest.Placement)
    choose = Chooser(False)
    assert not drag_joints.rotate_checked(guest, snap.Turn.Y, choose=choose)
    assert choose.asked == [["« " + joint.Label + " »"]]
    assert guest.Placement == start
    document.recompute()
    assert "Invalid" not in joint.State
