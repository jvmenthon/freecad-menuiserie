# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ligne supplémentaire de la page de préférences, fournie par l'atelier (ADR 0069).

Qt par la couche ``PySide`` de FreeCAD.
"""

from __future__ import annotations

from PySide import QtGui

from . import page_model as model

__all__ = ["ExtraLine"]
Widget = model.Widget


class ExtraLine:
    """Ligne d'une :class:`~.page_model.ExtraRow` : libellé et contrôle de l'atelier, dans les deux
    premières colonnes de la grille (comme une :class:`Row`)."""

    def __init__(self, extra: model.ExtraRow, translate: model.Translate) -> None:
        self.extra = extra
        self.label = QtGui.QLabel(translate(extra.label))
        self.tip = translate(extra.tooltip) if extra.tooltip else ""
        for widget in (self.label, extra.widget):
            widget.setToolTip(self.tip)
        self._text = f"{self.label.text()} {self.tip}"

    def widgets(self) -> list[Widget | None]:
        """Widgets des colonnes de la grille : libellé et contrôle."""
        return [self.label, self.extra.widget]

    def all_widgets(self) -> list[Widget]:
        """Widgets à montrer ou masquer ensemble."""
        return [self.label, self.extra.widget]

    def matches(self, query: str) -> bool:
        """Vrai si la recherche trouve le libellé ou l'infobulle."""
        return model.text_matches(self._text, query)
