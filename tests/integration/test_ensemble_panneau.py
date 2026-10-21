# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que le panneau de l'ensemble lit et écrit (J4c, P3 à P5), sans interface : distance au
bord saisie (``set_edge_distance``) et membres vus par le panneau (``member_views``)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
furniture_view = pytest.importorskip("freecad.menuiserie.features.furniture_view")
core = pytest.importorskip("freecad.menuiserie.core.furniture")


def loose_desk(doc: Any) -> Bureau:
    """Bureau sans assemblage, regroupé dans l'ensemble « Bureau » (options par défaut)."""
    bureau = build_parts(doc)
    bureau.furniture, bureau.notices = api.make_furniture(list(bureau.parts.values()), "Bureau")
    return bureau


def test_distance_face_opposee_fixe_change_la_cote(document: Any) -> None:
    """Plateau : gauche à 10 mm, la droite (fixe) reste au bord ; il suit ensuite la largeur."""
    bureau = loose_desk(document)
    assert api.set_edge_distance(bureau.parts["P"], "Left", 10.0) == ()
    assert bureau.bounds("P")[0] == (10.0, 1200.0)
    assert bureau.expressions("P")["Length"] == "<<Bureau>>.Width - 10 mm"
    assert bureau.parts["P"].FixedLeft is True
    api.resize_furniture(bureau.furniture, width=1400)
    assert bureau.bounds("P")[0] == (10.0, 1400.0)
    assert stale_or_invalid(document) == []


def test_distance_sur_l_epaisseur_deplace(document: Any) -> None:
    """Joue gauche : 5 mm à gauche, elle se déplace sans changer d'épaisseur."""
    bureau = loose_desk(document)
    api.set_edge_distance(bureau.parts["JG"], "Left", 5.0)
    assert bureau.bounds("JG")[0] == (5.0, 27.0)
    assert bureau.sizes("JG") == (720.0, 560.0, 22.0)


def test_distance_face_opposee_non_fixe_deplace(document: Any) -> None:
    """Avant de la joue décoché : l'arrière à 20 mm la recule, sa largeur ne change pas."""
    bureau = loose_desk(document)
    api.set_member_options(bureau.parts["JG"], fixed={"Front": False})
    api.set_edge_distance(bureau.parts["JG"], "Back", 20.0)
    assert bureau.bounds("JG")[1] == (20.0, 580.0)
    assert bureau.sizes("JG")[1] == 560.0
    assert "Width" in bureau.expressions("JG")


def test_distance_annulable_en_une_entree(document: Any) -> None:
    bureau = loose_desk(document)
    document.UndoMode = 1
    before = dict(bureau.expressions("JG"))
    document.openTransaction("Distance")
    api.set_edge_distance(bureau.parts["JG"], "Back", 20.0)
    document.commitTransaction()
    document.undo()
    document.recompute()
    assert bureau.expressions("JG") == before
    assert bureau.sizes("JG")[1] == 560.0


@pytest.mark.parametrize(
    ("edge", "distance", "text"),
    [
        ("Left", 1199.95, "trop petite"),
        ("Avant", 1.0, "Option « fixe » inconnue"),
        ("Left", float("nan"), "Distance au bord invalide"),
    ],
    ids=["trop-petite", "bord-inconnu", "nan"],
)
def test_distance_refusee_avant_modification(
    document: Any, edge: str, distance: float, text: str
) -> None:
    bureau = loose_desk(document)
    before = (bureau.sizes("P"), bureau.expressions("P"))
    with pytest.raises(ValueError, match=text):
        api.set_edge_distance(bureau.parts["P"], edge, distance)
    assert (bureau.sizes("P"), bureau.expressions("P")) == before


def test_distance_d_une_face_pilotee_refusee(document: Any) -> None:
    """P5 : position du voile pilotée par une formule de l'utilisateur."""
    bureau = build_parts(document)
    bureau.parts["V"].setExpression("Placement.Base.y", "<<Plateau>>.Width - 141 mm")
    furniture, _ = api.make_furniture(list(bureau.parts.values()), "Bureau")
    with pytest.raises(ValueError, match="formule"):
        api.set_edge_distance(bureau.parts["V"], "Back", 100.0)
    views, notices = furniture_view.member_views(furniture)
    voile = next(view for view in views if view.obj == bureau.parts["V"])
    assert voile.driven == {core.Edge.FRONT, core.Edge.BACK}
    assert core.Follow.FORMULA in voile.follows
    assert any("Placement.Base.y" in message for message in notices)


def test_membres_vus_par_le_panneau(bureau: Bureau) -> None:
    """P3 : mode, colonne « Suit », distances et options du bureau de référence."""
    views, notices = furniture_view.member_views(bureau.furniture)
    by_label = {view.obj.Label: view for view in views}
    joue = by_label["Joue gauche"]
    assert (joue.mode, joue.follows) == ("Stay", (core.Follow.STRETCHED,))
    assert round(joue.distances[core.Edge.BACK], 6) == 40.0
    assert core.Edge.RIGHT not in joue.fixed
    assert by_label["Voile"].follows == (core.Follow.STRETCHED, core.Follow.MOVED)
    assert notices == ()


def test_pas_d_equerre_vu_par_le_panneau(document: Any) -> None:
    bureau = build_parts(document)
    bureau.parts["V"].Placement = App.Placement(
        App.Vector(300, 300, 100), App.Rotation(App.Vector(0, 0, 1), 45)
    )
    document.recompute()
    furniture, _ = api.make_furniture(list(bureau.parts.values()), "Bureau")
    views, notices = furniture_view.member_views(furniture)
    voile = next(view for view in views if view.obj == bureau.parts["V"])
    assert (voile.follows, dict(voile.distances)) == ((core.Follow.NOT_SQUARE,), {})
    assert any("pas d'équerre" in message for message in notices)
