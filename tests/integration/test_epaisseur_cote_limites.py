# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de l'épaisseur d'une pièce assemblée (ADR 0060) : pièce sans assemblage, plusieurs
pièces à fleur, expressions, membre d'ensemble, annulation, enregistrement, souris."""

from __future__ import annotations

import contextlib
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.test_epaisseur_cote import corner, holds

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
choice = pytest.importorskip("freecad.menuiserie.features.thickness_choice")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
thickness_drag = pytest.importorskip("freecad.menuiserie.features.thickness_drag")
Vec3 = pytest.importorskip("freecad.menuiserie.core.geometry").Vec3


def two_hosts(doc: Any) -> tuple[Any, Any, Any, Any, Any]:
    """I debout, deux H à fleur de sa face extérieure (l'un à chaque bout)."""
    host, guest, joint = corner(doc)
    top = api.make_wood_part(400, 150, 18, "chene", mark="K", doc=doc)
    top.Label = "K"
    top.Placement = App.Placement(App.Vector(0, 0, 400), App.Rotation())
    doc.recompute()
    joint2 = api.make_dovetail(top, guest)
    doc.recompute()
    return host, top, guest, joint, joint2


def test_piece_sans_assemblage(document: Any) -> None:
    part = api.make_wood_part(400, 150, 18, "chene", mark="A", doc=document)
    document.recompute()
    assert not choice.has_joints(part)
    assert choice.ThicknessEdit(part).conflict(30) is None
    assert part.Thickness.Value == 30
    assert thickness_drag.drag_follow(part, False) is None
    memento = drag.begin_drag(part)
    assert drag.resize_part(memento, "Thickness", 40, Vec3(0, 0, 0)) == ""
    assert part.Thickness.Value == 40
    assert drag.end_drag(memento) == []


@pytest.mark.parametrize("value", [0.0, -5.0, 1e9])
def test_epaisseurs_invalides_ou_enormes_ne_cassent_pas_le_document(
    document: Any, value: float
) -> None:
    """Valeurs limites passées à l'API de l'encadré : exception propre ou conflit, jamais un
    document corrompu ni un état de départ perdu."""
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    with contextlib.suppress(ValueError, App.Base.FreeCADError):
        edit.conflict(value)
    edit.restore()
    assert guest.Thickness.Value == 18
    assert host.Length.Value == 400
    assert holds(document, joint)


def test_plusieurs_pieces_a_fleur_sont_toutes_allongees(document: Any) -> None:
    host, top, guest, joint, joint2 = two_hosts(document)
    edit = choice.ThicknessEdit(guest)
    conflict = edit.conflict(30)
    assert conflict is not None
    assert "« H »" in conflict.options[1].text or "« K »" in conflict.options[1].text
    edit.apply(30, choice.Choice.EXTEND)
    assert (host.Length.Value, top.Length.Value) == (412, 412)
    assert holds(document, joint) and holds(document, joint2)
    edit.apply(30, choice.Choice.REVERT)
    assert (host.Length.Value, top.Length.Value) == (400, 400)


def test_autre_piece_pilotee_par_une_expression(document: Any) -> None:
    host, guest, joint = corner(document)
    host.setExpression("Length", "400 mm")
    document.recompute()
    edit = choice.ThicknessEdit(guest)
    conflict = edit.conflict(30)
    assert conflict is not None
    reasons = {o.choice: o.reason for o in conflict.options}
    assert reasons[choice.Choice.EXTEND] is not None
    assert "expression" in reasons[choice.Choice.EXTEND]
    assert conflict.preferred() is choice.Choice.OTHER_SIDE
    with pytest.raises(choice.UnavailableError):
        edit.apply(30, choice.Choice.EXTEND)
    assert host.Length.Value == 400 and guest.Thickness.Value == 18
    assert holds(document, joint)


def test_placement_pilote_de_la_piece_grise_vers_l_interieur(document: Any) -> None:
    _host, guest, _joint = corner(document)
    guest.setExpression("Placement.Base.x", "18 mm")
    document.recompute()
    conflict = choice.ThicknessEdit(guest).conflict(30)
    assert conflict is not None
    reasons = {o.choice: o.reason for o in conflict.options}
    assert reasons[choice.Choice.OTHER_SIDE] is not None
    assert guest.Thickness.Value == 18


def test_cote_epaisseur_pilotee_ne_perd_pas_son_expression(document: Any) -> None:
    host, guest, _joint = corner(document)
    guest.setExpression("Thickness", "18 mm")
    document.recompute()
    edit = choice.ThicknessEdit(guest)
    with contextlib.suppress(ValueError, App.Base.FreeCADError):
        edit.conflict(30)
    edit.restore()
    assert any(path == "Thickness" for path, _ in guest.ExpressionEngine)
    assert host.Length.Value == 400


def test_partenaire_membre_d_ensemble(document: Any) -> None:
    host, guest, joint = corner(document)
    api.make_furniture([host], "Meuble")
    document.recompute()
    assert api.furniture_of(host) is not None
    conflict = choice.ThicknessEdit(guest).conflict(30)
    if conflict is None:
        pytest.skip("assemblage non défait : ensemble relié")
    reasons = {o.choice: o.reason for o in conflict.options}
    assert "ensemble" in (reasons[choice.Choice.EXTEND] or "")
    memento = drag.begin_drag(guest)
    stop = drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert stop.startswith("Butée") and "ensemble" in stop
    assert guest.Thickness.Value == 18
    drag.end_drag(memento)
    assert holds(document, joint)


def test_piece_membre_d_ensemble_pas_de_suivi(document: Any) -> None:
    host, guest, _joint = corner(document)
    api.make_furniture([guest], "Meuble")
    document.recompute()
    assert thickness_drag.drag_follow(guest, False) is None
    assert host.Length.Value == 400


def test_echap_apres_plusieurs_pas_et_deux_faces(document: Any) -> None:
    host, top, guest, _joint, _joint2 = two_hosts(document)
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, -12), lowered=True)
    drag.resize_part(memento, "Thickness", 35, Vec3(0, 0, 0))
    drag.restore(memento)
    for part in (host, top):
        assert part.Length.Value == 400
    assert tuple(host.Placement.Base) == pytest.approx((0, 0, 0))
    assert tuple(top.Placement.Base) == pytest.approx((0, 0, 400))
    assert guest.Thickness.Value == 18
    assert tuple(guest.Placement.Base) == pytest.approx((18, 0, 18))
    document.recompute()
    assert stale_or_invalid(document) == []


def test_souris_plusieurs_pieces_et_retour_au_depart(document: Any) -> None:
    host, top, guest, joint, joint2 = two_hosts(document)
    memento = drag.begin_drag(guest)
    assert drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0)) == ""
    assert (host.Length.Value, top.Length.Value) == (412, 412)
    assert drag.resize_part(memento, "Thickness", 18, Vec3(0, 0, 0)) == ""  # revenu au départ
    assert (host.Length.Value, top.Length.Value) == (400, 400)
    drag.end_drag(memento)
    assert holds(document, joint) and holds(document, joint2)


def test_souris_butee_si_une_seule_des_pieces_est_bloquee(document: Any) -> None:
    host, top, guest, _joint, _joint2 = two_hosts(document)
    top.setExpression("Length", "400 mm")
    document.recompute()
    memento = drag.begin_drag(guest)
    stop = drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert stop.startswith("Butée")
    assert host.Length.Value == 400 and guest.Thickness.Value == 18  # rien d'à moitié écrit
    drag.end_drag(memento)


def test_souris_amincir_raccourcit(document: Any) -> None:
    host, guest, joint = corner(document)
    memento = drag.begin_drag(guest)
    assert drag.resize_part(memento, "Thickness", 12, Vec3(0, 0, 0)) == ""
    assert host.Length.Value == 394
    messages = drag.end_drag(memento)
    assert any("raccourcie" in m for m in messages)
    assert holds(document, joint)


def test_annuler_retablir_apres_allonger(document: Any) -> None:
    host, guest, joint = corner(document)
    document.UndoMode = 1
    document.openTransaction("Modifier une pièce de bois")
    edit = choice.ThicknessEdit(guest)
    edit.conflict(30)
    edit.apply(30, choice.Choice.EXTEND)
    document.commitTransaction()
    document.recompute()
    assert document.UndoNames[0] == "Modifier une pièce de bois"
    document.undo()
    document.recompute()
    assert (host.Length.Value, guest.Thickness.Value) == (400, 18)
    assert tuple(host.Placement.Base) == pytest.approx((0, 0, 0))
    document.redo()
    document.recompute()
    assert (host.Length.Value, guest.Thickness.Value) == (412, 30)
    assert holds(document, joint)


def test_enregistrer_rouvrir_apres_allonger(document: Any, rouvrir: Any) -> None:
    _host, guest, _joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    edit.conflict(30)
    edit.apply(30, choice.Choice.EXTEND)
    document.recompute()
    reopened = rouvrir(document)
    reopened.recompute()
    host2 = next(o for o in reopened.Objects if getattr(o, "Label", "") == "H")
    guest2 = next(o for o in reopened.Objects if getattr(o, "Label", "") == "I")
    assert (host2.Length.Value, guest2.Thickness.Value) == (412, 30)
    assert tuple(host2.Placement.Base) == pytest.approx((-12, 0, 0))
    assert stale_or_invalid(reopened) == []


def test_epaisseur_revenue_a_l_origine_ne_laisse_rien(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    edit.conflict(30)
    edit.apply(30, choice.Choice.EXTEND)
    assert edit.conflict(18) is None  # saisie revenue à l'origine : plus de conflit
    assert (host.Length.Value, guest.Thickness.Value) == (400, 18)
    assert tuple(host.Placement.Base) == pytest.approx((0, 0, 0))
    assert tuple(guest.Placement.Base) == pytest.approx((18, 0, 18))
    assert holds(document, joint)


def test_sous_ensemble_partenaire(document: Any) -> None:
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, parts = caisson(document)
    api.make_furniture([desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub], "Bureau")
    document.recompute()
    member = parts[0] if isinstance(parts, (list, tuple)) else next(iter(parts.values()))
    assert thickness_drag.drag_follow(member, False) is None
