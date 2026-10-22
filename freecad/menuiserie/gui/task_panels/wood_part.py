# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche de la pièce de bois : création (commande) et modification (double-clic).

Chaque modification est écrite aussitôt dans l'objet, puis l'objet est recalculé (aperçu en
direct). « OK » valide la transaction ouverte par la commande ou par :func:`start_editing`,
« Annuler » l'abandonne : la pièce créée disparaît, la pièce modifiée retrouve ses valeurs.
En création, la pièce est un aperçu semi-transparent (:class:`PreviewStyle`), rétabli à « OK ».
Les boutons X, Y, Z font tourner la pièce d'un quart de tour autour de l'axe du document : en
création elle reste accrochée (:class:`SnapSession`), en modification elle tourne sur place.
Une cote pilotée par une expression est affichée par le champ (icône d'expression) et n'est
jamais écrite par le panneau.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind
from freecad.menuiserie.core.part_model import (
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    GrainDirection,
    is_nonstandard_panel_thickness,
)
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_members import quoted_label
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.placement import (
    SnapSession,
    placement_expression,
    rotate_part,
    snap_part,
)
from freecad.menuiserie.features.wood_part import set_material, shows_grain
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    ObjectTaskPanel,
    UpdateGuard,
    connect,
    has_expression,
    panel_title,
)
from freecad.menuiserie.gui.task_panels.preview import PreviewStyle
from freecad.menuiserie.gui.view_providers.wood_part import ICON

UI_FILE: Final = Path(__file__).with_name("wood_part.ui")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier une pièce de bois")
_CREATE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouvelle pièce de bois")
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


@dataclass(frozen=True)
class LengthField:
    """Champ de cote du formulaire, lié à une propriété ``App::PropertyLength``."""

    widget: str
    prop: str
    minimum: float


# Champs sans liaison d'expression possible : inactifs si leur propriété est pilotée (C6).
DRIVEN_FIELDS: Final = (
    ("markEdit", "Mark"),
    ("materialCombo", "Material"),
    ("grainCombo", "GrainDirection"),
)
LENGTH_FIELDS: Final = (
    LengthField("lengthEdit", "Length", MIN_DIMENSION_MM),
    LengthField("widthEdit", "Width", MIN_DIMENSION_MM),
    LengthField("thicknessEdit", "Thickness", MIN_DIMENSION_MM),
    LengthField("lengthAllowanceEdit", "LengthAllowance", 0.0),
    LengthField("widthAllowanceEdit", "WidthAllowance", 0.0),
    LengthField("thicknessAllowanceEdit", "ThicknessAllowance", 0.0),
)


class WoodPartTaskPanel(ObjectTaskPanel):
    """Panneau de tâche d'une pièce de bois, en création (``creating``) ou en modification."""

    def __init__(
        self, obj: DocumentObject, *, creating: bool, session: SnapSession | None = None
    ) -> None:
        super().__init__(obj, creating=creating)
        self._guard = UpdateGuard()
        self._session = (session or SnapSession()) if creating else None
        self._style = PreviewStyle(getattr(obj, "ViewObject", None)) if creating else None
        self.form = Gui.PySideUic.loadUi(str(UI_FILE))
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(panel_title(str(obj.Label), creating, _CREATE_TITLE))
        self._bindings = [self._bind(field) for field in LENGTH_FIELDS]
        self._thickness_menu = QtGui.QMenu(self.form.standardThicknessButton)
        self.form.standardThicknessButton.setMenu(self._thickness_menu)
        self._fill_fixed_choices()
        self._fill_materials()
        self._show_values()
        self._show_allowances(False)
        self._lock_driven_fields()
        self._setup_rotation_buttons()
        self._connect_signals()
        if self._session is not None and self._session.targets:
            self._recompute()

    # --- Construction du formulaire -------------------------------------------------------

    def _bind(self, field: LengthField) -> Any:
        """Bornes du champ et liaison à la propriété (affichage et édition des expressions)."""
        widget = getattr(self.form, field.widget)
        widget.setProperty("minimum", field.minimum)
        widget.setProperty("maximum", MAX_DIMENSION_MM)
        binding = Gui.ExpressionBinding(widget)
        binding.bind(self.obj, field.prop)
        binding.setAutoApply(True)
        return binding

    def _fill_fixed_choices(self) -> None:
        for label, _kinds in KIND_FILTERS:
            self.form.kindCombo.addItem(translated(label))
        for grain, label in GRAIN_LABELS:
            self.form.grainCombo.addItem(translated(label), grain.value)

    def _lock_driven_fields(self) -> None:
        """Repère, matériau ou fil pilotés par une expression : champ inactif (C6)."""
        for widget, prop in DRIVEN_FIELDS:
            if has_expression(self.obj, prop):
                getattr(self.form, widget).setEnabled(False)

    def _setup_rotation_buttons(self) -> None:
        """Icônes et infobulle des boutons X, Y, Z ; inactifs si une expression pilote la
        position de la pièce (V6)."""
        for widget, _turn, icon in ROTATIONS:
            getattr(self.form, widget).setIcon(QtGui.QIcon(icon_path(icon)))
        if placement_expression(self.obj) is None:
            return
        furniture = getattr(self.obj, "Furniture", None)
        if is_furniture(furniture):
            reason = translated(_FOLLOWS_FURNITURE, quoted_label(furniture))
        else:
            reason = translated(_DRIVEN_PLACEMENT)
        for widget, _turn, _icon in ROTATIONS:
            button = getattr(self.form, widget)
            button.setEnabled(False)
            button.setToolTip(reason)

    def _connect_signals(self) -> None:
        form = self.form
        for widget, turn, _icon in ROTATIONS:
            connect(getattr(form, widget), "clicked()", partial(self._on_rotate, turn))
        connect(form.markEdit, "textEdited(QString)", self._on_mark_edited)
        connect(form.kindCombo, _INDEX_CHANGED, self._on_kind_chosen)
        connect(form.materialCombo, _INDEX_CHANGED, self._on_material_chosen)
        connect(form.grainCombo, _INDEX_CHANGED, self._on_grain_chosen)
        connect(form.allowancesToggle, "toggled(bool)", self._show_allowances)
        for field in LENGTH_FIELDS:
            slot = partial(self._on_length_changed, field.prop)
            connect(getattr(form, field.widget), "valueChanged(double)", slot)

    # --- Affichage ------------------------------------------------------------------------

    def _fill_materials(self) -> None:
        """Matériaux du type choisi ; hors filtre, le premier de la liste est appliqué."""
        combo = self.form.materialCombo
        kinds = KIND_FILTERS[max(self.form.kindCombo.currentIndex(), 0)][1]
        with self._guard:
            combo.clear()
            for material in get_library().by_kind(*kinds):
                combo.addItem(material.name(display_language()), material.id)
            if not kinds and combo.findData(self.obj.MaterialId) < 0:
                # Matériau inconnu de la bibliothèque locale : son libellé enregistré reste affiché.
                combo.addItem(self.obj.Material, self.obj.MaterialId)
            combo.setCurrentIndex(combo.findData(self.obj.MaterialId))
        if combo.currentIndex() < 0 and combo.count() and not has_expression(self.obj, "Material"):
            combo.setCurrentIndex(0)

    def _show_values(self) -> None:
        """Valeurs de l'objet dans les champs (après ouverture ou changement de matériau)."""
        with self._guard:
            self.form.markEdit.setText(self.obj.Mark)
            grain = self.form.grainCombo.findData(self.obj.GrainDirection)
            self.form.grainCombo.setCurrentIndex(grain)
            self._show_grain_row(shows_grain(self.obj))
            for field in LENGTH_FIELDS:
                value = getattr(self.obj, field.prop).Value
                getattr(self.form, field.widget).setProperty("rawValue", value)
        self._show_thickness_tools()

    def _show_grain_row(self, shown: bool) -> None:
        """Ligne « Sens du fil » masquée pour un matériau sans fil."""
        self.form.grainLabel.setVisible(shown)
        self.form.grainCombo.setVisible(shown)

    def _show_thickness_tools(self) -> None:
        """Menu des épaisseurs standard et avertissement « hors standard » (panneaux)."""
        material = get_library().find(self.obj.MaterialId)
        self._fill_thickness_menu(material)
        button = self.form.standardThicknessButton
        button.setEnabled(material is not None and not has_expression(self.obj, "Thickness"))
        thickness = self.obj.Thickness.Value
        warn = material is not None and is_nonstandard_panel_thickness(material, thickness)
        self.form.thicknessWarning.setVisible(warn)

    def _fill_thickness_menu(self, material: Material | None) -> None:
        self._thickness_menu.clear()
        for thickness in material.thicknesses if material is not None else ():
            action = self._thickness_menu.addAction(_length_text(thickness))
            connect(action, "triggered()", partial(self._choose_thickness, thickness))

    def _show_allowances(self, shown: bool) -> None:
        """Zone « Surcotes de débit » repliée ou dépliée."""
        arrow = QtCore.Qt.ArrowType.DownArrow if shown else QtCore.Qt.ArrowType.RightArrow
        self.form.allowancesBox.setVisible(shown)
        self.form.allowancesToggle.setArrowType(arrow)

    # --- Modifications de l'utilisateur ---------------------------------------------------

    def _on_mark_edited(self, text: str) -> None:
        if not has_expression(self.obj, "Mark"):
            self.obj.Mark = text

    def _on_kind_chosen(self, _index: int) -> None:
        self._fill_materials()

    def _on_material_chosen(self, index: int) -> None:
        if self._guard.active or index < 0 or has_expression(self.obj, "Material"):
            return
        material_id = self.form.materialCombo.itemData(index)
        if material_id == self.obj.MaterialId or get_library().find(material_id) is None:
            return
        set_material(self.obj, material_id)
        self._show_values()  # le fil et les surcotes suivent le matériau
        self._recompute()

    def _on_grain_chosen(self, index: int) -> None:
        if not self._guard.active and index >= 0 and not has_expression(self.obj, "GrainDirection"):
            self.obj.GrainDirection = self.form.grainCombo.itemData(index)

    def _on_length_changed(self, prop: str, value: float) -> None:
        if self._guard.active or has_expression(self.obj, prop):
            return
        if getattr(self.obj, prop).Value != value:
            setattr(self.obj, prop, value)
            self._recompute()

    def _on_rotate(self, turn: Turn) -> None:
        """Quart de tour autour de l'axe du bouton : la pièce reste accrochée en création,
        tourne sur place en modification (aperçu recalculé)."""
        if rotate_part(self.obj, turn, self._session):
            self.preview()

    def _choose_thickness(self, thickness: float) -> None:
        """Épaisseur standard choisie dans le menu : écrite par le champ lui-même."""
        self.form.thicknessEdit.setProperty("rawValue", thickness)

    def _before_commit(self) -> None:
        """« OK » : transparence d'origine rétablie avant la validation de la transaction."""
        if self._style is not None:
            self._style.restore()

    def _recompute(self) -> None:
        """Pièce reposée en création, aperçu (la pièce, ses assemblages et sa pièce usinée),
        puis outils d'épaisseur."""
        if self._session is not None and snap_part(self.obj, self._session):
            self._show_values()  # cote étirée par l'accrochage
        self.preview()
        self._show_thickness_tools()


def start_editing(obj: DocumentObject, edited: DocumentObject | None = None) -> bool:
    """Ouvre le panneau sur une pièce existante, dans la transaction « Modifier une pièce de
    bois » ; ``edited`` : objet en mode édition (la pièce usinée de ``obj`` le cas échéant).
    Faux si un autre panneau de tâche est déjà ouvert."""
    build = partial(_build, obj, creating=False)
    return base.start_editing(obj.Document, EDIT_TRANSACTION, build, edited or obj)


def show_panel(obj: DocumentObject, *, creating: bool, session: SnapSession | None = None) -> None:
    """Construit puis affiche le panneau, dans la transaction déjà ouverte (voir
    :func:`base.show_panel`) ; ``session`` : accrochage de la pièce en création."""
    base.show_panel(partial(_build, obj, creating=creating, session=session))


def _build(
    obj: DocumentObject, *, creating: bool, session: SnapSession | None = None
) -> WoodPartTaskPanel:
    """Panneau de ``obj`` (classe lue à l'appel : remplaçable par les vérifications)."""
    return WoodPartTaskPanel(obj, creating=creating, session=session)


def _length_text(length_mm: float) -> str:
    """Longueur dans le système d'unités choisi par l'utilisateur (« 22 mm », « 0,87 in »…)."""
    text: str = App.Units.Quantity(length_mm, App.Units.Length).UserString
    return text
