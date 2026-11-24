# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Plans de pièce » quand rien n'est sélectionné (issue #153, maquette A choisie par jv
le 23/11).

Arbre à cases à cocher : les ensembles (sous-ensembles compris) avec leurs pièces, les copies par
lien, puis les pièces hors ensemble. Cocher un ensemble coche toutes ses pièces ; sélectionner une
pièce ou un ensemble dans la vue 3D ou l'arbre de FreeCAD la coche aussi, et les pièces cochées
restent en surbrillance. Le nombre de plans (une page par pièce distincte) est affiché. « OK »
crée les pages par l'api (sa propre transaction) et ouvre la première ; « Annuler » ne laisse rien.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from functools import partial
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing_choice import Choice, part_choices, part_label
from freecad.menuiserie.features.drawing_parts import distinct_parts
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui import drawing_pdf
from freecad.menuiserie.gui.display_io import later
from freecad.menuiserie.gui.drawing_hlr import HlrWait
from freecad.menuiserie.gui.task_panels.base import ok_cancel_buttons

__all__ = ["FORM_NAME", "PartDrawingsTaskPanel"]

FORM_NAME: Final = "MenuiseriePartDrawingsPanel"
_NAME_ROLE: Final = QtCore.Qt.UserRole
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plans de pièce")
_HINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochez les pièces à dessiner, ou un ensemble pour toutes ses pièces. La sélection dans la "
    "vue 3D coche aussi.",
)
_GROUP: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} ({count} pièces)")
_LOOSE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièces hors ensemble")
_COUNT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} plan(s) seront créés dans ce document (pièces identiques : un plan, avec la "
    "quantité).",
)
_NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plans de pièce : cochez au moins une pièce.")
_ALL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tout")
_NONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucune")
_DONE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} plan(s) de pièce faits ; chaque page s'exporte en PDF."
)


def _flag(name: str) -> Any:
    """Drapeau d'élément de Qt (énumérations de PySide2 ou PySide6)."""
    flags = getattr(QtCore.Qt, "ItemFlag", QtCore.Qt)
    return getattr(flags, name)


def _state(name: str) -> Any:
    states = getattr(QtCore.Qt, "CheckState", QtCore.Qt)
    return getattr(states, name)


class _SelectionWatcher:
    """Observateur de la sélection de FreeCAD : une pièce ou un ensemble sélectionné est coché
    (hors du rappel : FreeCAD interdit de toucher la sélection pendant). Il se retire de
    lui-même dès que le panneau ou son document n'existe plus."""

    def __init__(self, panel: PartDrawingsTaskPanel) -> None:
        self._panel = panel
        self.attached = False

    def attach(self) -> None:
        """Pose l'observateur."""
        Gui.Selection.addObserver(self)
        self.attached = True

    def detach(self, *_args: object) -> None:
        """Retire l'observateur (sans effet s'il l'est déjà)."""
        if self.attached:
            self.attached = False
            with contextlib.suppress(RuntimeError, ReferenceError):
                Gui.Selection.removeObserver(self)

    def addSelection(self, doc: str, obj: str, _sub: str, _pos: object) -> None:
        """Rappel de FreeCAD : ``obj`` du document ``doc`` a été sélectionné."""
        try:
            mine = doc == self._panel.doc.Name
        except (ReferenceError, RuntimeError, AttributeError):  # document fermé
            self.detach()
            return
        if mine:
            later(partial(self._panel.check, obj))


class PartDrawingsTaskPanel:
    """Panneau du choix des pièces dont faire les plans, dans ``doc``."""

    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.pages: list[DocumentObject] = []
        self._pushing = False
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowTitle(translated(_TITLE))
        layout = QtGui.QVBoxLayout(self.form)
        hint = QtGui.QLabel(translated(_HINT))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tree = QtGui.QTreeWidget()
        self.tree.setHeaderHidden(True)
        layout.addWidget(self.tree)
        self.count = QtGui.QLabel()
        self.count.setWordWrap(True)
        layout.addWidget(self.count)
        row = QtGui.QHBoxLayout()
        for text, state in ((_ALL, "Checked"), (_NONE, "Unchecked")):
            button = QtGui.QPushButton(translated(text))
            button.clicked.connect(partial(self._check_all, _state(state)))
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        self._pending = False
        self._fill()
        self.tree.itemChanged.connect(self._item_changed)
        self._watcher = _SelectionWatcher(self)
        self.form.destroyed.connect(self._watcher.detach)
        self._watcher.attach()
        try:
            self._changed()
        except Exception:
            self._watcher.detach()
            raise

    def _fill(self) -> None:
        groups, loose = part_choices(self.doc)
        for choice in groups:
            self.tree.addTopLevelItem(self._item(choice))
        if loose:
            top = self._new_item(translated(_LOOSE), "")
            top.addChildren([self._item(choice) for choice in loose])
            self.tree.addTopLevelItem(top)
        self.tree.expandAll()

    def _item(self, choice: Choice) -> Any:
        if choice.children:
            text = translated(_GROUP, {"label": part_label(choice.obj), "count": str(choice.parts)})
        else:
            text = part_label(choice.obj)
        item = self._new_item(text, choice.obj.Name)
        item.addChildren([self._item(child) for child in choice.children])
        return item

    @staticmethod
    def _new_item(text: str, name: str) -> Any:
        item = QtGui.QTreeWidgetItem([text])
        item.setData(0, _NAME_ROLE, name)
        item.setFlags(item.flags() | _flag("ItemIsUserCheckable") | _flag("ItemIsAutoTristate"))
        item.setCheckState(0, _state("Unchecked"))
        return item

    def _items(self) -> Iterator[Any]:
        found = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while found:
            item = found.pop(0)
            yield item
            found.extend(item.child(i) for i in range(item.childCount()))

    def _item_changed(self, *_args: object) -> None:
        """Une case a changé : le recalcul est fait une fois, après la rafale de changements
        qu'un ensemble ou « Tout » déclenche."""
        if not self._pending:
            self._pending = True
            later(self._run_changed)

    def _run_changed(self) -> None:
        self._pending = False
        try:
            self._changed()
        except RuntimeError:  # panneau fermé entre-temps
            self._watcher.detach()

    def _check_all(self, state: Any, *_args: object) -> None:
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, state)

    def check(self, name: str) -> None:
        """Coche la ligne de l'objet ``name`` (une pièce, un ensemble ou un lien), s'il y en a
        une et que le panneau ne pousse pas lui-même la sélection."""
        if self._pushing:
            return
        try:
            items = list(self._items())
        except RuntimeError:  # arbre détruit
            self._watcher.detach()
            return
        for item in items:  # un même objet peut avoir plusieurs lignes
            if item.data(0, _NAME_ROLE) == name:
                item.setCheckState(0, _state("Checked"))

    def chosen(self) -> list[DocumentObject]:
        """Pièces et liens cochés, dans l'ordre de l'arbre."""
        checked = _state("Checked")
        names = [
            item.data(0, _NAME_ROLE)
            for item in self._items()
            if item.childCount() == 0 and item.checkState(0) == checked
        ]
        found = (self.doc.getObject(name) for name in names if name)
        return [obj for obj in found if obj is not None]

    def _changed(self) -> None:
        """Nombre de plans recalculé et pièces cochées mises en surbrillance."""
        chosen = self.chosen()
        try:
            count = len(distinct_parts(self.doc, chosen)) if chosen else 0
        except ValueError:
            count = 0
        self.count.setText(translated(_COUNT, {"count": str(count)}))
        self._pushing = True
        try:
            Gui.Selection.clearSelection()
            for obj in chosen:
                Gui.Selection.addSelection(obj)
        finally:
            later(self._done_pushing)

    def _done_pushing(self) -> None:
        self._pushing = False

    def _detach(self) -> None:
        self._watcher.detach()

    def accept(self) -> bool:
        """Crée ou refait les plans des pièces cochées et ouvre le premier ; un refus de l'api
        (rien de coché) laisse le panneau ouvert."""
        from freecad.menuiserie.gui.commands.base import report_refusal
        from freecad.menuiserie.gui.commands.cutlist import show_status

        chosen = self.chosen()  # lu avant la fermeture, qui détruit l'arbre
        if not chosen:
            report_refusal(translated(_NOTHING))
            return False
        try:
            self.pages = api.make_part_drawings(
                self.doc, chosen, api.DrawingOptions(settle=HlrWait())
            )
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return False
        self._detach()
        Gui.Control.closeDialog()
        if self.pages:
            drawing_pdf.show_page(self.pages[0])
        show_status(translated(_DONE, {"count": str(len(self.pages))}))
        return True

    def reject(self) -> bool:
        """Ferme sans rien créer."""
        self._detach()
        Gui.Control.closeDialog()
        return True

    def getStandardButtons(self) -> int:
        """Boutons « OK » et « Annuler »."""
        return ok_cancel_buttons()
