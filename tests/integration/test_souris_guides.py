# SPDX-License-Identifier: LGPL-2.1-or-later
"""Guides d'aimantation et écriture d'un glissement à la souris (SM-b, B1 à B7, ADR 0021)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.elements_choisis import element_name
from tests.integration.bureau import EXPRESSIONS, LAYOUT, Bureau, build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
magnet = pytest.importorskip("freecad.menuiserie.core.magnet")
guides_module = pytest.importorskip("freecad.menuiserie.features.magnet_guides")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
machined_module = pytest.importorskip("freecad.menuiserie.features.machined_part")
wood_part_module = pytest.importorskip("freecad.menuiserie.features.wood_part")

Vec3 = geometry.Vec3
GuideKind = magnet.GuideKind


def neighbour(doc: Any, x: float, y: float, z: float, size: float = 10) -> Any:
    """Cube de Part (autre atelier) de côté ``size`` posé en (x, y, z)."""
    box = doc.addObject("Part::Box", "Voisin")
    box.Length = box.Width = box.Height = size
    box.Placement = App.Placement(App.Vector(x, y, z), App.Rotation())
    return box


def has_plane(found: Any, axis: int, position: float, sign: int) -> bool:
    return any(
        g.kind is GuideKind.PLANE
        and g.axis == axis
        and g.sign == sign
        and abs(g.position(axis) - position) < 1e-6
        for g in found
    )


def snapshot(bureau: Bureau) -> dict[str, dict[str, str]]:
    return {mark: bureau.expressions(mark) for mark in LAYOUT}


# --- B1 : guides lus dans le repère de la pièce -----------------------------------------------


def test_guides_des_voisins_dans_le_repere_de_la_piece(document: Any) -> None:
    part = api.make_wood_part(400, 100, 20, "chene", doc=document)
    neighbour(document, 400, 0, 0)
    document.recompute()
    found = guides_module.collect_guides(part, None)
    assert has_plane(found, 0, 400, -1)  # face de contact du voisin
    assert has_plane(found, 0, 410, 1)
    assert any(g.kind is GuideKind.LINE and g.axis == 2 for g in found)
    assert any(g.kind is GuideKind.POINT for g in found)
    assert len(found) == 6 + 12 + 8


def test_guides_d_une_piece_tournee(document: Any) -> None:
    part = api.make_wood_part(400, 100, 20, "chene", doc=document)
    part.Placement = App.Placement(App.Vector(1000, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    neighbour(document, 1000, 400, 0)  # son axe X (longueur) est l'axe Y du document
    document.recompute()
    assert has_plane(guides_module.collect_guides(part, None), 0, 400, -1)


def test_guides_exclus_et_conteneur(document: Any) -> None:
    container = document.addObject("App::Part", "Meuble")
    parts = build_parts(document, container)
    joint = api.make_dowels(parts.parts["JG"], parts.parts["V"])
    machined = machined_module.ensure_machined_part(parts.parts["V"])
    hidden = neighbour(document, 0, 0, 0)
    near = neighbour(document, 0, 0, 0)
    neighbour(document, 50, 0, 0)  # hors du conteneur
    for box in (hidden, near):
        container.addObject(box)
    hidden.Visibility = False
    document.recompute()
    found = guides_module.collect_guides(parts.parts["V"], container)
    assert machined.Visibility and joint.Visibility and not hidden.Visibility
    # Chaque cube visible apporte 26 guides (6 plans, 12 droites, 8 points) ; le cube masqué, la
    # pièce, sa usinée et son assemblage n'en apportent aucun.
    everywhere = guides_module.collect_guides(parts.parts["V"], None)
    near.Visibility = False
    without_near = guides_module.collect_guides(parts.parts["V"], container)
    assert (len(everywhere) - len(found), len(found) - len(without_near)) == (26, 26)
    for blank in (parts.parts["V"], machined):
        blank.Visibility = False
    assert guides_module.collect_guides(parts.parts["V"], container) == without_near


def test_guides_bornes_et_plus_proches_d_abord(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    part = api.make_wood_part(100, 100, 20, "chene", doc=document)
    neighbour(document, 5000, 0, 0)
    near = neighbour(document, 100, 0, 0)
    document.recompute()
    monkeypatch.setattr(guides_module, "MAX_GUIDES", 26)
    found = guides_module.collect_guides(part, None)
    assert len(found) == 26
    assert has_plane(found, 0, 100, -1)
    assert near.Visibility


# --- B2 : écriture de la brute, une pièce usinée renvoie à sa brute ---------------------------


def test_deplacer_et_redimensionner_la_brute(document: Any) -> None:
    blank = api.make_wood_part(400, 100, 20, "chene", doc=document)
    machined = machined_module.ensure_machined_part(blank)
    document.recompute()
    assert drag.raw_part(machined) == blank
    memento = drag.begin_drag(machined)
    assert memento.part == blank
    drag.move_part(memento, Vec3(50, 0, 0))
    drag.move_part(memento, Vec3(20, 0, 0))  # absolu par rapport au début : rien ne s'accumule
    assert blank.Placement.Base.x == 20
    assert machined.Placement.Base.x == 20
    drag.resize_part(memento, "Length", 300, Vec3(100, 0, 0))
    assert (blank.Length.Value, blank.Placement.Base.x) == (300, 100)
    assert blank.Shape.BoundBox.XLength == pytest.approx(300)
    assert drag.end_drag(memento) == []
    assert stale_or_invalid(document) == []
    assert machined.Shape.BoundBox.XMin == pytest.approx(100)


def test_assemblage_renvoie_a_la_piece_invitee(document: Any) -> None:
    parts = build_parts(document)
    joint = api.make_dowels(parts.parts["JG"], parts.parts["V"])
    assert drag.raw_part(joint) == parts.parts["V"]
    with pytest.raises(TypeError):
        drag.raw_part(document.addObject("Part::Box", "Autre"))


def test_echap_ramene_la_piece(document: Any) -> None:
    blank = api.make_wood_part(400, 100, 20, "chene", doc=document)
    memento = drag.begin_drag(blank)
    drag.move_part(memento, Vec3(50, 30, 0))
    drag.resize_part(memento, "Width", 60, Vec3(0, 40, 0))
    drag.restore(memento)
    assert blank.Placement.Base.y == 0
    assert (blank.Length.Value, blank.Width.Value) == (400, 100)


# --- B3 : membre d'ensemble, liaisons mises de côté puis ensemble relié -----------------------


def test_voile_glisse_de_100_mm(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    memento = drag.begin_drag(voile)
    for prop in ("Length", "Width", "Placement.Base.x", "Placement.Base.y"):
        assert prop not in bureau.expressions("V")  # mises de côté
    drag.move_part(memento, Vec3(0, 0, -100))  # l'axe Z de la pièce est l'axe -Y du document
    assert drag.end_drag(memento) == []
    assert bureau.expressions("V")["Placement.Base.y"] == (
        "<<Bureau>>.Origin.y + <<Bureau>>.Depth - 41 mm"
    )
    assert bureau.bounds("V")[1] == (541, 559)
    expected = {**EXPRESSIONS["V"], "Placement.Base.y": bureau.expressions("V")["Placement.Base.y"]}
    assert bureau.expressions("V") == expected
    assert bureau.furniture.Width.Value == 1200
    assert bureau.sizes("V")[0] == 1156
    assert {mark: bureau.expressions(mark) for mark in ("P", "JG", "JD")} == {
        mark: EXPRESSIONS[mark] for mark in ("P", "JG", "JD")
    }
    assert stale_or_invalid(bureau.doc) == []


def test_echap_retablit_les_liaisons(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    recorded = dict(voile.FurnitureBindings)
    memento = drag.begin_drag(voile)
    drag.move_part(memento, Vec3(0, 0, -100))
    drag.restore(memento)
    bureau.doc.recompute()
    assert snapshot(bureau) == EXPRESSIONS
    assert dict(voile.FurnitureBindings) == recorded
    assert bureau.bounds("V")[1] == (441, 459)


# --- B4 : formule de l'utilisateur ------------------------------------------------------------


def test_formule_de_l_utilisateur_fixe_l_axe(document: Any) -> None:
    blank = api.make_wood_part(400, 100, 20, "chene", doc=document)
    blank.setExpression("Placement.Base.x", "10 mm")
    blank.setExpression("Width", "80 mm")
    limits = drag.drag_limits(blank)
    assert limits.fixed_axes == frozenset({0})
    assert limits.resizable_axes == frozenset({2})  # X fixé, largeur pilotée : reste l'épaisseur
    memento = drag.begin_drag(blank)
    with pytest.raises(ValueError, match="piloté par une formule"):
        drag.move_part(memento, Vec3(5, 0, 0))
    drag.move_part(memento, Vec3(0, 5, 0))
    assert blank.Placement.Base.y == 5
    with pytest.raises(ValueError, match="ne peut pas être tirée"):
        drag.resize_part(memento, "Width", 50, Vec3(0, 0, 0))
    assert {path.lstrip("."): text for path, text in blank.ExpressionEngine} == {
        "Placement.Base.x": "10 mm",
        "Width": "80 mm",
    }


# --- B5 : pièce verrouillée -------------------------------------------------------------------


def test_piece_verrouillee_sans_poignees(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    assert drag.drag_limits(voile).resizable_axes == frozenset({0, 1, 2})  # chêne : massif
    assert drag.drag_limits(voile).fixed_axes == frozenset()
    api.set_member_options(voile, locked=True)
    limits = drag.drag_limits(voile)
    assert (limits.fixed_axes, limits.resizable_axes) == (frozenset(), frozenset())
    memento = drag.begin_drag(voile)
    with pytest.raises(ValueError, match="ne peut pas être tirée"):
        drag.resize_part(memento, "Length", 1000, Vec3(0, 0, 0))
    drag.move_part(memento, Vec3(0, 0, -100))  # le glissement reste permis
    assert drag.end_drag(memento) == []
    assert bureau.bounds("V")[1] == (541, 559)
    # Pièce en bois (#87, ShapedPart) : poignées refusées aussi, dans ``can_resize``.


# --- B5 bis : épaisseur du massif (Q4 amendée le 2026-10-26) ---------------------------------


def test_epaisseur_tirable_pour_le_massif_seulement(document: Any) -> None:
    """Massif : l'axe 2 est redimensionnable ; contreplaqué, MDF, mélaminé : l'épaisseur de la
    bibliothèque reste fixe, longueur et largeur se tirent toujours."""
    massif = api.make_wood_part(400, 100, 22, "chene", doc=document)
    assert drag.drag_limits(massif).resizable_axes == frozenset({0, 1, 2})
    for material, thickness in (("cp-bouleau", 18), ("mdf", 19), ("melamine-blanc", 19)):
        panneau = api.make_wood_part(400, 100, thickness, material, doc=document)
        assert drag.drag_limits(panneau).resizable_axes == frozenset({0, 1}), material
        memento = drag.begin_drag(panneau)
        with pytest.raises(ValueError, match="ne peut pas être tirée"):
            drag.resize_part(memento, "Thickness", thickness + 5, Vec3(0, 0, 0))
        assert panneau.Thickness.Value == thickness
    wood_part_module.set_material(massif, "mdf")  # la famille suit le matériau
    assert drag.drag_limits(massif).resizable_axes == frozenset({0, 1})


def test_epaisseur_sans_poignee_si_formule_ou_verrou(document: Any) -> None:
    """Même règle que Length et Width : formule de l'utilisateur sur ``Thickness`` ou sur la
    position en Z, pièce verrouillée : pas de poignée d'épaisseur."""
    driven = api.make_wood_part(400, 100, 22, "chene", doc=document)
    driven.setExpression("Thickness", "25 mm")
    assert drag.drag_limits(driven).resizable_axes == frozenset({0, 1})
    raised = api.make_wood_part(400, 100, 22, "chene", doc=document)
    raised.setExpression("Placement.Base.z", "10 mm")
    limits = drag.drag_limits(raised)
    assert (limits.fixed_axes, limits.resizable_axes) == (frozenset({2}), frozenset({0, 1}))


def test_epaisseur_tiree_puis_echap(document: Any) -> None:
    """Hors ensemble : l'épaisseur s'écrit sur la brute (poignée de début : l'origine suit),
    le relâchement la garde, Échap la rétablit."""
    blank = api.make_wood_part(400, 100, 20, "chene", doc=document)
    memento = drag.begin_drag(blank)
    drag.resize_part(memento, "Thickness", 35, Vec3(0, 0, -15))
    assert (blank.Thickness.Value, blank.Placement.Base.z) == (35, -15)
    assert blank.Shape.BoundBox.ZLength == pytest.approx(35)
    drag.restore(memento)
    assert (blank.Thickness.Value, blank.Placement.Base.z) == (20, 0)
    memento = drag.begin_drag(blank)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert drag.end_drag(memento) == []
    assert blank.Thickness.Value == 30
    assert stale_or_invalid(document) == []


def thickness_after(doc_name: str, change: Any) -> tuple[Any, dict[str, Any]]:
    """Bureau de référence neuf dans un second document, puis ``change(bureau)`` ; renvoie le
    bureau et ce qui permet de le comparer (expressions, étendues et cotes de chaque pièce)."""
    from tests.integration.bureau import build_desk

    bureau = build_desk(App.newDocument(doc_name))
    change(bureau)
    bureau.doc.recompute()
    state = {
        mark: (bureau.expressions(mark), bureau.bounds(mark), bureau.sizes(mark)) for mark in LAYOUT
    }
    return bureau, state


def dragged_thickness(mark: str, value: float, shift: Any) -> Any:
    """Changement : l'épaisseur de la pièce ``mark`` tirée à ``value`` (origine décalée de
    ``shift``) puis relâchée."""

    def change(bureau: Bureau) -> None:
        memento = drag.begin_drag(bureau.parts[mark])
        drag.resize_part(memento, "Thickness", value, shift)
        assert drag.end_drag(memento) == []

    return change


@pytest.mark.parametrize("shift", [Vec3(0, 0, 0), Vec3(0, 0, -3)], ids=["fin", "debut"])
def test_epaisseur_tiree_comme_saisie_dans_le_panneau(shift: Any) -> None:
    """Membre d'ensemble en massif : l'épaisseur tirée est gardée et la rangée recalculée, comme
    pour ``set_member_thickness`` (la saisie du panneau), quelle que soit la face tirée."""
    from freecad.menuiserie.features.furniture_locks import set_member_thickness

    _, typed = thickness_after(
        "TestPieceDeBoisSaisie", lambda b: set_member_thickness(b.parts["JG"], 25.0)
    )
    dragged, state = thickness_after("TestPieceDeBoisTiree", dragged_thickness("JG", 25.0, shift))
    assert state == typed
    assert dragged.parts["JG"].Thickness.Value == 25
    assert dragged.sizes("V")[0] == 1153  # le voile absorbe les 3 mm
    assert "Thickness" not in dragged.expressions("JG")
    assert stale_or_invalid(dragged.doc) == []


def test_epaisseur_tiree_echap_retablit_l_ensemble(bureau: Bureau) -> None:
    joue = bureau.parts["JG"]
    memento = drag.begin_drag(joue)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, -3))
    drag.restore(memento)
    bureau.doc.recompute()
    assert joue.Thickness.Value == 22
    assert snapshot(bureau) == EXPRESSIONS
    assert bureau.bounds("JG")[0] == (0, 22)
    assert bureau.sizes("V")[0] == 1156


def test_epaisseur_tiree_refusee_par_la_rangee_bloquee(bureau: Bureau) -> None:
    """Le voile verrouillé ne peut plus absorber : le relâchement est refusé, la joue revient."""
    api.set_member_options(bureau.parts["V"], locked=True)
    before = {mark: bureau.sizes(mark) for mark in LAYOUT}
    memento = drag.begin_drag(bureau.parts["JG"])
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    with pytest.raises(api.LockedPiecesError):
        drag.end_drag(memento)
    bureau.doc.recompute()
    assert bureau.parts["JG"].Thickness.Value == 22
    assert {mark: bureau.sizes(mark) for mark in LAYOUT} == before
    assert snapshot(bureau)["JG"] == EXPRESSIONS["JG"]


# --- B6 : Distance gardée ---------------------------------------------------------------------


def test_la_distance_gardee_suit_le_glissement(bureau: Bureau) -> None:
    """Q8 : au relâchement, la ``Value`` de la Distance prend la distance nouvelle ; Échap la
    rétablit."""
    side = api.PickedElement(
        bureau.parts["JG"], element_name(bureau.parts["JG"], "Face", (11, 280, 0))
    )
    web = api.PickedElement(
        bureau.parts["V"], element_name(bureau.parts["V"], "Face", (600, 450, 320))
    )
    api.set_distance(side, web, 320, keep=True)
    [distance] = [o for o in bureau.doc.Objects if o.Name.startswith("Distance")]
    voile = bureau.parts["V"]
    memento = drag.begin_drag(voile)
    drag.move_part(memento, Vec3(0, -40, 0))  # Y local du voile = Z : il descend de 40 mm
    drag.restore(memento)
    assert distance.Value.Value == pytest.approx(320)
    memento = drag.begin_drag(voile)
    drag.move_part(memento, Vec3(0, -40, 0))
    drag.end_drag(memento)
    assert distance.Value.Value == pytest.approx(280)
    assert bureau.bounds("V")[2] == (280, 680)
    assert bureau.expressions("V")["Placement.Base.z"] == "<<Bureau>>.Origin.z + Distance.Value"


# --- B7 : assemblage qui ne touche plus -------------------------------------------------------


def test_assemblage_qui_ne_touche_plus(document: Any) -> None:
    parts = build_parts(document)
    api.make_dowels(parts.parts["JG"], parts.parts["V"])
    document.recompute()
    voile = parts.parts["V"]
    memento = drag.begin_drag(voile)
    drag.move_part(memento, Vec3(60, 0, 0))
    warnings = drag.end_drag(memento)
    assert voile.Placement.Base.x == 82  # le glissement est gardé
    assert len(warnings) == 1
    assert "ne touche plus" in warnings[0]
    assert "ne se touchent pas" in warnings[0]


def test_assemblage_qui_touche_encore(document: Any) -> None:
    parts = build_parts(document)
    api.make_dowels(parts.parts["JG"], parts.parts["V"])
    document.recompute()
    memento = drag.begin_drag(parts.parts["V"])
    drag.move_part(memento, Vec3(0, 0, -100))
    assert drag.end_drag(memento) == []


def test_poignee_sur_une_piece_dont_l_assemblage_ne_tient_plus(document: Any) -> None:
    """Recette de jv : tant que l'assemblage ne tient plus, la poignée ne recalcule pas la pièce
    usinée (son ``execute()`` lèverait à chaque image, avec sa trace) ; le relâchement recalcule le
    document une fois et prévient (B7)."""
    parts = build_parts(document)
    api.make_dowels(parts.parts["JG"], parts.parts["V"])
    document.recompute()
    voile = parts.parts["V"]
    machined = machined_module.machined_part_of(voile)
    memento = drag.begin_drag(voile)
    drag.move_part(memento, Vec3(60, 0, 0))
    drag.resize_part(memento, "Length", voile.Length.Value - 10, Vec3(0, 0, 0))
    assert "Invalid" not in machined.State
    assert any("ne touche plus" in warning for warning in drag.end_drag(memento))
