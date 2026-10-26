# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois dans un ensemble (spec piece-en-bois, PD-f, F1 à F3 ; ADR 0020, décision 8).

Une pièce en bois suit l'ensemble par son ``Placement`` ; ses trois cotes viennent du dessin, donc
sont toujours fixes : l'ensemble la déplace sans l'étirer, ne pose aucune expression sur sa source
ni sur ``Length`` / ``Width`` / ``Thickness``, et avertit qu'une cote dessinée ne se modifie que
dans le dessin. F4 (pièce en bois assemblée, avec sa pièce usinée) dépend de PD-e.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

DRAWN = "cote dessinée : modifiez le dessin"
POSITION = {"Placement.Base.x", "Placement.Base.y", "Placement.Base.z"}
SIZES = ("Length", "Width", "Thickness")
LEG = (45.0, 95.0, 720.0)


@dataclass
class Table:
    """Plateau (pièce de bois) posé sur deux pieds (pièces en bois) dans l'ensemble « Table »."""

    doc: Any
    furniture: Any
    top: Any
    legs: dict[str, Any]
    notices: tuple[str, ...]

    def bounds(self, obj: Any) -> tuple[tuple[float, float], ...]:
        """Étendue (X, Y, Z) de ``obj`` dans le document, arrondie au millième."""
        box = obj.Shape.BoundBox
        axes = ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))
        return tuple((round(lo, 3), round(hi, 3)) for lo, hi in axes)

    def extents(self, obj: Any) -> tuple[float, ...]:
        """Cotes d'encombrement de la forme de ``obj``, triées."""
        return tuple(sorted(hi - lo for lo, hi in self.bounds(obj)))

    def sizes(self, obj: Any) -> tuple[float, ...]:
        return tuple(round(getattr(obj, name).Value, 6) for name in SIZES)

    def expressions(self, obj: Any) -> set[str]:
        return {path.lstrip(".") for path, _text in obj.ExpressionEngine}


def leg_at(doc: Any, x: float, mark: str, name: str) -> Any:
    """Pied : pièce en bois d'une boîte de 45 x 95 x 720 dont le coin est en (x, 505, 0)."""
    source = doc.addObject("Part::Box", name)
    source.Length, source.Width, source.Height = LEG
    source.Placement = App.Placement(App.Vector(x, 505, 0), App.Rotation())
    doc.recompute()
    return api.make_shaped_part(source, mark=mark)


@pytest.fixture
def table(document: Any) -> Table:
    top = api.make_wood_part(1200, 600, 30, "chene", mark="Plateau", doc=document)
    top.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    legs = {
        "A": leg_at(document, 0, "PiedA", "SourceA"),
        "B": leg_at(document, 1155, "PiedB", "SourceB"),
    }
    document.recompute()
    furniture, notices = api.make_furniture([top, legs["A"]], label="Table")
    notices += api.add_to_furniture(furniture, [legs["B"]])
    return Table(document, furniture, top, legs, notices)


# --- F1 : ajout à un ensemble ----------------------------------------------------------------


def test_la_piece_en_bois_entre_dans_l_ensemble(table: Table) -> None:
    for leg in table.legs.values():
        assert api.furniture_of(leg) == table.furniture
        assert leg.Locked is True  # cotes dessinées : toujours fixes
    assert [table.furniture.Width.Value, table.furniture.Depth.Value] == [1200.0, 600.0]
    assert table.furniture.Height.Value == 750.0


def test_avertissement_cote_dessinee(table: Table) -> None:
    assert any(DRAWN in message for message in table.notices)
    assert any("PiedA" in message or "Pied" in message for message in table.notices)


def test_seul_le_placement_est_pilote(table: Table) -> None:
    for leg in table.legs.values():
        assert table.expressions(leg) <= POSITION
    assert table.expressions(table.legs["B"]) >= {"Placement.Base.x"}


def test_aucune_expression_sur_la_source(table: Table) -> None:
    for leg in table.legs.values():
        assert table.expressions(leg.Source) == set()
        assert table.expressions(leg) & set(SIZES) == set()


# --- F3 : redimensionner l'ensemble déplace la pièce sans l'étirer ----------------------------


def test_profondeur_deplace_les_pieds_sans_les_etirer(table: Table) -> None:
    before = {key: (table.sizes(leg), table.extents(leg)) for key, leg in table.legs.items()}
    api.resize_furniture(table.furniture, depth=800)
    assert table.top.Width.Value == 800.0  # la pièce de bois, elle, est étirée
    for key, leg in table.legs.items():
        assert table.bounds(leg)[1] == (705.0, 800.0)  # suit le bord arrière
        assert (table.sizes(leg), table.extents(leg)) == before[key]
        assert table.expressions(leg) & set(SIZES) == set()
        assert table.expressions(leg.Source) == set()
    assert table.doc.getObject(table.legs["A"].Source.Name).Placement.Base.y == 505.0


def test_largeur_deplace_le_pied_de_droite(table: Table) -> None:
    api.resize_furniture(table.furniture, width=1400)
    assert table.bounds(table.legs["A"])[0] == (0.0, 45.0)
    assert table.bounds(table.legs["B"])[0] == (1355.0, 1400.0)
    for leg in table.legs.values():
        assert table.sizes(leg) == (720.0, 95.0, 45.0)
        assert table.expressions(leg) & set(SIZES) == set()


def test_dessin_modifie_d_un_membre_avertit(table: Table, vue_rapport: Any) -> None:
    table.legs["A"].Source.Height = 700.0
    table.doc.recompute()
    assert table.sizes(table.legs["A"])[0] == 700.0
    assert any("Relier les pièces" in text for text in vue_rapport.de_niveau("Warning"))


def test_le_redimensionnement_avertit(table: Table) -> None:
    messages = api.resize_furniture(table.furniture, depth=800)
    assert any(DRAWN in message for message in messages)


# --- Rangée bloquée par une pièce en bois ---------------------------------------------------


def test_hauteur_refusee_par_la_rangee_bloquee(table: Table) -> None:
    with pytest.raises(ValueError, match="aucune pièce de la rangée") as caught:
        api.resize_furniture(table.furniture, height=850)
    assert not isinstance(caught.value, api.LockedPiecesError)  # rien à déverrouiller
    assert "PiedA" in str(caught.value) or "PiedB" in str(caught.value)
    assert table.furniture.Height.Value == 750.0


def test_une_piece_en_bois_ne_se_deverrouille_pas(table: Table) -> None:
    leg = table.legs["A"]
    with pytest.raises(ValueError, match="cotes dessinées"):
        api.set_member_options(leg, locked=False)
    with pytest.raises(ValueError, match="cotes dessinées"):
        api.unlock_and_resize(table.furniture, [leg], height=850)
    assert leg.Locked is True
    assert table.furniture.Height.Value == 750.0


def test_decocher_locked_dans_l_editeur_le_recoche(table: Table, vue_rapport: Any) -> None:
    leg = table.legs["A"]
    leg.Locked = False
    table.doc.recompute()
    assert leg.Locked is True
    assert any("cotes dessinées" in text for _level, text in vue_rapport.messages)


def test_epaisseur_d_une_piece_en_bois_refusee(table: Table) -> None:
    with pytest.raises(ValueError, match="vient du dessin"):
        api.unlock_and_set_thickness(table.legs["A"], 40, [])


# --- Retrait de l'ensemble ------------------------------------------------------------------


def test_retrait_de_l_ensemble(table: Table) -> None:
    leg = table.legs["B"]
    placement = App.Placement(leg.Placement)
    api.remove_from_furniture([leg])
    assert api.furniture_of(leg) is None
    assert table.expressions(leg) == set()
    assert "Furniture" not in leg.PropertiesList
    assert leg.Placement.isSame(placement, 1e-6)
    assert table.expressions(leg.Source) == set()
    api.resize_furniture(table.furniture, width=1400)  # le pied retiré ne bouge plus
    assert table.bounds(leg)[0] == (1155.0, 1200.0)
    assert table.bounds(table.legs["A"])[0] == (0.0, 45.0)


def test_suppression_de_la_piece_relie_les_voisines(table: Table) -> None:
    table.doc.removeObject(table.legs["B"].Name)
    table.doc.recompute()
    assert table.expressions(table.legs["A"]) <= POSITION
    api.resize_furniture(table.furniture, depth=700)
    assert table.bounds(table.legs["A"])[1] == (605.0, 700.0)


# --- Souris et flèches (#65) : une pièce en bois membre ne s'étire jamais --------------------


def test_aucune_poignee_de_cote_sur_une_piece_en_bois(table: Table) -> None:
    drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
    for leg in table.legs.values():
        assert not drag.can_resize(leg)
        assert drag.drag_limits(leg).resizable_axes == frozenset()
    memento = drag.begin_drag(table.legs["A"])
    with pytest.raises(ValueError, match="ne peut pas être tirée"):
        drag.resize_part(memento, "Length", 800.0, Vec3(0.0, 0.0, 0.0))


def test_deplacement_par_fleches_puis_suivi_de_l_ensemble(table: Table) -> None:
    drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
    leg = table.legs["B"]
    before = table.bounds(leg)
    sizes = table.sizes(leg)
    memento = drag.begin_drag(leg)
    drag.move_part(memento, Vec3(0.0, -50.0, 0.0))  # repère de la pièce
    shift = leg.Placement.Rotation.multVec(App.Vector(0, -50, 0))
    drag.end_drag(memento)
    after = table.bounds(leg)
    for axis in range(3):
        assert after[axis][0] == pytest.approx(before[axis][0] + shift[axis], abs=1e-3)
    assert table.sizes(leg) == sizes
    api.resize_furniture(table.furniture, depth=800)
    assert table.sizes(leg) == sizes
    assert table.expressions(leg) & set(SIZES) == set()
    assert table.expressions(leg.Source) == set()


# --- F4 : pièce en bois assemblée, membre d'un ensemble ---------------------------------------


def test_piece_en_bois_assemblee_suit_avec_sa_piece_usinee(document: Any) -> None:
    """Pied (pièce en bois) relié par un tenon-mortaise à une traverse (pièce de bois) : quand la
    profondeur de l'ensemble change, le pied et sa pièce usinée sont déplacés, sans étirement."""
    source = document.addObject("Part::Box", "SourcePied")
    source.Length, source.Width, source.Height = LEG
    source.Placement = App.Placement(App.Vector(0, 305, 0), App.Rotation())  # contre le fond
    document.recompute()
    pied = api.make_shaped_part(source, mark="Pied")
    traverse = api.make_wood_part(300, 60, 20, "chene", mark="Traverse", doc=document)
    traverse.Placement = App.Placement(App.Vector(45, 322.5, 500), App.Rotation())
    plateau = api.make_wood_part(600, 400, 30, "chene", mark="Plateau", doc=document)
    plateau.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    document.recompute()
    joint = api.make_mortise_tenon(pied, traverse)
    machined = api.machined_part_of(pied)
    assert machined is not None
    furniture, _notices = api.make_furniture([pied, traverse, plateau], label="Table")
    api.set_member_options(traverse, fixed={"Front": False})  # la traverse suit le pied
    sizes = tuple(round(getattr(pied, name).Value, 6) for name in SIZES)
    api.resize_furniture(furniture, depth=500)
    assert pied.Shape.BoundBox.YMin == pytest.approx(405.0, abs=1e-3)
    assert pied.Shape.BoundBox.YMax == pytest.approx(500.0, abs=1e-3)
    assert tuple(round(getattr(pied, name).Value, 6) for name in SIZES) == sizes
    assert machined.Placement.isSame(pied.Placement, 1e-6)  # la pièce usinée suit
    assert machined.Shape.BoundBox.YMin == pytest.approx(405.0, abs=1e-3)
    assert machined.isValid()
    assert traverse.Shape.BoundBox.YMin == pytest.approx(422.5, abs=1e-3)
    assert traverse.Width.Value == 60.0
    assert "Invalid" not in joint.State
    expressions = {path.lstrip(".") for path, _text in pied.ExpressionEngine}
    assert expressions <= POSITION
    assert source.ExpressionEngine == []
