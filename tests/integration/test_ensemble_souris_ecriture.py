# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble à la souris, écriture : taille, déplacement, rotation (EN-b, B1 à B5, Q5, Q7)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.pieces_galbees import curved_rail, shaped
from tests.integration.test_ensemble_std_part import geometry

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
drag = pytest.importorskip("freecad.menuiserie.features.furniture_drag")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
core_furniture = pytest.importorskip("freecad.menuiserie.core.furniture")
core_geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
core_magnet = pytest.importorskip("freecad.menuiserie.core.magnet")

Handle = core_magnet.Handle
Vec3 = core_geometry.Vec3


def pull(memento: Any, axis: int, at_end: bool, delta: float) -> Any:
    """Pas de taille : la face (axe, sens) tirée de ``delta`` mm depuis la boîte du début."""
    box = core_furniture.resized_box(memento.box, Handle(axis, at_end), delta)
    return drag.resize_furniture_to(memento, box)


def gbounds(bureau: Bureau, mark: str) -> tuple[tuple[float, float], ...]:
    """Étendue (X, Y, Z) **globale** de la brute ``mark``, arrondie au millième."""
    shape = bureau.parts[mark].Shape.copy()
    shape.Placement = bureau.parts[mark].getGlobalPlacement()
    b = shape.BoundBox
    return tuple(
        (round(lo, 3) + 0.0, round(hi, 3) + 0.0)
        for lo, hi in ((b.XMin, b.XMax), (b.YMin, b.YMax), (b.ZMin, b.ZMax))
    )


def corner(bureau: Bureau, mark: str) -> tuple[float, float, float]:
    """Coin (x, y, z) global de la boîte de la brute ``mark``, arrondi."""
    box = bureau.parts[mark].Shape.copy()
    box.Placement = bureau.parts[mark].getGlobalPlacement()
    b = box.BoundBox
    return (round(b.XMin, 3), round(b.YMin, 3), round(b.ZMin, 3))


# --- B1 : taille, écritures absolues ------------------------------------------------------------


def test_face_de_fin_tiree_les_pieces_suivent(bureau: Bureau) -> None:
    furniture = bureau.furniture
    memento = drag.begin_furniture_drag(furniture)
    step = pull(memento, 0, True, 100)
    assert step.reached and step.message == "" and step.locked == ()
    assert furniture.Width.Value == 1300
    assert tuple(furniture.Origin) == (0, 0, 0)
    assert bureau.sizes("P")[0] == 1300  # brute recalculée pendant le geste
    assert bureau.bounds("JD")[0] == (1278, 1300)
    assert drag.end_furniture_drag(memento) == []
    assert stale_or_invalid(bureau.doc) == []


def test_ecritures_absolues_rien_ne_s_accumule(bureau: Bureau) -> None:
    memento = drag.begin_furniture_drag(bureau.furniture)
    for delta in (50, 120, 80, 100):
        pull(memento, 0, True, delta)
        assert bureau.furniture.Width.Value == 1200 + delta
    pull(memento, 0, True, 0)
    assert bureau.furniture.Width.Value == 1200
    assert bureau.sizes("P")[0] == 1200


def far_corner(bureau: Bureau) -> tuple[float, float, float]:
    """Coin arrière droit haut (global) de l'ensemble, d'après la joue droite et le voile."""
    right = bureau.parts["JD"].Shape.copy()
    right.Placement = bureau.parts["JD"].getGlobalPlacement()
    back = bureau.parts["V"].Shape.copy()
    back.Placement = bureau.parts["V"].getGlobalPlacement()
    top = bureau.parts["P"].Shape.copy()
    top.Placement = bureau.parts["P"].getGlobalPlacement()
    return (
        round(right.BoundBox.XMax, 3),
        round(max(back.BoundBox.YMax, top.BoundBox.YMax), 3),
        round(top.BoundBox.ZMax, 3),
    )


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_face_de_debut_tiree_la_face_opposee_reste(bureau: Bureau, axis: int) -> None:
    std = container.std_part_of(bureau.furniture)
    far, size = far_corner(bureau), bureau.furniture.Width.Value
    names = ("Width", "Depth", "Height")
    sizes = [getattr(bureau.furniture, name).Value for name in names]
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert pull(memento, axis, False, 60).reached  # la face avant, gauche ou basse avance
    assert getattr(bureau.furniture, names[axis]).Value == sizes[axis] - 60
    assert tuple(bureau.furniture.Origin) == (0, 0, 0)  # Origin ne bouge pas : c'est le Std Part
    assert std.Placement.Base[axis] == 60 and sum(abs(v) for v in std.Placement.Base) == 60
    drag.end_furniture_drag(memento)
    assert far_corner(bureau) == far  # l'arrière, la droite et le haut n'ont pas bougé
    assert size == 1200
    assert stale_or_invalid(bureau.doc) == []


def test_face_de_debut_vers_l_exterieur(bureau: Bureau) -> None:
    left = gbounds(bureau, "JG")[0][0]
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert pull(memento, 0, False, -100).reached
    drag.end_furniture_drag(memento)
    assert bureau.furniture.Width.Value == 1300
    assert gbounds(bureau, "JG")[0][0] == left - 100  # la joue gauche suit la face gauche
    assert gbounds(bureau, "JD")[0][1] == 1200  # la joue droite ne bouge pas
    assert gbounds(bureau, "P")[0] == (
        -100,
        1200,
    )  # le plateau, sans liaison en x, suit le Std Part
    assert stale_or_invalid(bureau.doc) == []


def test_face_basse_et_hauteur(bureau: Bureau) -> None:
    top = gbounds(bureau, "P")[2][1]
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert pull(memento, 2, False, -100).reached  # le dessous descend de 100 mm
    drag.end_furniture_drag(memento)
    assert gbounds(bureau, "P")[2][1] == top  # le plateau reste en haut
    assert gbounds(bureau, "JG")[2][0] == -100  # les joues descendent
    assert stale_or_invalid(bureau.doc) == []


# --- B2, B3 : refus -----------------------------------------------------------------------------


def test_cote_bloquee_le_geste_s_arrete_sans_ecriture_perdue(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    api.set_member_options(voile, locked=True)
    memento = drag.begin_furniture_drag(bureau.furniture)
    step = pull(memento, 0, True, 100)
    assert not step.reached and step.locked == (voile,)
    assert "cotes fixes" in step.message
    assert step.box == memento.box and bureau.furniture.Width.Value == 1200
    assert pull(memento, 1, True, 100).reached  # une autre cote reste libre
    assert bureau.furniture.Depth.Value == 700
    drag.end_furniture_drag(memento)
    assert stale_or_invalid(bureau.doc) == []


def test_piece_trop_petite_arret_a_la_derniere_valeur_permise(bureau: Bureau) -> None:
    memento = drag.begin_furniture_drag(bureau.furniture)
    step = pull(memento, 0, True, -1190)  # 10 mm de large : les pièces ne tiennent plus
    assert not step.reached and step.message
    written = bureau.furniture.Width.Value
    assert step.box.size(0) == pytest.approx(written)
    assert 10 < written < 1200  # a bougé jusqu'à la limite, pas au-delà
    again = pull(memento, 0, True, -1190)  # même refus, la limite est affinée
    assert not again.reached and written - 5 < again.box.size(0) <= written
    ok = pull(memento, 0, True, -100)  # la souris revient dans le permis
    assert ok.reached and bureau.furniture.Width.Value == 1100
    drag.end_furniture_drag(memento)
    assert stale_or_invalid(bureau.doc) == []


def test_formule_de_l_utilisateur_refuse_le_geste(bureau: Bureau) -> None:
    bureau.furniture.setExpression("Width", "1200 mm + 0 mm")
    memento = drag.begin_furniture_drag(bureau.furniture)
    step = pull(memento, 0, True, 100)
    assert not step.reached and "expression" in step.message
    assert bureau.furniture.Width.Value == 1200


def test_boite_sans_volume_refusee(bureau: Bureau) -> None:
    memento = drag.begin_furniture_drag(bureau.furniture)
    flat = memento.box.with_range(0, 0.0, 0.0)
    with pytest.raises(ValueError, match="volume"):
        drag.resize_furniture_to(memento, flat)


# --- Échap, relâchement -------------------------------------------------------------------------


def test_echap_ramene_au_debut(bureau: Bureau) -> None:
    before = geometry(bureau.doc)
    memento = drag.begin_furniture_drag(bureau.furniture)
    pull(memento, 0, False, -200)
    pull(memento, 2, True, 50)
    drag.restore(memento)
    assert tuple(container.std_part_of(bureau.furniture).Placement.Base) == (0, 0, 0)
    assert [bureau.furniture.Width.Value, bureau.furniture.Depth.Value] == [1200, 600]
    assert geometry(bureau.doc) == before
    assert stale_or_invalid(bureau.doc) == []


def test_relachement_recalcule_les_usinages(bureau: Bureau) -> None:
    memento = drag.begin_furniture_drag(bureau.furniture)
    pull(memento, 0, True, 100)
    drag.end_furniture_drag(memento)
    assert stale_or_invalid(bureau.doc) == []
    assert bureau.dowel_counts() and all(count > 0 for count in bureau.dowel_counts())
    assert bureau.shown("JD").Shape.BoundBox.XMax == pytest.approx(1300)


def test_relachement_avertit_comme_le_panneau(document: Any) -> None:
    """Une pièce en bois dessinée ne s'étire pas : elle est déplacée et l'on prévient."""

    desk = build_parts(document)
    drawn = shaped(curved_rail(document))
    drawn.Placement = App.Placement(App.Vector(300, 200, 800), App.Rotation())
    document.recompute()
    furniture, _ = api.make_furniture([*desk.parts.values(), drawn], label="Bureau")
    memento = drag.begin_furniture_drag(furniture)
    pull(memento, 0, True, 100)
    messages = drag.end_furniture_drag(memento)
    assert messages and all(isinstance(message, str) for message in messages)


# --- B4 : déplacement et rotation ---------------------------------------------------------------


def test_deplacement_par_le_std_part(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    start = corner(bureau, "P")
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert drag.move_furniture_by(memento, Vec3(100, 50, 0))
    assert drag.move_furniture_by(memento, Vec3(10, 0, 5))  # absolu : 100 puis 10, pas 110
    assert tuple(std.Placement.Base) == (10, 0, 5)
    assert tuple(corner(bureau, "P")) == pytest.approx((start[0] + 10, start[1], start[2] + 5))
    assert tuple(bureau.furniture.Origin) == (0, 0, 0)  # le modèle de l'ensemble ne bouge pas
    assert drag.end_furniture_drag(memento) == []
    assert stale_or_invalid(bureau.doc) == []


def test_rotation_autour_du_centre_de_la_boite(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert drag.rotate_furniture_by(memento, 2, 90)
    assert drag.rotate_furniture_by(memento, 2, 30)  # depuis le début : 30°, pas 120°
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(30)
    height = bureau.furniture.Height.Value
    middle = std.Placement.multVec(App.Vector(600, 300, height / 2))
    assert (middle.x, middle.y) == pytest.approx((600, 300))
    drag.end_furniture_drag(memento)
    assert stale_or_invalid(bureau.doc) == []
    where = bureau.parts["P"].getGlobalPlacement()
    assert where.Rotation.getYawPitchRoll()[0] == pytest.approx(30)


def test_taille_dans_un_std_part_tourne(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    memento = drag.begin_furniture_drag(bureau.furniture)
    drag.rotate_furniture_by(memento, 2, 90)
    drag.end_furniture_drag(memento)
    frame = drag.furniture_frame(bureau.furniture)
    assert frame.x.y == pytest.approx(1)  # X local vers Y global
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert pull(memento, 0, True, 100).reached  # la boîte reste dans le repère local
    assert bureau.furniture.Width.Value == 1300
    drag.end_furniture_drag(memento)
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(90)
    assert stale_or_invalid(bureau.doc) == []


def test_face_de_debut_dans_un_std_part_tourne(bureau: Bureau) -> None:
    memento = drag.begin_furniture_drag(bureau.furniture)
    drag.rotate_furniture_by(memento, 2, 90)
    drag.end_furniture_drag(memento)
    far = bureau.parts["JD"].getGlobalPlacement().Base
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert pull(memento, 0, False, -100).reached
    drag.end_furniture_drag(memento)
    assert bureau.parts["JD"].getGlobalPlacement().Base.isEqual(far, 1e-6)  # face opposée fixe


def test_rotation_absolue_par_les_angles(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    assert drag.rotate_furniture_to(bureau.furniture, (0.0, 0.0, 45.0))
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(45)
    assert drag.rotate_furniture_to(bureau.furniture, (0.0, 0.0, 0.0))
    assert tuple(std.Placement.Base) == pytest.approx((0, 0, 0), abs=1e-6)
    with pytest.raises(ValueError, match="360"):
        drag.rotate_furniture_to(bureau.furniture, (0.0, 0.0, 400.0))
    with pytest.raises(ValueError, match="angle"):
        drag.rotate_furniture_to(bureau.furniture, (0.0, float("nan"), 0.0))


def test_gestes_invalides(bureau: Bureau) -> None:
    memento = drag.begin_furniture_drag(bureau.furniture)
    with pytest.raises(ValueError, match="angle"):
        drag.rotate_furniture_by(memento, 2, float("inf"))
    with pytest.raises(ValueError, match="axis"):
        drag.rotate_furniture_by(memento, 3, 10)
    with pytest.raises(ValueError, match="delta"):
        drag.move_furniture_by(memento, Vec3(float("nan"), 0, 0))
    assert tuple(container.std_part_of(bureau.furniture).Placement.Base) == (0, 0, 0)


# --- Refus propres ------------------------------------------------------------------------------


def old_furniture(document: Any) -> Any:
    box = core_furniture.FurnitureBox(100, 100, 100)
    furniture_module = pytest.importorskip("freecad.menuiserie.features.furniture")
    return furniture_module.create_furniture(document, box, Vec3(0, 0, 0), "Ancien", None)


def test_ensemble_sans_std_part_ne_tourne_ni_ne_bouge(document: Any) -> None:
    old = old_furniture(document)
    memento = drag.begin_furniture_drag(old)
    assert not drag.move_furniture_by(memento, Vec3(10, 0, 0))
    assert not drag.rotate_furniture_by(memento, 2, 30)
    assert not drag.rotate_furniture_to(old, (0.0, 0.0, 30.0))
    assert "Std Part" in (drag.turn_refusal(old) or "")
    assert pull(memento, 0, True, 50).reached  # la taille reste permise
    assert old.Width.Value == 150


def test_std_part_qui_contient_autre_chose(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    std.addObject(bureau.doc.addObject("Part::Box", "Intrus"))
    assert "contient autre chose" in (drag.turn_refusal(bureau.furniture) or "")
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert not drag.rotate_furniture_by(memento, 2, 30)
    assert not drag.move_furniture_by(memento, Vec3(5, 0, 0))
    assert tuple(std.Placement.Base) == (0, 0, 0)


def test_formule_sur_le_std_part_refuse_la_rotation(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    std.setExpression("Placement.Base.x", "10 mm")
    bureau.doc.recompute()
    memento = drag.begin_furniture_drag(bureau.furniture)
    assert not drag.rotate_furniture_by(memento, 2, 30)
    assert "expression" in (drag.turn_refusal(bureau.furniture) or "")
    assert not drag.rotate_furniture_to(bureau.furniture, (0.0, 0.0, 30.0))


def test_boite_et_repere_de_l_ensemble(bureau: Bureau) -> None:
    box = drag.furniture_box(bureau.furniture)
    assert (box.lo(0), box.hi(0), box.hi(1), box.hi(2)) == (
        0,
        1200,
        600,
        bureau.furniture.Height.Value,
    )
    frame = drag.furniture_frame(bureau.furniture)
    assert (frame.x.x, frame.y.y, frame.z.z) == (1, 1, 1)
    layout = core_furniture.furniture_layout(box, frame, 100.0)
    assert len(layout.handles) == 6 and len(layout.arrows) == 3 and len(layout.rings) == 3
