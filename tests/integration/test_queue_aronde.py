# SPDX-License-Identifier: LGPL-2.1-or-later
"""Queue d'aronde traversante dans le document (J4f, critère D5) ; réouverture, annulation,
export STEP et compatibilité sont couverts avec les autres types
(``test_assemblages_types_persistance.py``)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import DOVETAIL, DOVETAIL_TAN, DOVETAIL_VOLUME, build, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")

BLANK = 400 * 150 * 18


def tails_volume(count: int, width: float, pin: float = 6.0, angle: float = 10.0) -> float:
    """Volume de ``count`` queues de 18 x 18 dans un contact de ``width`` mm."""
    tail = (width - (count + 1) * pin) / count
    return count * (tail - 18 * math.tan(math.radians(angle))) * 18 * 18


def test_objet_du_document(document: Any) -> None:
    joint = build(document, DOVETAIL).joint
    proxy = type(joint.Proxy)
    assert (proxy.__module__, proxy.__name__) == (
        "freecad.menuiserie.features.joints.dovetail",
        "DovetailJoint",
    )
    assert proxy.TYPE == "Menuiserie::Dovetail"
    assert joint.Name == "Dovetail"
    assert joint.Label == "Queue d'aronde"
    assert joint.Version == 1
    assert joint.getDocumentationOfProperty("Angle") == (
        "Angle des flancs des queues, en degrés (0 à 30) ; 0 = automatique (10°)."
    )
    assert joint.getTypeIdOfProperty("Angle") == "App::PropertyAngle"
    assert joint.getTypeIdOfProperty("TailCount") == "App::PropertyIntegerConstraint"
    joint.TailCount = 60
    assert joint.TailCount == 50  # contrainte 0 à 50
    joint.TailCount = 0
    document.recompute()
    assert joint.isValid()
    assert joint.Shape.isNull() or joint.Shape.Volume == pytest.approx(0)


def test_planches_volumes_et_solides(document: Any) -> None:
    montage = build(document, DOVETAIL)
    montage.assert_expected()
    assert tails_volume(3, 150) == DOVETAIL_VOLUME
    for blank in (montage.host, montage.guest):
        assert api.machined_part_of(blank).Shape.isValid()
    assert stale_or_invalid(document) == []


def test_queues_et_logements_s_emboitent(document: Any) -> None:
    """Dans le repère du document : aucun recouvrement, réunion = les deux brutes."""
    montage = build(document, DOVETAIL, frame=App.Placement())
    host, guest = (api.machined_part_of(part).Shape for part in (montage.host, montage.guest))
    assert host.common(guest).Volume == pytest.approx(0, abs=1e-6)
    assert host.fuse(guest).Volume == pytest.approx(2 * BLANK)
    box = guest.BoundBox
    assert (box.XMin, box.XMax, box.ZMin, box.ZMax) == pytest.approx((0, 18, 0, 418))
    # Logements traversants : la face extérieure de l'hôte (z = 0) est ouverte sur 3 x 42 mm,
    # rétrécis de 1 mm sur 6 de profondeur de chaque côté.
    skin = Part.makeBox(18, 150, 0.5, App.Vector(0, 0, 0))
    assert skin.cut(host).Volume == pytest.approx(3 * (42 - 0.5 * DOVETAIL_TAN) * 18 * 0.5)


def test_nombre_de_queues_saisi(document: Any) -> None:
    montage = build(document, DOVETAIL, tail_count=2)
    assert montage.joint.TailCount == 2
    volume = tails_volume(2, 150)
    assert montage.volumes() == pytest.approx((BLANK - volume, BLANK + volume))
    montage.joint.TailCount = 0
    montage.joint.Angle = 8
    document.recompute()
    volume = tails_volume(3, 150, angle=8)
    assert montage.volumes() == pytest.approx((BLANK - volume, BLANK + volume))


def test_les_queues_suivent_la_largeur(document: Any) -> None:
    """Planches de 200 mm : 4 queues automatiques, un seul recalcul."""
    montage = build(document, DOVETAIL)
    for part in (montage.host, montage.guest):
        part.Width = 200
    document.recompute()
    volume = tails_volume(4, 200)
    blank = 400 * 200 * 18
    assert montage.volumes() == pytest.approx((blank - volume, blank + volume))
    assert stale_or_invalid(document) == []


def test_queues_trop_etroites_en_erreur(document: Any) -> None:
    montage = build(document, DOVETAIL)
    montage.joint.TailCount = 20
    document.recompute()
    assert not montage.joint.isValid()
    assert "Queues trop étroites" in montage.joint.getStatusString()
    montage.joint.TailCount = 0
    document.recompute()
    montage.assert_expected()


def test_refus_avant_creation(document: Any) -> None:
    host = wood(document, "H", (400, 150, 18), (0, 0, 0))
    guest_place = App.Placement(App.Vector(23, 0, 18), App.Rotation(App.Vector(0, 1, 0), -90))
    guest = wood(document, "I", (400, 150, 18), guest_place)
    document.recompute()
    count = len(document.Objects)
    with pytest.raises(ValueError, match="angle = 45"):
        api.make_dovetail(host, guest, angle=45)
    assert len(document.Objects) == count
    joint = api.make_dovetail(host, guest)
    assert not joint.isValid()
    assert "à fleur de la face extérieure" in joint.getStatusString()


def test_ancienne_pente_convertie_en_angle(document: Any) -> None:
    """Un document de développement porte ``Slope`` (pente 1:n) : convertie en ``Angle``."""
    joint = build(document, DOVETAIL).joint
    joint.addProperty("App::PropertyFloat", "Slope", "Queue d'aronde", "ancienne pente")
    joint.Slope = 8
    joint.Proxy.onDocumentRestored(joint)
    assert "Slope" not in joint.PropertiesList
    assert joint.Angle.Value == pytest.approx(math.degrees(math.atan(1 / 8)))
