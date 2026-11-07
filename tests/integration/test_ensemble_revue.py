# SPDX-License-Identifier: LGPL-2.1-or-later
"""Relecture de fin de jalon « Ensemble à la souris » (ADR 0038) : Std Part tourné, suppression,
messages de sortie, Std Parts de l'utilisateur."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_membres import caisson
from tests.integration.test_ensemble_std_part import geometry

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")


# --- 1 : ensemble déjà tourné, puis rangé dans un parent ----------------------------------------


def test_ensemble_tourne_puis_range_dans_un_parent(document: Any) -> None:
    desk = build_parts(document)
    sub, parts = caisson(document)
    assert api.rotate_furniture(sub, (0, 0, 30))
    document.recompute()
    before = geometry(document)
    members = [desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub]
    furniture, _ = api.make_furniture(members, "Bureau")
    sub_std = container.std_part_of(sub)
    assert tuple(sub.Origin) == (0, 0, 0)  # l'Origin est passée dans le Placement du Std Part
    assert geometry(document) == before
    corner = sub_std.Placement.Base
    furniture.Width = 1400
    document.recompute()
    assert stale_or_invalid(document) == []
    assert sub_std.Placement.Base.isEqual(corner, 1e-6)  # ne se décale pas au recalcul
    assert {p.Name for p in parts.values()} <= {o.Name for o in sub_std.Group}


# --- 2 : les messages de sortie ne se perdent pas ----------------------------------------------


def test_retrait_renvoie_les_messages_de_sortie(bureau: Any) -> None:
    joue = bureau.parts["JG"]  # assemblée au voile, qui reste dans l'ensemble
    messages = api.remove_from_furniture([joue])
    assert len(messages) == 1 and "Std Part" in messages[0] and joue.Label in messages[0]
    assert joue.getParentGeoFeatureGroup() == container.std_part_of(bureau.furniture)
    assert api.remove_from_furniture([bureau.parts["P"]]) == ()  # rien à signaler


# --- 3 : suppression à la main du Std Part -------------------------------------------------------


@pytest.fixture
def watching() -> Any:
    """Observateur de suppression des Std Parts, posé comme le fait l'atelier actif."""
    from freecad.menuiserie.features.std_part_watch import StdPartObserver

    observer = StdPartObserver()
    App.addDocumentObserver(observer)
    yield observer
    App.removeDocumentObserver(observer)


def test_std_part_deplace_supprime_les_pieces_ne_sautent_pas(bureau: Any, watching: Any) -> None:
    furniture, doc = bureau.furniture, bureau.doc
    assert api.move_furniture(furniture, (120.0, -40.0, 10.0))
    doc.recompute()
    before = geometry(doc)
    doc.removeObject(container.std_part_of(furniture).Name)
    doc.recompute()
    assert geometry(doc) == before
    assert stale_or_invalid(doc) == []
    assert tuple(furniture.Origin) == pytest.approx((120, -40, 10))
    api.resize_furniture(furniture, depth=800)  # les liaisons suivent la nouvelle Origin
    assert bureau.sizes("JG")[1] == 760
    assert geometry(doc)[bureau.parts["P"].Name][:3] == before[bureau.parts["P"].Name][:3]


def test_std_part_tourne_supprime_les_pieces_gardent_leur_place(
    bureau: Any, watching: Any
) -> None:
    furniture, doc = bureau.furniture, bureau.doc
    assert api.rotate_furniture(furniture, (0, 0, 30))
    doc.recompute()
    before = geometry(doc)
    doc.removeObject(container.std_part_of(furniture).Name)
    doc.recompute()
    assert geometry(doc) == before  # même après recalcul : plus aucune liaison ne les ramène
    assert stale_or_invalid(doc) == []


def test_std_part_d_un_sous_ensemble_supprime(document: Any, watching: Any) -> None:
    desk = build_parts(document)
    sub, parts = caisson(document)
    furniture, _ = api.make_furniture(
        [desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub], "Bureau"
    )
    assert api.move_furniture(furniture, (60.0, 30.0, 0.0))
    document.recompute()
    before = geometry(document)
    document.removeObject(container.std_part_of(sub).Name)
    document.recompute()
    assert geometry(document) == before
    assert api.furniture_of(sub) is None  # il n'est plus rangé dans le parent
    api.resize_furniture(furniture, depth=800)
    assert stale_or_invalid(document) == []
    assert geometry(document)[parts["CG"].Name][:3] == before[parts["CG"].Name][:3]
