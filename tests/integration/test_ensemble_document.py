# SPDX-License-Identifier: LGPL-2.1-or-later
"""L'ensemble dans le document : création, suivi des cotes, options (J4b', N1 à N7, B5, D7, A6)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.bureau import EXPRESSIONS, LAYOUT, Bureau, build_desk, build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import DOVETAIL, HALF_LAP, MITER, blanks

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

EDGES = ("Left", "Right", "Front", "Back", "Bottom", "Top")
DEFAULT_FIXED = {  # tableau de référence (§ 3)
    "P": {"Left", "Right", "Front", "Back", "Top"},
    "JG": {"Left", "Front", "Back", "Bottom", "Top"},
    "JD": {"Right", "Front", "Back", "Bottom", "Top"},
    "V": {"Left", "Right", "Back", "Bottom", "Top"},
}


def fixed(part: Any) -> set[str]:
    return {edge for edge in EDGES if getattr(part, f"Fixed{edge}")}


def volumes(bureau: Bureau) -> dict[str, float]:
    return {mark: round(float(bureau.shown(mark).Shape.Volume), 3) for mark in LAYOUT}


# --- N1 : création --------------------------------------------------------------------------


def test_creation_du_bureau(document: Any) -> None:
    bureau = build_parts(document)
    reference = volumes(bureau)
    furniture, notices = api.make_furniture(list(bureau.parts.values()), label="Bureau")
    assert (furniture.Name, furniture.Label) == ("Furniture", "Bureau")
    assert furniture.TypeId == "App::FeaturePython"
    sizes = [furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value]
    assert sizes == pytest.approx([1200, 600, 750])
    assert tuple(furniture.Origin) == pytest.approx((0, 0, 0))
    for mark, part in bureau.parts.items():
        assert part.Furniture == furniture
        assert part.PositionMode == "Stay"
        assert fixed(part) == DEFAULT_FIXED[mark], mark
        assert bureau.expressions(mark) == EXPRESSIONS[mark], mark
        assert dict(part.FurnitureBindings) == EXPRESSIONS[mark], mark
    assert volumes(bureau) == reference
    assert stale_or_invalid(document) == []
    assert notices == ()


def test_creation_depuis_les_pieces_usinees(bureau: Bureau) -> None:
    for mark in ("JG", "V"):
        machined = api.machined_part_of(bureau.parts[mark])
        assert "Furniture" not in machined.PropertiesList
        assert api.furniture_of(machined) == bureau.furniture
    assert bureau.dowel_counts() == [4, 4]
    assert stale_or_invalid(bureau.doc) == []


# --- N2 : propriétés ------------------------------------------------------------------------

FURNITURE_SPECS = {
    "Width": ("App::PropertyLength", [], "Largeur de l'ensemble (axe X de son repère)."),
    "Depth": ("App::PropertyLength", [], "Profondeur de l'ensemble (axe Y)."),
    "Height": ("App::PropertyLength", [], "Hauteur de l'ensemble (axe Z)."),
    "Origin": ("App::PropertyVectorDistance", ["ReadOnly"], "Coin de départ de l'ensemble"),
    "Template": ("App::PropertyString", ["ReadOnly"], "Gabarit qui a créé l'ensemble"),
}
MEMBER_SPECS = {
    "Furniture": ("App::PropertyLink", ["ReadOnly"], "Ensemble dont la pièce suit les cotes."),
    "PositionMode": ("App::PropertyEnumeration", [], "Faces dont la distance au bord n'est pas"),
    "FixedLeft": ("App::PropertyBool", [], "Distance fixe au bord gauche de l'ensemble"),
    "FixedRight": ("App::PropertyBool", [], "Distance fixe au bord droit"),
    "FixedFront": ("App::PropertyBool", [], "Distance fixe au bord avant."),
    "FixedBack": ("App::PropertyBool", [], "Distance fixe au bord arrière"),
    "FixedBottom": ("App::PropertyBool", [], "Distance fixe au bas de l'ensemble."),
    "FixedTop": ("App::PropertyBool", [], "Distance fixe au haut de l'ensemble"),
    "Locked": ("App::PropertyBool", [], "Cotes fixes : la pièce ne change pas de cotes"),
    "FurnitureBindings": ("App::PropertyMap", ["Hidden"], "Expressions posées par l'atelier"),
}


def assert_specs(obj: Any, specs: dict[str, tuple[str, list[str], str]]) -> None:
    for name, (type_id, mode, tooltip) in specs.items():
        assert obj.getTypeIdOfProperty(name) == type_id, name
        assert obj.getGroupOfProperty(name) == "Ensemble", name
        assert obj.getEditorMode(name) == mode, name
        assert obj.getDocumentationOfProperty(name).startswith(tooltip), name


def test_proprietes_de_l_ensemble_et_des_membres(bureau: Bureau) -> None:
    furniture = bureau.furniture
    assert_specs(furniture, FURNITURE_SPECS)
    assert furniture.Template == ""
    assert furniture.Version == 1
    assert furniture.getEditorMode("Version") == ["Hidden"]
    assert furniture.getGroupOfProperty("Version") == "Base"
    joue = bureau.parts["JG"]
    assert_specs(joue, MEMBER_SPECS)
    assert joue.getEnumerationsOfProperty("PositionMode") == ["Stay", "Proportional"]
    assert joue.Locked is False
    assert joue.Version == 2


def test_piece_hors_ensemble_sans_propriete_ajoutee(document: Any) -> None:
    alone = api.make_wood_part(doc=document)
    names = set(alone.PropertiesList)
    build_desk(document)
    assert set(alone.PropertiesList) == names
    assert api.furniture_of(alone) is None


# --- N3 : le bureau suit ------------------------------------------------------------------


def test_le_bureau_suit_la_profondeur(bureau: Bureau) -> None:
    bureau.furniture.Depth = 800
    bureau.doc.recompute()
    assert bureau.sizes("P") == (1200, 800, 30)
    assert bureau.sizes("JG") == bureau.sizes("JD") == (720, 760, 22)
    assert bureau.bounds("V")[1] == (641, 659)
    assert stale_or_invalid(bureau.doc) == []


def test_le_bureau_suit_la_hauteur_et_la_largeur(bureau: Bureau) -> None:
    bureau.furniture.Height = 800
    bureau.doc.recompute()
    assert bureau.bounds("P")[2] == (770, 800)
    assert bureau.sizes("JG")[0] == bureau.sizes("JD")[0] == 770
    assert bureau.sizes("V")[:2] == (1156, 450)
    assert bureau.dowel_counts() == [5, 5]
    bureau.furniture.Width = 1400
    bureau.doc.recompute()
    assert bureau.sizes("P")[0] == 1400
    assert bureau.bounds("JD")[0] == (1378, 1400)
    assert bureau.sizes("V")[0] == 1356
    assert stale_or_invalid(bureau.doc) == []


def test_joues_qui_restent_en_place(bureau: Bureau) -> None:
    for mark in ("JG", "JD"):
        assert api.set_member_options(bureau.parts[mark], fixed={"Back": False}) == ()
    # Le voile, qui suit le fond par défaut, perdrait ses tourillons : refus d'avance.
    with pytest.raises(ValueError, match="« Joue gauche » et « Voile » ne seraient plus"):
        api.resize_furniture(bureau.furniture, depth=800)
    api.set_member_options(bureau.parts["V"], fixed={"Back": False})
    api.resize_furniture(bureau.furniture, depth=800)
    assert bureau.sizes("P")[1] == 800
    assert bureau.sizes("JG")[1] == bureau.sizes("JD")[1] == 560
    assert bureau.bounds("V")[1] == (441, 459)
    assert stale_or_invalid(bureau.doc) == []


# --- N4 : option dans l'éditeur de propriétés -----------------------------------------------


def test_option_changee_dans_l_editeur(bureau: Bureau) -> None:
    doc, joue = bureau.doc, bureau.parts["JG"]
    doc.UndoMode = 1
    before = bureau.expressions("JD")
    doc.openTransaction("Modifier FixedBack")
    joue.FixedBack = False
    doc.commitTransaction()
    without_width = {k: v for k, v in EXPRESSIONS["JG"].items() if k != "Width"}
    assert bureau.expressions("JG") == without_width
    assert dict(joue.FurnitureBindings) == without_width
    assert bureau.expressions("JD") == before
    doc.recompute()
    assert bureau.sizes("JG")[1] == 560
    doc.undo()
    assert joue.FixedBack is True
    assert bureau.expressions("JG") == EXPRESSIONS["JG"]
    assert dict(joue.FurnitureBindings) == EXPRESSIONS["JG"]
    doc.redo()
    assert bureau.expressions("JG") == without_width
    joue.FixedBack = True
    assert bureau.expressions("JG") == EXPRESSIONS["JG"]


def test_mode_proportion_dans_l_editeur(bureau: Bureau) -> None:
    doc, voile = bureau.doc, bureau.parts["V"]
    voile.FixedBack = False
    # Le voile garde sa place : l'origine locale est à son bord arrière, 441 + son épaisseur.
    stays = "<<Bureau>>.Origin.y + Thickness + 441 mm"
    assert bureau.expressions("V")["Placement.Base.y"] == stays
    voile.PositionMode = "Proportional"
    expected = "<<Bureau>>.Origin.y + <<Bureau>>.Depth * 0.757731959 + Thickness * 0.242268041"
    assert bureau.expressions("V")["Placement.Base.y"] == expected
    bureau.furniture.Depth = 800
    doc.recompute()
    # Les deux écarts gardent leur proportion : 441 x 782 / 582.
    assert bureau.bounds("V")[1] == pytest.approx((592.546, 610.546), abs=2e-3)
    voile.PositionMode = "Stay"
    assert bureau.expressions("V")["Placement.Base.y"] == (
        "<<Bureau>>.Origin.y + Thickness + 592.546392 mm"
    )
    doc.recompute()
    assert bureau.bounds("V")[1] == pytest.approx((592.546, 610.546), abs=2e-3)
    assert stale_or_invalid(doc) == []


# --- N5 : formule et contrainte de l'utilisateur ----------------------------------------------


def test_formule_de_l_utilisateur_gardee(document: Any, vue_rapport: Any) -> None:
    bureau = build_parts(document)
    voile = bureau.parts["V"]
    formula = "<<Plateau>>.Width - 141 mm"
    voile.setExpression("Placement.Base.y", formula)
    furniture, notices = api.make_furniture(list(bureau.parts.values()), label="Bureau")
    warning = "« Voile » : Placement.Base.y suit une formule ou une contrainte de l'utilisateur"
    assert [text for text in notices if text.startswith(warning)]
    assert any(warning in text for text in vue_rapport.de_niveau("Warning"))
    assert bureau.expressions("V")["Placement.Base.y"] == formula
    assert "Placement.Base.y" not in voile.FurnitureBindings
    vue_rapport.messages.clear()
    furniture.Depth = 800
    document.recompute()
    assert bureau.bounds("V")[1] == (641, 659)
    assert any(warning in text for text in vue_rapport.de_niveau("Warning"))
    for options in ({"mode": "Proportional"}, {"fixed": {"Back": True}}):
        assert any(text.startswith(warning) for text in api.set_member_options(voile, **options))
        assert bureau.expressions("V")["Placement.Base.y"] == formula


def test_contrainte_de_l_atelier_assembly(document: Any) -> None:
    bureau = build_parts(document)
    group = document.addObject("Assembly::JointGroup", "Joints")
    joint = document.addObject("App::FeaturePython", "Joint")
    joint.addProperty("App::PropertyXLinkSub", "Reference1")
    joint.Reference1 = (bureau.parts["V"], [""])
    group.addObject(joint)
    _, notices = api.make_furniture(list(bureau.parts.values()), label="Bureau")
    assert any(text.startswith("« Voile » : Placement suit une formule") for text in notices)
    assert not any(path.startswith("Placement") for path in bureau.expressions("V"))


# --- N6 : assemblages J3 -----------------------------------------------------------------------


def test_assemblages_et_pieces_usinees_suivent(bureau: Bureau) -> None:
    for changes, counts in (({"Depth": 800}, [4, 4]), ({"Height": 800}, [5, 5])):
        for name, value in changes.items():
            setattr(bureau.furniture, name, value)
        bureau.doc.recompute()
        assert bureau.dowel_counts() == counts
        for mark in ("JG", "JD", "V"):
            machined = api.machined_part_of(bureau.parts[mark])
            assert machined.isValid()
            assert len(machined.Shape.Solids) == 1
            assert "Furniture" not in machined.PropertiesList
        assert stale_or_invalid(bureau.doc) == []


def test_deplacer_une_piece_usinee_liee_est_refuse(bureau: Bureau, vue_rapport: Any) -> None:
    machined, blank = api.machined_part_of(bureau.parts["V"]), bureau.parts["V"]
    before = App.Placement(blank.Placement)
    moved = App.Placement(machined.Placement)
    moved.Base.y = 300
    machined.Placement = moved
    assert blank.Placement == before
    warnings = vue_rapport.de_niveau("Warning")
    assert any("« Voile » est placée par une expression (Placement.Base." in w for w in warnings)
    bureau.doc.recompute()
    assert machined.Placement == before
    assert stale_or_invalid(bureau.doc) == []


# --- N7 : refus et cote qui casse une pièce -------------------------------------------------


def test_redimensionnement_refuse(bureau: Bureau) -> None:
    doc = bureau.doc
    engines = {mark: bureau.expressions(mark) for mark in LAYOUT}
    with pytest.raises(ValueError, match="« Joue gauche » deviendrait trop petite : Width"):
        api.resize_furniture(bureau.furniture, depth=30)
    assert bureau.furniture.Depth.Value == 600
    assert {mark: bureau.expressions(mark) for mark in LAYOUT} == engines
    assert not doc.HasPendingTransaction
    with pytest.raises(ValueError, match="« Voile » deviendrait trop petite : Width = 0,05 mm"):
        api.resize_furniture(bureau.furniture, height=350.05)
    api.resize_furniture(bureau.furniture, depth=800, height=800)
    assert bureau.sizes("JG")[:2] == (770, 760)
    assert stale_or_invalid(doc) == []


def test_cote_qui_casse_une_piece_appliquee(bureau: Bureau, vue_rapport: Any) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    doc.openTransaction("Profondeur")
    bureau.furniture.Depth = 30
    doc.commitTransaction()
    assert bureau.furniture.Depth.Value == 30
    warnings = vue_rapport.de_niveau("Warning")
    assert any("« Joue gauche » deviendrait trop petite" in text for text in warnings)
    doc.recompute()
    assert stale_or_invalid(doc) != []
    for mark in ("JG", "JD"):
        shown = bureau.shown(mark)
        assert not shown.isValid() or shown.Shape.Volume == pytest.approx(720 * 560 * 22, rel=0.1)
    doc.undo()
    doc.recompute()
    assert bureau.furniture.Depth.Value == 600
    assert bureau.sizes("JG") == (720, 560, 22)
    assert stale_or_invalid(doc) == []


# --- B5 : mi-bois dans un ensemble -------------------------------------------------------------


def test_croix_a_mi_bois_qui_suit_la_largeur(document: Any) -> None:
    host, guest = blanks(document, HALF_LAP, frame=App.Placement())
    api.make_half_lap(host, guest)
    furniture, _ = api.make_furniture([host, guest], label="Cadre")
    assert tuple(furniture.Origin) == pytest.approx((0, -270, 0))
    api.set_member_options(guest, mode="Proportional", fixed={"Left": False, "Right": False})
    furniture.Width = 800
    document.recompute()
    cut = 80 * 60 * 11
    machined = [api.machined_part_of(part) for part in (host, guest)]
    assert [m.Shape.Volume for m in machined] == pytest.approx(
        [800 * 60 * 22 - cut, 600 * 80 * 22 - cut]
    )
    assert guest.Shape.BoundBox.XMin == pytest.approx(360)
    assert all(len(m.Shape.Solids) == 1 for m in machined)
    assert stale_or_invalid(document) == []


# --- D7 : queue d'aronde dans un ensemble ------------------------------------------------------


def test_tiroir_a_queues_d_aronde_qui_suit_la_hauteur(document: Any) -> None:
    """Façade à plat et côté debout (150 mm selon Y) : la hauteur du tiroir est la cote Y."""
    host, guest = blanks(document, DOVETAIL, frame=App.Placement())
    joint = api.make_dovetail(host, guest)
    furniture, notices = api.make_furniture([host, guest], label="Tiroir")
    assert notices == ()
    assert furniture.Depth.Value == pytest.approx(150)
    api.resize_furniture(furniture, depth=200)
    assert host.Width.Value == guest.Width.Value == pytest.approx(200)
    tails = (
        4 * ((200 - 5 * 6) / 4 - 18 * math.tan(math.radians(10))) * 18 * 18
    )  # 4 queues automatiques
    blank = 400 * 200 * 18
    machined = [api.machined_part_of(part) for part in (host, guest)]
    assert [m.Shape.Volume for m in machined] == pytest.approx([blank - tails, blank + tails])
    assert joint.TailCount == 0
    assert all(len(m.Shape.Solids) == 1 for m in machined)
    assert stale_or_invalid(document) == []


# --- A6 : onglet dans un ensemble --------------------------------------------------------------


def test_cadre_a_onglets_qui_suit_les_cotes(document: Any) -> None:
    """Angle à onglet : chaque traverse s'allonge avec l'ensemble (bords touchés fixes), un
    seul recalcul, onglets toujours jointifs."""
    host, guest = blanks(document, MITER, frame=App.Placement())
    api.make_miter(host, guest)
    furniture, notices = api.make_furniture([host, guest], label="Cadre")
    assert notices == ()
    assert (furniture.Width.Value, furniture.Depth.Value) == pytest.approx((500, 500))
    api.set_member_options(host, fixed={"Back": False})  # la traverse ne touche que l'avant
    api.set_member_options(guest, fixed={"Right": False})  # ... et celle-ci que la gauche
    api.resize_furniture(furniture, width=700, depth=700)
    assert (host.Length.Value, guest.Length.Value) == pytest.approx((700, 700))
    assert (host.Width.Value, guest.Width.Value) == pytest.approx((84, 84))
    machined = [api.machined_part_of(part) for part in (host, guest)]
    cut = 84 * 84 * 20 / 2  # les largeurs suivent la rangée : 60 x 700 / 500 = 84
    assert [m.Shape.Volume for m in machined] == pytest.approx(
        [700 * 84 * 20 - cut, 700 * 84 * 20 - cut]
    )
    assert machined[0].Shape.common(machined[1].Shape).Volume == pytest.approx(0, abs=1e-6)
    assert all(len(m.Shape.Solids) == 1 for m in machined)
    assert stale_or_invalid(document) == []


# --- ADR 0017 : avertissements renvoyés par l'API de l'ensemble -----------------------------------


def test_redimensionner_et_retirer_renvoient_leurs_avertissements(
    bureau: Bureau, vue_rapport: Any
) -> None:
    """Comme les autres fonctions de l'ensemble : tuple d'avertissements traduits, ceux-là
    mêmes qui sont écrits dans la vue rapport."""
    messages = api.resize_furniture(bureau.furniture, depth=800, height=800)
    assert isinstance(messages, tuple)
    warnings = vue_rapport.de_niveau("Warning")
    assert all(any(message in text for text in warnings) for message in messages)
    assert api.remove_from_furniture([bureau.parts["P"]]) == ()
