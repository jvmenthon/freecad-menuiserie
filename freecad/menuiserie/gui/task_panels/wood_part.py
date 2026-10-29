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
Trois champs d'angle X, Y, Z (:class:`AngleRows`) donnent la rotation libre de la pièce.
Toute saisie est visible aussitôt dans la vue 3D (cotes, matériau, fil, rotation).
Une cote pilotée par une expression est affichée par le champ (icône d'expression) et n'est
jamais écrite par le panneau. L'épaisseur d'une pièce membre d'un ensemble est contrôlée avant
d'être écrite : refusée par une rangée bloquée (ADR 0019), elle s'accompagne des cases des pièces
verrouillées et du bouton « Déverrouiller et appliquer » (:mod:`unlock_widgets`).
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.features.drag_joints import rotate_checked
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture_bindings import notice_messages, report
from freecad.menuiserie.features.furniture_locks import (
    set_member_thickness,
    unlock_and_set_thickness,
)
from freecad.menuiserie.features.placement import (
    SnapSession,
    snap_part,
)
from freecad.menuiserie.features.wood_part_schema import is_from_newer_version
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.angle_rows import AngleRows
from freecad.menuiserie.gui.task_panels.base import (
    ObjectTaskPanel,
    UpdateGuard,
    connect,
    panel_title,
)
from freecad.menuiserie.gui.task_panels.preview import PreviewStyle
from freecad.menuiserie.gui.task_panels.timber_rows import (
    AllowanceRows,
    LengthField,
    MaterialRows,
    bind_length_field,
    connect_rotations,
    setup_rotation_buttons,
)
from freecad.menuiserie.gui.task_panels.unlock_widgets import UnlockBox
from freecad.menuiserie.gui.task_panels.wood_part_drag import PanelDrag
from freecad.menuiserie.gui.task_panels.wood_part_snap import SnapRows
from freecad.menuiserie.gui.task_panels.wood_part_thickness import ThicknessTools
from freecad.menuiserie.gui.view_providers.wood_part import ICON

UI_FILE: Final = Path(__file__).with_name("wood_part.ui")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier une pièce de bois")
_CREATE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouvelle pièce de bois")

# Champs de cote : les trois cotes finies, puis les trois surcotes (ALLOWANCE_FIELDS).
LENGTH_FIELDS: Final = (
    LengthField("lengthEdit", "Length", MIN_DIMENSION_MM),
    LengthField("widthEdit", "Width", MIN_DIMENSION_MM),
    LengthField("thicknessEdit", "Thickness", MIN_DIMENSION_MM),
    LengthField("lengthAllowanceEdit", "LengthAllowance", 0.0),
    LengthField("widthAllowanceEdit", "WidthAllowance", 0.0),
    LengthField("thicknessAllowanceEdit", "ThicknessAllowance", 0.0),
)
ALLOWANCE_FIELDS: Final = LENGTH_FIELDS[3:]


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
        self._bindings = [bind_length_field(self.form, obj, field) for field in LENGTH_FIELDS[:3]]
        self._unlock = UnlockBox(self.form.unlockHost.layout(), self._unlock_and_apply)
        self._thickness_tools = ThicknessTools(self.form, obj)
        self._angles = AngleRows(
            self.form, obj, self._on_angle_edit, self._recompute, joint_choice.choose
        )
        self._material = MaterialRows(self.form, obj, self._guard, self._on_material, self.preview)
        self._allowances = AllowanceRows(
            self.form, obj, self._guard, ALLOWANCE_FIELDS, self._recompute
        )
        self._material.fill_choices()
        self._material.fill_materials()
        self._show_values()
        self._allowances.fold(False)
        self._material.lock(is_from_newer_version(obj))
        setup_rotation_buttons(self.form, obj)
        self._angles.setup()
        self._connect_signals()
        self._snap = SnapRows(self.form, obj, self._session)
        self._drag = PanelDrag(self)  # flèches et poignées dans la vue 3D (ADR 0021)
        if self._session is not None and self._session.targets:
            self._recompute()

    # --- Affichage et saisies -------------------------------------------------------------

    def _connect_signals(self) -> None:
        connect_rotations(self.form, self._on_rotate)
        self._angles.connect_signals()
        self._material.connect_signals()
        self._allowances.connect_signals()
        for field in LENGTH_FIELDS[:3]:
            slot = partial(self._on_length_changed, field.prop)
            connect(getattr(self.form, field.widget), "valueChanged(double)", slot)

    def _show_values(self) -> None:
        """Valeurs de l'objet dans les champs (après ouverture ou changement de matériau)."""
        self._material.show()
        with self._guard:
            for field in LENGTH_FIELDS[:3]:
                value = getattr(self.obj, field.prop).Value
                getattr(self.form, field.widget).setProperty("rawValue", value)
        self._allowances.show()
        self._angles.show()
        self._thickness_tools.show()

    def _on_material(self) -> None:
        """Nouveau matériau : le fil et les surcotes suivent, aperçu recalculé."""
        self._show_values()
        self._recompute()

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
        tourne sur place en modification (aperçu recalculé) ; les champs d'angle relisent le
        placement."""
        self._angles.finish()  # saisie d'angle en cours : contrôlée avant le quart de tour
        if rotate_checked(self.obj, turn, self._session, joint_choice.choose):
            self._angles.show()
            self.preview()
            self._snap.show()  # notices en direct : la pièce touche ou non ses cibles

    def after_drag(self) -> None:
        """Pièce déplacée ou étirée à la souris : cotes relues par les champs ; l'accrochage de la
        création ne la repose plus (il la ramènerait là où elle a été posée)."""
        self._session = None
        self._angles.drop()  # le glissement prend le relais d'une saisie d'angle en cours
        self._show_values()

    def _on_angle_edit(self) -> None:
        """Angle saisi : comme un glissement, la saisie arrête l'accrochage de la création (la
        pièce n'est plus reposée) ; les boutons de quart de tour le gardent (C5)."""
        self._session = None

    def _before_commit(self) -> None:
        """« OK » : transparence d'origine rétablie, pièce ajoutée à l'ensemble si la case est
        cochée, le tout avant la validation de la transaction. Une saisie d'angle en cours est
        d'abord contrôlée. L'entrée dans l'ensemble passe en premier : son refus (message)
        n'empêche pas de rétablir la transparence."""
        self._angles.finish()
        try:
            self._snap.join_furniture()
        finally:
            if self._style is not None:
                self._style.restore()

    def _release_display(self) -> None:
        """Panneau fermé : plus d'aperçu d'angle différé."""
        self._angles.drop()

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
