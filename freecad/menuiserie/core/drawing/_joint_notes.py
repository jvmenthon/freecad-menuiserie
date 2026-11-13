# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lignes du tableau des usinages propres à un type d'assemblage (retour de jv du 2026-11-13).

Le menuisier règle ses outils sur des angles et des largeurs que l'encombrement d'un usinage ne
donne pas : angle et pente des queues d'aronde, largeur des queues et des griffes, angle d'une
coupe d'onglet, réglages de la scie d'un bout coupé en biais, diamètre et longueur des
tourillons. Ces lignes viennent des valeurs effectives de l'assemblage (celles du panneau).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import JointKind
from freecad.menuiserie.core.joints.dovetail import DovetailValues
from freecad.menuiserie.core.joints.dowels import DowelValues
from freecad.menuiserie.core.joints.miter import MiterValues

__all__ = ["NoteLine", "bevel_line", "joint_note_lines", "machining_name"]

NoteLine = tuple[str, dict[str, str]]  # (gabarit à traduire, valeurs)

_DOVETAIL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{label} : flancs des queues à {angle}° (pente 1:{ratio}), {count} queues de {tail} en "
    "pointe et {base} à l'épaulement, griffes de {pin}",
)
_DOWELS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} tourillons Ø {diameter}, longueur {length}"
)
_MITER: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} : onglet coupé à {angle}°")
_BEVEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {end} coupé en biais, angle de coupe {cut}°, lame inclinée {tilt}°"
)
_ENDS: Final = {
    (0, 1): QT_TRANSLATE_NOOP("Menuiserie", "bout droit"),
    (0, -1): QT_TRANSLATE_NOOP("Menuiserie", "bout gauche"),
    (1, 1): QT_TRANSLATE_NOOP("Menuiserie", "chant haut"),
    (1, -1): QT_TRANSLATE_NOOP("Menuiserie", "chant bas"),
    (2, 1): QT_TRANSLATE_NOOP("Menuiserie", "face"),
    (2, -1): QT_TRANSLATE_NOOP("Menuiserie", "contre-face"),
}
# Nom de l'usinage (clé de ``NAMES``) selon le type d'assemblage et le groupe de formes de son
# plan : enlèvements et ajouts de l'hôte, enlèvements, arasements et ajouts de l'invitée.
_NAMES: Final = {
    JointKind.MORTISE_TENON: {"host_cuts": "mortise", "guest_additions": "tenon"},
    JointKind.TONGUE_GROOVE: {"host_cuts": "groove", "guest_additions": "tongue"},
    JointKind.RABBET: {"host_cuts": "rabbet"},
    JointKind.HALF_LAP: {"host_cuts": "half_lap", "guest_cuts": "half_lap"},
    JointKind.DOVETAIL: {
        "host_cuts": "socket",
        "guest_additions": "tail",
        "host_additions": "tail",
        "guest_cuts": "socket",
    },
    JointKind.MITER: {"host_cuts": "miter", "guest_cuts": "miter"},
    JointKind.DOWELS: {"host_cuts": "dowel_hole", "guest_cuts": "dowel_hole"},
    JointKind.LOOSE_TENON: {"host_cuts": "loose_mortise", "guest_cuts": "loose_mortise"},
    JointKind.BISCUIT: {"host_cuts": "biscuit", "guest_cuts": "biscuit"},
    JointKind.FOOT: {"host_cuts": "foot_hole"},
    JointKind.SHELF_PINS: {"host_cuts": "pin_hole", "guest_cuts": "pin_hole"},
    JointKind.DRAWER_SLIDE: {"host_cuts": "screw_hole", "guest_cuts": "screw_hole"},
}
_MIN_ANGLE_DEG: Final = 0.05  # en deçà, l'angle est nul pour le menuisier


def _number(value: float) -> str:
    """Valeur au dixième, écrite à la française (« 14,5 »)."""
    rounded = round(value, 1)
    return f"{0.0 if rounded == 0 else rounded:g}".replace(".", ",")


def machining_name(kind: JointKind, group: str) -> str:
    """Nom (clé de ``NAMES``) des formes du groupe ``group`` (« host_cuts »…) d'un assemblage
    ``kind`` ; « shoulder » pour les arasements de l'invitée, vide si rien ne convient."""
    if group == "guest_trims":
        return "shoulder"
    return _NAMES.get(kind, {}).get(group, "")


def joint_note_lines(label: str, values: object, is_host: bool) -> list[NoteLine]:
    """Lignes propres à l'assemblage ``label`` d'après ses valeurs effectives ``values`` ; la
    pièce dessinée est l'hôte de l'assemblage si ``is_host``. Vide pour un type sans réglage
    particulier (tenon, rainure, feuillure… dont l'encombrement suffit)."""
    if isinstance(values, DovetailValues) and values.angle > _MIN_ANGLE_DEG:
        ratio = 1.0 / math.tan(math.radians(values.angle))
        return [
            (
                _DOVETAIL,
                {
                    "label": label,
                    "angle": _number(values.angle),
                    "ratio": _number(ratio),
                    "count": str(values.tail_count),
                    "tail": _number(values.tail_width),
                    "base": _number(values.tail_base),
                    "pin": _number(values.pin_width),
                },
            )
        ]
    if isinstance(values, DowelValues):
        return [
            (
                _DOWELS,
                {
                    "label": label,
                    "count": str(values.count),
                    "diameter": _number(values.diameter),
                    "length": _number(values.dowel_length),
                },
            )
        ]
    if isinstance(values, MiterValues):
        angle = values.host_angle if is_host else values.guest_angle
        return [(_MITER, {"label": label, "angle": _number(angle)})]
    return []


def bevel_line(label: str, face: tuple[int, int], saw: Sequence[float]) -> NoteLine | None:
    """Ligne d'un bout coupé en biais (``face`` : indice d'axe et signe, ``saw`` : angle de coupe
    et inclinaison de lame en degrés) ; ``None`` pour une coupe d'équerre."""
    cut, tilt = float(saw[0]), float(saw[1])
    if max(cut, tilt) <= _MIN_ANGLE_DEG:
        return None
    return (
        _BEVEL,
        {
            "label": label,
            "end": _ENDS.get(face, _ENDS[(0, 1)]),
            "cut": _number(cut),
            "tilt": _number(tilt),
        },
    )
