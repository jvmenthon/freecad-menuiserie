# SPDX-License-Identifier: LGPL-2.1-or-later
"""Champs du panneau d'un assemblage, construits d'après la description des paramètres
(:class:`~freecad.menuiserie.features.schema.PropertySpec`) : un champ par paramètre, sans
formulaire ``.ui`` par type (critère E1 de J3).

- cote (longueur ou décalage) : champ d'unité de FreeCAD ; nombre : compteur entier ;
- paramètre « 0 = automatique » (``spec.resolved``) : case « Auto » ; cochée, le champ est
  inactif et montre la valeur effective (``resolve`` de ``core``) ;
- booléen : case à cocher ;
- paramètre piloté par une expression : champ inactif, jamais écrit (règle C6 de J1).

Les champs ne touchent jamais l'objet : chaque saisie est remise au panneau (``Write``), qui
l'écrit puis rafraîchit l'affichage par :meth:`ParamField.show`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.schema import DISTANCE, PropertySpec
from freecad.menuiserie.gui.task_panels.base import Widget, connect, has_expression

Write = Callable[[str, object], None]  # (propriété, valeur) écrite par le panneau

BOOL: Final = "App::PropertyBool"
COUNT: Final = "App::PropertyIntegerConstraint"
MAX_COUNT: Final = 50
_AUTO: Final = QT_TRANSLATE_NOOP("Menuiserie", "Auto")
_AUTO_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Valeur automatique (proportions de menuisier), recalculée quand les pièces changent ; "
    "décochez pour saisir une valeur fixe.",
)
_DRIVEN_TIP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Piloté par une expression : {expression}")


def property_tooltip(spec: PropertySpec) -> str:
    """Infobulle de la propriété, traduite comme dans l'éditeur de propriétés."""
    text: str = App.Qt.translate("App::Property", spec.tooltip)
    return text


def expression_of(obj: DocumentObject, prop: str) -> str | None:
    """Expression qui pilote ``prop``, ``None`` s'il n'y en a pas."""
    if not has_expression(obj, prop):
        return None
    expression: str = next(e for path, e in obj.ExpressionEngine if path.lstrip(".") == prop)
    return expression


class ParamField:
    """Champ d'un paramètre : libellé, widget de saisie et case « Auto » éventuelle."""

    def __init__(self, spec: PropertySpec, write: Write) -> None:
        self.spec = spec
        self._write = write
        self._updating = False
        self.label = QtGui.QLabel(translated(spec.label))
        self.editor: Widget = self._make_editor()
        self.editor.setObjectName(spec.name)
        self.auto: Widget = self._make_auto() if spec.resolved else None
        for widget in (self.label, self.editor):
            widget.setToolTip(property_tooltip(spec))

    def show(self, obj: DocumentObject, resolved: object | None) -> None:
        """Valeur de ``obj`` (ou valeur effective en mode auto), état actif des widgets."""
        value = getattr(obj, self.spec.name)
        expression = expression_of(obj, self.spec.name)
        automatic = self.auto is not None and not value
        shown = getattr(resolved, self.spec.resolved, value) if automatic else value
        with self._quiet():
            self._display(getattr(shown, "Value", shown))
            if self.auto is not None:
                self.auto.setChecked(automatic)
                self.auto.setEnabled(expression is None)
        self.editor.setEnabled(expression is None and not automatic)
        if expression is not None:
            self.editor.setToolTip(translated(_DRIVEN_TIP, {"expression": expression}))

    def widgets(self) -> tuple[Widget, Widget, Widget | None]:
        """Libellé, champ et case « Auto » (ligne de la grille du panneau)."""
        return self.label, self.editor, self.auto

    # --- Étapes propres au genre de champ -------------------------------------------------

    def _make_editor(self) -> Widget:
        """Champ d'unité (mm) d'une cote ; compteur pour un nombre ; case pour un booléen."""
        if self.spec.type_id == BOOL:
            box = QtGui.QCheckBox()
            connect(box, "toggled(bool)", self._on_edited)
            return box
        if self.spec.type_id == COUNT:
            spin = QtGui.QSpinBox()
            spin.setRange(0, MAX_COUNT)
            connect(spin, "valueChanged(int)", self._on_edited)
            return spin
        field = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
        field.setProperty("unit", "mm")
        minimum = -MAX_DIMENSION_MM if self.spec.type_id == DISTANCE else 0.0
        field.setProperty("minimum", minimum)
        field.setProperty("maximum", MAX_DIMENSION_MM)
        connect(field, "valueChanged(double)", self._on_edited)
        return field

    def _display(self, value: object) -> None:
        if self.spec.type_id == BOOL:
            self.editor.setChecked(bool(value))
        elif self.spec.type_id == COUNT:
            self.editor.setValue(int(value))  # type: ignore[call-overload]
        else:
            self.editor.setProperty("rawValue", float(value))  # type: ignore[arg-type]

    def _current(self) -> object:
        """Valeur saisie dans le champ (mm, entier ou booléen)."""
        if self.spec.type_id == BOOL:
            return bool(self.editor.isChecked())
        if self.spec.type_id == COUNT:
            return int(self.editor.value())
        return float(self.editor.property("rawValue"))

    # --- Saisies --------------------------------------------------------------------------

    def _make_auto(self) -> Widget:
        box = QtGui.QCheckBox(translated(_AUTO))
        box.setObjectName(f"{self.spec.name}Auto")
        box.setToolTip(translated(_AUTO_TIP))
        connect(box, "toggled(bool)", self._on_auto_toggled)
        return box

    def _on_edited(self, *_value: object) -> None:
        if not self._updating:
            self._write(self.spec.name, self._current())

    def _on_auto_toggled(self, automatic: bool) -> None:
        """Cochée : 0 (automatique) ; décochée : la valeur effective affichée devient fixe."""
        if not self._updating:
            self._write(self.spec.name, 0 if automatic else self._current())

    @contextmanager
    def _quiet(self) -> Iterator[None]:
        """Mise à jour des widgets par le panneau : rien n'est réécrit dans l'objet."""
        previous, self._updating = self._updating, True
        try:
            yield
        finally:
            self._updating = previous


def fields_of(specs: tuple[PropertySpec, ...], write: Write) -> list[ParamField]:
    """Un champ par paramètre décrit avec un libellé (``spec.label``), dans l'ordre."""
    return [ParamField(spec, write) for spec in specs if spec.label]
