# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lignes du formulaire communes aux panneaux de la pièce de bois et de la pièce en bois
(ADR 0020, D2) : repère, matériau, sens du fil, surcotes et boutons de rotation X, Y, Z.

Les deux panneaux chargent le même formulaire (``wood_part.ui``) ; ces classes en pilotent les
widgets sans rien garder de plus que le formulaire et l'objet du panneau, que le panneau tient
en vie. Chaque saisie est écrite aussitôt dans l'objet puis le panneau recalcule l'aperçu ; une
propriété pilotée par une expression n'est jamais écrite.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, GrainDirection
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    has_expression,
    placement_expression,
)
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_members import quoted_label
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.wood_part import set_material, shows_grain
from freecad.menuiserie.gui.task_panels.base import UpdateGuard, connect, weak_callback

__all__ = [
    "DRIVEN_FIELDS",
    "GRAIN_LABELS",
    "KIND_FILTERS",
    "ROTATIONS",
    "AllowanceRows",
    "LengthField",
    "MaterialRows",
    "bind_field",
    "bind_length_field",
    "connect_rotations",
    "setup_rotation_buttons",
]

Widget = Any
_INDEX_CHANGED: Final = "currentIndexChanged(int)"
_FOLLOWS_FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cette pièce suit l'ensemble « {label} » : tournez-la avec Std Transform après l'avoir "
    "retirée de l'ensemble.",
)
_DRIVEN_PLACEMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La position de cette pièce est pilotée par une expression : retirez l'expression ou "
    "tournez la pièce avec Std Transform.",
)
# Boutons de rotation : widget, axe tourné, icône générée.
ROTATIONS: Final = (
    ("rotateXButton", Turn.X, "Menuiserie_RotateX.svg"),
    ("rotateYButton", Turn.Y, "Menuiserie_RotateY.svg"),
    ("rotateZButton", Turn.Z, "Menuiserie_RotateZ.svg"),
)

# Filtre « Type » : libellé, puis familles retenues (aucune : tous les matériaux).
KIND_FILTERS: Final[tuple[tuple[str, tuple[MaterialKind, ...]], ...]] = (
    (QT_TRANSLATE_NOOP("Menuiserie", "Tous"), ()),
    (QT_TRANSLATE_NOOP("Menuiserie", "Massif"), (MaterialKind.SOLID,)),
    (QT_TRANSLATE_NOOP("Menuiserie", "Contreplaqué"), (MaterialKind.PLYWOOD,)),
    (QT_TRANSLATE_NOOP("Menuiserie", "MDF"), (MaterialKind.MDF,)),
    (QT_TRANSLATE_NOOP("Menuiserie", "Mélaminé"), (MaterialKind.MELAMINE,)),
)
# Sens du fil : valeur stable écrite dans l'objet, libellé traduit affiché.
GRAIN_LABELS: Final = (
    (GrainDirection.LENGTH, QT_TRANSLATE_NOOP("Menuiserie", "Longueur")),
    (GrainDirection.WIDTH, QT_TRANSLATE_NOOP("Menuiserie", "Largeur")),
    (GrainDirection.NONE, QT_TRANSLATE_NOOP("Menuiserie", "Sans fil")),
)
# Champs sans liaison d'expression possible : inactifs si leur propriété est pilotée (C6).
DRIVEN_FIELDS: Final = (
    ("markEdit", "Mark"),
    ("materialCombo", "Material"),
    ("grainCombo", "GrainDirection"),
)


@dataclass(frozen=True)
class LengthField:
    """Champ de cote du formulaire, lié à une propriété ``App::PropertyLength``."""

    widget: str
    prop: str
    minimum: float


def bind_field(widget: Widget, obj: DocumentObject, prop: str, minimum: float) -> Any:
    """Bornes du champ de cote ``widget`` et liaison à la propriété ``prop`` de ``obj`` (affichage
    et édition des expressions). La liaison rendue doit être gardée en vie par l'appelant."""
    widget.setProperty("minimum", minimum)
    widget.setProperty("maximum", MAX_DIMENSION_MM)
    binding = Gui.ExpressionBinding(widget)
    binding.bind(obj, prop)
    binding.setAutoApply(True)
    return binding


def bind_length_field(form: Widget, obj: DocumentObject, field: LengthField) -> Any:
    """Liaison du champ ``field`` du formulaire à la propriété de ``obj`` (:func:`bind_field`)."""
    return bind_field(getattr(form, field.widget), obj, field.prop, field.minimum)


class MaterialRows:
    """Repère, type, matériau et sens du fil du formulaire ``form`` pour la pièce ``obj``.

    ``guard`` : garde du panneau (les mises à jour des widgets ne sont pas réécrites dans l'objet) ;
    ``on_material`` : appelé après un nouveau matériau, une fois le fil et les surcotes de l'objet
    suivis (le panneau relit ses champs et recalcule l'aperçu) ; ``on_grain`` : appelé après un
    nouveau sens du fil (le panneau recalcule l'aperçu)."""

    def __init__(
        self,
        form: Widget,
        obj: DocumentObject,
        guard: UpdateGuard,
        on_material: Callable[[], None],
        on_grain: Callable[[], None],
    ) -> None:
        self._form = form
        self._obj = obj
        self._guard = guard
        self._on_material = weak_callback(on_material)
        self._on_grain = weak_callback(on_grain)

    def fill_choices(self) -> None:
        """Libellés des filtres de type et des sens du fil."""
        for label, _kinds in KIND_FILTERS:
            self._form.kindCombo.addItem(translated(label))
        for grain, label in GRAIN_LABELS:
            self._form.grainCombo.addItem(translated(label), grain.value)

    def fill_materials(self) -> None:
        """Matériaux du type choisi ; hors filtre, le premier de la liste est appliqué."""
        combo = self._form.materialCombo
        obj = self._obj
        kinds = KIND_FILTERS[max(self._form.kindCombo.currentIndex(), 0)][1]
        with self._guard:
            combo.clear()
            for material in get_library().by_kind(*kinds):
                combo.addItem(material.name(display_language()), material.id)
            if not kinds and combo.findData(obj.MaterialId) < 0:
                # Matériau inconnu de la bibliothèque locale : son libellé enregistré reste affiché.
                combo.addItem(obj.Material, obj.MaterialId)
            combo.setCurrentIndex(combo.findData(obj.MaterialId))
        if combo.currentIndex() < 0 and combo.count() and not has_expression(obj, "Material"):
            combo.setCurrentIndex(0)

    def show(self) -> None:
        """Repère et sens du fil de l'objet dans les champs (sous la garde du panneau)."""
        with self._guard:
            self._form.markEdit.setText(self._obj.Mark)
            grain = self._form.grainCombo.findData(self._obj.GrainDirection)
            self._form.grainCombo.setCurrentIndex(grain)
            shown = shows_grain(self._obj)
            self._form.grainLabel.setVisible(shown)  # masquée pour un matériau sans fil
            self._form.grainCombo.setVisible(shown)

    def lock(self, newer_version: bool) -> None:
        """Repère, matériau ou fil pilotés par une expression : champ inactif (C6). Pièce d'un
        document plus récent (``newer_version``) : matériau en lecture seule (listes du type et du
        matériau inactives) et message dans le formulaire."""
        for widget, prop in DRIVEN_FIELDS:
            if has_expression(self._obj, prop):
                getattr(self._form, widget).setEnabled(False)
        if newer_version:
            for widget in ("kindCombo", "materialCombo"):
                getattr(self._form, widget).setEnabled(False)
            self._form.newerVersionNotice.setVisible(True)

    def connect_signals(self) -> None:
        """Saisies du repère, du type, du matériau et du sens du fil."""
        form = self._form
        connect(form.markEdit, "textEdited(QString)", self._on_mark_edited)
        connect(form.kindCombo, _INDEX_CHANGED, self._on_kind_chosen)
        connect(form.materialCombo, _INDEX_CHANGED, self._on_material_chosen)
        connect(form.grainCombo, _INDEX_CHANGED, self._on_grain_chosen)

    def _on_mark_edited(self, text: str) -> None:
        if not has_expression(self._obj, "Mark"):
            self._obj.Mark = text

    def _on_kind_chosen(self, _index: int) -> None:
        self.fill_materials()

    def _on_material_chosen(self, index: int) -> None:
        if self._guard.active or index < 0 or has_expression(self._obj, "Material"):
            return
        material_id = self._form.materialCombo.itemData(index)
        if material_id == self._obj.MaterialId or get_library().find(material_id) is None:
            return
        set_material(self._obj, material_id)
        self._on_material()  # le fil et les surcotes suivent le matériau

    def _on_grain_chosen(self, index: int) -> None:
        if (
            not self._guard.active
            and index >= 0
            and not has_expression(self._obj, "GrainDirection")
        ):
            self._obj.GrainDirection = self._form.grainCombo.itemData(index)
            self._on_grain()  # la texture tourne aussitôt


class AllowanceRows:
    """Surcotes de débit du formulaire ``form`` : champs ``fields`` liés à l'objet, zone repliable.

    ``on_changed`` : appelé après l'écriture d'une surcote (le panneau recalcule l'aperçu)."""

    def __init__(
        self,
        form: Widget,
        obj: DocumentObject,
        guard: UpdateGuard,
        fields: tuple[LengthField, ...],
        on_changed: Callable[[], None],
    ) -> None:
        self._form = form
        self._obj = obj
        self._guard = guard
        self._fields = fields
        self._on_changed = weak_callback(on_changed)
        self._bindings = [bind_length_field(form, obj, field) for field in fields]

    def show(self) -> None:
        """Valeurs des surcotes de l'objet dans les champs (sous la garde du panneau)."""
        with self._guard:
            for field in self._fields:
                value = getattr(self._obj, field.prop).Value
                getattr(self._form, field.widget).setProperty("rawValue", value)

    def fold(self, shown: bool) -> None:
        """Zone « Surcotes de débit » repliée ou dépliée."""
        arrow = QtCore.Qt.ArrowType.DownArrow if shown else QtCore.Qt.ArrowType.RightArrow
        self._form.allowancesBox.setVisible(shown)
        self._form.allowancesToggle.setArrowType(arrow)

    def connect_signals(self) -> None:
        """Saisies des surcotes et bouton qui plie ou déplie la zone."""
        connect(self._form.allowancesToggle, "toggled(bool)", self.fold)
        for field in self._fields:
            slot = partial(self._on_edited, field.prop)
            connect(getattr(self._form, field.widget), "valueChanged(double)", slot)

    def _on_edited(self, prop: str, value: float) -> None:
        if self._guard.active or has_expression(self._obj, prop):
            return
        if getattr(self._obj, prop).Value != value:
            setattr(self._obj, prop, value)
            self._on_changed()


def setup_rotation_buttons(form: Widget, obj: DocumentObject) -> None:
    """Icônes et infobulle des boutons X, Y, Z ; inactifs si une expression pilote la position
    de la pièce (V6)."""
    for widget, _turn, icon in ROTATIONS:
        getattr(form, widget).setIcon(QtGui.QIcon(icon_path(icon)))
    if placement_expression(obj) is None:
        return
    furniture = getattr(obj, "Furniture", None)
    if is_furniture(furniture):
        reason = translated(_FOLLOWS_FURNITURE, quoted_label(furniture))
    else:
        reason = translated(_DRIVEN_PLACEMENT)
    for widget, _turn, _icon in ROTATIONS:
        button = getattr(form, widget)
        button.setEnabled(False)
        button.setToolTip(reason)


def connect_rotations(form: Widget, on_turn: Callable[[Turn], None]) -> None:
    """Les boutons X, Y, Z appellent ``on_turn`` avec l'axe de leur quart de tour."""
    for widget, turn, _icon in ROTATIONS:
        connect(getattr(form, widget), "clicked()", partial(on_turn, turn))
