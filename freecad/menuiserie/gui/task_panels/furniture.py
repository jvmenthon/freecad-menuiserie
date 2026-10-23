# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche de l'ensemble (J4c, critères P3 à P5), ouvert au double-clic.

Trois cotes ; liste des membres (position, ce qu'ils font quand une cote change) ; pour le
membre choisi, son mode et six lignes « distance au bord » avec une case « fixe » ; bouton
« Relier les pièces ». Chaque saisie passe par ``features`` (mêmes règles que l'api), est
écrite aussitôt dans la transaction du panneau puis prévisualisée : « OK » donne une seule
entrée « Modifier l'ensemble », « Annuler » rétablit tout.

Une cote refusée par ``check_resize`` n'est pas écrite (le panneau refuse d'avance, Q4) : le
refus s'affiche sous les cotes et « OK » reste inactif jusqu'à une cote acceptée. Les
avertissements (formule de l'utilisateur, pas d'équerre, épaisseur gardée, pièce qui dépasse)
s'affichent dans le panneau et dans la vue rapport. Transactions, fermeture et surveillance du
document : :mod:`base`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.furniture import Edge, InteriorMode, Notice
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import furniture_edges, furniture_members
from freecad.menuiserie.features.freecad_types import DocumentObject, expression_of
from freecad.menuiserie.features.furniture_bindings import notice_messages, report
from freecad.menuiserie.features.furniture_view import MemberView, member_views, shown_object
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    EDIT_TITLE,
    ObjectTaskPanel,
    UpdateGuard,
    Widget,
    connect,
)
from freecad.menuiserie.gui.task_panels.furniture_widgets import (
    MODE_LABELS,
    EdgeRow,
    dimension_fields,
    fill_tree,
    members_tree,
    message_label,
    show_message,
)
from freecad.menuiserie.gui.view_providers.furniture import ICON

FORM_NAME: Final = "FurnitureTaskPanel"
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier l'ensemble")
_MEMBER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce choisie : « {label} »")
_NO_MEMBER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Choisissez une pièce dans la liste.")
_POSITION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Position")
_REBIND: Final = QT_TRANSLATE_NOOP("Menuiserie", "Relier les pièces")
_REBIND_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Recalcule les expressions qui relient les pièces aux cotes de l'ensemble d'après leur "
    "position actuelle (après une retouche à la main) ; les options « fixe » sont gardées.",
)
_HINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pour déplacer, tourner ou dupliquer le meuble, rangez l'ensemble et ses pièces dans un "
    "Std Part, puis utilisez App::Link.",
)
_USER_ROLE: Final = QtCore.Qt.ItemDataRole.UserRole


class FurnitureTaskPanel(ObjectTaskPanel):
    """Panneau de tâche d'un ensemble, ouvert en modification seulement (aucun panneau à la
    création)."""

    def __init__(self, obj: DocumentObject) -> None:
        super().__init__(obj, creating=False)
        self._guard = UpdateGuard()
        self._refusal = ""
        self._resize_notices: tuple[str, ...] = ()
        self._views: dict[str, MemberView] = {}
        self._current: str | None = None
        self._buttons: Widget = None
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(EDIT_TITLE, {"label": quoted_value(obj.Label)}))
        layout = QtGui.QVBoxLayout(self.form)
        grid = QtGui.QGridLayout()
        self._dimensions = dimension_fields(grid)
        layout.addLayout(grid)
        self._refusal_label = message_label("refusalLabel", error=True)
        layout.addWidget(self._refusal_label)
        self._tree = members_tree()
        layout.addWidget(self._tree)
        self._rows = self._add_member_editor(layout)
        self._add_buttons_and_messages(layout)
        for name, field in self._dimensions.items():
            connect(field, "valueChanged(double)", partial(self._dimension_edited, name))
        connect(self._tree, "itemSelectionChanged()", self._member_chosen)
        self._refresh()

    # --- Construction ---------------------------------------------------------------------

    def _add_member_editor(self, layout: Widget) -> list[EdgeRow]:
        """Pièce choisie : son mode et ses six lignes « distance au bord »."""
        self._member_label = message_label("memberLabel")
        layout.addWidget(self._member_label)
        grid = QtGui.QGridLayout()
        grid.addWidget(QtGui.QLabel(translated(_POSITION)), 0, 0)
        self._mode = QtGui.QComboBox()
        self._mode.setObjectName("modeCombo")
        for mode in InteriorMode:
            self._mode.addItem(translated(MODE_LABELS[mode.value]), mode.value)
        grid.addWidget(self._mode, 0, 1, 1, 2)
        rows = [EdgeRow(edge, self._distance_edited) for edge in Edge]
        for index, row in enumerate(rows, start=1):
            for column, widget in enumerate((row.label, row.distance, row.fixed)):
                grid.addWidget(widget, index, column)
            connect(row.fixed, "toggled(bool)", partial(self._fixed_toggled, row))
        layout.addLayout(grid)
        self._edit_error = message_label("editErrorLabel", error=True)
        layout.addWidget(self._edit_error)
        connect(self._mode, "currentIndexChanged(int)", self._mode_chosen)
        return rows

    def _add_buttons_and_messages(self, layout: Widget) -> None:
        button = QtGui.QPushButton(translated(_REBIND))
        button.setObjectName("rebindButton")
        button.setToolTip(translated(_REBIND_TIP))
        connect(button, "clicked()", self._rebind)
        layout.addWidget(button)
        self._notices = message_label("noticesLabel")
        layout.addWidget(self._notices)
        hint = message_label("hintLabel", hint=True)
        hint.setText(translated(_HINT))
        layout.addWidget(hint)

    # --- « OK » ---------------------------------------------------------------------------

    def modifyStandardButtons(self, box: Widget) -> None:
        """Boutons du panneau, passés par FreeCAD à l'affichage : gardés (l'enveloppe Python
        de la boîte doit vivre pour que celle de « OK » reste valide) pour rendre « OK »
        inactif pendant un refus (P4)."""
        self._buttons = box
        self._enable_ok()

    def _enable_ok(self) -> None:
        """« OK » actif sauf pendant un refus (boîte détruite par FreeCAD : oubliée)."""
        try:
            button = self._buttons.button(QtGui.QDialogButtonBox.Ok) if self._buttons else None
            if button is not None:
                button.setEnabled(not self._refusal)
        except RuntimeError:
            self._buttons = None

    def accept(self) -> bool:
        """« OK » : refusé tant qu'une cote saisie est refusée (le bouton est alors inactif)."""
        if self._refusal:
            return False
        return super().accept()

    # --- Saisies --------------------------------------------------------------------------

    def _dimension_edited(self, _name: str, *_value: object) -> None:
        """Cotes saisies : contrôlées (``check_resize``) puis écrites, ou refusées sans rien
        écrire ; une cote pilotée par une expression n'est jamais écrite (P5)."""
        if self._guard.active:
            return
        sizes: dict[str, float | None] = {}
        for name, field in self._dimensions.items():
            value = round(float(field.property("rawValue")), 6)
            current = getattr(self.obj, name).Value
            free = expression_of(self.obj, name) is None
            sizes[name] = value if free and abs(value - current) > 1e-9 else None
        if not any(value is not None for value in sizes.values()):
            self._refusal = ""
            self._refresh()
            return
        try:
            notices = furniture_members.resize(self.obj, sizes)
        except ValueError as error:
            self._refusal = str(error)
            self._refresh()
            return
        self._refusal = ""
        self._applied(notices, resizing=True)

    def _member_chosen(self) -> None:
        if self._guard.active:
            return
        items = self._tree.selectedItems()
        self._current = str(items[0].data(0, _USER_ROLE)) if items else None
        show_message(self._edit_error, "")  # un refus sur la pièce précédente ne la suit pas
        self._show_member()

    def _mode_chosen(self, index: int) -> None:
        member = self._member()
        if member is not None and not self._guard.active:
            mode = str(self._mode.itemData(index))
            self._edit(lambda: furniture_members.set_options(member, mode, None))

    def _fixed_toggled(self, row: EdgeRow, checked: bool) -> None:
        member = self._member()
        if member is not None and not (self._guard.active or row.updating):
            options = {row.edge.value: bool(checked)}
            self._edit(lambda: furniture_members.set_options(member, None, options))

    def _distance_edited(self, edge: Edge, value: float) -> None:
        member = self._member()
        if member is not None and not self._guard.active:
            self._edit(lambda: furniture_edges.set_edge_distance(member, edge.value, value))

    def _rebind(self) -> None:
        self._edit(lambda: furniture_members.relink(self.obj))

    def _edit(self, action: Callable[[], Sequence[Notice]]) -> None:
        """Action sur un membre ou sur l'ensemble ; un refus s'affiche sous la pièce choisie,
        sans rien écrire."""
        try:
            notices = action()
        except ValueError as error:
            show_message(self._edit_error, str(error))
            self._refresh()
            return
        show_message(self._edit_error, "")
        self._applied(notices)

    def _applied(self, notices: Sequence[Notice], *, resizing: bool = False) -> None:
        """Après une écriture : avertissements dans la vue rapport (ceux d'un
        redimensionnement restent affichés dans le panneau), aperçu, affichage."""
        messages = notice_messages(notices)
        report(messages)
        if resizing:
            self._resize_notices = messages
        self.preview()
        self._refresh()

    def _member(self) -> DocumentObject | None:
        view = self._views.get(self._current or "")
        return view.obj if view is not None else None

    # --- Affichage ------------------------------------------------------------------------

    def _refresh(self) -> None:
        """Cotes, refus, membres, pièce choisie et avertissements."""
        with self._guard:
            for name, field in self._dimensions.items():
                if not self._refusal:
                    field.setProperty("rawValue", getattr(self.obj, name).Value)
                field.setEnabled(expression_of(self.obj, name) is None)
        show_message(self._refusal_label, self._refusal)
        self._enable_ok()
        try:
            views, notices = member_views(self.obj)
        except ValueError as error:
            views, notices = (), (str(error),)
        self._views = {view.obj.Name: view for view in views}
        labels = {name: str(shown_object(view.obj).Label) for name, view in self._views.items()}
        with self._guard:
            fill_tree(self._tree, views, labels)
            self._select_current()
        self._show_member()
        show_message(self._notices, "\n".join(dict.fromkeys([*notices, *self._resize_notices])))

    def _select_current(self) -> None:
        if self._current not in self._views:
            self._current = next(iter(self._views), None)
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            item.setSelected(item.data(0, _USER_ROLE) == self._current)

    def _show_member(self) -> None:
        """Mode et six distances du membre choisi (tout inactif sans membre)."""
        view = self._views.get(self._current or "")
        label = (
            translated(_MEMBER, {"label": quoted_value(shown_object(view.obj).Label)})
            if view is not None
            else translated(_NO_MEMBER)
        )
        self._member_label.setText(label)
        with self._guard:
            self._mode.setCurrentIndex(max(self._mode.findData(view.mode if view else ""), 0))
        self._mode.setEnabled(view is not None)
        for row in self._rows:
            row.show(view)


def start_editing(obj: DocumentObject) -> bool:
    """Ouvre le panneau sur un ensemble (double-clic), dans la transaction « Modifier
    l'ensemble » ; faux si un autre panneau de tâche est déjà ouvert."""
    build = partial(FurnitureTaskPanel, obj)
    return base.start_editing(obj.Document, EDIT_TRANSACTION, build, obj)
