# SPDX-License-Identifier: LGPL-2.1-or-later
"""Widgets du panneau de l'ensemble (J4c, critère P3) : cotes, liste des membres, six lignes
« distance au bord » du membre choisi, libellés de message.

Les widgets ne touchent jamais le document : chaque saisie est remise au panneau
(:mod:`freecad.menuiserie.gui.task_panels.furniture`), qui l'écrit puis rafraîchit
l'affichage. Les noms d'objets Qt (``Width``, ``distanceLeft``, ``fixedLeft``…) servent aux
vérifications d'interface.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.furniture import Edge, Follow, InteriorMode
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.features.furniture import DIMENSIONS
from freecad.menuiserie.features.furniture_view import MemberView
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import UpdateGuard, Widget, connect

DIMENSION_LABELS: Final = {
    "Width": QT_TRANSLATE_NOOP("Menuiserie", "Largeur"),
    "Depth": QT_TRANSLATE_NOOP("Menuiserie", "Profondeur"),
    "Height": QT_TRANSLATE_NOOP("Menuiserie", "Hauteur"),
}
MODE_LABELS: Final = {
    InteriorMode.STAY.value: QT_TRANSLATE_NOOP("Menuiserie", "Reste en place"),
    InteriorMode.PROPORTIONAL.value: QT_TRANSLATE_NOOP("Menuiserie", "Proportion"),
}
FOLLOW_LABELS: Final = {
    Follow.NOT_SQUARE: QT_TRANSLATE_NOOP("Menuiserie", "pas d'équerre"),
    Follow.FORMULA: QT_TRANSLATE_NOOP("Menuiserie", "formule"),
    Follow.STRETCHED: QT_TRANSLATE_NOOP("Menuiserie", "étirée"),
    Follow.MOVED: QT_TRANSLATE_NOOP("Menuiserie", "déplacée"),
    Follow.PROPORTION: QT_TRANSLATE_NOOP("Menuiserie", "proportion"),
    Follow.STAYS: QT_TRANSLATE_NOOP("Menuiserie", "fixe"),
    Follow.LOCKED: QT_TRANSLATE_NOOP("Menuiserie", "cotes fixes"),
}
EDGE_LABELS: Final = {
    Edge.LEFT: QT_TRANSLATE_NOOP("Menuiserie", "Gauche"),
    Edge.RIGHT: QT_TRANSLATE_NOOP("Menuiserie", "Droite"),
    Edge.FRONT: QT_TRANSLATE_NOOP("Menuiserie", "Avant"),
    Edge.BACK: QT_TRANSLATE_NOOP("Menuiserie", "Arrière"),
    Edge.BOTTOM: QT_TRANSLATE_NOOP("Menuiserie", "Bas"),
    Edge.TOP: QT_TRANSLATE_NOOP("Menuiserie", "Haut"),
}
COLUMNS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Pièce"),
    QT_TRANSLATE_NOOP("Menuiserie", "Position"),
    QT_TRANSLATE_NOOP("Menuiserie", "Suit"),
)
_LOCKED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Cotes fixes")
_LOCKED_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cotes fixes : la pièce ne change pas de cotes quand l'ensemble change. Si aucune pièce "
    "d'une rangée ne peut s'adapter, la cote de l'ensemble est refusée.",
)
_DRAWN_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cotes dessinées : les cotes d'une pièce en bois viennent de son dessin, elles sont "
    "toujours fixes et ne s'étirent jamais. L'ensemble déplace la pièce ; pour changer ses "
    "cotes, modifiez le dessin.",
)
_FIXED: Final = QT_TRANSLATE_NOOP("Menuiserie", "fixe")
_FIXED_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance fixe : la pièce garde cette distance et suit ce bord quand la cote de "
    "l'ensemble change. Décochée : la pièce reste en place, ou garde sa proportion.",
)
_DISTANCE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance entre la face de la pièce et ce bord de l'ensemble. La modifier déplace la "
    "pièce, ou change sa cote si la distance opposée est fixe ; la case « fixe » ne change "
    "pas.",
)
_DRIVEN_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Formule de l'utilisateur : cette distance suit une expression ou une contrainte, "
    "l'atelier ne la modifie pas.",
)
_ERROR_STYLE: Final = "color: #c0392b;"
_HINT_STYLE: Final = "color: #6b6b6b;"


def quantity_field(name: str, minimum: float) -> Widget:
    """Champ d'unité de FreeCAD, en mm, de ``minimum`` à 20 000 mm."""
    field = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    field.setObjectName(name)
    field.setProperty("unit", "mm")
    field.setProperty("minimum", minimum)
    field.setProperty("maximum", MAX_DIMENSION_MM)
    field.setKeyboardTracking(False)
    return field


def locked_check() -> Widget:
    """Case « Cotes fixes » du membre choisi (ADR 0019)."""
    check = QtGui.QCheckBox(translated(_LOCKED))
    check.setObjectName("lockedCheck")
    check.setToolTip(translated(_LOCKED_TIP))
    return check


def show_locked(check: Widget, view: MemberView | None) -> None:
    """Case « Cotes fixes » du membre ``view`` : grisée, avec l'infobulle qui dit pourquoi, pour
    une pièce en bois (cotes dessinées, F2) ; inactive sans membre."""
    drawn = view is not None and view.drawn
    check.setEnabled(view is not None and not drawn)
    check.setToolTip(translated(_DRAWN_TIP if drawn else _LOCKED_TIP))


def message_label(name: str, *, error: bool = False, hint: bool = False) -> Widget:
    """Libellé de texte brut à la ligne (rouge pour un refus, gris pour une aide)."""
    label = QtGui.QLabel()
    label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    if error or hint:
        label.setStyleSheet(_ERROR_STYLE if error else _HINT_STYLE)
    return label


def show_message(label: Widget, text: str) -> None:
    """Texte du libellé, masqué s'il est vide."""
    label.setText(text)
    label.setVisible(bool(text))


def dimension_fields(grid: Widget) -> dict[str, Widget]:
    """Trois champs de cotes (``Width``, ``Depth``, ``Height``), une ligne chacun."""
    fields = {}
    for row, name in enumerate(DIMENSIONS):
        grid.addWidget(QtGui.QLabel(translated(DIMENSION_LABELS[name])), row, 0)
        fields[name] = quantity_field(name, MIN_DIMENSION_MM)
        grid.addWidget(fields[name], row, 1)
    return fields


def members_tree() -> Widget:
    """Liste des membres : pièce, position (mode), ce qu'elle fait quand une cote change."""
    tree = QtGui.QTreeWidget()
    tree.setObjectName("membersTree")
    tree.setRootIsDecorated(False)
    tree.setColumnCount(len(COLUMNS))
    tree.setHeaderLabels([translated(text) for text in COLUMNS])
    tree.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.SingleSelection)
    return tree


def follow_text(follows: tuple[Follow, ...]) -> str:
    """Colonne « Suit » : mots traduits séparés par des virgules."""
    return ", ".join(translated(FOLLOW_LABELS[follow]) for follow in follows)


def fill_tree(tree: Widget, views: tuple[MemberView, ...], labels: dict[str, str]) -> None:
    """Une ligne par membre ; ``labels`` : libellé affiché par nom de membre."""
    tree.clear()
    for view in views:
        item = QtGui.QTreeWidgetItem(tree)
        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, view.obj.Name)
        mode = MODE_LABELS.get(view.mode)
        texts = (labels[view.obj.Name], translated(mode) if mode else view.mode)
        for column, text in enumerate((*texts, follow_text(view.follows))):
            item.setText(column, text)
    for column in range(len(COLUMNS)):
        tree.resizeColumnToContents(column)


class EdgeRow:
    """Ligne « distance au bord » : libellé, distance (mm) et case « fixe »."""

    def __init__(self, edge: Edge, on_distance: Callable[[Edge, float], None]) -> None:
        self.edge = edge
        self._guard = UpdateGuard()
        self._on_distance = on_distance
        self.label = QtGui.QLabel(translated(EDGE_LABELS[edge]))
        self.distance = quantity_field(f"distance{edge.value}", -MAX_DIMENSION_MM)
        self.fixed = QtGui.QCheckBox(translated(_FIXED))
        self.fixed.setObjectName(f"fixed{edge.value}")
        connect(self.distance, "valueChanged(double)", self._distance_edited)

    @property
    def updating(self) -> bool:
        """Vrai pendant une mise à jour des widgets par le panneau."""
        return self._guard.active

    def show(self, view: MemberView | None) -> None:
        """Distance et option du membre ; champ et case inactifs sans membre, pour un membre
        qui n'est pas d'équerre ou pour une face pilotée par une formule (P5)."""
        distance = view.distances.get(self.edge) if view is not None else None
        driven = view is None or distance is None or self.edge in view.driven
        with self._guard:
            self.distance.setProperty("rawValue", round(distance or 0.0, 6))
            self.fixed.setChecked(view is not None and self.edge in view.fixed)
        formula = view is not None and distance is not None and self.edge in view.driven
        for widget, tip in ((self.distance, _DISTANCE_TIP), (self.fixed, _FIXED_TIP)):
            widget.setEnabled(not driven)
            widget.setToolTip(translated(_DRIVEN_TIP if formula else tip))

    def _distance_edited(self, value: float) -> None:
        if not self._guard.active:
            self._on_distance(self.edge, float(value))
