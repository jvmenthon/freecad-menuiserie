# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mi-bois dans le document (J4e, critère B3) ; réouverture, annulation et compatibilité sont
couvertes avec les autres types (``test_assemblages_types_persistance.py``)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import HALF_LAP, build, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

BLANK = 600 * 60 * 22


def test_objet_du_document(document: Any) -> None:
    joint = build(document, HALF_LAP).joint
    proxy = type(joint.Proxy)
    assert (proxy.__module__, proxy.__name__) == (
        "freecad.menuiserie.features.joints.half_lap",
        "HalfLapJoint",
    )
    assert proxy.TYPE == "Menuiserie::HalfLap"
    assert joint.Name == "HalfLap"
    assert joint.Label == "Mi-bois"
    assert joint.Version == 1
    assert joint.getDocumentationOfProperty("Depth") == (
        "Profondeur de l'entaille de la pièce hôte ; 0 = moitié de l'épaisseur."
    )
    assert joint.getDocumentationOfProperty("FlipSide") == "Entaille de l'hôte par-dessous."
    assert joint.isValid()
    assert joint.Shape.isNull() or joint.Shape.Volume == pytest.approx(0)


def test_croix_volumes_et_solides(document: Any) -> None:
    montage = build(document, HALF_LAP)
    montage.assert_expected()
    assert montage.volumes() == pytest.approx((BLANK - 39_600, BLANK - 39_600))
    assert stale_or_invalid(document) == []


def test_les_entailles_se_completent(document: Any) -> None:
    """Hôte entaillée par-dessus, invitée par-dessous : leur réunion ne se recouvre pas."""
    montage = build(document, HALF_LAP, frame=App.Placement())
    host, guest = (api.machined_part_of(part).Shape for part in (montage.host, montage.guest))
    assert host.common(guest).Volume == pytest.approx(0, abs=1e-6)
    assert host.common(_slab(270, 330, 0, 60, 11, 22)).Volume == pytest.approx(0, abs=1e-6)
    assert guest.common(_slab(270, 330, 0, 60, 0, 11)).Volume == pytest.approx(0, abs=1e-6)


def _slab(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Any:
    part = pytest.importorskip("Part")
    return part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def test_profondeur_et_cote_inversee(document: Any) -> None:
    montage = build(document, HALF_LAP, depth=8)
    assert montage.joint.Depth.Value == 8
    assert montage.volumes() == pytest.approx((BLANK - 60 * 60 * 8, BLANK - 60 * 60 * 14))
    montage.joint.FlipSide = True
    document.recompute()
    assert montage.volumes() == pytest.approx((BLANK - 60 * 60 * 8, BLANK - 60 * 60 * 14))
    host = api.machined_part_of(montage.host).Shape.copy()
    host.Placement = App.Placement()  # repère local de l'hôte
    assert host.common(_slab(270, 330, 0, 60, 0, 8)).Volume == pytest.approx(0, abs=1e-6)
    montage.joint.Depth = 0
    document.recompute()
    montage.assert_expected()


def test_l_entaille_suit_la_largeur(document: Any) -> None:
    montage = build(document, HALF_LAP, frame=App.Placement())
    montage.guest.Width = 80
    montage.guest.Placement.Base.x = 350
    document.recompute()
    assert montage.volumes() == pytest.approx((BLANK - 80 * 60 * 11, 600 * 80 * 22 - 80 * 60 * 11))
    assert stale_or_invalid(document) == []


def test_profondeur_trop_grande_en_erreur(document: Any) -> None:
    montage = build(document, HALF_LAP)
    montage.joint.Depth = 22
    document.recompute()
    assert not montage.joint.isValid()
    assert "moins profonde que l'épaisseur" in montage.joint.getStatusString()
    montage.joint.Depth = 0
    document.recompute()
    montage.assert_expected()


def test_refus_avant_creation(document: Any) -> None:
    host = wood(document, "A", (600, 60, 22), (0, 0, 0))
    guest = wood(document, "B", (600, 60, 18), (330, -270, 90))
    document.recompute()
    count = len(document.Objects)
    with pytest.raises(ValueError, match="depth = -1"):
        api.make_half_lap(host, guest, depth=-1)
    assert len(document.Objects) == count
    joint = api.make_half_lap(host, guest)
    assert not joint.isValid()
    assert "même épaisseur et être à fleur" in joint.getStatusString()
