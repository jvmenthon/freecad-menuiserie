# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tenon et queue d'aronde entre pièces dessinées hors tout, qui se chevauchent (ADR 0016) :
la pièce usinée de l'invitée est raccourcie jusqu'au contact puis reçoit ses ajouts."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import DOVETAIL_VOLUME, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

TENON = 40 * 40 * 7  # tenon automatique d'une traverse 60 x 22 dans un montant de 60
MORTISE = 40 * 42 * 7


def machined(*parts: Any) -> list[Any]:
    return [api.machined_part_of(part).Shape for part in parts]


def test_tenon_traverse_dessinee_hors_tout(document: Any) -> None:
    """Traverse 340 dessinée jusqu'au chant extérieur du montant : raccourcie de 60 mm."""
    stile = wood(document, "M", (600, 60, 22), (0, 0, 0))
    rail = wood(document, "T", (340, 60, 22), (60, 0, 90))
    document.recompute()
    joint = api.make_mortise_tenon(stile, rail)
    document.recompute()
    assert joint.isValid(), joint.getStatusString()
    stile_shape, rail_shape = machined(stile, rail)
    assert stile_shape.Volume == pytest.approx(600 * 60 * 22 - MORTISE)
    assert rail_shape.Volume == pytest.approx(280 * 60 * 22 + TENON)
    assert rail_shape.BoundBox.YMin == pytest.approx(60 - 40)  # le tenon entre de 40 mm
    assert stile_shape.common(rail_shape).Volume == pytest.approx(0, abs=1e-6)
    assert rail.Length.Value == 340  # la brute garde ses cotes
    assert stale_or_invalid(document) == []


def test_queue_d_aronde_planches_dessinees_hors_tout(document: Any) -> None:
    """Angle de caisson, les deux planches hors tout : l'invitée perd l'épaisseur de l'hôte,
    ses queues traversent l'hôte."""
    host = wood(document, "H", (400, 150, 18), (0, 0, 0))
    guest_place = App.Placement(App.Vector(18, 0, 0), App.Rotation(App.Vector(0, 1, 0), -90))
    guest = wood(document, "I", (418, 150, 18), guest_place)
    document.recompute()
    joint = api.make_dovetail(host, guest)
    document.recompute()
    assert joint.isValid(), joint.getStatusString()
    host_shape, guest_shape = machined(host, guest)
    assert host_shape.Volume == pytest.approx(400 * 150 * 18 - DOVETAIL_VOLUME)
    assert guest_shape.Volume == pytest.approx(400 * 150 * 18 + DOVETAIL_VOLUME)
    assert host_shape.common(guest_shape).Volume == pytest.approx(0, abs=1e-6)
    assert stale_or_invalid(document) == []


# --- Liste de débit (demande de jv) ------------------------------------------------------


def rail_line(document: Any, mark: str) -> Any:
    cut_list = api.cut_list_of(document)
    (line,) = [line for line in cut_list.lines if mark in line.marks]
    return line


def test_liste_de_debit_longueur_reelle_de_la_traverse(document: Any) -> None:
    """Traverse de 340 dessinée hors tout : cote finie 280 (raccourcie de 60), tenon de 40 en
    ajout, débit 320 plus la surcote ; la brute dessinée (340) ne compte plus."""
    stile = wood(document, "M", (600, 60, 22), (0, 0, 0))
    rail = wood(document, "T", (340, 60, 22), (60, 0, 90))
    document.recompute()
    api.make_mortise_tenon(stile, rail)
    document.recompute()
    line = rail_line(document, "T")
    assert line.finished.length == pytest.approx(280)
    assert (line.finished.width, line.finished.thickness) == (60, 22)
    assert line.additions.length == pytest.approx(40)
    assert line.rough.length == pytest.approx(280 + 40 + line.allowances.length)
    assert rail_line(document, "M").finished.length == 600  # l'hôte n'est pas raccourci


def test_liste_de_debit_traverse_hors_tout_entre_deux_montants(document: Any) -> None:
    """Traverse de 400 dessinée d'un chant extérieur à l'autre de deux montants de 60 :
    raccourcie aux deux bouts (280), deux tenons de 40."""
    first = wood(document, "M1", (600, 60, 22), (0, 0, 0))
    second = wood(document, "M2", (600, 60, 22), (0, 340, 0))
    rail = wood(document, "T", (400, 60, 22), (60, 0, 90))
    document.recompute()
    for stile in (first, second):
        api.make_mortise_tenon(stile, rail)
    document.recompute()
    line = rail_line(document, "T")
    assert line.finished.length == pytest.approx(280)
    assert line.additions.length == pytest.approx(80)
