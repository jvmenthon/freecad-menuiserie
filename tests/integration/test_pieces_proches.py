# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces proches qui ne se touchent pas : déplacer ou agrandir jusqu'au contact avant
l'assemblage (ADR 0039)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

GAP = 8.0
THICKNESS = 22.0


def stack(doc: Any, gap: float = GAP) -> tuple[Any, Any]:
    """Deux planches superposées : la seconde à ``gap`` mm au-dessus de la première."""
    lower = api.make_wood_part(400, 60, THICKNESS, "chene", mark="A", doc=doc)
    upper = api.make_wood_part(400, 60, THICKNESS, "chene", mark="B", doc=doc)
    upper.Placement = App.Placement(App.Vector(0, 0, THICKNESS + gap), App.Rotation())
    doc.recompute()
    return lower, upper


def test_pieces_proches_proposent_deplacer_et_agrandir(document: Any) -> None:
    lower, upper = stack(document)
    closing = api.closing_options(lower, upper)
    assert closing is not None
    assert closing.distance == pytest.approx(GAP)
    assert closing.options == {"move": upper.Label, "grow": upper.Label}


@pytest.mark.parametrize("gap", [0.0, 50.0])
def test_rien_a_proposer_au_contact_ou_trop_loin(document: Any, gap: float) -> None:
    lower, upper = stack(document, gap)
    assert api.closing_options(lower, upper) is None


def test_deplacer_amene_l_invitee_au_contact(document: Any) -> None:
    lower, upper = stack(document)
    api.close_gap(lower, upper, "move")
    assert upper.Placement.Base.z == pytest.approx(THICKNESS)
    assert upper.Thickness.Value == pytest.approx(THICKNESS)
    assert api.closing_options(lower, upper) is None


def test_assemblage_possible_apres_le_deplacement(document: Any) -> None:
    """Montant et traverse (cadre de référence des tourillons), la traverse à 8 mm du montant."""
    host = api.make_wood_part(600, 60, 22, "chene", mark="M", doc=document)
    guest = api.make_wood_part(280, 60, 22, "chene", mark="T", doc=document)
    rotation = App.Rotation(App.Vector(0, 0, 1), 90)
    guest.Placement = App.Placement(App.Vector(60, 60 + GAP, 0), rotation)
    document.recompute()
    closing = api.closing_options(host, guest)
    assert closing is not None
    assert closing.distance == pytest.approx(GAP)
    api.close_gap(host, guest, "move")
    assert guest.Placement.Base.y == pytest.approx(60.0)
    api.make_dowels(host, guest)
    document.recompute()
    assert stale_or_invalid(document) == []


def test_agrandir_etend_l_invitee_vers_l_hote(document: Any) -> None:
    lower, upper = stack(document)
    api.close_gap(lower, upper, "grow")
    assert upper.Thickness.Value == pytest.approx(THICKNESS + GAP)
    assert upper.Placement.Base.z == pytest.approx(THICKNESS)  # sa face haute n'a pas bougé
    assert lower.Thickness.Value == pytest.approx(THICKNESS)
    assert api.closing_options(lower, upper) is None


def test_agrandir_une_invitee_placee_sous_l_hote(document: Any) -> None:
    lower, upper = stack(document)
    api.close_gap(upper, lower, "grow")  # lower est l'invitée, au-dessous de l'hôte
    assert lower.Thickness.Value == pytest.approx(THICKNESS + GAP)
    assert lower.Placement.Base.z == pytest.approx(0.0)
    assert upper.Placement.Base.z == pytest.approx(THICKNESS + GAP)


def test_formule_de_l_invitee_reporte_l_option_sur_l_hote(document: Any) -> None:
    lower, upper = stack(document)
    upper.setExpression("Thickness", f"{THICKNESS} mm")
    closing = api.closing_options(lower, upper)
    assert closing is not None
    assert closing.options["grow"] == lower.Label
    api.close_gap(lower, upper, "grow")
    assert lower.Thickness.Value == pytest.approx(THICKNESS + GAP)
    assert upper.Thickness.Value == pytest.approx(THICKNESS)


def test_option_inconnue_refusee(document: Any) -> None:
    lower, upper = stack(document)
    with pytest.raises(ValueError, match="rapprochées"):
        api.close_gap(lower, upper, "teleporter")


def frame_with_joint(doc: Any) -> tuple[Any, Any, Any, Any]:
    """Traverse T déjà assemblée au montant M2 (en y = 340) ; le montant M est à 8 mm de son
    autre bout. Rapprocher T de M défait l'assemblage avec M2."""
    rotation = App.Rotation(App.Vector(0, 0, 1), 90)
    near = api.make_wood_part(600, 60, 22, "chene", mark="M", doc=doc)
    far = api.make_wood_part(600, 60, 22, "chene", mark="N", doc=doc)
    rail = api.make_wood_part(280, 60, 22, "chene", mark="T", doc=doc)
    near.Placement = App.Placement(App.Vector(0, -GAP, 0), App.Rotation())
    far.Placement = App.Placement(App.Vector(0, 340, 0), App.Rotation())
    rail.Placement = App.Placement(App.Vector(60, 60, 0), rotation)
    doc.recompute()
    joint = api.make_dowels(far, rail)
    doc.recompute()
    return near, far, rail, joint


def test_deplacer_qui_defait_un_assemblage_peut_etre_annule(document: Any) -> None:
    drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
    near, _far, rail, joint = frame_with_joint(document)
    asked: list[Any] = []

    def refuse(labels: Any) -> bool:
        asked.append(list(labels))
        return False

    with pytest.raises(drag.DragCancelledError):
        api.close_gap(near, rail, "move", refuse)
    assert len(asked) == 1
    assert rail.Placement.Base.y == pytest.approx(60.0)
    assert document.getObject(joint.Name) is not None


def test_deplacer_qui_defait_un_assemblage_peut_le_supprimer(document: Any) -> None:
    near, _far, rail, joint = frame_with_joint(document)
    name = joint.Name
    api.close_gap(near, rail, "move", lambda labels: True)
    assert rail.Placement.Base.y == pytest.approx(60.0 - GAP)
    assert document.getObject(name) is None


def test_agrandir_garde_l_assemblage_de_l_autre_bout(document: Any) -> None:
    near, _far, rail, joint = frame_with_joint(document)
    api.close_gap(near, rail, "grow", lambda labels: pytest.fail("rien n'est défait"))
    assert rail.Length.Value == pytest.approx(280.0 + GAP)
    assert document.getObject(joint.Name) is not None
    assert "Invalid" not in joint.State


def test_option_deplacer_signale_les_assemblages_portes(document: Any) -> None:
    near, _far, rail, _joint = frame_with_joint(document)
    closing = api.closing_options(near, rail)
    assert closing is not None
    assert closing.move_has_joints is True
