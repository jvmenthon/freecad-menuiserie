# SPDX-License-Identifier: LGPL-2.1-or-later
"""Synchronisation du panneau « Structure » avec FreeCAD (ADR 0046, lot 2).

Le panneau reste en lecture seule du modèle : il lit le document, la sélection et l'état de
l'interface, et n'écrit que dans la **sélection** de FreeCAD (``Gui.Selection``) et dans la
vue d'édition (double-clic). Observateurs posés tant que le panneau est visible, retirés
à sa fermeture ou à sa destruction (ADR 0007 : aucun observateur laissé en place).

- document : les notifications sont fondues par un :class:`Coalescer` (un seul recalcul par
  rafale) ; un arbre inchangé ne reconstruit rien, un arbre modifié garde son état déplié ;
- sélection : ligne → FreeCAD par ``itemSelectionChanged``, FreeCAD → ligne par un observateur
  de sélection ; la garde et la comparaison des deux ensembles coupent la rétroaction.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_sync import (
    Coalescer,
    ReentrancyGuard,
    is_relevant_change,
    keys_to_select_in_freecad,
    rows_for_selection,
)
from freecad.menuiserie.core.structure_tree import NodeKind, StructureNode
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat import is_copy
from freecad.menuiserie.features.structure_source import row_key_of, structure_of
from freecad.menuiserie.gui.structure_highlight import RowHighlight
from freecad.menuiserie.gui.structure_switch import ask_user, switch_to
from freecad.menuiserie.gui.structure_tree_widget import (
    KEY_ROLE,
    KIND_ROLE,
    expansion_of,
    fill_tree,
    select_keys,
    selected_keys,
)

__all__ = ["StructureSync", "later", "open_object_panel", "report_errors"]

NO_DOCUMENT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun document ouvert.")
EMPTY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun ensemble ni aucune pièce.")


def later(callback: Callable[[], None]) -> None:
    QtCore.QTimer.singleShot(0, callback)


def open_object_panel(obj: Any) -> bool:
    """Ouvre le panneau de tâche de ``obj`` comme le double-clic de l'arbre natif : le
    ``doubleClicked`` de son ViewProvider (``PanelEditing`` ou liste de débit), sinon le mode
    d'édition 0. Un ensemble copie de répétition ouvre « Modifier la répétition », comme une pièce
    copie (son ViewProvider d'ensemble n'ouvre que le panneau de l'ensemble). Refusé tant qu'un
    panneau de tâche est ouvert."""
    vobj = getattr(obj, "ViewObject", None)
    if vobj is None:
        return False
    if is_furniture(obj) and is_copy(obj):
        from freecad.menuiserie.gui.task_panels.repeat import start_editing

        return bool(start_editing(obj.Repeat, obj))
    double_click = getattr(getattr(vobj, "Proxy", None), "doubleClicked", None)
    if callable(double_click):
        return bool(double_click(vobj))
    if Gui.Control.activeDialog():
        return False
    return bool(vobj.Document.setEdit(obj, 0))


class _Lifetime:
    """Vrai tant que l'arbre Qt existe : le signal ``destroyed`` de l'arbre le baisse. Remplace
    le test de validité de shiboken (ADR 0023 : compatibilité Qt 5, PySide seul importé)."""

    def __init__(self) -> None:
        self.alive = True

    def mark_destroyed(self, *_args: object) -> None:
        """Slot de ``destroyed`` : l'objet C++ de l'arbre n'existe plus."""
        self.alive = False


def _in_active_document(obj: Any) -> bool:
    """Vrai si ``obj`` est du document actif (le panneau n'en montre pas d'autre) ; faux pour un
    objet dont le document a disparu."""
    active = App.ActiveDocument
    try:
        return active is not None and obj.Document.Name == active.Name
    except (ReferenceError, RuntimeError, TypeError):
        return False


class _DocumentWatcher:
    """Observateur de documents : ne fait que demander un rafraîchissement différé, et seulement
    pour le document actif (la modification d'un autre ne change pas l'arbre affiché)."""

    def __init__(self, request: Callable[[], None]) -> None:
        self._request = request

    def slotCreatedObject(self, obj: Any) -> None:
        if _in_active_document(obj):
            self._request()

    def slotDeletedObject(self, obj: Any) -> None:
        if _in_active_document(obj):
            self._request()

    def slotChangedObject(self, obj: Any, prop: str) -> None:
        if is_relevant_change(prop) and _in_active_document(obj):
            self._request()

    def slotDeletedDocument(self, _doc: Any) -> None:
        self._request()


class _ActivationWatcher:
    """Observateur de l'interface : le document actif change."""

    def __init__(self, request: Callable[[], None]) -> None:
        self._request = request

    def slotActivateDocument(self, _doc: Any) -> None:
        self._request()


class _SelectionWatcher:
    """Observateur de sélection : une notification par élément, fondues par l'appelant."""

    def __init__(self, request: Callable[[], None]) -> None:
        self._request = request

    def _changed(self, *_args: object) -> None:
        self._request()

    addSelection = removeSelection = setSelection = clearSelection = _changed


class _Observers:
    """Observateurs posés dans FreeCAD, hors de tout QObject : le retrait doit rester possible
    quand le dock et son contrôleur sont déjà détruits (ADR 0007)."""

    def __init__(
        self,
        request_refresh: Callable[[], None],
        request_select: Callable[[], None],
        on_detach: Callable[[], None],
    ):
        self._on_detach = on_detach
        self._documents = _DocumentWatcher(request_refresh)
        self._activation = _ActivationWatcher(request_refresh)
        self._selection = _SelectionWatcher(request_select)
        self.attached = False

    def attach(self) -> bool:
        """Pose les observateurs ; faux s'ils l'étaient déjà."""
        if self.attached:
            return False
        self.attached = True
        App.addDocumentObserver(self._documents)
        if hasattr(Gui, "addDocumentObserver"):
            Gui.addDocumentObserver(self._activation)
        Gui.Selection.addObserver(self._selection)
        return True

    def detach(self) -> bool:
        """Retire les observateurs, chaque retrait étant tenté même si un autre échoue ; faux
        s'ils étaient déjà retirés."""
        if not self.attached:
            return False
        self.attached = False
        report_errors(App.removeDocumentObserver, self._documents)
        if hasattr(Gui, "removeDocumentObserver"):
            report_errors(Gui.removeDocumentObserver, self._activation)
        report_errors(Gui.Selection.removeObserver, self._selection)
        report_errors(self._on_detach)  # transparence de sélection rendue
        return True


class StructureSync(QtCore.QObject):  # type: ignore[misc]
    """Contrôleur du panneau : rafraîchissement, sélection et double-clic. Enfant du dock,
    donc détruit avec lui ; :meth:`attach` et :meth:`detach` posent et retirent les
    observateurs."""

    def __init__(self, tree: QtGui.QTreeWidget, parent: QtCore.QObject) -> None:
        super().__init__(parent)
        self._tree = tree
        self._lifetime = _Lifetime()
        tree.destroyed.connect(self._lifetime.mark_destroyed)
        self._guard = ReentrancyGuard()
        self._refresh = Coalescer(later, self._guarded_refresh)
        self._select = Coalescer(later, self._guarded_pull_selection)
        self.choose = ask_user  # boîte « appliquer / annuler » ; remplaçable (tests hors écran)
        self._highlight = RowHighlight(tree)
        self._observers = _Observers(
            self._refresh.request, self._select.request, self._highlight.clear
        )
        self._shown: tuple[str, tuple[StructureNode, ...]] | None = None
        tree.itemSelectionChanged.connect(self._push_selection)
        tree.itemSelectionChanged.connect(self._choose_rows)
        tree.itemDoubleClicked.connect(self._open_panel)

    # --- Observateurs ---------------------------------------------------------------------

    @property
    def attached(self) -> bool:
        """Vrai tant que les observateurs sont posés."""
        return self._observers.attached

    @property
    def observers(self) -> _Observers:
        """Les observateurs, que le retrait à la destruction du dock appelle sans le QObject."""
        return self._observers

    def attach(self) -> None:
        """Pose les observateurs (sans effet s'ils le sont) et met le panneau à jour."""
        self._observers.attach()
        self.refresh_now()

    def detach(self) -> None:
        """Retire les observateurs et annule les rafraîchissements en attente."""
        if self._observers.detach():
            self._refresh.cancel()
            self._select.cancel()

    def _tree_alive(self) -> bool:
        """Faux (et observateurs retirés) si l'arbre Qt est déjà détruit."""
        if self._lifetime.alive:
            return True
        self._observers.detach()
        return False

    # --- Document -------------------------------------------------------------------------

    def refresh_now(self, *, force: bool = False) -> None:
        """Recalcule l'arbre du document actif et rend la sélection de FreeCAD au panneau.
        Un arbre identique à celui affiché n'est pas reconstruit, sauf avec ``force`` (après un
        glisser-déposer, qui a pu laisser des lignes déplacées)."""
        if not self._tree_alive():
            return
        doc = App.ActiveDocument
        name = doc.Name if doc is not None else ""
        nodes = structure_of(doc) if doc is not None else ()
        if force or self._shown != (name, nodes):
            message = translated(EMPTY if doc is not None else NO_DOCUMENT)
            with self._guard.applying():
                fill_tree(self._tree, nodes, message, expansion_of(self._tree))
            self._shown = (name, nodes)
        self.pull_selection()
        self._follow_highlight()

    def _guarded_refresh(self) -> None:
        report_errors(self.refresh_now)

    # --- Sélection ------------------------------------------------------------------------

    def pull_selection(self) -> None:
        """FreeCAD → panneau : surligne les lignes des objets sélectionnés (sans rien envoyer
        en retour)."""
        if not self._tree_alive():
            return
        wanted = rows_for_selection(self._freecad_row_keys(), self._row_keys())
        if wanted == selected_keys(self._tree):
            return
        with self._guard.applying():
            select_keys(self._tree, wanted)  # signaux bloqués : la transparence suit à part
        self._follow_highlight()

    def _choose_rows(self) -> None:
        """Lignes choisies par l'utilisateur : transparence de sélection posée sur leurs objets
        (ou retirée à la désélection). Pas pendant un remplissage de l'arbre."""
        if self._lifetime.alive and self._observers.attached and not self._guard.active:
            report_errors(self._highlight.choose)

    def _follow_highlight(self) -> None:
        """Arbre rempli ou sélection reprise de FreeCAD : la transparence reste tant que les lignes
        sélectionnées sont celles que l'utilisateur a choisies, sinon elle est retirée."""
        if self._lifetime.alive and self._observers.attached:
            report_errors(self._highlight.follow)

    def _guarded_pull_selection(self) -> None:
        report_errors(self.pull_selection)

    def _push_selection(self) -> None:
        """Panneau → FreeCAD : sélectionne les objets des lignes choisies (arbre natif et 3D).
        Ignoré quand c'est le panneau qui vient d'être écrit par FreeCAD."""
        if self._guard.active:
            return
        report_errors(self._push_now)

    def _push_now(self) -> None:
        if not self._tree_alive():
            return
        doc = App.ActiveDocument
        if doc is None:
            return
        keys = keys_to_select_in_freecad(selected_keys(self._tree))
        if keys == self._freecad_row_keys():
            return
        with self._guard.applying():
            Gui.Selection.clearSelection()
            for key in keys:
                Gui.Selection.addSelection(doc.Name, key)

    def _freecad_row_keys(self) -> list[str]:
        """Clés de ligne des objets sélectionnés du document actif (la brute compte pour sa
        pièce usinée)."""
        doc = App.ActiveDocument
        if doc is None:
            return []
        return list(dict.fromkeys(row_key_of(o) for o in Gui.Selection.getSelection(doc.Name)))

    def _row_keys(self) -> set[str]:
        """Clés des objets que le panneau montre."""
        roots = self._shown[1] if self._shown is not None else ()
        return {node.key for root in roots for node in root.walk() if node.key}

    # --- Double-clic ----------------------------------------------------------------------

    def _open_panel(self, item: QtGui.QTreeWidgetItem, _column: int) -> None:
        """Même panneau de tâche que le double-clic de l'arbre natif. Jamais pour un objet d'un
        autre atelier : l'éditer, ce serait le modifier. Une tâche en cours est d'abord réglée
        (``structure_switch`` : fermée si inchangée, sinon l'utilisateur choisit)."""
        if item.data(0, KIND_ROLE) == NodeKind.OTHER.value:
            return
        key = item.data(0, KEY_ROLE)
        doc = App.ActiveDocument
        obj = doc.getObject(key) if key and doc is not None else None
        if obj is not None:
            report_errors(switch_to, obj, open_object_panel, self.choose)


def report_errors(action: Callable[..., object], *args: object) -> None:
    """Une erreur est écrite dans la vue rapport et ne remonte pas dans la boucle Qt."""
    try:
        action(*args)
    except Exception:  # pylint: disable=broad-exception-caught
        App.Console.PrintError(traceback.format_exc())
