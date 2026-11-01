# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profils d'arête dans un vrai document (issue #5, CH-b, ADR 0029 : B1 à B9)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import Cadre

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
machined_part = pytest.importorskip("freecad.menuiserie.features.machined_part")

Reopen = Callable[[Any], Any]
BOARD_VOLUME = 800.0 * 200.0 * 22.0
LENGTH = 800.0


def machined_of(blank: Any) -> Any:
    return api.machined_part_of(blank)


# --- B1, B2, B4 : création et usinage -----------------------------------------------------


def test_un_chanfrein_retire_la_section_balayee(document: Any, board: Any) -> None:
    blank = board(document)
    profile, warnings = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 4.0)
    assert warnings == ()
    assert profile.Edges == ["Z+Y-"]
    assert (profile.Family, profile.SizeA.Value, profile.SizeB.Value) == ("Chamfer", 5.0, 4.0)
    assert profile.Shape.isNull() or not profile.Shape.Solids  # forme vide (B1)
    machined = machined_of(blank)
    assert machined.Finishes == [profile]
    assert machined.Version == 2
    assert machined.Shape.isValid()
    assert machined.Shape.Volume == pytest.approx(BOARD_VOLUME - 5.0 * 4.0 / 2 * LENGTH, rel=1e-6)
    assert not blank.Visibility  # brute masquée sous sa pièce usinée


@pytest.mark.parametrize(
    ("family", "a", "b", "area"),
    [
        ("Round", 5.0, 0.0, (1 - math.pi / 4) * 25.0),
        ("Cove", 4.0, 0.0, math.pi / 4 * 16.0),
        ("Bullnose", 5.0, 0.0, (1 - math.pi / 4) * 25.0),
        ("Beak", 4.0, 3.0, 4.0 * 3.0 + (1 - math.pi / 4) * 16.0),
        ("Ogee", 8.0, 6.0, 24.0),
    ],
)
def test_chaque_famille_retire_son_aire(
    document: Any, board: Any, family: str, a: float, b: float, area: float
) -> None:
    blank = board(document)
    api.add_edge_profile(blank, ["Z+Y-"], family, a, b)
    removed = BOARD_VOLUME - machined_of(blank).Shape.Volume
    assert removed == pytest.approx(area * LENGTH, rel=1e-4)


def test_les_quatre_aretes_du_dessus(document: Any, board: Any) -> None:
    blank = board(document)
    api.add_edge_profile(blank, [e.code for e in api_edges("Z+")], "Chamfer", 2.0)
    shape = machined_of(blank).Shape
    assert shape.isValid()
    assert len(shape.Solids) == 1
    # Chanfreins de 2 mm (aire 2 mm²) au pourtour du dessus (2 x 800 + 2 x 200 mm de long) ; les
    # recouvrements aux quatre coins sont négligeables (quelques mm³).
    assert BOARD_VOLUME - shape.Volume == pytest.approx(2.0 * 2000.0, rel=0.02)


def api_edges(face: str) -> Any:
    from freecad.menuiserie.core.edges import loop_edges

    return loop_edges(face)


def test_l_arete_cassee_est_un_quart_de_rond_de_1_mm(document: Any, board: Any) -> None:
    blank = board(document)
    api.add_edge_profile(blank, ["Z+Y-"], "Round", 1.0)
    removed = BOARD_VOLUME - machined_of(blank).Shape.Volume
    assert removed == pytest.approx((1 - math.pi / 4) * LENGTH, rel=1e-4)


def test_le_profil_suit_les_cotes_de_la_piece(document: Any, board: Any) -> None:
    blank = board(document)
    api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    blank.Length = 1000.0
    document.recompute()
    removed = 1000.0 * 200.0 * 22.0 - machined_of(blank).Shape.Volume
    assert removed == pytest.approx(12.5 * 1000.0, rel=1e-6)


def test_le_profil_garde_son_choix_quand_la_piece_tourne(document: Any, board: Any) -> None:
    blank = board(document)
    api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    blank.Placement = App.Placement(App.Vector(10, 20, 30), App.Rotation(App.Vector(0, 0, 1), 90))
    document.recompute()
    machined = machined_of(blank)
    assert machined.Placement.isSame(blank.Placement, 1e-6)
    assert machined.Shape.Volume == pytest.approx(BOARD_VOLUME - 12.5 * LENGTH, rel=1e-6)


# --- B3 : assemblages -----------------------------------------------------------------------


def test_un_profil_loin_de_l_assemblage_n_avertit_pas(cadre_assemble: Cadre) -> None:
    host = cadre_assemble.parts["M1"]
    before = cadre_assemble.volume("M1")
    _, warnings = api.add_edge_profile(host, ["Z+Y-"], "Chamfer", 2.0, 2.0)
    assert warnings == ()
    assert cadre_assemble.volume("M1") == pytest.approx(before - 2.0 * 600.0, rel=1e-4)
    assert cadre_assemble.machined("M1").Shape.isValid()


def test_le_tenon_garde_ses_aretes_vives(cadre_assemble: Cadre) -> None:
    """Un profil sur le bout de T1 ne touche pas le tenon, ajouté après (B2)."""
    guest = cadre_assemble.parts["T1"]
    tenon_volume = cadre_assemble.volume("T1") - 280.0 * 60.0 * 22.0
    api.add_edge_profile(guest, ["Z+X-", "Z+X+"], "Chamfer", 3.0, 3.0)
    removed = 280.0 * 60.0 * 22.0 + tenon_volume - cadre_assemble.volume("T1")
    assert removed == pytest.approx(2 * 4.5 * 60.0, rel=1e-3)


# --- B5, B7, B9 : refus et API ---------------------------------------------------------------


def test_pieces_en_bois_refusees(document: Any) -> None:
    box = document.addObject("Part::Box", "Boite")
    document.recompute()
    shaped = api.make_shaped_part(box)
    with pytest.raises(ValueError, match="pièce en bois"):
        api.add_edge_profile(shaped, ["Z+Y-"], "Chamfer", 1.0)
    assert not [o for o in document.Objects if o.Name.startswith("EdgeProfile")]


@pytest.mark.parametrize("edges", [[], ["A+B-"], ["Z+Y-", "Z+Y-"], "Z+Y-", None])
def test_aretes_refusees_avant_toute_creation(document: Any, board: Any, edges: Any) -> None:
    blank = board(document)
    count = len(document.Objects)
    with pytest.raises(ValueError, match=r"[Aa]rête"):
        api.add_edge_profile(blank, edges, "Chamfer", 1.0)
    assert len(document.Objects) == count
    assert machined_of(blank) is None


def test_cote_trop_grande_refusee_avec_la_piece_citee(document: Any, board: Any) -> None:
    blank = board(document)
    blank.Label = "Planche"
    with pytest.raises(ValueError, match="Planche") as error:
        api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 12.0)
    assert "dessus-avant" in str(error.value)
    assert machined_of(blank) is None


def test_famille_inconnue_refusee(document: Any, board: Any) -> None:
    blank = board(document)
    with pytest.raises(ValueError, match="Spline"):
        api.add_edge_profile(blank, ["Z+Y-"], "Spline", 1.0)


def test_une_arete_a_un_seul_profil(document: Any, board: Any) -> None:
    blank = board(document)
    first, _ = api.add_edge_profile(blank, ["Z+Y-", "Z+Y+"], "Chamfer", 2.0)
    with pytest.raises(ValueError, match="Z\\+Y-"):
        api.add_edge_profile(blank, ["Z+Y-"], "Round", 3.0)
    second, _ = api.add_edge_profile(blank, ["Z+Y-"], "Round", 3.0, replace=True)
    assert first.Edges == ["Z+Y+"]
    assert second.Edges == ["Z+Y-"]
    assert api.edge_profiles_of(blank) == [first, second]
    api.add_edge_profile(blank, ["Z+Y+"], "Round", 3.0, replace=True)
    with pytest.raises(ReferenceError):  # plus aucune arête : profil supprimé
        _ = first.Name


def test_profils_d_une_piece_usinee(document: Any, board: Any) -> None:
    blank = board(document)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 2.0)
    machined = machined_of(blank)
    assert api.edge_profiles_of(machined) == [profile]
    other, _ = api.add_edge_profile(machined, ["Z-Y-"], "Chamfer", 2.0)
    assert api.edge_profiles_of(blank) == [profile, other]


# --- B4 : suppression ------------------------------------------------------------------------


def test_supprimer_le_dernier_profil_supprime_la_piece_usinee(document: Any, board: Any) -> None:
    blank = board(document)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 2.0)
    assert api.remove_edge_profile(profile) == ()
    assert machined_of(blank) is None
    assert blank.Visibility


def test_la_piece_usinee_reste_avec_ses_assemblages(cadre_assemble: Cadre) -> None:
    host = cadre_assemble.parts["M1"]
    before = cadre_assemble.volume("M1")
    profile, _ = api.add_edge_profile(host, ["Z+Y-"], "Chamfer", 2.0)
    api.remove_edge_profile(profile)
    assert cadre_assemble.machined("M1") is not None
    assert cadre_assemble.volume("M1") == pytest.approx(before, rel=1e-9)


def test_la_piece_usinee_reste_avec_un_profil_quand_l_assemblage_part(cadre: Any) -> None:
    host, guest = cadre.parts["M1"], cadre.parts["T1"]
    joint = api.make_mortise_tenon(host, guest)
    api.add_edge_profile(host, ["Z+Y-"], "Chamfer", 2.0)
    from freecad.menuiserie.features.drag_joints import remove_joints

    remove_joints([joint])
    cadre.doc.recompute()
    assert machined_of(host) is not None
    assert machined_of(guest) is None


def test_supprimer_la_piece_usinee_supprime_ses_profils(document: Any, board: Any) -> None:
    from freecad.menuiserie.features.drag_joints import delete_machined_part

    blank = board(document)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 2.0)
    machined = machined_of(blank)
    names = (machined.Name, profile.Name, blank.Name)
    assert delete_machined_part(machined, lambda _name, _labels: True) is False
    assert all(
        document.getObject(name) is None for name in names
    )  # pièce entière, comme avec ses assemblages


def test_supprimer_le_profil_par_un_script_refuse_un_autre_objet(document: Any, board: Any) -> None:
    with pytest.raises(TypeError, match="profil d'arête"):
        api.remove_edge_profile(board(document))


# --- B8 : persistance --------------------------------------------------------------------------


def test_reouverture_a_l_identique(document: Any, board: Any, rouvrir: Reopen) -> None:
    blank = board(document)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-", "Z-Y-"], "Ogee", 8.0, 6.0)
    volume = machined_of(blank).Shape.Volume
    names = (blank.Name, profile.Name, machined_of(blank).Name)
    doc = rouvrir(document)
    reopened = doc.getObject(names[1])
    assert (reopened.Edges, reopened.Family, reopened.SizeA.Value) == (
        ["Z+Y-", "Z-Y-"],
        "Ogee",
        8.0,
    )
    assert reopened.Version == 1
    assert reopened.Part == doc.getObject(names[0])
    machined = doc.getObject(names[2])
    assert machined.Finishes == [reopened]
    assert machined.Version == 2
    doc.recompute()
    assert machined.Shape.Volume == pytest.approx(volume, rel=1e-9)
    assert not [o.Name for o in doc.Objects if "Invalid" in o.State]


def test_ancienne_pièce_usinee_migree_sans_perte(cadre_assemble: Cadre, rouvrir: Reopen) -> None:
    machined = cadre_assemble.machined("M1")
    volume = machined.Shape.Volume
    name = machined.Name
    machined.removeProperty("Finishes")
    machined.Version = 1
    doc = rouvrir(cadre_assemble.doc)
    restored = doc.getObject(name)
    assert restored.Version == 2
    assert restored.Finishes == []
    doc.recompute()
    assert restored.Shape.Volume == pytest.approx(volume, rel=1e-9)


def test_la_forme_est_ordinaire_sans_l_atelier(document: Any, board: Any) -> None:
    """Pièce usinée : solide valide, exportable (compatibilité avec les autres ateliers)."""
    blank = board(document)
    api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 2.0)
    shape = machined_of(blank).Shape
    assert shape.isValid()
    assert shape.ShapeType in ("Solid", "Compound")
    assert len(shape.Solids) == 1


# --- Modification d'un profil (panneau de tâche) ---------------------------------------------


def test_modifier_un_profil_recalcule_la_piece(document: Any, board: Any) -> None:
    blank = board(document)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    warnings = api.set_edge_profile(profile, ["Z+Y-", "Z-Y-"], "Round", 4.0)
    assert warnings == ()
    assert (profile.Edges, profile.Family, profile.SizeA.Value) == (["Z+Y-", "Z-Y-"], "Round", 4.0)
    removed = BOARD_VOLUME - machined_of(blank).Shape.Volume
    assert removed == pytest.approx(2 * (1 - math.pi / 4) * 16.0 * LENGTH, rel=1e-4)


def test_modifier_un_profil_refuse_avant_d_ecrire(document: Any, board: Any) -> None:
    blank = board(document)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    with pytest.raises(ValueError, match="trop grand"):
        api.set_edge_profile(profile, ["Z+Y-"], "Chamfer", 5.0, 30.0)
    assert (profile.Family, profile.SizeB.Value) == ("Chamfer", 5.0)


def test_modifier_un_profil_reprend_les_aretes_d_un_autre(document: Any, board: Any) -> None:
    blank = board(document)
    other, _ = api.add_edge_profile(blank, ["Z-Y-"], "Chamfer", 2.0)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 2.0)
    with pytest.raises(ValueError, match="Z-Y-"):
        api.set_edge_profile(profile, ["Z+Y-", "Z-Y-"], "Chamfer", 2.0)
    api.set_edge_profile(profile, ["Z+Y-", "Z-Y-"], "Chamfer", 2.0, replace=True)
    with pytest.raises(ReferenceError):
        _ = other.Name
