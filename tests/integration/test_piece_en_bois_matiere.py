# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôle de la matière réelle des assemblages d'une pièce en bois (PD-e, critère E3 de
``docs/specs/piece-en-bois.md``, § 4.5 et § 4.9).

Un assemblage placé dans un vide ou sur une face courbe de la forme avertit, sans refus ; sur une
face plane qui coïncide avec la boîte d'encombrement, aucun avertissement.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.pieces_galbees import (
    machined_volume,
    notched_block,
    placed,
    shaped,
    void_block,
    wood_at,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

GUEST = (150.0, 40.0, 20.0)


def warnings_of(report: Any) -> list[str]:
    """Avertissements de la vue rapport sur la matière manquante."""
    return [text for text in report.de_niveau("Warning") if "manque" in text]


def joined(document: Any, source: Any, x: float, y: float) -> tuple[Any, Any, Any]:
    """Pièce en bois de ``source`` (hôte, repère H) et pièce de bois dont le bout touche son chant
    y = ``y``, le long de l'axe Y, du côté x - 40 à x ; tenon-mortaise créé."""
    host = shaped(source, "H")
    assert (host.Length.Value, host.Width.Value, host.Thickness.Value) == pytest.approx(
        (200.0, 100.0, 50.0), abs=1e-3
    )
    guest = wood_at(document, GUEST, placed(host.Placement, x, y, 10, 90), "I")
    return host, guest, api.make_mortise_tenon(host, guest)


def test_mortaise_dans_un_vide_avertit_sans_refus(document: Any, vue_rapport: Any) -> None:
    host, _guest, joint = joined(document, void_block(document), 190, 100)
    messages = warnings_of(vue_rapport)
    assert messages, "la mortaise est entièrement dans le vide de la forme"
    assert all(str(joint.Label) in text and "« H »" in text for text in messages)
    assert "100 %" in messages[0]
    # Aucun refus : l'assemblage est fait, la pièce usinée existe et garde la forme réelle.
    assert joint.isValid()
    assert api.machined_part_of(host).isValid()
    assert machined_volume(host) == pytest.approx(host.Shape.Volume, rel=1e-6)
    assert stale_or_invalid(document) == []


def test_mortaise_sur_une_face_courbe_avertit(document: Any, vue_rapport: Any) -> None:
    host, _guest, joint = joined(document, notched_block(document), 120, 100)
    messages = warnings_of(vue_rapport)
    assert messages, "la mortaise s'ouvre dans l'encoche cylindrique du chant"
    assert all(str(joint.Label) in text and "« H »" in text for text in messages)
    assert joint.isValid()
    assert api.machined_part_of(host).isValid()


def test_face_plane_dans_la_boite_sans_avertissement(document: Any, vue_rapport: Any) -> None:
    host, _guest, joint = joined(document, void_block(document), 100, 100)
    assert warnings_of(vue_rapport) == []
    assert joint.isValid()
    assert machined_volume(host) < host.Shape.Volume  # la mortaise est bien dans la matière


def test_face_plane_a_cote_de_l_encoche_sans_avertissement(document: Any, vue_rapport: Any) -> None:
    """Le chant y = 0 est plan et coïncide avec la boîte, même si le chant opposé est creusé."""
    host = shaped(notched_block(document), "H")
    guest = wood_at(document, GUEST, placed(host.Placement, 190, 0, 10, -90), "I")
    api.make_mortise_tenon(host, guest)
    assert warnings_of(vue_rapport) == []
    assert machined_volume(host) < host.Shape.Volume


def test_epaulement_du_tenon_dans_un_vide_avertit(document: Any, vue_rapport: Any) -> None:
    """Pièce en bois invitée dont le bout de la boîte (x = 200) est un vide : le tenon ne
    s'appuie sur aucune matière."""
    host = wood_at(document, (400.0, 300.0, 60.0), App.Placement(), "H")
    guest = shaped(void_block(document), "I")
    guest.Placement = placed(host.Placement, 250, -200, 5, 90)  # son bout x = 200 touche y = 0
    document.recompute()
    joint = api.make_mortise_tenon(host, guest)
    messages = warnings_of(vue_rapport)
    assert messages
    assert all(str(joint.Label) in text and "« I »" in text for text in messages)
    assert joint.isValid()
    assert api.machined_part_of(guest).isValid()
