# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cadre de référence de la spécification J3 (§ 3) : deux montants, deux traverses, en chêne.

M1 (0, 0, 0) et M2 (0, 340, 0) : 600 x 60 x 22 ; T1 (60, 60, 0) et T2 (600, 60, 0) : 280 x 60 x
22, tournées de 90° autour de Z. Chaque traverse touche par ses bouts les chants intérieurs des
montants. Module d'aide des tests d'intégration (importé seulement avec FreeCAD).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

# Volumes attendus (mm³) des pièces usinées du cadre aux valeurs automatiques (critère O1).
RAIL_VOLUME = 280 * 60 * 22 + 2 * 40 * 40 * 7
STILE_VOLUME = 600 * 60 * 22 - 2 * 42 * 40 * 7
# Paires (hôte, invitée) des quatre tenons-mortaises.
PAIRS = (("M1", "T1"), ("M2", "T1"), ("M1", "T2"), ("M2", "T2"))
NOT_TOUCHING = "Les pièces ne se touchent pas"


@dataclass
class Cadre:
    """Pièces brutes du cadre (par repère) et assemblages créés (par paire)."""

    doc: Any
    parts: dict[str, Any]
    joints: dict[tuple[str, str], Any]

    def machined(self, mark: str) -> Any:
        """Pièce usinée de la brute ``mark``."""
        return api.machined_part_of(self.parts[mark])

    def volume(self, mark: str) -> float:
        """Volume de la pièce usinée de ``mark``."""
        return float(self.machined(mark).Shape.Volume)

    def assemble(self, pairs: tuple[tuple[str, str], ...] = PAIRS) -> None:
        """Crée un tenon-mortaise par paire (hôte, invitée)."""
        for host, guest in pairs:
            joint = api.make_mortise_tenon(self.parts[host], self.parts[guest])
            self.joints[host, guest] = joint


def placement(x: float, y: float, degrees_z: float = 0.0) -> Any:
    """Placement de base (x, y, 0), tourné de ``degrees_z`` autour de Z."""
    return App.Placement(App.Vector(x, y, 0), App.Rotation(App.Vector(0, 0, 1), degrees_z))


def build_frame(doc: Any) -> Cadre:
    """Les quatre pièces brutes du cadre (libellés M1, M2, T1, T2), recalculées."""
    layout = {
        "M1": (600, placement(0, 0)),
        "M2": (600, placement(0, 340)),
        "T1": (280, placement(60, 60, 90)),
        "T2": (280, placement(600, 60, 90)),
    }
    parts = {}
    for mark, (length, where) in layout.items():
        part = api.make_wood_part(length, 60, 22, "chene", mark=mark, doc=doc)
        part.Label = mark
        part.Placement = where
        parts[mark] = part
    doc.recompute()
    return Cadre(doc, parts, {})


def touched(doc: Any) -> list[str]:
    """Noms des objets marqués « Touched » ou invalides."""
    return [
        obj.Name
        for obj in doc.Objects
        if "Touched" in obj.State or "Invalid" in obj.State or not obj.isValid()
    ]
