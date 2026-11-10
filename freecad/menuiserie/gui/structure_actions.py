# SPDX-License-Identifier: LGPL-2.1-or-later
"""Actions du panneau « Structure » : menu contextuel et glisser-déposer (ADR 0046, lot 3).

Les décisions (permis ou refusé, et pourquoi) viennent de ``core/structure_actions.py`` et
``core/structure_menu.py`` ; ici on les présente (entrées grisées avec infobulle, refus expliqué)
et on les exécute par l'api de l'atelier, chaque action dans **une** transaction annulable d'un
seul Ctrl+Z. Rien ne se fait si la décision est un refus. Le panneau se redessine ensuite.

- ranger, sortir, créer un (sous-)ensemble : ``api.add_to_furniture``, ``remove_from_furniture``
  et ``make_furniture`` (ADR 0037), comme les commandes de l'ensemble ;
- renommer : le libellé de la brute (celui que la ligne montre) ;
- supprimer : la commande « Std_Delete » de FreeCAD sur les objets des lignes, donc les mêmes
  fenêtres et avertissements que l'arbre natif (``onDelete`` de l'ensemble, fenêtre « assemblage
  lié » de la pièce usinée) et la transaction de FreeCAD ;
- ouvrir : le signal de double-clic de l'arbre, donc le même chemin.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from functools import partial
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_actions import (
    Decision,
    MoveFacts,
    cleaned_name,
    creates_sub_furniture,
    decide_drop,
    decide_rename,
)
from freecad.menuiserie.core.structure_menu import Action, MenuEntry, menu_entries
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.furniture_members import member_object
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.structure_facts import facts_of, renamed_object
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.commands.furniture import refresh_tree, show_notices
from freecad.menuiserie.gui.structure_dnd import DropTree
from freecad.menuiserie.gui.structure_sync import later, report_errors
from freecad.menuiserie.gui.structure_tree_widget import KEY_ROLE, item_for, selected_keys
from freecad.menuiserie.gui.task_panels.base import aborted_on_error, close_transaction

__all__ = ["StructureActions", "current_facts", "decision_text"]

_MOVE_IN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ranger dans l'ensemble")
_MOVE_OUT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Sortir de l'ensemble")
_CREATE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Créer un ensemble")
_CREATE_SUB: Final = QT_TRANSLATE_NOOP("Menuiserie", "Créer un sous-ensemble")
_RENAME: Final = QT_TRANSLATE_NOOP("Menuiserie", "Renommer")
_RENAME_PROMPT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouveau nom :")
_NO_DOCUMENT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun document ouvert.")

Handler = Callable[[MenuEntry], None]


def current_facts() -> MoveFacts | None:
    """Faits du document actif, avec l'état « panneau de tâche ouvert » ; ``None`` sans document."""
    doc = App.ActiveDocument
    if doc is None:
        return None
    return replace(facts_of(doc), busy=bool(Gui.Control.activeDialog()))


def decision_text(decision: Decision) -> str:
    """Raison d'un refus, traduite ; vide pour une décision permise ou muette."""
    return translated(decision.template, decision.params) if decision.template else ""


def run_in_transaction(
    doc: Any, name: str, action: Callable[[], Sequence[str]]
) -> Sequence[str] | None:
    """Exécute ``action`` dans une transaction ``name`` (une entrée d'annulation). Un refus de
    l'api (``TypeError``, ``ValueError`` traduites) abandonne la transaction, rien ne change, et
    s'explique par :func:`report_refusal` (``None``). Renvoie les avertissements sinon."""
    doc.openTransaction(translated(name))
    transaction = App.getActiveTransaction()
    try:
        with aborted_on_error(transaction):
            messages = action()
    except (TypeError, ValueError) as error:
        report_refusal(str(error))
        return None
    close_transaction(transaction, abort=False)
    show_notices(messages)
    return messages


def _objects(doc: Any, keys: Sequence[str]) -> list[DocumentObject]:
    return [obj for obj in (doc.getObject(key) for key in keys) if obj is not None]


def _owners(objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Ensembles actuels des ``objects`` (sans doublon), avant qu'ils ne changent."""
    found = (furniture_of(member_object(obj)) for obj in objects)
    return list({f.Name: f for f in found if f is not None}.values())


def move_rows(doc: Any, keys: Sequence[str], target: str | None) -> Sequence[str] | None:
    """Range les lignes ``keys`` dans l'ensemble ``target`` (``None`` : les sort de leur
    ensemble) en une transaction ; les propriétés de membre ne sont jamais retirées puis recréées
    (FreeCAD 1.1 ne les rétablit pas au Ctrl+Z) : ``move=True`` et ``keep_properties=True`` ;
    refus de l'api = rien ne change."""
    objects = _objects(doc, keys)
    destination = doc.getObject(target) if target is not None else None

    def action() -> Sequence[str]:
        owners = _owners(objects)
        leaving = [obj for obj in objects if furniture_of(member_object(obj)) is not None]
        messages: list[str] = []
        if destination is not None:
            messages += api.add_to_furniture(destination, objects, move=True)
        elif leaving:
            messages += api.remove_from_furniture(leaving, keep_properties=True)
        refresh_tree([*owners, *([destination] if destination is not None else [])])
        return messages

    return run_in_transaction(doc, _MOVE_OUT if target is None else _MOVE_IN, action)


class StructureActions(QtCore.QObject):  # type: ignore[misc]
    """Contrôleur du menu contextuel et du glisser-déposer. Enfant du dock, donc détruit avec lui.
    ``refresh`` redessine le panneau (reconstruction forcée) une fois l'action faite."""

    def __init__(self, tree: DropTree, refresh: Callable[[], None], parent: QtCore.QObject) -> None:
        super().__init__(parent)
        self._tree = tree
        self._refresh = refresh
        self._facts: MoveFacts | None = None  # faits lus au début d'un glissement
        self._handlers: dict[Action, Handler] = {
            Action.OPEN: self._open,
            Action.RENAME: self._rename,
            Action.MOVE_INTO: self._move_into,
            Action.LEAVE: self._leave,
            Action.CREATE: self._create,
            Action.DELETE: self._delete,
        }
        tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._show_menu)
        tree.judge = self._drop_refusal
        tree.on_drop = self._dropped
        tree.on_drag_start = self._read_facts

    # --- Glisser-déposer ------------------------------------------------------------------

    def _read_facts(self) -> None:
        self._facts = current_facts()

    def _drop_refusal(self, keys: list[str], target: str | None) -> str:
        """Raison pour laquelle le dépôt est refusé, vide s'il est permis (survol)."""
        facts = self._facts or current_facts()
        if facts is None:
            return translated(_NO_DOCUMENT)
        return decision_text(decide_drop(facts, keys, target))

    def _dropped(self, keys: list[str], target: str | None) -> None:
        """Dépôt : exécuté après la fin du glissement, sur des faits relus."""
        self._facts = None
        later(partial(report_errors, self._apply_drop, keys, target))

    def _apply_drop(self, keys: Sequence[str], target: str | None) -> None:
        facts = current_facts()
        if facts is None:
            return
        decision = decide_drop(facts, keys, target)
        if decision.allowed:
            move_rows(App.ActiveDocument, decision.keys, target)
        elif not decision.silent:
            report_refusal(decision_text(decision))
        self._redraw()

    def _redraw(self) -> None:
        later(partial(report_errors, self._refresh))

    # --- Menu contextuel ------------------------------------------------------------------

    def _show_menu(self, point: Any) -> None:
        """Menu de la ligne sous le curseur (ou de la sélection qui la contient)."""
        item = self._tree.itemAt(point)
        if item is None or not item.data(0, KEY_ROLE):
            return
        if not item.isSelected():
            self._tree.clearSelection()
            item.setSelected(True)
        facts = current_facts()
        if facts is None:
            return
        menu = QtGui.QMenu(self._tree)
        menu.setToolTipsVisible(True)
        for entry in menu_entries(facts, selected_keys(self._tree)):
            if entry.action in (Action.ADD_TO, Action.DELETE):
                menu.addSeparator()
            self._add_entry(menu, entry)
        menu.exec(self._tree.viewport().mapToGlobal(point))

    def _add_entry(self, menu: Any, entry: MenuEntry) -> None:
        """Entrée active, ou grisée avec la raison du refus en infobulle."""
        text = entry.label if entry.verbatim else translated(entry.label)
        if entry.children:
            submenu = menu.addMenu(text)
            submenu.setToolTipsVisible(True)
            for child in entry.children:
                self._add_entry(submenu, child)
            self._explain(submenu.menuAction(), entry.decision)
            return
        action = menu.addAction(text)
        self._explain(action, entry.decision)
        action.triggered.connect(lambda _checked=False: self._trigger(entry))

    @staticmethod
    def _explain(action: Any, decision: Decision) -> None:
        action.setEnabled(decision.allowed)
        reason = decision_text(decision)
        if reason:
            action.setToolTip(reason)
            action.setStatusTip(reason)

    def run_action(self, action: Action, keys: Sequence[str], target: str | None = None) -> bool:
        """Exécute l'entrée ``action`` (``target`` : ensemble d'accueil d'un « Ajouter à
        l'ensemble ») du menu des lignes ``keys`` comme un clic, sans afficher le menu. Faux, sans
        rien faire, si l'entrée est absente ou grisée."""
        facts = current_facts()
        entries = menu_entries(facts, keys) if facts is not None else []
        found = (e for top in entries for e in (top, *top.children) if e.action is action)
        entry = next((e for e in found if e.target == target), None)
        if entry is None or not entry.decision.allowed:
            return False
        self._run(entry)
        return True

    def _trigger(self, entry: MenuEntry) -> None:
        """Exécute l'entrée après la fermeture du menu, une erreur allant à la vue rapport."""
        later(partial(report_errors, self._run, entry))

    def _run(self, entry: MenuEntry) -> None:
        self._handlers[entry.action](entry)
        self._redraw()

    # --- Une méthode par entrée -----------------------------------------------------------

    def _open(self, entry: MenuEntry) -> None:
        """Équivaut au double-clic sur la ligne (même signal, même chemin)."""
        item = item_for(self._tree, entry.decision.keys[0])
        if item is not None:
            self._tree.itemDoubleClicked.emit(item, 0)

    def _move_into(self, entry: MenuEntry) -> None:
        move_rows(App.ActiveDocument, entry.decision.keys, entry.target)

    def _leave(self, entry: MenuEntry) -> None:
        move_rows(App.ActiveDocument, entry.decision.keys, None)

    def _rename(self, entry: MenuEntry) -> None:
        """Demande le nouveau nom puis le contrôle (``decide_rename``) avant de l'écrire."""
        doc, facts = App.ActiveDocument, current_facts()
        key = entry.decision.keys[0]
        if doc is None or facts is None or doc.getObject(key) is None:
            return
        old = facts.labels[key]
        text, accepted = QtGui.QInputDialog.getText(
            self._tree,
            translated(_RENAME),
            translated(_RENAME_PROMPT),
            QtGui.QLineEdit.Normal,
            old,
        )
        if not accepted:
            return
        decision = decide_rename(old, text, furniture=key in facts.furnitures)
        if decision.silent:
            return
        if not decision.allowed:
            report_refusal(decision_text(decision))
            return
        target = renamed_object(doc.getObject(key))
        run_in_transaction(doc, _RENAME, partial(_write_label, target, cleaned_name(text)))

    def _create(self, entry: MenuEntry) -> None:
        """Nouvel ensemble (ou sous-ensemble) autour de la sélection, comme la commande de l'ADR
        0037 ; le nouvel ensemble est ensuite sélectionné."""
        doc, facts = App.ActiveDocument, current_facts()
        if doc is None or facts is None:
            return
        keys = entry.decision.keys
        name = _CREATE_SUB if creates_sub_furniture(facts, keys) else _CREATE
        objects = _objects(doc, keys)
        created: list[str] = []

        def action() -> Sequence[str]:
            owners = _owners(objects)
            furniture, notices = api.make_furniture(objects)
            created.append(furniture.Name)
            refresh_tree([*owners, furniture])
            return notices

        if run_in_transaction(doc, name, action) is not None and created:
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, created[0])

    def _delete(self, entry: MenuEntry) -> None:
        """« Supprimer » de FreeCAD sur les objets des lignes : mêmes fenêtres que l'arbre natif
        (onDelete de l'ensemble, fenêtre « assemblage lié » de la pièce usinée), une seule
        transaction annulable, ouverte et fermée par FreeCAD."""
        doc = App.ActiveDocument
        if doc is None:
            return
        Gui.Selection.clearSelection()
        for key in entry.decision.keys:
            Gui.Selection.addSelection(doc.Name, key)
        Gui.runCommand("Std_Delete")


def _write_label(obj: DocumentObject, name: str) -> Sequence[str]:
    obj.Label = name
    return ()
