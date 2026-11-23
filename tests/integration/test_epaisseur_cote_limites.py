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
common = pytest.importorskip("freecad.menuiserie.features.thickness_common")
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
    assert not common.has_joints(part)
    assert choice.ThicknessEdit(part).probe(30) is None
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
        edit.probe(value)
    edit.restore()
    assert guest.Thickness.Value == 18
    assert host.Length.Value == 400
    assert holds(document, joint)


def test_plusieurs_pieces_a_fleur_sont_toutes_allongees(document: Any) -> None:
    host, top, guest, joint, joint2 = two_hosts(document)
    edit = choice.ThicknessEdit(guest)
    conflict = edit.probe(30)
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
    conflict = edit.probe(30)
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
    conflict = choice.ThicknessEdit(guest).probe(30)
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
        edit.probe(30)
    edit.restore()
    assert any(path == "Thickness" for path, _ in guest.ExpressionEngine)
    assert host.Length.Value == 400


def test_partenaire_membre_d_ensemble(document: Any) -> None:
    host, guest, joint = corner(document)
    api.make_furniture([host], "Meuble")
    document.recompute()
    assert api.furniture_of(host) is not None
    conflict = choice.ThicknessEdit(guest).probe(30)
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


def test_piece_membre_d_ensemble_suivie_sauf_a_cotes_fixes(document: Any) -> None:
    """jv, 2026-11-23 : un membre assemblé est suivi comme une pièce seule ; à cotes fixes, il
    garde l'ADR 0019 (pas de suivi)."""
    host, guest, _joint = corner(document)
    api.make_furniture([guest], "Meuble")
    document.recompute()
    assert thickness_drag.drag_follow(guest, False) is not None
    api.set_member_options(guest, locked=True)
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
    edit.probe(30)
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
    edit.probe(30)
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
    edit.probe(30)
    edit.apply(30, choice.Choice.EXTEND)
    assert edit.probe(18) is None  # saisie revenue à l'origine : plus de conflit
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


JOINT_MAKERS = {
    "tenon": api.make_mortise_tenon,
    "tourillons": api.make_dowels,
    "feuillure": api.make_rabbet,
    "mi-bois": api.make_half_lap,
}


def _joined(doc: Any, maker: Any) -> tuple[Any, Any, Any]:
    host, guest, _dovetail = corner(doc)
    doc.removeObject(_dovetail.Name)
    doc.recompute()
    joint = maker(host, guest)
    doc.recompute()
    if not holds(doc, joint):
        pytest.skip("assemblage non valide dans cette disposition d'angle")
    return host, guest, joint


@pytest.mark.parametrize("name", sorted(JOINT_MAKERS))
@pytest.mark.parametrize("which", ["host", "guest"])
def test_autres_assemblages_choix_et_retour(document: Any, name: str, which: str) -> None:
    """Pour chaque type d'assemblage : « Laisser en l'état » en tête s'il ne défait rien, chaque
    choix possible laisse un document sain, « Revenir » rend l'état de départ."""
    host, guest, joint = _joined(document, JOINT_MAKERS[name])
    part = host if which == "host" else guest
    start = {o.Name: (*o.Placement.Base[:], o.Length.Value) for o in (host, guest)}
    edit = choice.ThicknessEdit(part)
    conflict = edit.probe(24)
    assert stale_or_invalid(document) == [] or conflict is not None
    if conflict is None:
        assert part.Thickness.Value == 24
        return
    offered = [o.choice for o in conflict.options]
    assert offered[-1] is choice.Choice.REVERT
    assert part.Thickness.Value == 18  # état de départ rendu
    for option in conflict.options:
        if option.reason is not None:
            continue
        edit.apply(24, option.choice)
        assert holds(document, joint), (name, which, option.choice)
    edit.apply(24, choice.Choice.REVERT)
    assert part.Thickness.Value == 18
    for o in (host, guest):
        assert (*o.Placement.Base[:], o.Length.Value) == pytest.approx(start[o.Name])
    assert holds(document, joint)


@pytest.mark.parametrize("value", [2.0, 0.5, 1e-3])
def test_saisie_trop_mince_n_ecrit_rien_et_n_abime_rien(document: Any, value: float) -> None:
    """Saisie transitoire (« 2 » avant « 22 ») : aucun choix ne tient ou le conflit est rendu
    sans trace ; le document reste sain et la saisie suivante repart de l'état de départ."""
    _host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(guest)
    try:
        conflict = edit.probe(value)
    except ValueError:  # sous la cote minimale : refusée proprement, rien d'écrit
        assert guest.Thickness.Value == 18
        assert holds(document, joint)
        return
    assert conflict is not None
    assert guest.Thickness.Value == 18
    assert holds(document, joint)
    again = edit.probe(22)
    assert again is not None
    edit.apply(22, again.preferred() or choice.Choice.REVERT)
    assert holds(document, joint)


def test_laisser_en_l_etat_amincie_et_retour_au_depart(document: Any) -> None:
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(host)
    conflict = edit.probe(12)
    assert conflict is not None
    assert conflict.options[0].choice is choice.Choice.AS_TYPED
    edit.apply(12, choice.Choice.AS_TYPED)
    assert holds(document, joint)
    assert edit.probe(18) is None
    assert (host.Thickness.Value, guest.Placement.Base.z) == (18, pytest.approx(18))
    assert holds(document, joint)


def test_saisies_successives_avec_laisser_affiche(document: Any) -> None:
    """30 puis 24 puis 18 sur H (rien n'est défait) : chaque saisie repart du départ."""
    host, guest, joint = corner(document)
    edit = choice.ThicknessEdit(host)
    for value in (30, 24):
        conflict = edit.probe(value)
        assert conflict is not None
        assert conflict.options[0].choice is choice.Choice.AS_TYPED
        edit.apply(value, choice.Choice.AS_TYPED)
        assert guest.Placement.Base.z == pytest.approx(value)
    assert edit.probe(18) is None
    assert guest.Placement.Base.z == pytest.approx(18)
    assert holds(document, joint)


def test_deux_assemblages_laisser_et_parts(document: Any) -> None:
    host, top, guest, joint, joint2 = two_hosts(document)
    edit = choice.ThicknessEdit(guest)
    conflict = edit.probe(30)
    assert conflict is not None
    assert {p.Name for p in edit.parts} >= {host.Name, top.Name, guest.Name}
    edit2 = choice.ThicknessEdit(host)
    conflict2 = edit2.probe(30)
    assert conflict2 is not None
    for pick in (choice.Choice.OTHER_SIDE, choice.Choice.EXTEND, choice.Choice.AS_TYPED):
        try:
            edit2.apply(30, pick)
        except choice.UnavailableError:
            continue
        assert holds(document, joint) and holds(document, joint2), pick


def test_annuler_apres_laisser_en_l_etat(document: Any) -> None:
    host, guest, joint = corner(document)
    document.UndoMode = 1
    document.openTransaction("Modifier une pièce de bois")
    edit = choice.ThicknessEdit(host)
    edit.probe(30)
    edit.apply(30, choice.Choice.AS_TYPED)
    document.commitTransaction()
    document.recompute()
    document.undo()
    document.recompute()
    assert (host.Thickness.Value, guest.Placement.Base.z) == (18, pytest.approx(18))
    document.redo()
    document.recompute()
    assert (host.Thickness.Value, guest.Placement.Base.z) == (30, pytest.approx(30))
    assert holds(document, joint)


def test_assemblage_orphelin_rien_a_proposer(document: Any) -> None:
    """Autre pièce de l'assemblage disparue : rien à proposer, document jamais à moitié écrit
    (revue sécurité, 2026-11-16)."""
    host, guest, joint = corner(document)
    joint.HostPart = None
    edit = choice.ThicknessEdit(guest)
    try:
        conflict = edit.probe(30)
    except choice.UnavailableError:
        assert guest.Thickness.Value == 18
    else:
        assert conflict is None
    assert host.Length.Value == 400
