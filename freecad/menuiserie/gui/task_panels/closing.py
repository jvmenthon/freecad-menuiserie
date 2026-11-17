# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche « Fermer le caisson » (ADR 0064, maquette B de la spécification).

Le panneau règle la fermeture d'un caisson autour de la pièce sélectionnée (l'ancre) et montre
aussitôt le résultat dans la vue 3D : chaque saisie abandonne la transaction « Fermer le
caisson », la rouvre et recrée les pièces par :func:`freecad.menuiserie.api.make_closed_carcass`
(comme le panneau « Caisson »). « OK » la valide (une seule entrée d'annulation), « Annuler »
l'abandonne : le document redevient identique, ancre comprise. Le schéma isométrique
(:mod:`.closing_schema`) active ou désactive chaque élément d'un clic ; un assemblage impossible
avec les cotes saisies est grisé, sa raison en infobulle.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from functools import partial
from typing import Any, Final

import FreeCAD as App
from PySide import QtCore, QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.templates.closing import (
    back_availability,
    closing_layout,
    joinery_availability,
)
from freecad.menuiserie.core.templates.closing_params import (
    BackJoinery,
    ClosingJoinery,
    ClosingParams,
    ClosingRole,
    Element,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import templated_message, translated, translated_errors
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    TransactionTaskPanel,
    close_transaction,
    connect,
)
from freecad.menuiserie.gui.task_panels.closing_schema import COLORS, NAMES, ClosingSchema
from freecad.menuiserie.gui.task_panels.form_fields import (
    build_preview,
    clear_selection_later,
    combo,
    length_field,
    material_box,
)

FORM_NAME: Final = "ClosingTaskPanel"
ICON: Final = "Menuiserie_CloseCarcass.svg"
CLOSE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fermer le caisson")
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fermer le caisson")
_BANNER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Pièce sélectionnée : {label} · {length} x {width} x {thickness} mm · {material}"
)
_ROLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Cette pièce est")
_ROLES: Final = {
    ClosingRole.BOTTOM: QT_TRANSLATE_NOOP("Menuiserie", "le dessous"),
    ClosingRole.TOP: QT_TRANSLATE_NOOP("Menuiserie", "le dessus"),
}
_HEIGHT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Hauteur hors tout")
_JOINERY: Final = QT_TRANSLATE_NOOP("Menuiserie", "① Assemblage des côtés")
_JOINERIES: Final = {
    ClosingJoinery.NONE: QT_TRANSLATE_NOOP("Menuiserie", "Aucun (aboutés, vissés ou collés)"),
    ClosingJoinery.DOWELS: QT_TRANSLATE_NOOP("Menuiserie", "Tourillons"),
    ClosingJoinery.DOVETAIL: QT_TRANSLATE_NOOP("Menuiserie", "Queues d'aronde"),
    ClosingJoinery.MITER: QT_TRANSLATE_NOOP("Menuiserie", "Onglet"),
    ClosingJoinery.RABBET: QT_TRANSLATE_NOOP("Menuiserie", "Feuillure"),
}
_BACK: Final = QT_TRANSLATE_NOOP("Menuiserie", "② Fond")
_BACKS: Final = {
    BackJoinery.RABBET: QT_TRANSLATE_NOOP("Menuiserie", "Feuillure"),
    BackJoinery.GROOVE: QT_TRANSLATE_NOOP("Menuiserie", "Rainure"),
    BackJoinery.NONE: QT_TRANSLATE_NOOP("Menuiserie", "Aucun (vissé derrière)"),
}
_THICK_BACK: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fond épais entre les côtés")
_FIELDS: Final = {  # champ de ClosingParams → (nom du widget, libellé)
    "thickness": ("thickness", QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur des côtés")),
    "opposite_thickness": (
        "oppositeThickness",
        QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur de la pièce opposée"),
    ),
    "back_thickness": ("backThickness", QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur du fond")),
}
_MATERIALS: Final = {
    "material_id": ("material", QT_TRANSLATE_NOOP("Menuiserie", "Matériau des côtés")),
    "opposite_material_id": (
        "oppositeMaterial",
        QT_TRANSLATE_NOOP("Menuiserie", "Matériau de la pièce opposée"),
    ),
    "back_material_id": ("backMaterial", QT_TRANSLATE_NOOP("Menuiserie", "Matériau du fond")),
}
_FRONT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Avant du caisson")
_TURN_FRONT: Final = QT_TRANSLATE_NOOP("Menuiserie", "⟳ Tourner l'avant")
_LEGEND_ANCHOR: Final = {
    ClosingRole.BOTTOM: QT_TRANSLATE_NOOP("Menuiserie", "Dessous (sélectionné)"),
    ClosingRole.TOP: QT_TRANSLATE_NOOP("Menuiserie", "Dessus (sélectionné)"),
}
_UNEXPECTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le caisson n'a pas pu être construit avec ces paramètres ({reason}). Modifiez une cote ou "
    "un choix.",
)
_UNAVAILABLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Impossible avec ces cotes : {reason}")
_ERROR_STYLE: Final = "color: #c0392b;"
_PREFERRED: Final = (ClosingJoinery.DOWELS, ClosingJoinery.NONE)


def _set_availability(box: Any, reasons: dict[Any, TemplatedError | None]) -> None:
    """Choix de ``box`` impossibles grisés, raison en infobulle (le choix courant est gardé)."""
    model = box.model()
    for index in range(box.count()):
        reason = reasons.get(box.itemData(index))
        model.item(index).setEnabled(reason is None)
        tip = "" if reason is None else translated(_UNAVAILABLE, {"reason": _reason(reason)})
        box.setItemData(index, tip, QtCore.Qt.ItemDataRole.ToolTipRole)


def _reason(error: TemplatedError) -> str:
    return templated_message(error)


class ClosingTaskPanel(TransactionTaskPanel):
    """Paramètres de la fermeture et aperçu, dans la transaction ouverte par la commande ;
    transaction, fermeture et surveillance du document : :mod:`base`."""

    def __init__(
        self, doc: Document, anchor: DocumentObject, role: ClosingRole, front_turns: int
    ) -> None:
        super().__init__(doc, creating=True)
        self.anchor = anchor
        self.furniture: DocumentObject | None = None
        self._front = front_turns
        self._ready = False  # aperçu seulement une fois tous les champs construits
        defaults = api.closing_params(anchor, joinery=ClosingJoinery.NONE)
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(_TITLE))
        layout = QtGui.QFormLayout(self.form)
        layout.addRow(self._banner(defaults))
        self._roles = self._role_buttons(layout, role)
        self._height = length_field(layout, "height", _HEIGHT, defaults.height, self.rebuild)
        self._schema = ClosingSchema(self._toggle)
        layout.addRow(self._schema)
        self._boxes = self._legend(layout, defaults)
        self._joinery = self._joinery_box(layout, defaults)
        self._back = combo(
            layout, "backJoinery", _BACK, {k.value: translated(v) for k, v in _BACKS.items()}
        )
        connect(self._back, "currentIndexChanged(int)", self.rebuild)
        self._thick_back = QtGui.QCheckBox(translated(_THICK_BACK))
        self._thick_back.setObjectName("thickBack")
        connect(self._thick_back, "toggled(bool)", self.rebuild)
        layout.addRow(self._thick_back)
        self._lengths = {
            name: length_field(layout, widget, label, getattr(defaults, name), self.rebuild)
            for name, (widget, label) in _FIELDS.items()
        }
        self._materials = {
            name: material_box(layout, widget, label, getattr(defaults, name), self.rebuild)
            for name, (widget, label) in _MATERIALS.items()
        }
        self._turn = QtGui.QPushButton(translated(_TURN_FRONT))
        self._turn.setObjectName("turnFront")
        connect(self._turn, "clicked()", self._turn_front)
        layout.addRow(translated(_FRONT), self._turn)
        self._error = QtGui.QLabel()
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)
        self._error.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._error.setStyleSheet(_ERROR_STYLE)
        layout.addRow(self._error)
        self._ready = True
        self._choose_default_joinery()
        self.rebuild()

    # --- Construction du formulaire -------------------------------------------------------

    def _banner(self, defaults: ClosingParams) -> Any:
        """Bandeau « Pièce sélectionnée » : libellé, cotes et matériau de l'ancre."""
        size = defaults.anchor
        material = get_library().get(defaults.anchor_material_id).name(display_language())
        text = translated(
            _BANNER,
            {
                "label": str(self.anchor.Label),
                "length": f"{size.length:g}",
                "width": f"{size.width:g}",
                "thickness": f"{size.thickness:g}",
                "material": material,
            },
        )
        banner = QtGui.QLabel(text)
        banner.setObjectName("anchorBanner")
        banner.setWordWrap(True)
        banner.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        banner.setStyleSheet("background: #e6edf8; border: 1px solid #9db4d8; padding: 4px;")
        return banner

    def _role_buttons(self, layout: Any, role: ClosingRole) -> dict[ClosingRole, Any]:
        """Bascule « Cette pièce est : le dessous / le dessus »."""
        row = QtGui.QHBoxLayout()
        group = QtGui.QButtonGroup(self.form)
        buttons = {}
        for kind, text in _ROLES.items():
            button = QtGui.QRadioButton(translated(text))
            button.setObjectName("roleBottom" if kind is ClosingRole.BOTTOM else "roleTop")
            button.setChecked(kind is role)
            group.addButton(button)
            row.addWidget(button)
            buttons[kind] = button
        connect(buttons[ClosingRole.BOTTOM], "toggled(bool)", self.rebuild)  # une fois par bascule
        layout.addRow(translated(_ROLE), row)
        return buttons

    def _legend(self, layout: Any, defaults: ClosingParams) -> dict[str, Any]:
        """Légende du schéma : une case colorée par élément, cochée s'il est créé."""
        grid = QtGui.QGridLayout()
        anchor = QtGui.QLabel(translated(_LEGEND_ANCHOR[self.role()]))
        anchor.setObjectName("legendAnchor")
        anchor.setStyleSheet(f"color: {COLORS['anchor']}; font-weight: bold;")
        grid.addWidget(anchor, 0, 0)
        boxes = {}
        for index, (key, text) in enumerate(NAMES.items(), start=1):
            box = QtGui.QCheckBox(translated(text))
            box.setObjectName(f"element_{key}")
            box.setChecked(Element(key) in defaults.elements)
            box.setStyleSheet(f"QCheckBox {{ color: {COLORS[key]}; font-weight: bold; }}")
            connect(box, "toggled(bool)", self.rebuild)
            grid.addWidget(box, index // 3, index % 3)
            boxes[key] = box
        layout.addRow(grid)
        return boxes

    def _joinery_box(self, layout: Any, defaults: ClosingParams) -> Any:
        box = combo(
            layout, "joinery", _JOINERY, {k.value: translated(v) for k, v in _JOINERIES.items()}
        )
        box.setCurrentIndex(box.findData(defaults.joinery.value))
        connect(box, "currentIndexChanged(int)", self.rebuild)
        return box

    def _choose_default_joinery(self) -> None:
        """Tourillons par défaut, sinon le premier assemblage possible (ancre mince)."""
        probe = self._probe()
        if probe is None:
            return
        reasons = joinery_availability(probe)
        wanted = next((k for k in _PREFERRED if reasons[k] is None), ClosingJoinery.NONE)
        self._joinery.blockSignals(True)
        try:
            self._joinery.setCurrentIndex(self._joinery.findData(wanted.value))
        finally:
            self._joinery.blockSignals(False)

    # --- Lecture des champs ---------------------------------------------------------------

    def role(self) -> ClosingRole:
        """Rôle choisi : le dessous (le caisson monte) ou le dessus (il descend)."""
        bottom = self._roles[ClosingRole.BOTTOM].isChecked()
        return ClosingRole.BOTTOM if bottom else ClosingRole.TOP

    def values(self) -> dict[str, Any]:
        """Paramètres saisis, par champ de :class:`ClosingParams`."""
        values: dict[str, Any] = {
            "role": self.role(),
            "height": float(self._height.property("rawValue")),
            "front_turns": self._front,
            "elements": frozenset(Element(k) for k, box in self._boxes.items() if box.isChecked()),
            "thick_back": self._thick_back.isChecked(),
            "joinery": ClosingJoinery(str(self._joinery.currentData())),
            "back_joinery": BackJoinery(str(self._back.currentData())),
        }
        for name, field in self._lengths.items():
            values[name] = float(field.property("rawValue"))
        for name, box in self._materials.items():
            values[name] = str(box.itemData(box.currentIndex()))
        return values

    def _probe(self) -> ClosingParams | None:
        """Paramètres saisis sans assemblage (toujours constructibles si les cotes le sont), base
        du calcul des choix impossibles ; ``None`` si les cotes sont refusées."""
        values = {**self.values(), "joinery": ClosingJoinery.NONE, "back_joinery": BackJoinery.NONE}
        try:
            with translated_errors():
                return api.closing_params(self.anchor, **values)
        except (TypeError, ValueError):
            return None

    # --- Aperçu ---------------------------------------------------------------------------

    def _toggle(self, key: str) -> None:
        """Clic dans le schéma : la case de l'élément change, donc l'aperçu."""
        box = self._boxes[key]
        box.setChecked(not box.isChecked())

    def _turn_front(self) -> None:
        self._front = (self._front + 1) % 4
        self.rebuild()

    def _refresh_choices(self) -> None:
        """Schéma et choix d'assemblage mis à jour d'après les cotes saisies."""
        probe = self._probe()
        self._back.setEnabled(not self._thick_back.isChecked())
        if probe is None:
            return
        _set_availability(self._joinery, joinery_availability(probe))
        _set_availability(self._back, back_availability(probe))
        everything = replace(probe, elements=frozenset(Element))
        enabled = {element.value for element in probe.elements}
        self._schema.show_layout(closing_layout(everything), enabled)

    def rebuild(self, *_changed: object) -> None:
        """Caisson précédent abandonné avec sa transaction, puis recréé dans une transaction
        rouverte ; un refus s'affiche sous les champs. Une erreur inattendue (noyau
        géométrique) ou un objet créé en erreur abandonne aussi l'aperçu : rien ne reste."""
        if not self._ready or self.closed:
            return
        self._restart()
        self._refresh_choices()
        self.furniture, message = build_preview(self.doc, self._build, self._restart, _UNEXPECTED)
        self._error.setText(message)
        self._error.setVisible(bool(message))
        base.set_ok_enabled(self.form, self.furniture is not None)

    def _build(self) -> tuple[Any, Sequence[str]]:
        """Caisson d'aperçu autour de l'ancre."""
        params = api.closing_params(self.anchor, **self.values())
        return api.make_closed_carcass(self.anchor, params)

    def _restart(self) -> None:
        """Transaction abandonnée (l'aperçu disparaît, l'ancre est rétablie) puis rouverte."""
        close_transaction(self._transaction, abort=True)
        self.doc.openTransaction(translated(CLOSE_TRANSACTION))
        self._transaction = App.getActiveTransaction()

    # --- Cycle de vie (FreeCAD) -----------------------------------------------------------

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation ; sans caisson
        (paramètres refusés), le panneau reste ouvert."""
        if self.furniture is None:
            return False
        accepted = super().accept()
        clear_selection_later(self.doc.Name)
        return accepted


def show_panel(doc: Document, anchor: DocumentObject, role: ClosingRole, front_turns: int) -> None:
    """Ouvre le panneau dans la transaction de la commande ; une exception l'abandonne."""
    base.show_panel(partial(ClosingTaskPanel, doc, anchor, role, front_turns))
