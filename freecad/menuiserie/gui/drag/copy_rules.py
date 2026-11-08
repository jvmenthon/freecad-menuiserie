# SPDX-License-Identifier: LGPL-2.1-or-later
"""Règles pures de la copie par glissement (lot R-d, ADR 0043) : axe global d'une flèche et
paramètres de la répétition d'une copie. Aucun import de FreeCAD ni de Qt ; le glissement
(``copying.py``) les applique."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, SpacingMode
from freecad.menuiserie.core.snap import Frame

__all__ = ["MIN_MOVE", "copy_params", "global_axis"]

MIN_MOVE: Final = 0.01  # mm : en deçà, le glissement n'est qu'un clic, aucune copie
_AXES: Final = (RepeatAxis.X, RepeatAxis.Y, RepeatAxis.Z)
_NOT_ON_AN_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Copie par glissement impossible : cette flèche n'est pas parallèle à un axe X, Y ou Z du "
    "document (pièce tournée). Utilisez la commande « Répéter », ou déplacez la pièce sans Ctrl.",
)


def global_axis(frame: Frame, axis: int) -> tuple[RepeatAxis, float]:
    """Axe global et sens (+1 ou -1) de l'axe ``axis`` de la pièce de repère ``frame`` ;
    ``TemplatedError`` s'il n'est pas parallèle à X, Y ou Z."""
    direction = (frame.x, frame.y, frame.z)[axis]
    main = max(range(3), key=lambda i: abs(direction.component(i)))
    others = (abs(direction.component(i)) for i in range(3) if i != main)
    if any(value > ANGLE_TOLERANCE for value in others):
        raise TemplatedError(_NOT_ON_AN_AXIS, {})
    return _AXES[main], 1.0 if direction.component(main) > 0 else -1.0


def copy_params(axis: RepeatAxis, sign: float, delta: float) -> RepeatParams | None:
    """Paramètres de la copie pour un déplacement de ``delta`` mm le long de l'axe de la pièce
    dont l'axe global est ``axis`` et le sens ``sign`` (:func:`global_axis`) : une copie, pas =
    distance, ``reverse`` si le déplacement va dans le sens négatif. ``None`` si le déplacement
    est inférieur à :data:`MIN_MOVE` (un simple clic)."""
    moved = sign * delta
    if abs(moved) < MIN_MOVE:
        return None
    return RepeatParams(
        spacing=SpacingMode.COUNT_AND_STEP,
        count=1,
        step=abs(moved),
        axis=axis,
        reverse=moved < 0,
    )
