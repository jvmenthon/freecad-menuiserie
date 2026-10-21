# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bureau de référence de la spécification J4 (§ 3), dans le document.

Plateau P (1200 x 600 x 30, z = 720), joues JG et JD (720 x 560 x 22, tournées de -90° autour
de Y), voile V (1156 x 400 x 18, tourné de +90° autour de X), en chêne ; tourillons JG-V et
JD-V (hôte = joue). Module d'aide des tests d'intégration (importé seulement avec FreeCAD).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

Y_AXIS = App.Vector(0, 1, 0)
X_AXIS = App.Vector(1, 0, 0)
LAYOUT = {
    "P": ("Plateau", (1200, 600, 30), (0, 0, 720), App.Rotation()),
    "JG": ("Joue gauche", (720, 560, 22), (22, 0, 0), App.Rotation(Y_AXIS, -90)),
    "JD": ("Joue droite", (720, 560, 22), (1200, 0, 0), App.Rotation(Y_AXIS, -90)),
    "V": ("Voile", (1156, 400, 18), (22, 459, 320), App.Rotation(X_AXIS, 90)),
}
# Expressions de F8 (options par défaut), par repère et propriété.
EXPRESSIONS = {
    "P": {
        "Length": "<<Bureau>>.Width",
        "Width": "<<Bureau>>.Depth",
        "Placement.Base.z": "<<Bureau>>.Origin.z + <<Bureau>>.Height - 30 mm",
    },
    "JG": {"Length": "<<Bureau>>.Height - 30 mm", "Width": "<<Bureau>>.Depth - 40 mm"},
    "JD": {
        "Length": "<<Bureau>>.Height - 30 mm",
        "Width": "<<Bureau>>.Depth - 40 mm",
        "Placement.Base.x": "<<Bureau>>.Origin.x + <<Bureau>>.Width",
    },
    "V": {
        "Length": "<<Bureau>>.Width - 44 mm",
        "Width": "<<Bureau>>.Height - 350 mm",
        "Placement.Base.y": "<<Bureau>>.Origin.y + <<Bureau>>.Depth - 141 mm",
    },
}


@dataclass
class Bureau:
    """Pièces brutes (par repère), assemblages et ensemble du bureau."""

    doc: Any
    parts: dict[str, Any]
    joints: list[Any] = field(default_factory=list)
    furniture: Any = None
    notices: tuple[str, ...] = ()

    def shown(self, mark: str) -> Any:
        """Pièce visible : la pièce usinée de la brute, sinon la brute."""
        machined = api.machined_part_of(self.parts[mark])
        return machined if machined is not None else self.parts[mark]

    def bounds(self, mark: str) -> tuple[tuple[float, float], ...]:
        """Étendue (X, Y, Z) de la brute ``mark``, arrondie au millième."""
        box = self.parts[mark].Shape.BoundBox
        return tuple(
            (round(lo, 3), round(hi, 3))
            for lo, hi in ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))
        )

    def sizes(self, mark: str) -> tuple[float, float, float]:
        """Cotes L x l x e de la brute ``mark``."""
        part = self.parts[mark]
        return tuple(  # type: ignore[return-value]
            round(float(getattr(part, name).Value), 6) for name in ("Length", "Width", "Thickness")
        )

    def expressions(self, mark: str) -> dict[str, str]:
        """Expressions de la brute ``mark`` (chemins sans le point initial de FreeCAD)."""
        return {path.lstrip("."): text for path, text in self.parts[mark].ExpressionEngine}

    def dowel_counts(self) -> list[int]:
        """Nombre de tourillons de chaque assemblage."""
        return [len(joint.Shape.Solids) for joint in self.joints]


def build_parts(doc: Any, container: Any = None) -> Bureau:
    """Les quatre pièces brutes du bureau, dans ``container`` (Std Part) s'il est donné."""
    parts = {}
    for mark, (label, size, base, rotation) in LAYOUT.items():
        part = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
        part.Label = label
        part.Placement = App.Placement(App.Vector(*base), rotation)
        if container is not None:
            container.addObject(part)
        parts[mark] = part
    doc.recompute()
    return Bureau(doc, parts)


def build_desk(doc: Any, container: Any = None, *, joined: bool = True) -> Bureau:
    """Bureau assemblé (tourillons si ``joined``) puis regroupé dans l'ensemble « Bureau »."""
    bureau = build_parts(doc, container)
    if joined:
        for side in ("JG", "JD"):
            bureau.joints.append(api.make_dowels(bureau.parts[side], bureau.parts["V"]))
    bureau.furniture, bureau.notices = api.make_furniture(
        [bureau.shown(mark) for mark in LAYOUT], label="Bureau"
    )
    return bureau
