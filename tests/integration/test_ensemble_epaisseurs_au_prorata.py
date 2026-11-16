# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hauteur d'un ensemble que remplissent des planches à plat (ADR 0062, doute D11 de jv) : les
épaisseurs suivent au prorata, par l'api, l'éditeur de propriétés et « Déverrouiller »."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


def empilees(document: Any) -> tuple[Any, Any, Any]:
    """Fond de 22 mm et dessus de 18 mm empilés (600 x 400), dans un ensemble de 40 mm."""
    fond = api.make_wood_part(600, 400, 22, "chene", mark="F", doc=document)
    dessus = api.make_wood_part(600, 400, 18, "chene", mark="D", doc=document)
    dessus.Placement = App.Placement(App.Vector(0, 0, 22), App.Rotation())
    document.recompute()
    furniture, _ = api.make_furniture([fond, dessus], label="Plateau")
    document.recompute()
    assert furniture.Height.Value == pytest.approx(40.0)
    return furniture, fond, dessus


def etat(fond: Any, dessus: Any) -> tuple[float, ...]:
    hauts = (fond.Shape.BoundBox.ZMin, dessus.Shape.BoundBox.ZMin, dessus.Shape.BoundBox.ZMax)
    epaisseurs = (fond.Thickness.Value, dessus.Thickness.Value)
    return tuple(round(value, 6) for value in (*epaisseurs, *hauts))


def test_hauteur_par_l_api_au_prorata_puis_annulee(document: Any) -> None:
    document.UndoMode = 1
    furniture, fond, dessus = empilees(document)
    document.clearUndos()
    document.openTransaction("Hauteur")
    api.resize_furniture(furniture, height=50)
    document.commitTransaction()
    document.recompute()
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    assert stale_or_invalid(document) == []
    document.undo()
    document.recompute()
    assert furniture.Height.Value == pytest.approx(40.0)
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)
    document.redo()
    document.recompute()
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    document.clearUndos()


def test_hauteur_saisie_dans_l_editeur(document: Any, vue_rapport: Any) -> None:
    furniture, fond, dessus = empilees(document)
    vue_rapport.messages.clear()
    furniture.Height = 20
    document.recompute()
    assert etat(fond, dessus) == (11.0, 9.0, 0.0, 11.0, 20.0)
    assert vue_rapport.de_niveau("Warning") == []
    assert stale_or_invalid(document) == []


def test_planche_verrouillee_toujours_refusee(document: Any) -> None:
    furniture, fond, dessus = empilees(document)
    dessus.Locked = True
    document.recompute()
    with pytest.raises(ValueError, match="hauteur"):
        api.resize_furniture(furniture, height=50)
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)
    api.unlock_and_resize(furniture, [dessus], height=50)
    document.recompute()
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    assert stale_or_invalid(document) == []


def tirer_le_dessus(furniture: Any, delta: float) -> Any:
    """Poignée du dessus de l'ensemble tirée de ``delta`` mm (pas de la souris)."""
    drag = pytest.importorskip("freecad.menuiserie.features.furniture_drag")
    core_furniture = pytest.importorskip("freecad.menuiserie.core.furniture")
    core_magnet = pytest.importorskip("freecad.menuiserie.core.magnet")
    memento = drag.begin_furniture_drag(furniture)
    for step in (4.0, delta / 2, delta):  # plusieurs pas : écritures absolues
        box = core_furniture.resized_box(memento.box, core_magnet.Handle(2, True), step)
        assert drag.resize_furniture_to(memento, box).reached
    return drag, memento


def test_poignee_les_epaisseurs_suivent_au_relachement(document: Any) -> None:
    furniture, fond, dessus = empilees(document)
    drag, memento = tirer_le_dessus(furniture, 10.0)
    assert furniture.Height.Value == pytest.approx(50.0)
    assert (fond.Thickness.Value, dessus.Thickness.Value) == (22.0, 18.0)  # pendant le geste
    drag.end_furniture_drag(memento)
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    assert stale_or_invalid(document) == []


def test_poignee_echap_rend_tout(document: Any) -> None:
    furniture, fond, dessus = empilees(document)
    drag, memento = tirer_le_dessus(furniture, 10.0)
    drag.restore(memento)
    assert furniture.Height.Value == pytest.approx(40.0)
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)
    assert stale_or_invalid(document) == []
