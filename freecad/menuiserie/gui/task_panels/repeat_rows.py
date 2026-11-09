# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lignes X, Y et Z du panneau « Répéter » (grille, ADR 0045).

Un seul mode de saisie pour tout le panneau (``SpacingMode``) ; chaque axe a sa ligne : case
d'activation (le nom de l'axe), nombre d'éléments sur l'axe (original compris, au moins 2), pas,
longueur et case « Inverser ». Seuls les champs que le mode utilise sont visibles ; une ligne
décochée est grisée et ne compte pas dans la grille.
"""

from __future__ import annotations

from typing import Final

from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import MAX_COPIES, AxisRepeat, RepeatAxis, SpacingMode
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import Widget
from freecad.menuiserie.gui.task_panels.furniture_widgets import quantity_field

__all__ = ["COLUMN_CAPTIONS", "AxisRow", "uses"]

DEFAULT_CELLS: Final = 2  # nombre proposé à l'activation d'un axe
_ACTIVE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répète sur l'axe {axis} du repère de la pièce. Décochée, l'axe est inactif (nombre 1).",
)
_COUNT_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Nombre d'éléments sur cet axe, pièce d'origine comprise (de 2 à {max}). Le total des copies "
    "est le produit des nombres de tous les axes moins un, au plus {copies}.",
)
_STEP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance entre deux copies, mesurée sur l'axe (d'une face à la même face de la suivante).",
)
_SPAN_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Longueur à remplir sur l'axe, pièce d'origine comprise."
)
_REVERSE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Inverser")
_REVERSE_TIP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répète dans le sens négatif de l'axe.")
COLUMN_CAPTIONS: Final = (
    ("count", QT_TRANSLATE_NOOP("Menuiserie", "Nombre")),
    ("step", QT_TRANSLATE_NOOP("Menuiserie", "Pas")),
    ("span", QT_TRANSLATE_NOOP("Menuiserie", "Longueur")),
)
_USED: Final = {
    SpacingMode.COUNT_AND_STEP: ("count", "step"),
    SpacingMode.COUNT_ON_SPAN: ("count", "span"),
    SpacingMode.STEP_ON_SPAN: ("step", "span"),
}


def uses(spacing: SpacingMode) -> tuple[str, ...]:
    """Colonnes (``count``, ``step``, ``span``) que le mode de saisie ``spacing`` utilise."""
    return _USED[spacing]


class AxisRow:
    """Ligne de l'axe ``axis`` : ``active`` (case), ``count``, ``step``, ``span``, ``reverse``.
    Noms d'objets Qt : ``axisX``, ``countX``, ``stepX``, ``spanX``, ``reverseX`` (Y, Z de même)."""

    def __init__(self, axis: RepeatAxis) -> None:
        name = axis.value
        self.axis = axis
        self.active = QtGui.QCheckBox(name)
        self.active.setObjectName(f"axis{name}")
        self.active.setToolTip(translated(_ACTIVE_TIP, {"axis": name}))
        self.count = QtGui.QSpinBox()
        self.count.setObjectName(f"count{name}")
        self.count.setRange(DEFAULT_CELLS, MAX_COPIES + 1)
        self.count.setKeyboardTracking(False)  # aperçu à la fin de la saisie
        self.count.setToolTip(
            translated(_COUNT_TIP, {"max": str(MAX_COPIES + 1), "copies": str(MAX_COPIES)})
        )
        self.step = quantity_field(f"step{name}", 0.0)
        self.step.setToolTip(translated(_STEP_TIP))
        self.span = quantity_field(f"span{name}", 0.0)
        self.span.setToolTip(translated(_SPAN_TIP))
        self.reverse = QtGui.QCheckBox(translated(_REVERSE))
        self.reverse.setObjectName(f"reverse{name}")
        self.reverse.setToolTip(translated(_REVERSE_TIP))

    def widgets(self) -> tuple[Widget, ...]:
        """Les cinq widgets de la ligne, dans l'ordre des colonnes."""
        return (self.active, self.count, self.step, self.span, self.reverse)

    def checked(self) -> bool:
        """Vrai si l'axe est actif."""
        return bool(self.active.isChecked())

    def line(self) -> AxisRepeat:
        """Saisie de la ligne (valeurs brutes, contrôlées par ``RepeatParams``)."""
        return AxisRepeat(
            self.axis,
            int(self.count.value()),
            float(self.step.property("rawValue")),
            float(self.span.property("rawValue")),
            self.reverse.isChecked(),
        )

    def load(self, line: AxisRepeat | None, step: float) -> None:
        """Champs de la ligne : ceux de ``line`` (axe actif), ou axe inactif avec le pas ``step``
        et le nombre par défaut. Les signaux sont à bloquer par l'appelant (garde du panneau)."""
        self.active.setChecked(line is not None)
        self.count.setValue(DEFAULT_CELLS if line is None else max(DEFAULT_CELLS, line.count))
        self.step.setProperty("rawValue", step if line is None else line.step)
        self.span.setProperty(
            "rawValue", round(step * DEFAULT_CELLS, 6) if line is None else line.span
        )
        self.reverse.setChecked(False if line is None else line.reverse)

    def show_for(self, spacing: SpacingMode) -> None:
        """Seuls les champs du mode de saisie sont visibles ; une ligne décochée est grisée."""
        used = uses(spacing)
        active = self.checked()
        for name, widget in (("count", self.count), ("step", self.step), ("span", self.span)):
            widget.setVisible(name in used)
            widget.setEnabled(active)
        self.reverse.setEnabled(active)
