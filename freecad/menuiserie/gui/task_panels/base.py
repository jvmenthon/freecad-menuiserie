# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle commun des panneaux de tâche (pièce de bois J1c, assemblage J3e).

Un panneau modifie un objet dans une transaction ouverte par sa commande (création) ou par
:func:`start_editing` (modification) : « OK » la valide en une seule entrée d'annulation,
« Annuler » l'abandonne. FreeCAD peut aussi fermer le panneau de lui-même (document fermé, objet
supprimé, Édition > Annuler) : la transaction et le mode édition sont alors soldés après coup.
Chaque modification est visible aussitôt (:func:`recompute_preview`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final, Protocol

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated

Widget = Any  # widgets Qt créés par FreeCAD, sans annotations de type

# Préfixe des types TechDraw : leurs pages ne sont pas recalculées par l'aperçu.
_TECHDRAW: Final = "TechDraw::"


class Panel(Protocol):
    """Ce que FreeCAD et :func:`show_panel` attendent d'un panneau."""

    form: Widget

    def watch_document(self, edited: DocumentObject | None = None) -> None:
        """Surveillance du document une fois le panneau affiché."""


class ObjectTaskPanel:
    """Base des panneaux de tâche sur un objet ``obj``, en création ou en modification : cycle
    de vie (transaction, fermeture, surveillance du document). Les sous-classes construisent
    ``self.form`` et réagissent aux saisies."""

    def __init__(self, obj: DocumentObject, *, creating: bool) -> None:
        self.obj = obj
        self.doc = obj.Document
        self.creating = creating
        self.form: Widget = None
        self._closed = False
        self._edited_name: str | None = None
        self._transaction = App.getActiveTransaction()
        self._watcher = DeletionWatcher(obj, Gui.Control.closeDialog)

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation."""
        self._finish(abort=False)
        return True

    def reject(self) -> bool:
        """« Annuler » : abandon de la transaction (objet supprimé ou valeurs rétablies)."""
        self._finish(abort=True)
        return True

    def getStandardButtons(self) -> int:
        """Boutons « OK » et « Annuler »."""
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))  # énumérations de PySide6 ou PySide2

    def watch_document(self, edited: DocumentObject | None = None) -> None:
        """Panneau affiché : FreeCAD le ferme si le document est fermé (sans quoi FreeCAD 1.0
        plante en détruisant les liaisons d'expression) ou si Édition > Annuler / Rétablir
        change la transaction ; le mode édition et la transaction sont alors soldés.
        ``edited`` : objet mis en mode édition par le double-clic (la pièce usinée pour sa
        brute), mémorisé ici car il peut perdre son lien vers ``obj`` avant la fermeture."""
        self._edited_name = edited.Name if edited is not None else None
        dialog = Gui.Control.activeTaskDialog()
        dialog.setDocumentName(self.doc.Name)
        dialog.setAutoCloseOnDeletedDocument(True)
        dialog.setAutoCloseOnTransactionChange(True)
        connect(self.form, "destroyed()", self._on_closed_by_freecad)
        App.addDocumentObserver(self._watcher)

    def preview(self) -> None:
        """Aperçu : l'objet et ce qui en dépend, sans le reste du document."""
        recompute_preview(self.obj)

    # --- Fermeture ------------------------------------------------------------------------

    def _finish(self, *, abort: bool) -> None:
        """Solde la transaction du panneau, sans entrée parasite, puis ferme le panneau."""
        self._closed = True
        self._watcher.stop()
        App.removeDocumentObserver(self._watcher)
        close_transaction(self._transaction, abort=abort)
        _close(self.doc)

    def _on_closed_by_freecad(self) -> None:
        """Formulaire détruit sans « OK » ni « Annuler » (document fermé, objet supprimé,
        Édition > Annuler) : la suite est différée hors du signal qui a fermé le panneau."""
        if self._closed:
            return
        self._closed = True
        self._watcher.stop()
        QtCore.QTimer.singleShot(0, self._clean_up_after_forced_close)

    def _clean_up_after_forced_close(self) -> None:
        """Observateur retiré, transaction du panneau abandonnée en création (validée en
        modification, après recalcul comme avec « OK ») si elle est encore ouverte, mode
        édition quitté s'il porte encore sur l'objet mémorisé par :meth:`watch_document`."""
        App.removeDocumentObserver(self._watcher)
        name = self._watcher.document_name
        alive = name in App.listDocuments()
        if alive and not self.creating:
            App.getDocument(name).recompute()
        close_transaction(self._transaction, abort=self.creating)
        if not alive:
            return
        gui_doc = Gui.getDocument(name)
        in_edit = gui_doc.getInEdit()
        if in_edit is not None and in_edit.Object.Name == self._edited_name:
            gui_doc.resetEdit()


def show_panel(build: Callable[[], Panel], edited: DocumentObject | None = None) -> None:
    """Construit le panneau par ``build`` puis l'affiche, dans la transaction déjà ouverte.
    Une exception abandonne cette transaction (objet en création compris) avant d'être
    propagée."""
    try:
        panel = build()
        Gui.Control.showDialog(panel)
        panel.watch_document(edited)
    except BaseException:
        close_transaction(App.getActiveTransaction(), abort=True)
        raise


def start_editing(
    doc: Document, transaction: str, build: Callable[[], Panel], edited: DocumentObject
) -> bool:
    """Ouvre le panneau construit par ``build`` dans la transaction ``transaction`` (gabarit
    traduisible) ; faux si un autre panneau de tâche est déjà ouvert."""
    if Gui.Control.activeDialog():
        return False
    doc.openTransaction(translated(transaction))
    show_panel(build, edited)
    return True


def finish_editing() -> None:
    """Fin de l'édition (``unsetEdit``) : le panneau est fermé."""
    Gui.Control.closeDialog()


def close_transaction(transaction: tuple[str, int] | None, *, abort: bool) -> None:
    """Valide ou abandonne ``transaction`` (``(nom, identifiant)``) si elle est encore la
    transaction active. Passe par l'application : une transaction encore vide est aussi
    refermée, sans quoi le recalcul suivant y serait enregistré (entrée parasite)."""
    active = App.getActiveTransaction()
    if transaction is not None and active == transaction:
        App.closeActiveTransaction(abort, transaction[1])


def recompute_preview(obj: DocumentObject) -> None:
    """Recalcule ``obj`` et ce qui en dépend dans son document (assemblages, pièces usinées),
    sans les pages TechDraw ni les objets d'autres documents qui le citent."""
    doc = obj.Document
    dependents = [
        o for o in obj.InListRecursive if o.Document is doc and not o.TypeId.startswith(_TECHDRAW)
    ]
    doc.recompute([obj, *dependents])


class DeletionWatcher:
    """Observateur de document : ferme le panneau quand son objet est supprimé (Édition >
    Supprimer, console). Rendu inerte par :meth:`stop` (retrait différé de l'observateur)."""

    def __init__(self, obj: DocumentObject, on_deleted: Callable[[], None]) -> None:
        self.document_name: str = obj.Document.Name
        self.object_name: str = obj.Name
        self._on_deleted: Callable[[], None] | None = on_deleted

    def stop(self) -> None:
        """Panneau fermé : l'observateur ne réagit plus (il peut être retiré plus tard)."""
        self._on_deleted = None

    def slotDeletedObject(self, obj: DocumentObject) -> None:
        """Objet du panneau supprimé : le panneau est fermé."""
        if self._on_deleted is None:
            return
        if (obj.Document.Name, obj.Name) == (self.document_name, self.object_name):
            self._on_deleted()


class UpdateGuard:
    """Garde des mises à jour des widgets par le panneau (``with guard:``) : tant qu'elle est
    levée (:attr:`active`), les saisies ne sont pas réécrites dans l'objet. Réentrante."""

    def __init__(self) -> None:
        self._depth = 0

    @property
    def active(self) -> bool:
        """Vrai pendant une mise à jour des widgets par le panneau."""
        return self._depth > 0

    def __enter__(self) -> None:
        self._depth += 1

    def __exit__(self, *_exc_info: object) -> None:
        self._depth -= 1


def expression_of(obj: DocumentObject, prop: str) -> str | None:
    """Expression qui pilote la propriété ``prop`` de ``obj``, ``None`` s'il n'y en a pas."""
    for path, expression in obj.ExpressionEngine:
        if path.lstrip(".") == prop:
            text: str = expression
            return text
    return None


def has_expression(obj: DocumentObject, prop: str) -> bool:
    """Vrai si la propriété ``prop`` de ``obj`` est pilotée par une expression."""
    return expression_of(obj, prop) is not None


def connect(sender: Widget, signature: str, slot: Callable[..., None]) -> None:
    """Connexion par signature Qt : les champs de FreeCAD (``Gui::QuantitySpinBox``) n'ont pas
    d'attribut de signal en Python, et la connexion par attribut garde en vie l'enveloppe
    Python des widgets après leur destruction (enveloppe réutilisée à tort ensuite)."""
    QtCore.QObject.connect(sender, QtCore.SIGNAL(signature), slot)


def _close(doc: Document) -> None:
    """Recalcule le document, quitte le mode édition et ferme le panneau."""
    doc.recompute()
    Gui.getDocument(doc.Name).resetEdit()
    Gui.Control.closeDialog()
