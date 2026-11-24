# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce assemblée qui défait l'assemblage : où ajouter l'écart (ADR 0060).

Angle à queue d'aronde : H à plat (griffes), I debout (queues), sa face extérieure à fleur du
bout de H. Épaissir I déplace sa face extérieure : H n'arrive plus à fleur (doute D1 du fil QTest).
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
choice = pytest.importorskip("freecad.menuiserie.features.thickness_choice")
base = pytest.importorskip("freecad.menuiserie.features.joints.base")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")

STANDING = App.Rotation(App.Vector(0, 1, 0), -90)


def corner(doc: Any, *, host_at: tuple[float, float, float] = (0, 0, 0)) -> tuple[Any, Any, Any]:
    """H à plat en ``host_at``, I debout sur son bout, queue d'aronde I -> H."""
    host = api.make_wood_part(400, 150, 18, "chene", mark="H", doc=doc)
    host.Label = "H"
    host.Placement = App.Placement(App.Vector(*host_at), App.Rotation())
    guest = api.make_wood_part(400, 150, 18, "chene", mark="I", doc=doc)
    guest.Label = "I"
    guest.Placement = App.Placement(App.Vector(18 + host_at[0], host_at[1], 18), STANDING)
    doc.recompute()
    joint = api.make_dovetail(host, guest)
    doc.recompute()
    return host, guest, joint


def holds(doc: Any, joint: Any) -> bool:
    doc.recompute()
    try:
        base.plan_for(joint)
    except ValueError:
        return False
    return "Invalid" not in joint.State and stale_or_invalid(doc) == []


def test_epaisseur_qui_ne_defait_rien_propose_laisser_en_l_etat(document: Any) -> None:
    """H plus épaisse : I suit sa face haute (#133), rien n'est défait ; « Laisser en l'état »
    est proposé en tête, avec les autres choix (jv, 2026-11-15)."""
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(host)
    conflict = edit.probe(30)
    assert conflict is not None
    assert [o.choice for o in conflict.options] == [
        choice.Choice.AS_TYPED,
        choice.Choice.OTHER_SIDE,
        choice.Choice.EXTEND,
        choice.Choice.REVERT,
    ]
    assert conflict.options[0].text == "Vers l'intérieur"  # face haute, du côté de I
    assert conflict.preferred() is choice.Choice.AS_TYPED
    assert host.Thickness.Value == 18  # état de départ rendu : au panneau d'appliquer
    edit.apply(30, choice.Choice.AS_TYPED)
    assert host.Thickness.Value == 30
    assert guest.Placement.Base.z == pytest.approx(30)
    assert holds(document, joint)


def test_epaisseur_de_depart_rien_a_proposer(document: Any) -> None:
    host, _guest, _joint = corner(document)
    edit = choice.ThicknessEdit(host)
    edit.probe(30)
    assert edit.probe(18) is None


def test_laisser_en_l_etat_absent_si_l_assemblage_est_defait(document: Any) -> None:
    _host, guest, _joint = corner(document)
    conflict = choice.ThicknessEdit(guest).probe(30)
    assert conflict is not None
    assert choice.Choice.AS_TYPED not in [o.choice for o in conflict.options]


def test_trois_choix_proposes(document: Any) -> None:
    _host, guest, _joint = corner(document)
    conflict = choice.ThicknessEdit(guest).probe(30)
    assert conflict is not None
    assert conflict.title == "Queue d'aronde avec « H »."
    assert conflict.question.startswith("Où ajouter les 12")
    texts = [option.text for option in conflict.options]
    assert texts[0] == "Vers l'intérieur (reste à fleur)"
    assert texts[1].startswith("Vers l'extérieur et allonger « H » de 12")
    assert texts[2].startswith("Revenir à 18")
    assert [option.reason for option in conflict.options] == [None, None, None]
    assert conflict.preferred() is choice.Choice.OTHER_SIDE
    assert guest.Thickness.Value == 18  # état de départ rendu, au panneau d'appliquer


def test_vers_l_interieur(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    edit.probe(30)
    edit.apply(30, choice.Choice.OTHER_SIDE)
    assert guest.Thickness.Value == 30
    assert tuple(guest.Placement.Base) == pytest.approx((30, 0, 18))  # face extérieure en x = 0
    assert host.Length.Value == 400
    assert holds(document, joint)


def test_vers_l_exterieur_et_allonger(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    edit.probe(30)
    edit.apply(30, choice.Choice.EXTEND)
    assert tuple(guest.Placement.Base) == pytest.approx((18, 0, 18))
    assert host.Length.Value == 412
    assert tuple(host.Placement.Base) == pytest.approx((-12, 0, 0))  # bout de début à fleur
    assert holds(document, joint)


def test_revenir_et_changer_d_avis(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    edit.probe(30)
    edit.apply(30, choice.Choice.EXTEND)
    edit.apply(30, choice.Choice.OTHER_SIDE)  # repart de l'état de départ
    assert host.Length.Value == 400
    assert tuple(host.Placement.Base) == pytest.approx((0, 0, 0))
    edit.apply(30, choice.Choice.REVERT)
    assert guest.Thickness.Value == 18
    assert tuple(guest.Placement.Base) == pytest.approx((18, 0, 18))
    assert holds(document, joint)


def test_amincir_propose_de_raccourcir(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    conflict = edit.probe(12)
    assert conflict is not None
    assert conflict.question.startswith("Où retirer les 6")
    assert conflict.options[0].text == "Côté intérieur (reste à fleur)"
    assert conflict.options[1].text.startswith("Côté extérieur et raccourcir « H » de 6")
    edit.apply(12, choice.Choice.EXTEND)
    assert host.Length.Value == 394
    assert holds(document, joint)


def test_saisies_successives_repartent_du_depart(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    edit.probe(3)
    edit.apply(3, choice.Choice.OTHER_SIDE)
    edit.probe(30)
    edit.apply(30, choice.Choice.EXTEND)
    assert host.Length.Value == 412
    assert tuple(guest.Placement.Base) == pytest.approx((18, 0, 18))
    assert holds(document, joint)


def test_autre_piece_copie_d_une_repetition(document: Any) -> None:
    host = api.make_wood_part(400, 150, 18, "chene", mark="H", doc=document)
    host.Label = "H"
    rep = api.make_repeat([host], api.RepeatParams(count=1, step=500.0, axis="Y"))
    copy = repeat.copies_of(rep)[0]
    guest = api.make_wood_part(400, 150, 18, "chene", mark="I", doc=document)
    guest.Label = "I"
    guest.Placement = App.Placement(App.Vector(18, 500, 18), STANDING)
    document.recompute()
    joint = api.make_dovetail(copy, guest)
    document.recompute()
    edit = choice.ThicknessEdit(guest)
    conflict = edit.probe(30)
    assert conflict is not None
    reasons = {option.choice: option.reason for option in conflict.options}
    assert reasons[choice.Choice.OTHER_SIDE] is None
    assert "copie" in (reasons[choice.Choice.EXTEND] or "")
    assert conflict.preferred() is choice.Choice.OTHER_SIDE
    with pytest.raises(choice.UnavailableError):
        edit.apply(30, choice.Choice.EXTEND)
    assert guest.Thickness.Value == 18  # refus : état de départ rendu
    edit.apply(30, choice.Choice.OTHER_SIDE)
    assert holds(document, joint)


def test_piece_posee_sur_la_face_basse_suit(document: Any) -> None:
    """Vers l'intérieur, la face basse bouge : une pièce assemblée contre elle la suit."""
    host, guest, joint = corner(document)
    shelf = api.make_wood_part(150, 150, 18, "chene", mark="T", doc=document)
    shelf.Label = "T"
    shelf.Placement = App.Placement(App.Vector(18, 0, 200), App.Rotation())  # bout contre I
    document.recompute()
    dowels = api.make_dowels(guest, shelf)
    assert holds(document, dowels)
    edit = choice.ThicknessEdit(guest)
    edit.probe(30)
    edit.apply(30, choice.Choice.OTHER_SIDE)
    assert shelf.Placement.Base.x == pytest.approx(30)
    assert holds(document, joint) and holds(document, dowels)
    assert host.Length.Value == 400


# --- À la souris (maquette souris B) : la face tirée décide ----------------------------------

drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
thickness_drag = pytest.importorskip("freecad.menuiserie.features.thickness_drag")
Vec3 = pytest.importorskip("freecad.menuiserie.core.geometry").Vec3


def test_face_exterieure_tiree_l_autre_piece_s_allonge(document: Any) -> None:
    host, guest, joint = corner(document)
    memento = drag.begin_drag(guest)
    assert drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0)) == ""
    assert host.Length.Value == 407
    assert drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0)) == ""  # repart du début
    assert host.Length.Value == 412
    assert tuple(host.Placement.Base) == pytest.approx((-12, 0, 0))
    assert "« H » +12" in memento.follows.note()
    messages = drag.end_drag(memento)
    assert any("allongée de 12" in m for m in messages)
    assert holds(document, joint)


def test_face_interieure_tiree_rien_ne_suit(document: Any) -> None:
    host, guest, joint = corner(document)
    memento = drag.begin_drag(guest)
    assert drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, -12), lowered=True) == ""
    assert host.Length.Value == 400
    drag.end_drag(memento)
    assert holds(document, joint)


def test_echap_rend_l_autre_piece(document: Any) -> None:
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    drag.restore(memento)
    assert (host.Length.Value, tuple(host.Placement.Base)) == (400, (0, 0, 0))
    assert guest.Thickness.Value == 18


def test_copie_non_modifiable_butee(document: Any) -> None:
    host = api.make_wood_part(400, 150, 18, "chene", mark="H", doc=document)
    rep = api.make_repeat([host], api.RepeatParams(count=1, step=500.0, axis="Y"))
    copy = repeat.copies_of(rep)[0]
    guest = api.make_wood_part(400, 150, 18, "chene", mark="I", doc=document)
    guest.Placement = App.Placement(App.Vector(18, 500, 18), STANDING)
    document.recompute()
    joint = api.make_dovetail(copy, guest)
    document.recompute()
    memento = drag.begin_drag(guest)
    stop = drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert stop.startswith("Butée") and "copie" in stop
    assert guest.Thickness.Value == 18
    assert tuple(guest.Placement.Base) == pytest.approx((18, 500, 18))
    assert drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, -12), lowered=True) == ""
    drag.end_drag(memento)
    assert holds(document, joint)


def test_echap_rend_la_piece_usinee_avec_ses_queues(document: Any) -> None:
    """Revue Copilot de la PR #264 : Échap rend H avant de recalculer l'aperçu de I, qui
    retrouve ses queues sans recalcul du document."""
    _host, guest, _joint = corner(document)
    usinee = api.machined_part_of(guest)
    volume = usinee.Shape.Volume
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    drag.restore(memento)
    assert usinee.Shape.Volume == pytest.approx(volume)


def test_cote_de_caisson_le_premier_choix_dit_vers_l_exterieur(document: Any) -> None:
    """Cas de jv (2026-11-24) : caisson par défaut, queue d'aronde côté gauche et dessous. Le
    choix « telle que saisie » épaissit le côté vers l'extérieur et le dit ; « allonger » est
    grisé, le dessous s'arrête à la face intérieure du côté."""
    from freecad.menuiserie.features.furniture_bindings import members_of

    caisson, _ = api.make_carcass(document)
    document.recompute()
    pieces = {str(m.Label): m for m in members_of(caisson)}
    side = pieces["Côté gauche"]
    api.make_dovetail(side, pieces["Dessous"])
    document.recompute()
    edit = choice.ThicknessEdit(side)
    conflict = edit.probe(30)
    assert conflict is not None
    texts = {o.choice: (o.text, o.reason) for o in conflict.options}
    assert texts[choice.Choice.AS_TYPED] == ("Vers l'extérieur", None)
    assert texts[choice.Choice.OTHER_SIDE][0] == "Vers l'intérieur (reste à fleur)"
    assert texts[choice.Choice.EXTEND][1] is not None
    edit.apply(30, choice.Choice.AS_TYPED)
    edit.finish()
    document.recompute()
    shape = side.Shape.copy()
    shape.Placement = side.getGlobalPlacement()
    assert (shape.BoundBox.XMin, shape.BoundBox.XMax) == pytest.approx((-12, 18))  # dehors
    assert caisson.Width.Value == pytest.approx(612)


def near_face(part: Any, partner: Any) -> float:
    """Position de la face de ``part`` du côté de ``partner``, comptée vers ``partner``, sur
    l'axe de l'épaisseur de ``part`` (le plus petit côté de sa boîte)."""

    def box(obj: Any) -> Any:
        shape = obj.Shape.copy()
        shape.Placement = obj.getGlobalPlacement()
        return shape.BoundBox

    mine, other = box(part), box(partner)
    sizes = (mine.XLength, mine.YLength, mine.ZLength)
    axis = sizes.index(min(sizes))
    toward = 1 if other.Center[axis] > mine.Center[axis] else -1
    return float(
        toward
        * ((mine.XMin, mine.YMin, mine.ZMin), (mine.XMax, mine.YMax, mine.ZMax))[toward > 0][axis]
    )


def says_inward(text: str) -> bool:
    return text.startswith(("Vers l'intérieur", "Côté intérieur"))


def carcass_pieces(doc: Any) -> dict[str, Any]:
    """Pièces du caisson par défaut, côtés et dessous assemblés en queue d'aronde."""
    from freecad.menuiserie.features.furniture_bindings import members_of

    caisson, _ = api.make_carcass(doc)
    doc.recompute()
    pieces = {str(m.Label): m for m in members_of(caisson)}
    for side in ("Côté gauche", "Côté droit"):
        api.make_dovetail(pieces[side], pieces["Dessous"])
    doc.recompute()
    return pieces


@pytest.mark.parametrize("new", [30, 10])
@pytest.mark.parametrize(
    ("mover", "partner"),
    [
        ("H", "I"),  # pièce posée sur la face haute (corner)
        ("I", "H"),
        ("Côté gauche", "Dessous"),
        ("Côté droit", "Dessous"),
        ("Dessous", "Côté gauche"),
    ],
)
def test_le_libelle_dit_le_cote_ou_va_l_epaisseur(
    document: Any, mover: str, partner: str, new: float
) -> None:
    """Chaque choix proposé, une fois appliqué, déplace la face du côté qu'il annonce ; le
    premier choix n'est jamais d'accord avec « de l'autre côté » et l'est avec « allonger »."""
    host, guest, _joint = corner(document)
    pieces = {"H": host, "I": guest, **carcass_pieces(document)}
    part, other = pieces[mover], pieces[partner]
    edit = choice.ThicknessEdit(part)
    conflict = edit.probe(new)
    assert conflict is not None
    texts = {o.choice: o.text for o in conflict.options}
    adding = new > 18
    wording = texts.get(choice.Choice.AS_TYPED)
    if wording is not None:
        assert wording.startswith("Vers l'" if adding else "Côté ")
        assert says_inward(wording) is not says_inward(texts[choice.Choice.OTHER_SIDE])
        assert says_inward(wording) is says_inward(texts[choice.Choice.EXTEND])
    near = near_face(part, other)
    for chosen, text in texts.items():
        if chosen is choice.Choice.REVERT or any(
            o.choice is chosen and o.reason for o in conflict.options
        ):
            continue
        edit.apply(new, chosen)
        document.recompute()
        moved = near_face(part, other) - near
        assert says_inward(text) is (moved > 0 if adding else moved < 0), (mover, chosen, text)
        edit.restore()
        document.recompute()


def test_pieces_des_deux_cotes_libelle_neutre(document: Any) -> None:
    """Revue de sécurité (2026-11-24) : H assemblée à une pièce dessus et à une pièce dessous ;
    aucun côté à nommer, le premier choix dit « Telle que saisie »."""
    host, _guest, _joint = corner(document)
    below = api.make_wood_part(300, 150, 18, "chene", mark="J", doc=document)
    below.Placement = App.Placement(App.Vector(200, 0, -300), STANDING)
    document.recompute()
    api.make_mortise_tenon(host, below)
    document.recompute()
    edit = choice.ThicknessEdit(host)
    conflict = edit.probe(30)
    assert conflict is not None
    first = conflict.options[0]
    assert first.choice is choice.Choice.AS_TYPED
    assert first.text == "Telle que saisie"
