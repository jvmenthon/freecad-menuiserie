# SPDX-License-Identifier: LGPL-2.1-or-later
"""Champs d'angle X, Y, Z du panneau de l'ensemble (EN-d, ADR 0038, critère D1).

Les champs montrent les trois angles du ``Placement`` du Std Part propre à l'ensemble (degrés, au
dixième). Comme ceux de la pièce (:mod:`angle_rows`), ils acceptent de -360 à 360 sur les trois
axes : l'ensemble tourne comme saisi, autour du centre de sa boîte (``rotate_furniture_to``), puis
les champs sont recalculés en fin de saisie (``editingFinished``) en la forme canonique de
:func:`~freecad.menuiserie.core.rotation.angles_of` (X et Z dans [-180, 180], Y dans [-90, 90]).
Un geste dans la vue 3D (anneau) fait relire les champs par :meth:`FurnitureAngleRows.show`,
signaux bloqués : pas de boucle.

Les champs sont grisés, avec la raison en infobulle, quand ``rotate_furniture_to`` est impossible :
sous-ensemble dont le parent lie la position du Std Part, ensemble sans Std Part propre (ancien
document, Std Part partagé) ou position pilotée par une formule.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.rotation import Angles, angles_of
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.furniture_bindings import workshop_expressions
from freecad.menuiserie.features.furniture_checks import quoted_label
from freecad.menuiserie.features.furniture_container import own_std_part
from freecad.menuiserie.features.furniture_drag import rotate_furniture_to, turn_refusal
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.gui.task_panels.base import Widget, connect

__all__ = ["FurnitureAngleRows", "angle_refusal"]

MAX_ANGLE_DEGREES: Final = 360.0
DECIMALS: Final = 1
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Rotation")
_AXES: Final = (
    ("X", QT_TRANSLATE_NOOP("Menuiserie", "Autour de X")),
    ("Y", QT_TRANSLATE_NOOP("Menuiserie", "Autour de Y")),
    ("Z", QT_TRANSLATE_NOOP("Menuiserie", "Autour de Z")),
)
_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Angle de l'ensemble autour de l'axe {axis} de son conteneur, de -360 à 360 degrés. L'ensemble "
    "tourne avec ses pièces autour du centre de sa boîte et la vue 3D suit votre saisie. À la fin "
    "de la saisie, les trois angles sont recalculés (même orientation).",
)
_LINKED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est lié à son ensemble parent : sa position suit les cotes de ce dernier. "
    "Il ne peut pas être tourné ici.",
)


def _linked_by_parent(furniture: DocumentObject) -> bool:
    """Vrai si l'ensemble est un sous-ensemble dont le parent lie la position du Std Part
    (liaison de l'atelier sur son ``Placement``)."""
    if furniture_of(furniture) is None:
        return False
    return any(path.split(".")[0] == "Placement" for path in workshop_expressions(furniture))


def angle_refusal(furniture: DocumentObject) -> str | None:
    """Raison (traduite) pour laquelle ``rotate_furniture_to`` est impossible pour ``furniture``,
    ``None`` s'il peut tourner : sous-ensemble lié par son parent, pas de Std Part propre, position
    du Std Part pilotée par une formule."""
    if own_std_part(furniture) is not None and _linked_by_parent(furniture):
        return translated(_LINKED, quoted_label(furniture))
    return turn_refusal(furniture)


def _angle_field(name: str) -> Widget:
    """Champ d'unité de FreeCAD, en degrés, de -360 à 360."""
    field = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    field.setObjectName(name)
    field.setProperty("unit", "deg")
    field.setProperty("minimum", -MAX_ANGLE_DEGREES)
    field.setProperty("maximum", MAX_ANGLE_DEGREES)
    field.setProperty("singleStep", 1.0)
    field.setProperty("decimals", DECIMALS)
    field.setKeyboardTracking(False)
    return field


class FurnitureAngleRows:
    """Groupe « Rotation » (trois champs) de l'ensemble ``obj``, ajouté à ``layout``.

    ``on_written`` : appelé quand une saisie a tourné l'ensemble (le panneau recalcule son
    aperçu) ; les champs et leurs libellés portent les noms ``angleXEdit``, ``angleXLabel``…"""

    def __init__(self, layout: Widget, obj: DocumentObject, on_written: Callable[[], None]) -> None:
        self._obj = obj
        self._on_written = on_written
        self.group = QtGui.QGroupBox(translated(_TITLE))
        self.group.setObjectName("rotationGroup")
        grid = QtGui.QGridLayout(self.group)
        self._labels: list[Widget] = []
        self._fields: list[Widget] = []
        for row, (axis, text) in enumerate(_AXES):
            label = QtGui.QLabel(translated(text))
            label.setObjectName(f"angle{axis}Label")
            field = _angle_field(f"angle{axis}Edit")
            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)
            connect(field, "valueChanged(double)", self._edited)
            connect(field, "editingFinished()", self.finish)
            self._labels.append(label)
            self._fields.append(field)
        layout.addWidget(self.group)
        self.show()

    @property
    def fields(self) -> list[Widget]:
        """Les trois champs d'angle (X, Y, Z)."""
        return list(self._fields)

    def angles(self) -> Angles:
        """Angles X, Y, Z lus dans les champs, en degrés."""
        x, y, z = (float(field.property("rawValue")) for field in self._fields)
        return (x, y, z)

    def show(self) -> None:
        """Angles du Std Part dans les champs, signaux bloqués ; champs grisés, avec la raison en
        infobulle, si l'ensemble ne peut pas tourner ici."""
        part = own_std_part(self._obj)
        angles = angles_of(rigid_transform(part.Placement).rotation) if part else (0.0, 0.0, 0.0)
        reason = angle_refusal(self._obj)
        for (axis, _text), label, field, angle in zip(
            _AXES, self._labels, self._fields, angles, strict=True
        ):
            blocked = field.blockSignals(True)
            try:
                field.setProperty("rawValue", angle)
            finally:
                field.blockSignals(blocked)
            tip = reason or translated(_TIP, {"axis": axis})
            for widget in (label, field):
                widget.setEnabled(reason is None)
                widget.setToolTip(tip)

    def _edited(self, _value: float) -> None:
        """Un champ a changé : l'ensemble tourne aussitôt, l'aperçu suit."""
        try:
            written = rotate_furniture_to(self._obj, self.angles())
        except ValueError as error:  # angle non fini ou hors de [-360, 360] : rien n'est écrit
            report_warning(str(error))
            return
        if written:
            self._on_written()

    def finish(self) -> None:
        """Fin de saisie : les trois champs montrent la forme canonique de l'orientation."""
        self.show()
