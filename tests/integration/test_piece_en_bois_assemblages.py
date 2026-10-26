# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages avec une pièce en bois (PD-e, critères E1, E2, E4 et E5 de
``docs/specs/piece-en-bois.md``, ADR 0006 complété par l'ADR 0020).

Tenon-mortaise entre une traverse galbée (corps PartDesign, pièce en bois) et une pièce de bois,
dans les deux sens, entre deux pièces en bois ; forme usinée réelle ; formes usinées des pièces
de bois inchangées ; recalcul quand le dessin change ; tenon dans la liste de débit.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import RAIL_VOLUME, STILE_VOLUME, Cadre, stale_or_invalid
from tests.integration.pieces_galbees import (
    BOX_VOLUME,
    box_volume,
    curved_rail,
    expected_volume,
    machined_volume,
    mixed_montage,
    placed,
    shaped,
    twin_gains,
    wood_at,
)
from tests.integration.test_piece_en_bois import leg
from tests.integration.types_assemblages import SCENARIOS, Scenario

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

IDENTITY = App.Placement()
GUEST = (200.0, 40.0, 20.0)


def assert_machined_valid(part: Any) -> None:
    """Pièce usinée de ``part`` : valide, un seul solide, au ``Placement`` de la pièce."""
    machined = api.machined_part_of(part)
    assert machined is not None
    assert machined.isValid()
    assert machined.Base == part
    assert len(machined.Shape.Solids) == 1
    assert machined.Shape.isValid()
    assert machined.Placement == part.Placement
    assert part.Visibility is False


def rail_on_wood_face(document: Any) -> tuple[Any, Any]:
    """Traverse galbée (hôte) et pièce de bois (invitée) dont le bout touche le chant plat y = 0."""
    host = shaped(curved_rail(document), "G")
    guest = wood_at(document, GUEST, placed(host.Placement, 300, 0, 10, -90), "T")
    return host, guest


# --- E1, E2 : pièce en bois hôte, pièce de bois invitée --------------------------------------


def test_pied_hote_et_piece_de_bois_invitee(document: Any, vue_rapport: Any) -> None:
    host, guest = rail_on_wood_face(document)
    assert (host.Length.Value, host.Width.Value, host.Thickness.Value) == pytest.approx(
        (720.0, 95.0, 45.0), abs=1e-3
    )
    joint = api.make_mortise_tenon(host, guest)
    gains = twin_gains(document, host, guest)
    document.recompute()
    assert joint.HostPart == host
    assert joint.GuestPart == guest
    assert_machined_valid(host)
    assert_machined_valid(guest)
    # E2 : la pièce usinée part de la forme réelle, pas de la boîte.
    assert machined_volume(host) < BOX_VOLUME
    assert machined_volume(host) == pytest.approx(expected_volume(host, gains[0]), rel=1e-6)
    assert machined_volume(guest) == pytest.approx(box_volume(guest) + gains[1], rel=1e-6)
    assert gains[0] < 0 < gains[1]  # mortaise dans l'hôte, tenon sur l'invitée
    assert vue_rapport.de_niveau("Warning") == []
    assert stale_or_invalid(document) == []


def test_pied_invite_et_piece_de_bois_hote(document: Any, vue_rapport: Any) -> None:
    host = wood_at(document, (600.0, 200.0, 60.0), IDENTITY, "H")
    guest = shaped(curved_rail(document), "G")
    guest.Placement = placed(host.Placement, 300, 200, 5, 90)
    document.recompute()
    api.make_mortise_tenon(host, guest)
    gains = twin_gains(document, host, guest)
    document.recompute()
    assert_machined_valid(host)
    assert_machined_valid(guest)
    assert machined_volume(guest) == pytest.approx(expected_volume(guest, gains[1]), rel=1e-6)
    assert machined_volume(guest) > guest.Shape.Volume  # le tenon s'ajoute à la forme réelle
    assert machined_volume(host) == pytest.approx(box_volume(host) + gains[0], rel=1e-6)
    assert vue_rapport.de_niveau("Warning") == []


def test_deux_pieces_en_bois(document: Any, vue_rapport: Any) -> None:
    host = shaped(curved_rail(document), "G")
    guest = shaped(leg(document), "P")
    guest.Placement = placed(host.Placement, 300, 0, 0, -90)
    document.recompute()
    assert (guest.Length.Value, guest.Width.Value, guest.Thickness.Value) == pytest.approx(
        (720.0, 95.0, 45.0), abs=1e-3
    )
    api.make_mortise_tenon(host, guest)
    gains = twin_gains(document, host, guest)
    document.recompute()
    for part, gain in ((host, gains[0]), (guest, gains[1])):
        assert_machined_valid(part)
        assert machined_volume(part) == pytest.approx(expected_volume(part, gain), rel=1e-6)
    assert vue_rapport.de_niveau("Warning") == []


ROLES = [(True, False), (False, True), (True, True)]


@pytest.mark.parametrize("roles", ROLES, ids=["hote", "invitee", "deux"])
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_six_types_avec_une_piece_en_bois(
    document: Any, scenario: Scenario, roles: tuple[bool, bool], vue_rapport: Any
) -> None:
    """Rainure, feuillure, tourillons, mi-bois, queue d'aronde, onglet : une pièce en bois qui a
    la forme de sa boîte est usinée comme la pièce de bois, hôte, invitée ou les deux (E1)."""
    montage = mixed_montage(document, scenario, roles)
    montage.assert_expected()
    assert api.is_shaped_part(montage.host) is roles[0]
    assert api.is_shaped_part(montage.guest) is roles[1]
    assert montage.joint.isValid()
    assert stale_or_invalid(document) == []
    assert vue_rapport.de_niveau("Warning") == []


@pytest.mark.parametrize("roles", ROLES, ids=["hote", "invitee", "deux"])
def test_tenon_mortaise_avec_une_piece_en_bois_de_la_forme_de_sa_boite(
    document: Any, roles: tuple[bool, bool], vue_rapport: Any
) -> None:
    mortise_scenario = Scenario(
        "tenon-mortaise",
        "make_mortise_tenon",
        ((600, 60, 22), (0, 0, 0)),
        ((280, 60, 22), (60, 60, 90)),
        600 * 60 * 22 - 42 * 40 * 7,
        280 * 60 * 22 + 40 * 40 * 7,
    )
    montage = mixed_montage(document, mortise_scenario, roles)
    montage.assert_expected()
    assert vue_rapport.de_niveau("Warning") == []


# --- E2 : pièces de bois inchangées -------------------------------------------------------------


def local_extent(part: Any) -> tuple[float, float, float]:
    """Étendue de la forme usinée de ``part`` dans son repère."""
    shape = api.machined_part_of(part).Shape.copy()
    shape.Placement = App.Placement()
    box_ = shape.BoundBox
    return (box_.XLength, box_.YLength, box_.ZLength)


def test_formes_usinees_des_pieces_de_bois_inchangees(cadre: Cadre) -> None:
    cadre.assemble()
    for mark in ("M1", "M2"):
        assert cadre.volume(mark) == pytest.approx(STILE_VOLUME)
        assert local_extent(cadre.parts[mark]) == pytest.approx((600, 60, 22))
    for mark in ("T1", "T2"):
        assert cadre.volume(mark) == pytest.approx(RAIL_VOLUME)
        assert local_extent(cadre.parts[mark]) == pytest.approx((360, 60, 22))
    for mark in cadre.parts:
        shape = cadre.machined(mark).Shape
        assert shape.isValid()
        assert len(shape.Solids) == 1


# --- E4 : le dessin change, tout se recalcule ---------------------------------------------------


def test_allonger_le_pad_recalcule_la_mortaise_et_la_piece_usinee(document: Any) -> None:
    body = curved_rail(document)
    host = shaped(body, "G")
    guest = wood_at(document, GUEST, placed(host.Placement, 300, 0, 10, -90), "T")
    joint = api.make_mortise_tenon(host, guest)
    old_volume = host.Shape.Volume
    mortise = old_volume - machined_volume(host)
    assert mortise > 0
    machined = api.machined_part_of(host)
    # Graphe sans cycle : source → pièce en bois → assemblage → pièce usinée.
    assert body in host.OutListRecursive
    assert host in joint.OutList
    assert joint in machined.OutList
    assert machined.Base == host
    assert machined not in body.OutListRecursive
    assert joint not in body.OutListRecursive
    body.Group[-1].Length = 60.0  # la protrusion passe de 45 à 60 mm
    document.recompute()
    assert host.Thickness.Value == pytest.approx(60.0, abs=1e-3)
    assert stale_or_invalid(document) == []
    assert machined_volume(host) == pytest.approx(host.Shape.Volume - mortise, rel=1e-6)
    assert host.Shape.Volume == pytest.approx(old_volume * 60 / 45, rel=1e-6)
    assert joint.isValid()


def test_assemblage_conserve_apres_reouverture(document: Any, rouvrir: Any) -> None:
    host, guest = rail_on_wood_face(document)
    api.make_mortise_tenon(host, guest)
    volumes = (machined_volume(host), machined_volume(guest))
    reopened = rouvrir(document)
    reopened.recompute()
    parts = [obj for obj in reopened.Objects if obj.Label in ("G", "T")]
    assert {obj.Label for obj in parts} == {"G", "T"}
    by_label = {obj.Label: obj for obj in parts}
    assert machined_volume(by_label["G"]) == pytest.approx(volumes[0], rel=1e-6)
    assert machined_volume(by_label["T"]) == pytest.approx(volumes[1], rel=1e-6)
    assert api.machined_part_of(by_label["G"]).Version == 1
    assert stale_or_invalid(reopened) == []


# --- E5 : liste de débit ------------------------------------------------------------------------


def test_le_tenon_d_une_piece_en_bois_est_compte_au_debit(document: Any) -> None:
    host = wood_at(document, (600.0, 200.0, 60.0), IDENTITY, "H")
    guest = shaped(curved_rail(document), "G")
    guest.Placement = placed(host.Placement, 300, 200, 5, 90)
    document.recompute()
    api.make_mortise_tenon(host, guest, tenon_length=30)
    document.recompute()
    (line,) = [line for line in api.cut_list_of(document).lines if "G" in line.marks]
    assert line.additions.length == pytest.approx(30)
    assert line.finished.length == pytest.approx(720.0, abs=1e-3)
    assert line.shape is not None
