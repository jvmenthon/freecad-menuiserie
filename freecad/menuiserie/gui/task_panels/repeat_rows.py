# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lignes X, Y et Z du panneau « Répéter » (grille, ADR 0045).

Un seul mode de saisie pour tout le panneau (``SpacingMode``) ; chaque axe a sa ligne : case
d'activation (le nom de l'axe), nombre d'éléments sur l'axe (original compris, au moins 2), pas,
longueur, butée (bouton « Butée… », nom de la butée choisie et bouton pour l'enlever ; avec une
butée la longueur est calculée, en lecture seule, ADR 0047) et case « Inverser ». Seuls les
champs que le mode utilise sont visibles ; une ligne décochée est grisée et ne compte pas dans
la grille.
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
_STOP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Butée…")
_STOP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Choisissez dans la vue 3D une face, un sommet ou une pièce : la longueur est alors calculée "
    "jusqu'à elle et suit la butée si elle bouge.",
)
_PICKING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Cliquez dans la vue 3D…")
_CLEAR: Final = QT_TRANSLATE_NOOP("Menuiserie", "Retirer")
_CLEAR_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Enlève la butée : la longueur se saisit de nouveau."
)
_REVERSE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Inverser")
_REVERSE_TIP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répète dans le sens négatif de l'axe.")
COLUMN_CAPTIONS: Final = (
    ("count", QT_TRANSLATE_NOOP("Menuiserie", "Nombre")),
    ("step", QT_TRANSLATE_NOOP("Menuiserie", "Pas")),
    ("span", QT_TRANSLATE_NOOP("Menuiserie", "Longueur")),
    ("stop", QT_TRANSLATE_NOOP("Menuiserie", "Butée")),
)
_USED: Final = {
    SpacingMode.COUNT_AND_STEP: ("count", "step"),
    SpacingMode.COUNT_ON_SPAN: ("count", "span", "stop"),
    SpacingMode.STEP_ON_SPAN: ("step", "span", "stop"),
}


def uses(spacing: SpacingMode) -> tuple[str, ...]:
    """Colonnes (``count``, ``step``, ``span``, ``stop``) que le mode ``spacing`` utilise."""
    return _USED[spacing]


class AxisRow:
    """Ligne de l'axe ``axis`` : ``active`` (case), ``count``, ``step``, ``span``, butée (``stop``,
    ``stop_name``, ``stop_clear``), ``reverse``. Noms d'objets Qt : ``axisX``, ``countX``,
    ``stepX``, ``spanX``, ``stopX``, ``stopNameX``, ``stopClearX``, ``reverseX`` (Y, Z de même)."""

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
        self.stop_box = QtGui.QWidget()
        box = QtGui.QHBoxLayout(self.stop_box)
        box.setContentsMargins(0, 0, 0, 0)
        self.stop = QtGui.QPushButton(translated(_STOP))
        self.stop.setObjectName(f"stop{name}")
        self.stop.setToolTip(translated(_STOP_TIP))
        self.stop_name = QtGui.QLabel("")
        self.stop_name.setObjectName(f"stopName{name}")
        self.stop_clear = QtGui.QToolButton()
        self.stop_clear.setObjectName(f"stopClear{name}")
        self.stop_clear.setText(translated(_CLEAR))
        self.stop_clear.setToolTip(translated(_CLEAR_TIP))
        for widget in (self.stop, self.stop_name, self.stop_clear):
            box.addWidget(widget)
        self.reverse = QtGui.QCheckBox(translated(_REVERSE))
        self.reverse.setObjectName(f"reverse{name}")
        self.reverse.setToolTip(translated(_REVERSE_TIP))
        self.stopped = False  # longueur calculée par une butée : lecture seule
        self.show_stop(None)

    def widgets(self) -> tuple[Widget, ...]:
        """Les six widgets de la ligne, dans l'ordre des colonnes."""
        return (self.active, self.count, self.step, self.span, self.stop_box, self.reverse)

    def show_stop(self, text: str | None, *, picking: bool = False) -> None:
        """Butée de la ligne : son nom (``None`` : aucune) et le bouton pour l'enlever ; la
        longueur est en lecture seule (grisée) tant qu'il y en a une. ``picking`` : choix en
        cours."""
        self.stop_name.setText(translated(_PICKING) if picking else (text or ""))
        self.stop_name.setToolTip(text or "")
        self.stop_clear.setVisible(text is not None)
        self.stopped = text is not None
        self.span.setReadOnly(self.stopped)
        self.span.setEnabled(self.checked() and not self.stopped)
        self.reverse.setEnabled(self.checked() and not self.stopped)  # sens déduit de la butée
        self.stop.setText(translated(_PICKING if picking else _STOP))
        self.stop.setDown(picking)

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
        shown = (
            ("count", self.count),
            ("step", self.step),
            ("span", self.span),
            ("stop", self.stop_box),
        )
        for name, widget in shown:
            widget.setVisible(name in used)
            widget.setEnabled(active and not (name == "span" and self.stopped))
        self.reverse.setEnabled(active and not self.stopped)
