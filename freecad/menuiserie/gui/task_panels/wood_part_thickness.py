# SPDX-License-Identifier: LGPL-2.1-or-later
"""Outils d'épaisseur du panneau de la pièce de bois : menu des épaisseurs standard du matériau
et avertissement « hors standard » (panneaux).

Séparés de :mod:`freecad.menuiserie.gui.task_panels.wood_part` pour garder chaque panneau
court. Le menu écrit l'épaisseur choisie dans le champ du formulaire, qui la remet au panneau.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie.core.materials import Material
from freecad.menuiserie.core.part_model import is_nonstandard_panel_thickness
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.task_panels.base import connect


class ThicknessTools:
    """Bouton « épaisseurs standard » et avertissement du formulaire ``form`` pour ``obj``."""

    def __init__(self, form: Any, obj: DocumentObject) -> None:
        self._form = form
        self._obj = obj
        self._menu = QtGui.QMenu(form.standardThicknessButton)
        form.standardThicknessButton.setMenu(self._menu)

    def show(self) -> None:
        """Menu des épaisseurs standard et avertissement « hors standard » (panneaux)."""
        material = get_library().find(self._obj.MaterialId)
        self._fill_menu(material)
        button = self._form.standardThicknessButton
        button.setEnabled(material is not None and not has_expression(self._obj, "Thickness"))
        thickness = self._obj.Thickness.Value
        warn = material is not None and is_nonstandard_panel_thickness(material, thickness)
        self._form.thicknessWarning.setVisible(warn)

    def _fill_menu(self, material: Material | None) -> None:
        self._menu.clear()
        for thickness in material.thicknesses if material is not None else ():
            action = self._menu.addAction(_length_text(thickness))
            connect(action, "triggered()", partial(self._choose, thickness))

    def _choose(self, thickness: float) -> None:
        """Épaisseur standard choisie dans le menu : écrite par le champ lui-même."""
        self._form.thicknessEdit.setProperty("rawValue", thickness)


def _length_text(length_mm: float) -> str:
    """Longueur dans le système d'unités choisi par l'utilisateur (« 22 mm », « 0,87 in »…)."""
    text: str = App.Units.Quantity(length_mm, App.Units.Length).UserString
    return text
