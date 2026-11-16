# SPDX-License-Identifier: LGPL-2.1-or-later
"""Orientations des voisins lues pour aimanter une rotation (ADR 0025, complément)."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
guides_module = pytest.importorskip("freecad.menuiserie.features.magnet_guides")
rotation = pytest.importorskip("freecad.menuiserie.core.rotation")


def box(doc: Any, x: float, angle: float = 0.0, visible: bool = True) -> Any:
    """Cube de Part de 10 mm en (x, 0, 0), tourné de ``angle`` degrés autour de Z."""
    found = doc.addObject("Part::Box", "Voisin")
    found.Length = found.Width = found.Height = 10
    found.Placement = App.Placement(App.Vector(x, 0, 0), App.Rotation(App.Vector(0, 0, 1), angle))
    found.Visibility = visible
    return found


def z_angles(found: Any) -> list[float]:
    return sorted(rotation.angles_of(m)[2] for m in found)


def test_rotations_des_voisins_sans_doublon(document: Any) -> None:
    part = api.make_wood_part(400, 100, 20, "chene", doc=document)
    box(document, 500, 30.0)
    box(document, 600, 30.0)
    box(document, 700, 0.0)
    document.recompute()
    found = guides_module.neighbor_rotations(part, None)
    assert z_angles(found) == pytest.approx([0.0, 30.0])


def test_voisin_masque_ou_sans_forme_ignore(document: Any) -> None:
    part = api.make_wood_part(400, 100, 20, "chene", doc=document)
    box(document, 500, 30.0, visible=False)
    document.addObject("App::FeaturePython", "SansPlacement")
    document.recompute()
    assert guides_module.neighbor_rotations(part, None) == ()


def test_orientations_bornees_aux_plus_proches(document: Any) -> None:
    part = api.make_wood_part(400, 100, 20, "chene", doc=document)
    count = guides_module.MAX_ORIENTATIONS + 4
    for index in range(count):
        box(document, 1000 + 100 * index, 1.0 + index)
    document.recompute()
    found = guides_module.neighbor_rotations(part, None)
    assert len(found) == guides_module.MAX_ORIENTATIONS
    assert z_angles(found)[0] == pytest.approx(1.0)  # le plus proche est gardé
