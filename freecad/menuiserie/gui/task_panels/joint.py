# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche commun aux assemblages (J3e) : création (commande) et modification
(double-clic).

Le formulaire est construit d'après la description des paramètres du type
(:mod:`joint_fields`) : pièces reliées, bouton « Inverser » (échange hôte et invitée), un champ
par paramètre. Chaque saisie est écrite aussitôt dans l'assemblage puis recalculée avec ses
pièces usinées (aperçu) ; une erreur d'assemblage s'affiche dans le panneau sans empêcher
« OK ». Transactions, fermeture et surveillance du document : :mod:`base` (comme J1c).
"""

from __future__ import annotations

from functools import partial
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import (
    COMMON_PROPERTIES,
    JointFeature,
    plan_for,
    resolved_for,
)
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    ObjectTaskPanel,
    Widget,
    connect,
    expression_of,
    panel_title,
)
from freecad.menuiserie.gui.task_panels.joint_fields import ParamField, fields_of, property_tooltip
from freecad.menuiserie.gui.view_providers.joint import joint_icon

FORM_NAME: Final = "JointTaskPanel"
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier un assemblage")
_CREATE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouvel assemblage : {label}")
_HOST: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce hôte : « {label} »")
_GUEST: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce invitée : « {label} »")
_MISSING: Final = QT_TRANSLATE_NOOP("Menuiserie", "(pièce supprimée)")
_INVERT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Inverser")
_INVERT_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Échange les rôles des deux pièces : la pièce hôte devient la pièce invitée et inversement.",
)
_ROLES: Final = ("HostPart", "GuestPart")
_ERROR_STYLE: Final = "color: #c0392b;"


class JointTaskPanel(ObjectTaskPanel):
    """Panneau de tâche d'un assemblage, en création (``creating``) ou en modification."""

    def __init__(self, obj: DocumentObject, *, creating: bool) -> None:
        super().__init__(obj, creating=creating)
        proxy: JointFeature = obj.Proxy
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(joint_icon(proxy))))
        self.form.setWindowTitle(panel_title(quoted_value(obj.Label), creating, _CREATE_TITLE))
        self.fields = fields_of(proxy.PROPERTIES, self._write)
        layout = QtGui.QVBoxLayout(self.form)
        self._parts = self._add_parts(layout)
        layout.addLayout(_grid(self.fields))
        self._error = _error_label()
        layout.addWidget(self._error)
        self._refresh()

    # --- Construction ---------------------------------------------------------------------

    def _add_parts(self, layout: Widget) -> tuple[Widget, Widget]:
        """Pièces reliées (libellés) et bouton « Inverser »."""
        host, guest = QtGui.QLabel(), QtGui.QLabel()
        for label, spec, name in zip(
            (host, guest), COMMON_PROPERTIES[:2], ("hostLabel", "guestLabel"), strict=True
        ):
            label.setObjectName(name)
            label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            label.setToolTip(property_tooltip(spec))
            layout.addWidget(label)
        button = QtGui.QPushButton(translated(_INVERT))
        button.setObjectName("invertButton")
        button.setToolTip(translated(_INVERT_TIP))
        button.setEnabled(not any(expression_of(self.obj, role) for role in _ROLES))
        connect(button, "clicked()", self._invert)
        layout.addWidget(button)
        return host, guest

    # --- Saisies --------------------------------------------------------------------------

    def _write(self, prop: str, value: object) -> None:
        """Saisie d'un champ : écrite (sauf propriété pilotée ou valeur inchangée), aperçu."""
        if expression_of(self.obj, prop) is not None:
            return
        current = getattr(self.obj, prop)
        if getattr(current, "Value", current) != value:
            setattr(self.obj, prop, value)
            self.preview()
        self._refresh()

    def _invert(self) -> None:
        """« Inverser » : la pièce hôte devient l'invitée et inversement."""
        self.obj.HostPart, self.obj.GuestPart = self.obj.GuestPart, self.obj.HostPart
        self.preview()
        self._refresh()

    # --- Affichage ------------------------------------------------------------------------

    def _refresh(self) -> None:
        """Pièces, valeurs (effectives en mode auto) et message d'erreur éventuel."""
        for label, template, part in zip(
            self._parts, (_HOST, _GUEST), (self.obj.HostPart, self.obj.GuestPart), strict=True
        ):
            name = quoted_value(part.Label) if part is not None else translated(_MISSING)
            label.setText(translated(template, {"label": name}))
        resolved = _resolved(self.obj)
        for field in self.fields:
            field.show(self.obj, resolved)
        error = joint_error(self.obj)
        self._error.setText(error or "")
        self._error.setVisible(error is not None)


def joint_error(joint: DocumentObject) -> str | None:
    """Message traduit si l'assemblage est impossible (E3), ``None`` sinon."""
    try:
        plan_for(joint)
    except ValueError as error:
        return str(error)
    return None


def _resolved(joint: DocumentObject) -> object | None:
    """Valeurs effectives de l'assemblage, ``None`` si elles ne peuvent être calculées."""
    try:
        return resolved_for(joint)
    except ValueError:
        return None


def _grid(fields: list[ParamField]) -> Widget:
    """Une ligne par paramètre : libellé, champ, case « Auto »."""
    grid = QtGui.QGridLayout()
    for row, field in enumerate(fields):
        for column, widget in enumerate(field.widgets()):
            if widget is not None:
                grid.addWidget(widget, row, column)
    return grid


def _error_label() -> Widget:
    label = QtGui.QLabel()
    label.setObjectName("errorLabel")
    label.setWordWrap(True)
    label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    label.setStyleSheet(_ERROR_STYLE)
    label.setVisible(False)
    return label


def start_editing(obj: DocumentObject) -> bool:
    """Ouvre le panneau sur un assemblage existant (double-clic), dans la transaction
    « Modifier un assemblage » ; faux si un autre panneau de tâche est déjà ouvert."""
    build = partial(JointTaskPanel, obj, creating=False)
    return base.start_editing(obj.Document, EDIT_TRANSACTION, build, obj)


def show_panel(obj: DocumentObject) -> None:
    """Ouvre le panneau d'un assemblage qui vient d'être créé, dans la transaction de la
    commande (« Annuler » l'abandonne : rien ne reste)."""
    base.show_panel(partial(JointTaskPanel, obj, creating=True))
