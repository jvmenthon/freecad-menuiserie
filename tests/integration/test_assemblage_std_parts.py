# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage entre deux pièces rangées dans des Std Part imbriqués (issue #209, ADR 0054)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import RAIL_VOLUME, Cadre, api

App = pytest.importorskip("FreeCAD")

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
    child.Placement = App.Placement(App.Vector(SHIFT + 500, 0, 0), App.Rotation())
    cadre.doc.recompute()
    assert "Invalid" in joint.State  # les pièces ne se touchent plus : l'assemblage a été recalculé


def test_refus_conteneurs_sans_parente(cadre: Cadre) -> None:
    first = cadre.doc.addObject("App::Part", "Un")
    second = cadre.doc.addObject("App::Part", "Deux")
    first.addObject(cadre.parts["M1"])
    second.addObject(cadre.parts["T1"])
    with pytest.raises(ValueError, match="même conteneur"):
        api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"])
