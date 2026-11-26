# SPDX-License-Identifier: LGPL-2.1-or-later
"""Outils d'épaisseur du panneau de la pièce de bois : menu des épaisseurs standard du matériau
et de l'utilisateur, ajout d'une épaisseur personnelle (issue #71, ADR 0028) et avertissement
« hors standard » (panneaux). Les formats de panneau n'y sont plus (jv, 2026-11-26).

Séparés de :mod:`freecad.menuiserie.gui.task_panels.wood_part` pour garder chaque panneau
court. Le menu écrit l'épaisseur choisie dans le champ du formulaire, qui la remet au panneau.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any, Final

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import MAX_THICKNESS_MM, Material
from freecad.menuiserie.core.part_model import (
    is_nonstandard_panel_thickness,
)
from freecad.menuiserie.core.user_dimensions import UserDimensions
from freecad.menuiserie.features import user_dimensions
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.task_panels.base import connect

_ADD_THICKNESS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ajouter une épaisseur…")
_ADD_THICKNESS_PROMPT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur à ajouter (mm) :")
_REFUSED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Valeur refusée")
ADD_THICKNESS_ACTION: Final = "addThicknessAction"  # repérée par les vérifications du panneau


class ThicknessTools:
    """Bouton « épaisseurs standard » et avertissement du formulaire ``form`` pour ``obj`` ;
    le menu propose aussi les épaisseurs personnelles et leur ajout."""

    def __init__(self, form: Any, obj: DocumentObject) -> None:
        self._form = form
        self._obj = obj
        self._personal: UserDimensions = user_dimensions.read_dimensions()
        self._menu = QtGui.QMenu(form.standardThicknessButton)
        form.standardThicknessButton.setMenu(self._menu)

    def show(self) -> None:
        """Menu des épaisseurs, et avertissement « hors standard » (panneaux)."""
        material = get_library().find(self._obj.MaterialId)
        self._fill_menu(material)
        button = self._form.standardThicknessButton
        button.setEnabled(material is not None and not has_expression(self._obj, "Thickness"))
        thickness = self._obj.Thickness.Value
        warn = material is not None and is_nonstandard_panel_thickness(
            material, thickness, self._personal.thicknesses
        )
        self._form.thicknessWarning.setVisible(warn)

    def _fill_menu(self, material: Material | None) -> None:
        self._menu.clear()
        standard = material.thicknesses if material is not None else ()
        for thickness in (*standard, *self._personal.thicknesses):
            action = self._menu.addAction(_length_text(thickness))
            connect(action, "triggered()", partial(self._choose, thickness))
        add = self._menu.addAction(translated(_ADD_THICKNESS))
        add.setObjectName(ADD_THICKNESS_ACTION)
        connect(add, "triggered()", self._add_thickness)

    def _choose(self, thickness: float) -> None:
        """Épaisseur choisie dans le menu : écrite par le champ lui-même."""
        self._form.thicknessEdit.setProperty("rawValue", thickness)

    def _ask(self, prompt: str, maximum: float) -> float | None:
        """Valeur en mm saisie dans une boîte de dialogue, ``None`` si elle est annulée."""
        value, accepted = QtGui.QInputDialog.getDouble(
            self._form,
            translated(prompt),
            translated(prompt),
            0.0,
            0.0,
            maximum,
            2,
        )
        return float(value) if accepted else None

    def _add_thickness(self) -> None:
        value = self._ask(_ADD_THICKNESS_PROMPT, MAX_THICKNESS_MM)
        if value is not None:
            self._save(lambda: user_dimensions.add_thickness(value))

    def _save(self, action: Callable[[], UserDimensions]) -> None:
        """Enregistre une valeur personnelle, puis met à jour le menu ; un refus s'affiche."""
        try:
            self._personal = action()
        except ValueError as error:
            QtGui.QMessageBox.warning(self._form, translated(_REFUSED), str(error))
            return
        self.show()


def _length_text(length_mm: float) -> str:
    """Longueur dans le système d'unités choisi par l'utilisateur (« 22 mm », « 0,87 in »…)."""
    text: str = App.Units.Quantity(length_mm, App.Units.Length).UserString
    return text
