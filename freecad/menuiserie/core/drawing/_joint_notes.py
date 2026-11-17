# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lignes du tableau des usinages propres à un type d'assemblage (retour de jv du 2026-11-13).

Le menuisier règle ses outils sur des angles et des largeurs que l'encombrement d'un usinage ne
donne pas : angle et pente des queues d'aronde, largeur des queues et des griffes, angle d'une
coupe d'onglet, réglages de la scie d'un bout coupé en biais, diamètre et longueur des
tourillons. Ces lignes viennent des valeurs effectives de l'assemblage (celles du panneau).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dovetail import DovetailValues
from freecad.menuiserie.core.joints.dowels import DowelValues
from freecad.menuiserie.core.joints.miter import MiterValues

__all__ = ["TRANSLATED_VALUES", "NoteLine", "bevel_line", "joint_note_lines", "machining_name"]

NoteLine = tuple[str, dict[str, str]]  # (gabarit à traduire, valeurs)
# Valeurs d'une ligne du tableau qui sont elles-mêmes des textes à traduire (noms d'usinage,
# faces, bouts, mots au singulier ou au pluriel), ici et dans ``_machining``.
TRANSLATED_VALUES: Final = ("name", "face", "end", "tails", "dowels")

_DOVETAIL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{label} : flancs des queues à {angle}° (pente 1:{ratio}), {count} {tails} de {tail} en "
    "pointe et {base} à l'épaulement, griffes de {pin}",
)
_DOWELS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} {dowels} Ø {diameter}, longueur {length}"
)
_TAILS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "queue"),
    QT_TRANSLATE_NOOP("Menuiserie", "queues"),
)
_DOWEL_WORDS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "tourillon"),
    QT_TRANSLATE_NOOP("Menuiserie", "tourillons"),
)
_MITER: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} : onglet coupé à {angle}°")
_BEVEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {end} coupé en biais, angle de coupe {cut}°, lame inclinée {tilt}°"
)
_END: Final = QT_TRANSLATE_NOOP("Menuiserie", "bout")  # face inattendue
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
# Queues taillées dans l'hôte (« queues sur l'hôte ») : l'invitée porte les griffes.
_PIN_NAMES: Final = {"guest_additions": "pin", "host_cuts": "pin_socket"}
_MIN_ANGLE_DEG: Final = 0.05  # en deçà, l'angle est nul pour le menuisier


def _number(value: float) -> str:
    """Valeur au dixième, écrite à la française (« 14,5 »)."""
    rounded = round(value, 1)
    return f"{0.0 if rounded == 0 else rounded:g}".replace(".", ",")


def machining_name(kind: JointKind, group: str, tails_on_host: bool = False) -> str:
    """Nom (clé de ``NAMES``) des formes du groupe ``group`` (« host_cuts »…) d'un assemblage
    ``kind`` ; « shoulder » pour les arasements de l'invitée, vide si rien ne convient. Une
    queue d'aronde aux queues sur l'hôte donne des griffes à l'invitée et leurs logements à
    l'hôte."""
    if group == "guest_trims":
        return "shoulder"
    if kind is JointKind.DOVETAIL and tails_on_host and group in _PIN_NAMES:
        return _PIN_NAMES[group]
    return _NAMES.get(kind, {}).get(group, "")


def _dovetail_lines(label: str, values: DovetailValues, _is_host: bool) -> list[NoteLine]:
    """Angle et pente des flancs, largeur des queues et des griffes."""
    if values.angle <= _MIN_ANGLE_DEG:
        return []
    ratio = 1.0 / math.tan(math.radians(values.angle))
    return [
        (
            _DOVETAIL,
            {
                "label": label,
                "angle": _number(values.angle),
                "ratio": _number(ratio),
                "count": str(values.tail_count),
                "tails": _TAILS[values.tail_count > 1],
                "tail": _number(values.tail_width),
                "base": _number(values.tail_base),
                "pin": _number(values.pin_width),
            },
        )
    ]


def _dowel_lines(label: str, values: DowelValues, _is_host: bool) -> list[NoteLine]:
    """Nombre, diamètre et longueur des tourillons."""
    return [
        (
            _DOWELS,
            {
                "label": label,
                "count": str(values.count),
                "dowels": _DOWEL_WORDS[values.count > 1],
                "diameter": _number(values.diameter),
                "length": _number(values.dowel_length),
            },
        )
    ]


def _miter_lines(label: str, values: MiterValues, is_host: bool) -> list[NoteLine]:
    """Angle de la coupe d'onglet de la pièce dessinée."""
    angle = values.host_angle if is_host else values.guest_angle
    return [(_MITER, {"label": label, "angle": _number(angle)})]


# Registre (type des valeurs effectives d'un assemblage → ses lignes) : un nouvel assemblage
# qui demande un réglage particulier ajoute ici sa fonction, sans toucher à la recherche.
_NOTE_LINES: Final[dict[type, Callable[[str, Any, bool], list[NoteLine]]]] = {
    DovetailValues: _dovetail_lines,
    DowelValues: _dowel_lines,
    MiterValues: _miter_lines,
}


def joint_note_lines(label: str, values: object, is_host: bool) -> list[NoteLine]:
    """Lignes propres à l'assemblage ``label`` d'après ses valeurs effectives ``values`` ; la
    pièce dessinée est l'hôte de l'assemblage si ``is_host``. Vide pour un type sans réglage
    particulier (tenon, rainure, feuillure… dont l'encombrement suffit)."""
    lines = _NOTE_LINES.get(type(values))
    return lines(label, values, is_host) if lines is not None else []


def bevel_line(label: str, face: tuple[int, int], saw: Sequence[float]) -> NoteLine | None:
    """Ligne d'un bout coupé en biais (``face`` : indice d'axe et signe, ``saw`` : angle de coupe
    et inclinaison de lame en degrés) ; ``None`` pour une coupe d'équerre."""
    cut, tilt = float(saw[0]), float(saw[1])
    if max(abs(cut), abs(tilt)) <= _MIN_ANGLE_DEG:
        return None
    return (
        _BEVEL,
        {
            "label": label,
            "end": _ENDS.get(face, _END),
            "cut": _number(cut),
            "tilt": _number(tilt),
        },
    )
