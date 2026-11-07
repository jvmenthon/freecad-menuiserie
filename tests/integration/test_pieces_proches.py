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
    api.make_dowels(lower, upper)
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
