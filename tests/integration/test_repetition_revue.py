# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition, correctifs de la revue finale (jalon « Répétition », ADR 0043 et 0044).

Assemblage ou membre ajouté à la source après coup (copié dans toutes les copies), sources dans un
conteneur ``App::Part`` translaté et tourné, sources de conteneurs différents refusées, dernière
source supprimée.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.test_repetition_ensembles import Meuble, board, copies

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
joints_of = pytest.importorskip("freecad.menuiserie.features.repeat_joints")


def joints(doc: Any) -> list[Any]:
    return [obj for obj in doc.Objects if hasattr(obj, "HostPart")]


def children(doc: Any) -> list[Any]:
    return [joint for joint in joints(doc) if joints_of.origin_of(joint) is not None]


# --- Assemblage ajouté à la source après coup ---------------------------------------------


def frame(doc: Any) -> tuple[Any, Any]:
    stile = board(doc, "Montant", (600, 60, 22), (60, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    rail = board(doc, "Traverse", (200, 40, 22), (60, 10, 0))
    doc.recompute()
    return stile, rail


def test_un_assemblage_ajoute_a_la_source_va_a_toutes_les_copies(document: Any) -> None:
    stile, rail = frame(document)
    rep = api.make_repeat([rail], api.RepeatParams(count=2, step=100.0, axis="Y"))
    assert children(document) == []
    api.make_mortise_tenon(stile, rail)
    document.recompute()
    api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="Y"))
    assert len(children(document)) == 3  # les rangs 1 et 2 aussi, pas seulement le nouveau
    api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="Y"))
    assert len(children(document)) == 3  # sans doublon
    assert stale_or_invalid(document) == []


def test_un_enfant_dissocie_ne_revient_pas_en_double(document: Any) -> None:
    stile, rail = frame(document)
    api.make_mortise_tenon(stile, rail)
    document.recompute()
    rep = api.make_repeat([rail], api.RepeatParams(count=2, step=100.0, axis="Y"))
    free = children(document)[0]
    joints_of.unlink_joint(free)
    api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="Y"))
    pairs = [(j.HostPart.Name, j.GuestPart.Name) for j in joints(document)]
    assert len(pairs) == len(set(pairs))


# --- Membre ajouté à l'ensemble source après coup -----------------------------------------


def test_un_membre_ajoute_a_l_ensemble_source_est_copie_dans_chaque_copie(document: Any) -> None:
    meuble = Meuble(document)
    rep = api.make_repeat([meuble.furniture], api.RepeatParams(count=2, step=900.0, axis="X"))
    plinth = board(document, "Plinthe", (564, 60, 18), (18, 0, 100))
    document.recompute()
    api.add_to_furniture(meuble.furniture, [plinth])
    api.edit_repeat(rep, api.RepeatParams(count=3, step=900.0, axis="X"))
    furnitures = copies(rep, meuble.furniture)
    assert len(furnitures) == 3
    plinths = copies(rep, plinth)
    assert [c.RepeatIndex for c in plinths] == [1, 2, 3]
    assert [api.furniture_of(c).Name for c in plinths] == [f.Name for f in furnitures]
    api.edit_repeat(rep, api.RepeatParams(count=3, step=900.0, axis="X"))
    assert len(copies(rep, plinth)) == 3  # sans doublon
    assert stale_or_invalid(document) == []


# --- Sources dans un conteneur App::Part ---------------------------------------------------


def container(doc: Any, name: str, base: Any, rotation: Any) -> Any:
    part = doc.addObject("App::Part", name)
    part.Placement = App.Placement(base, rotation)
    return part


@pytest.mark.parametrize(
    ("base", "rotation"),
    [
        (App.Vector(1000, 500, 0), App.Rotation()),
        (App.Vector(1000, 500, 0), App.Rotation(App.Vector(0, 0, 1), 37)),
        (App.Vector(0, 0, 300), App.Rotation(App.Vector(0, 1, 0), 90)),
    ],
)
def test_sources_dans_un_conteneur(document: Any, base: Any, rotation: Any) -> None:
    box = container(document, "Conteneur", base, rotation)
    bar = board(document, "Barreau", (300, 40, 22), (10, 20, 30))
    box.addObject(bar)
    document.recompute()
    rep = api.make_repeat([bar], api.RepeatParams(count=3, step=100.0, axis="Y"))
    assert rep.getParentGeoFeatureGroup() == box  # répétition et copies dans le même conteneur
    assert [c.getParentGeoFeatureGroup() for c in copies(rep)] == [box] * 3
    # L'axe est celui du repère du conteneur : les décalages sont locaux.
    assert [round(c.Placement.Base.y - bar.Placement.Base.y, 6) for c in copies(rep)] == [
        100.0,
        200.0,
        300.0,
    ]
    assert stale_or_invalid(document) == []
    assert all(obj.isValid() for obj in document.Objects)
    api.edit_repeat(rep, api.RepeatParams(count=5, step=100.0, axis="Y"))
    assert len(copies(rep)) == 5
    assert stale_or_invalid(document) == []
    global_shift = copies(rep)[0].getGlobalPlacement().Base - bar.getGlobalPlacement().Base
    expected = box.Placement.Rotation.multVec(App.Vector(0, 100, 0))
    assert (global_shift - expected).Length < 1e-6


def test_sources_de_conteneurs_differents_refusees(document: Any) -> None:
    first = container(document, "A", App.Vector(), App.Rotation())
    second = container(document, "B", App.Vector(0, 1000, 0), App.Rotation())
    one = board(document, "Un", (300, 40, 22), (0, 0, 0))
    two = board(document, "Deux", (300, 40, 22), (0, 0, 100))
    first.addObject(one)
    second.addObject(two)
    document.recompute()
    before = len(document.Objects)
    with pytest.raises(ValueError, match="conteneurs différents"):
        api.make_repeat([one, two], api.RepeatParams(count=2, step=100.0, axis="Y"))
    assert len(document.Objects) == before


# --- Dernière source supprimée -------------------------------------------------------------


def test_modifier_une_repetition_sans_source_est_refuse(document: Any) -> None:
    stile, _rail = frame(document)
    rep = api.make_repeat([stile], api.RepeatParams(count=2, step=100.0, axis="Y"))
    document.removeObject(stile.Name)
    assert repeat.sources_of(rep) == []
    with pytest.raises(ValueError, match="aucune pièce à répéter"):
        api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="Y"))
