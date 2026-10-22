# SPDX-License-Identifier: LGPL-2.1-or-later
"""Montages de référence des assemblages de J3c et J4 : rainure-languette, feuillure,
tourillons, mi-bois, queue d'aronde, onglet.

Chaque montage pose deux pièces de chêne (hôte, invitée), les assemble par la fabrique de
l'API et connaît les volumes attendus des deux pièces usinées. Module d'aide des tests
d'intégration (importé seulement avec FreeCAD).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest

from tests.integration.cadre import placement

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

Size = tuple[float, float, float]
Where = tuple[float, float, float]  # x, y, rotation autour de Z (degrés)
Pose = Where | Any  # ou un ``App.Placement`` (pièce debout)

# Repère quelconque où sont posés les montages (rotation et translation non triviales) : seule
# la position relative des pièces compte.
FRAME = App.Placement(App.Vector(120, -75, 40), App.Rotation(App.Vector(1, 2, 3), 37))

# Entaille de chaque traverse de la croix à mi-bois (critère B3 de J4) : 60 x 60 x 11.
HALF_LAP_CUT = 60 * 60 * 11

# Deux tourillons Ø 10 x 40, percés de 20 + 1 dans chaque pièce (critère T1, cadre M1 / T1).
DOWEL_VOLUME = math.pi * 5**2 * 40
DOWEL_HOLE_VOLUME = math.pi * 5**2 * 21

# Trois queues d'aronde de 42 mm côté pointe sur 18 x 18, flancs à 10° (angle automatique,
# critère D5 de J4) : 3 x (42 - 18 tan 10°) x 18 x 18.
DOVETAIL_TAN = math.tan(math.radians(10))
DOVETAIL_VOLUME = 3 * (42 - 18 * DOVETAIL_TAN) * 18 * 18


@dataclass(frozen=True)
class Scenario:
    """Deux pièces (hôte, invitée), la fabrique ``api`` et les volumes usinés attendus."""

    name: str
    factory: str
    host: tuple[Size, Pose]
    guest: tuple[Size, Pose]
    host_volume: float
    guest_volume: float


TONGUE_GROOVE = Scenario(
    "rainure-languette",
    "make_tongue_groove",
    ((1000, 100, 22), (0, 0, 0)),
    ((1000, 100, 22), (0, 100, 0)),
    1000 * 100 * 22 - 1000 * 11 * 7,
    1000 * 100 * 22 + 1000 * 10 * 7,
)
RABBET = Scenario(
    "feuillure",
    "make_rabbet",
    ((600, 300, 18), (0, 0, 0)),
    ((600, 400, 6), (0, 290, 0)),
    600 * 300 * 18 - 600 * 10 * 6,
    600 * 400 * 6,
)
DOWELS = Scenario(
    "tourillons",
    "make_dowels",
    ((600, 60, 22), (0, 0, 0)),
    ((280, 60, 22), (60, 60, 90)),
    600 * 60 * 22 - 2 * DOWEL_HOLE_VOLUME,
    280 * 60 * 22 - 2 * DOWEL_HOLE_VOLUME,
)
HALF_LAP = Scenario(
    "mi-bois",
    "make_half_lap",
    ((600, 60, 22), (0, 0, 0)),
    ((600, 60, 22), (330, -270, 90)),
    600 * 60 * 22 - HALF_LAP_CUT,
    600 * 60 * 22 - HALF_LAP_CUT,
)
# Deux planches 400 x 150 x 18 en angle : l'hôte à plat, l'invitée debout sur son bout
# (épaisseur selon -X), sa face extérieure à fleur du bout de l'hôte.
DOVETAIL = Scenario(
    "queue d'aronde",
    "make_dovetail",
    ((400, 150, 18), (0, 0, 0)),
    (
        (400, 150, 18),
        App.Placement(App.Vector(18, 0, 18), App.Rotation(App.Vector(0, 1, 0), -90)),
    ),
    400 * 150 * 18 - DOVETAIL_VOLUME,
    400 * 150 * 18 + DOVETAIL_VOLUME,
)
# Angle de cadre à onglet (critère A2 de J4) : deux traverses 500 x 60 x 20 dessinées hors
# tout, qui se chevauchent de 60 x 60 au coin ; chacune perd la moitié de la boîte commune.
MITER_CUT = 60 * 60 * 20 / 2
MITER = Scenario(
    "onglet",
    "make_miter",
    ((500, 60, 20), (0, 0, 0)),
    ((500, 60, 20), (60, 0, 90)),
    500 * 60 * 20 - MITER_CUT,
    500 * 60 * 20 - MITER_CUT,
)
SCENARIOS = (TONGUE_GROOVE, RABBET, DOWELS, HALF_LAP, DOVETAIL, MITER)
PROXIES = {
    "make_tongue_groove": ("tongue_groove", "TongueGrooveJoint"),
    "make_rabbet": ("rabbet", "RabbetJoint"),
    "make_dowels": ("dowels", "DowelJoint"),
    "make_half_lap": ("half_lap", "HalfLapJoint"),
    "make_dovetail": ("dovetail", "DovetailJoint"),
    "make_miter": ("miter", "MiterJoint"),
}


@dataclass
class Montage:
    """Pièces brutes et assemblage d'un montage."""

    scenario: Scenario
    host: Any
    guest: Any
    joint: Any

    def volumes(self) -> tuple[float, float]:
        """Volumes des pièces usinées (hôte, invitée)."""
        return tuple(  # type: ignore[return-value]
            float(api.machined_part_of(blank).Shape.Volume) for blank in (self.host, self.guest)
        )

    def assert_expected(self) -> None:
        """Volumes attendus ; pièces usinées valides, au ``Placement`` de leur brute."""
        expected = (self.scenario.host_volume, self.scenario.guest_volume)
        assert self.volumes() == pytest.approx(expected)
        for blank in (self.host, self.guest):
            machined = api.machined_part_of(blank)
            assert machined.isValid()
            assert len(machined.Shape.Solids) == 1
            assert machined.Placement == blank.Placement
            # La forme garde son placement en matrice : égalité à l'arrondi près.
            assert machined.Shape.Placement.isSame(blank.Placement, 1e-9)


def wood(doc: Any, mark: str, size: Size, where: Pose, frame: Any = None) -> Any:
    """Pièce de chêne de cotes ``size`` posée en ``where`` (``Where`` ou ``Placement``) dans le
    repère ``frame`` (celui du document par défaut)."""
    part = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
    part.Label = mark
    local = where if isinstance(where, App.Placement) else placement(*where)
    part.Placement = local if frame is None else frame.multiply(local)
    return part


def blanks(doc: Any, scenario: Scenario, frame: Any = FRAME) -> tuple[Any, Any]:
    """Pose les deux pièces brutes du montage dans ``frame``, libellées H (hôte) et I
    (invitée)."""
    host = wood(doc, "H", *scenario.host, frame)
    guest = wood(doc, "I", *scenario.guest, frame)
    doc.recompute()
    return host, guest


def assemble(scenario: Scenario, host: Any, guest: Any, **params: object) -> Montage:
    """Assemble les deux pièces par la fabrique ``api`` du montage (document recalculé)."""
    joint = getattr(api, scenario.factory)(host, guest, **params)
    return Montage(scenario, host, guest, joint)


def build(doc: Any, scenario: Scenario, frame: Any = FRAME, **params: object) -> Montage:
    """Pose les deux pièces du montage dans ``frame`` et les assemble (document recalculé)."""
    return assemble(scenario, *blanks(doc, scenario, frame), **params)
