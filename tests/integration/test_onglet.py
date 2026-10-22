# SPDX-License-Identifier: LGPL-2.1-or-later
"""Onglet dans le document (J4g, critère A4) : objet, pièces usinées qui se touchent sans
chevauchement ni jour, coin de caisson, suivi des cotes, refus. Réouverture, annulation, export
STEP et compatibilité sont couverts avec les autres types
(``test_assemblages_types_persistance.py``)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import MITER, MITER_CUT, build, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

RAIL = 500 * 60 * 20
COMMON = 60 * 60 * 20


def shapes(montage: Any) -> tuple[Any, Any]:
    """Formes des pièces usinées (hôte, invitée), dans le repère du document."""
    return api.machined_part_of(montage.host).Shape, api.machined_part_of(montage.guest).Shape


def miter_faces(shape: Any, normal: Any) -> list[Any]:
    """Faces planes de ``shape`` de normale ± ``normal`` (face coupée d'onglet)."""
    faces = []
    for face in shape.Faces:
        if face.Surface.TypeId != "Part::GeomPlane":
            continue
        direction = face.normalAt(0, 0)
        if abs(abs(direction.dot(normal)) - 1) < 1e-9:
            faces.append(face)
    return faces


def test_objet_du_document(document: Any) -> None:
    montage = build(document, MITER)
    joint = montage.joint
    proxy = type(joint.Proxy)
    assert (proxy.__module__, proxy.__name__) == (
        "freecad.menuiserie.features.joints.miter",
        "MiterJoint",
    )
    assert proxy.TYPE == "Menuiserie::Miter"
    assert proxy.PROPERTIES == ()
    assert (joint.Name, joint.Version) == ("Miter", 1)
    assert joint.Label == f"Onglet : {joint.HostPart.Label} {joint.GuestPart.Label}"
    assert set(joint.PropertiesList) >= {"HostPart", "GuestPart", "Version"}
    assert joint.isValid()
    assert joint.Shape.isNull() or joint.Shape.Volume == pytest.approx(0)
    montage.assert_expected()
    assert stale_or_invalid(document) == []


def test_pieces_jointives_sans_chevauchement_ni_jour(document: Any) -> None:
    """A4 : intersection nulle ; réunion = celle des deux brutes (chacune a perdu la moitié de la
    boîte commune, que l'autre garde) ; faces coupées coplanaires et confondues."""
    montage = build(document, MITER, frame=App.Placement())
    host, guest = shapes(montage)
    assert host.isValid() and guest.isValid()
    assert (len(host.Solids), len(guest.Solids)) == (1, 1)
    assert host.common(guest).Volume == pytest.approx(0, abs=1e-6)
    blanks = [part.Shape for part in (montage.host, montage.guest)]
    union = blanks[0].fuse(blanks[1]).Volume
    assert union == pytest.approx(2 * RAIL - COMMON, rel=1e-6)
    assert host.fuse(guest).Volume == pytest.approx(union, rel=1e-6)
    assert host.Volume + guest.Volume == pytest.approx(2 * RAIL - 2 * MITER_CUT, rel=1e-6)
    diagonal = App.Vector(1, -1, 0).normalize()
    (host_face,), (guest_face,) = miter_faces(host, diagonal), miter_faces(guest, diagonal)
    assert host_face.Area == pytest.approx(math.hypot(60, 60) * 20)
    assert host_face.isCoplanar(guest_face)
    assert host_face.common(guest_face).Area == pytest.approx(host_face.Area)


def test_coin_de_caisson(document: Any) -> None:
    """A2 : côté 720 x 400 x 18 debout, dessus 600 x 400 x 18 posé sur toute son épaisseur ;
    axe commun = profondeur, chacun perd 64 800 mm³."""
    side_place = App.Placement(App.Vector(18, 0, 0), App.Rotation(App.Vector(0, 1, 0), -90))
    side = wood(document, "C", (720, 400, 18), side_place)
    top = wood(document, "D", (600, 400, 18), (0, 0, 0))
    top.Placement.Base.z = 702
    document.recompute()
    api.make_miter(side, top)
    volumes = [api.machined_part_of(part).Shape.Volume for part in (side, top)]
    assert volumes == pytest.approx([720 * 400 * 18 - 64_800, 600 * 400 * 18 - 64_800])
    host, guest = (api.machined_part_of(part).Shape for part in (side, top))
    assert host.common(guest).Volume == pytest.approx(0, abs=1e-6)
    assert stale_or_invalid(document) == []


def test_largeurs_differentes_et_suivi(document: Any) -> None:
    """Traverse de 40 contre traverse de 60 : coupe à 33,69° / 56,31°, toujours jointive ; la
    coupe suit la largeur en un recalcul."""
    montage = build(document, MITER, frame=App.Placement())
    montage.guest.Width = 40
    montage.guest.Placement.Base.x = 40
    document.recompute()
    host, guest = shapes(montage)
    half = 40 * 60 * 20 / 2
    assert (host.Volume, guest.Volume) == pytest.approx((RAIL - half, 500 * 40 * 20 - half))
    assert host.common(guest).Volume == pytest.approx(0, abs=1e-6)
    assert stale_or_invalid(document) == []


def test_refus_avant_et_apres_creation(document: Any) -> None:
    host = wood(document, "H", (500, 60, 20), (0, 0, 0))
    guest = wood(document, "I", (500, 60, 20), (300, 0, 90))  # T : pas au même coin
    document.recompute()
    count = len(document.Objects)
    with pytest.raises(TypeError):
        api.make_miter(host, guest, reinforcement=1)
    assert len(document.Objects) == count
    joint = api.make_miter(host, guest)
    assert not joint.isValid()
    assert "s'arrêter au même coin" in joint.getStatusString()
    guest.Placement.Base.x = 60
    document.recompute()
    assert joint.isValid()
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(RAIL - MITER_CUT)
