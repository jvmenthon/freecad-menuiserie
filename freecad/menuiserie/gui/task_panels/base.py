# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle commun des panneaux de tâche (pièce de bois J1c, assemblage J3e, ensemble J4c,
caisson J4d).

Un panneau modifie un objet dans une transaction ouverte par sa commande (création) ou par
:func:`start_editing` (modification) : « OK » la valide en une seule entrée d'annulation,
« Annuler » l'abandonne. FreeCAD peut aussi fermer le panneau de lui-même (document fermé, objet
supprimé, Édition > Annuler) : la transaction et le mode édition sont alors soldés après coup.
Chaque modification est visible aussitôt (:func:`recompute_preview`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Final, Protocol

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated

Widget = Any  # widgets Qt créés par FreeCAD, sans annotations de type

EDIT_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier « {label} »")
# Préfixe des types TechDraw : leurs pages ne sont pas recalculées par l'aperçu.
_TECHDRAW: Final = "TechDraw::"


class Panel(Protocol):
    """Ce que FreeCAD et :func:`show_panel` attendent d'un panneau."""

    form: Widget

    def watch_document(self, edited: DocumentObject | None = None) -> None:
        """Surveillance du document une fois le panneau affiché."""


class TransactionTaskPanel:
    """Base des panneaux de tâche qui travaillent dans une transaction du document ``doc``
    (Template Method) : « OK » la valide, « Annuler » l'abandonne, une fermeture par FreeCAD la
    solde après coup (abandonnée en création, validée en modification). Les sous-classes
    construisent ``self.form`` et réagissent aux saisies ; ``watcher`` ferme le panneau quand
    son objet est supprimé."""

    def __init__(
        self, doc: Document, *, creating: bool, watcher: DeletionWatcher | None = None
    ) -> None:
        self.doc = doc
        self.creating = creating
        self.form: Widget = None
        self._closed = False
        self._edited_name: str | None = None
        self._document_name: str = doc.Name
        self._transaction = App.getActiveTransaction()
        self._watcher = watcher

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation."""
        self._before_commit()
        self._finish(abort=False)
        return True

    def _before_commit(self) -> None:
        """Étape des sous-classes juste avant la validation (par exemple rétablir l'affichage
        d'un aperçu) ; rien par défaut."""

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
        if self._watcher is not None:
            App.addDocumentObserver(self._watcher)

    # --- Fermeture ------------------------------------------------------------------------

    def _finish(self, *, abort: bool) -> None:
        """Solde la transaction du panneau, sans entrée parasite, puis ferme le panneau."""
        self._closed = True
        self._stop_watching()
        self._remove_watcher()
        close_transaction(self._transaction, abort=abort)
        _close(self.doc)

    def _on_closed_by_freecad(self) -> None:
        """Formulaire détruit sans « OK » ni « Annuler » (document fermé, objet supprimé,
        Édition > Annuler) : la suite est différée hors du signal qui a fermé le panneau."""
        if self._closed:
            return
        self._closed = True
        self._stop_watching()
        QtCore.QTimer.singleShot(0, self._clean_up_after_forced_close)

    def _clean_up_after_forced_close(self) -> None:
        """Observateur retiré, transaction du panneau abandonnée en création (validée en
        modification, après recalcul comme avec « OK ») si elle est encore ouverte, mode
        édition quitté s'il porte encore sur l'objet mémorisé par :meth:`watch_document`."""
        self._remove_watcher()
        name = self._document_name
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

    def _stop_watching(self) -> None:
        """L'observateur de suppression ne réagit plus (il peut être retiré plus tard)."""
        if self._watcher is not None:
            self._watcher.stop()

    def _remove_watcher(self) -> None:
        if self._watcher is not None:
            App.removeDocumentObserver(self._watcher)


class ObjectTaskPanel(TransactionTaskPanel):
    """Base des panneaux de tâche sur un objet ``obj``, en création ou en modification : le
    panneau se ferme aussi quand ``obj`` est supprimé."""

    def __init__(self, obj: DocumentObject, *, creating: bool) -> None:
        watcher = DeletionWatcher(obj, Gui.Control.closeDialog)
        super().__init__(obj.Document, creating=creating, watcher=watcher)
        self.obj = obj

    def preview(self) -> None:
        """Aperçu : l'objet et ce qui en dépend, sans le reste du document."""
        recompute_preview(self.obj)


def show_panel(build: Callable[[], Panel], edited: DocumentObject | None = None) -> None:
    """Construit le panneau par ``build`` puis l'affiche, dans la transaction déjà ouverte.
    Une exception abandonne cette transaction (objet en création compris) avant d'être
    propagée."""
    with aborted_on_error(App.getActiveTransaction()):
        panel = build()
        Gui.Control.showDialog(panel)
        panel.watch_document(edited)


def panel_title(label: str, creating: bool, create_template: str) -> str:
    """Titre du panneau : ``create_template`` en création, « Modifier « … » » sinon ; ``label``
    (libellé de l'objet déjà mis en forme) remplit ``{label}``."""
    return translated(create_template if creating else EDIT_TITLE, {"label": label})


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


@contextmanager
def aborted_on_error(transaction: tuple[str, int] | None) -> Iterator[None]:
    """Toute exception du bloc abandonne ``transaction`` (:func:`close_transaction`) avant
    d'être propagée."""
    try:
        yield
    except BaseException:
        close_transaction(transaction, abort=True)
        raise


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
