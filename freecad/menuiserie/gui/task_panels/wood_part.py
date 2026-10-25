# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche de la pièce de bois : création (commande) et modification (double-clic).

Chaque modification est écrite aussitôt dans l'objet, puis l'objet est recalculé (aperçu en
direct). « OK » valide la transaction ouverte par la commande ou par :func:`start_editing`,
« Annuler » l'abandonne : la pièce créée disparaît, la pièce modifiée retrouve ses valeurs.
En création, la pièce est un aperçu semi-transparent (:class:`PreviewStyle`), rétabli à « OK ».
Les boutons X, Y, Z font tourner la pièce d'un quart de tour autour de l'axe du document : en
création elle reste accrochée (:class:`SnapSession`), en modification elle tourne sur place.
Lancée avec une sélection (J6d), la pièce est posée contre les éléments choisis : le groupe
« Rotation » les cite (« Contre : … »), signale ceux qui sont ignorés ou qui ne touchent pas la
pièce, et propose d'ajouter la pièce à l'ensemble de l'élément (case cochée par défaut).
Toute saisie est visible aussitôt dans la vue 3D (cotes, matériau, fil, rotation).
Une cote pilotée par une expression est affichée par le champ (icône d'expression) et n'est
jamais écrite par le panneau. L'épaisseur d'une pièce membre d'un ensemble est contrôlée avant
d'être écrite : refusée par une rangée bloquée (ADR 0019), elle s'accompagne des cases des pièces
verrouillées et du bouton « Déverrouiller et appliquer » (:mod:`unlock_widgets`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.core.part_model import (
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    GrainDirection,
)
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    has_expression,
    placement_expression,
)
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import notice_messages, report
from freecad.menuiserie.features.furniture_locks import (
    set_member_thickness,
    unlock_and_set_thickness,
)
from freecad.menuiserie.features.furniture_members import quoted_label
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.placement import (
    SnapSession,
    rotate_part,
    snap_part,
)
from freecad.menuiserie.features.wood_part import set_material, shows_grain
from freecad.menuiserie.features.wood_part_schema import is_from_newer_version
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    ObjectTaskPanel,
    UpdateGuard,
    connect,
    panel_title,
)
from freecad.menuiserie.gui.task_panels.preview import PreviewStyle
from freecad.menuiserie.gui.task_panels.unlock_widgets import UnlockBox
from freecad.menuiserie.gui.task_panels.wood_part_snap import SnapRows
from freecad.menuiserie.gui.task_panels.wood_part_thickness import ThicknessTools
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
        self._unlock = UnlockBox(self.form.unlockHost.layout(), self._unlock_and_apply)
        self._thickness_tools = ThicknessTools(self.form, obj)
        self._fill_fixed_choices()
        self._fill_materials()
        self._show_values()
        self._show_allowances(False)
        self._lock_driven_fields()
        self._lock_newer_version()
        self._setup_rotation_buttons()
        self._connect_signals()
        self._snap = SnapRows(self.form, obj, self._session)
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

    def _lock_newer_version(self) -> None:
        """Pièce d'un document plus récent : matériau en lecture seule (listes du type et du
        matériau inactives) et message dans le formulaire."""
        if not is_from_newer_version(self.obj):
            return
        for widget in ("kindCombo", "materialCombo"):
            getattr(self.form, widget).setEnabled(False)
        self.form.newerVersionNotice.setVisible(True)

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
        self._thickness_tools.show()

    def _show_grain_row(self, shown: bool) -> None:
        """Ligne « Sens du fil » masquée pour un matériau sans fil."""
        self.form.grainLabel.setVisible(shown)
        self.form.grainCombo.setVisible(shown)

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
            self.preview()  # la texture tourne aussitôt

    def modifyStandardButtons(self, box: Any) -> None:
        """Boutons du panneau, passés par FreeCAD à l'affichage : « OK » est inactif pendant le
        refus d'une épaisseur."""
        self._unlock.attach_buttons(box)

    def accept(self) -> bool:
        """« OK » : refusé tant qu'une épaisseur saisie est refusée (le bouton est inactif)."""
        if self._unlock.refused:
            return False
        return super().accept()

    def _on_length_changed(self, prop: str, value: float) -> None:
        if self._guard.active or has_expression(self.obj, prop):
            return
        if prop == "Thickness":
            self._on_thickness_changed(value)
        elif getattr(self.obj, prop).Value != value:
            setattr(self.obj, prop, value)
            self._recompute()

    def _on_thickness_changed(self, value: float) -> None:
        """Épaisseur saisie : contrôlée puis écrite pour une pièce membre d'un ensemble (sous
        ``writing``, les avertissements sont rapportés ici et non par ``onChanged``) ; refusée,
        elle n'est pas écrite et le refus s'affiche (G3)."""
        if self.obj.Thickness.Value == value:
            self._unlock.clear()  # retour à l'épaisseur écrite : plus de refus
            return
        try:
            notices = set_member_thickness(self.obj, value)
        except ValueError as error:
            self._unlock.refuse(error)
            return
        self._thickness_written(notices)

    def _unlock_and_apply(self, pieces: Sequence[DocumentObject]) -> None:
        """« Déverrouiller et appliquer » : pièces cochées déverrouillées, ensemble relié et
        épaisseur saisie écrite, dans la transaction du panneau ; encore refusée, le refus et
        les cases sont mis à jour."""
        value = round(float(self.form.thicknessEdit.property("rawValue")), 6)
        try:
            notices = unlock_and_set_thickness(self.obj, value, pieces)
        except ValueError as error:
            self._unlock.refuse(error)
            return
        self._thickness_written(notices)

    def _thickness_written(self, notices: Sequence[Notice]) -> None:
        """Épaisseur écrite : avertissements dans la vue rapport, aperçu."""
        self._unlock.clear()
        report(notice_messages(notices))
        self._recompute()

    def _on_rotate(self, turn: Turn) -> None:
        """Quart de tour autour de l'axe du bouton : la pièce reste accrochée en création,
        tourne sur place en modification (aperçu recalculé)."""
        if rotate_part(self.obj, turn, self._session):
            self.preview()
            self._snap.show()  # notices en direct : la pièce touche ou non ses cibles

    def _before_commit(self) -> None:
        """« OK » : transparence d'origine rétablie, pièce ajoutée à l'ensemble si la case est
        cochée, le tout avant la validation de la transaction. L'entrée dans l'ensemble passe en
        premier : son refus (message) n'empêche pas de rétablir la transparence."""
        try:
            self._snap.join_furniture()
        finally:
            if self._style is not None:
                self._style.restore()

    def _recompute(self) -> None:
        """Pièce reposée en création, aperçu (la pièce, ses assemblages et sa pièce usinée),
        puis outils d'épaisseur."""
        if self._session is not None and snap_part(self.obj, self._session):
            self._show_values()  # cote étirée par l'accrochage
        self.preview()
        self._snap.show()
        self._thickness_tools.show()


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
