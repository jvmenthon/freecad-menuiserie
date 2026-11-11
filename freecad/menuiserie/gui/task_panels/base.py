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
from contextlib import contextmanager, nullcontext
from typing import Any, Final, Protocol
from weakref import WeakMethod

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.display_layers import ORIGIN_LOOK
from freecad.menuiserie.core.document_state import Snapshot, differs
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM
from freecad.menuiserie.features.document_snapshot import snapshot_of
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.display_layers import DISPLAY, object_alive
from freecad.menuiserie.gui.task_panels import active
from freecad.menuiserie.gui.task_panels.preview import PartsPreview

Widget = Any  # widgets Qt créés par FreeCAD, sans annotations de type

_TASK_VIEW: Final = "Gui::TaskView::TaskView"  # classe Qt de la vue des tâches (porte « OK »)
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
        self._widgets_gone = False  # formulaire en cours de destruction
        self._edited_name: str | None = None
        self._document_name: str = doc.Name
        self._transaction = App.getActiveTransaction()
        self._watcher = watcher
        self._edit_transparency: PartsPreview | None = None
        self._tinted: PartsPreview | None = None
        self._initial: Snapshot | None = None

    def has_changes(self) -> bool:
        """Vrai si le document a changé depuis l'ouverture du panneau (photo des propriétés
        saisies comparée à l'état actuel : lecture seule, la transaction n'est pas touchée)."""
        return self._initial is not None and differs(self._initial, snapshot_of(self.doc))

    def _unchanged(self) -> bool:
        """Vrai pour une modification que rien n'a changée : seul l'affichage retiré de la
        transaction y est écrit, la valider laisserait une entrée d'annulation vide."""
        return not self.creating and self._initial is not None and not self.has_changes()

    def transparent_objects(self) -> list[DocumentObject]:
        """Objets affichés en transparence tant que le panneau est ouvert (pièce en édition, ou
        sa pièce usinée si elle a des assemblages), relus à chaque aperçu ; aucun par défaut. Leur
        transparence d'origine est rétablie à toute fermeture (« OK », « Annuler » ou fermeture
        par FreeCAD)."""
        return []

    def tinted_objects(self) -> list[DocumentObject]:
        """Objets transparents et teints (``ORIGIN_LOOK``) tant que le panneau est ouvert, comme
        :meth:`transparent_objects` ; aucun par défaut."""
        return []

    def sync_styles(self) -> None:
        """Objets transparents ou teints relus après un aperçu (pièce apparue ou supprimée)."""
        for preview in (self._edit_transparency, self._tinted):
            if preview is not None:
                preview.sync()

    def reapply_styles(self) -> None:
        """Transparence et teinte reposées après l'abandon de la transaction du panneau (qui les
        rétablit quand elles ont été posées dans cette transaction)."""
        for preview in (self._edit_transparency, self._tinted):
            if preview is not None:
                preview.reapply()

    @contextmanager
    def _without_transaction(self) -> Iterator[None]:
        """Contexte où une propriété du ViewObject s'écrit sans entrée d'annulation : FreeCAD
        l'enregistre dans la transaction ouverte, donc celle d'une modification, encore vide
        puisque le panneau vient de s'ouvrir, est refermée (abandonnée) le temps de la pose puis
        rouverte : « OK » sans changement ne laisse aucune entrée d'annulation. Seulement à
        l'ouverture : plus tard, rien ne dit que la transaction est vide, et l'abandonner
        défairait les modifications. En création, la pose reste dans la transaction de création."""
        transaction = self._transaction
        reopen = (
            not self.creating
            and transaction is not None
            and App.getActiveTransaction() == transaction
        )
        if reopen:
            App.closeActiveTransaction(True, transaction[1])
        try:
            yield
        finally:
            if reopen:
                self.doc.openTransaction(transaction[0])
                self._transaction = App.getActiveTransaction()

    def _apply_styles(self) -> None:
        """Transparence d'édition posée sur :meth:`transparent_objects` (calque « édition », partagé
        avec la sélection de ligne) et teinte sur :meth:`tinted_objects` (calque « origine »),
        hors transaction (:meth:`_without_transaction`)."""
        objects = self.transparent_objects() + self.tinted_objects()
        context = self._without_transaction() if objects else nullcontext()
        with context:
            self._edit_transparency = PartsPreview(self.transparent_objects, object_alive, DISPLAY)
            self._tinted = PartsPreview(self.tinted_objects, object_alive, DISPLAY, ORIGIN_LOOK)

    def _restore_styles(self) -> None:
        """Transparence d'origine rétablie (idempotent, sans effet sur un objet supprimé)."""
        previews = (self._edit_transparency, self._tinted)
        self._edit_transparency = self._tinted = None
        for preview in previews:
            if preview is not None:
                preview.restore()

    @property
    def closed(self) -> bool:
        """Vrai une fois le panneau fermé (« OK », « Annuler » ou fermeture par FreeCAD), ou dès
        qu'un widget suivi par :meth:`watch_widgets` est détruit."""
        return self._closed or self._widgets_gone

    def watch_widgets(self, *widgets: Widget) -> None:
        """Le panneau se tient pour fermé dès que l'un de ``widgets`` est détruit : un signal émis
        pendant la destruction du formulaire (champ qui perd le focus) ne touche plus à rien."""
        for widget in widgets:
            connect(widget, "destroyed()", self._widget_destroyed)

    def _widget_destroyed(self) -> None:
        self._widgets_gone = True

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation."""
        self._before_commit()
        self._finish(abort=False)
        return True

    def _before_commit(self) -> None:
        """Étape des sous-classes juste avant la validation (par exemple rétablir l'affichage
        d'un aperçu) ; rien par défaut."""

    def _release_display(self) -> None:
        """Étape des sous-classes à chaque fermeture, avant le solde de la transaction (par
        exemple rétablir l'affichage modifié par le panneau) ; rien par défaut."""

    def reject(self) -> bool:
        """« Annuler » : abandon de la transaction (objet supprimé ou valeurs rétablies)."""
        self._finish(abort=True)
        return True

    def getStandardButtons(self) -> int:
        """Boutons « OK » et « Annuler »."""
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))  # énumérations de PySide6 ou PySide2

    def watch_document(self, edited: DocumentObject | None = None) -> None:
        """Panneau affiché : FreeCAD le ferme si le document est fermé (sans quoi FreeCAD peut
        planter en détruisant les liaisons d'expression) ou si Édition > Annuler / Rétablir
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
        self._initial = snapshot_of(self.doc)
        active.register(self)
        self._apply_styles()  # en dernier : le panneau est affiché, plus rien ne peut échouer

    # --- Fermeture ------------------------------------------------------------------------

    def _finish(self, *, abort: bool) -> None:
        """Solde la transaction du panneau, sans entrée parasite, puis ferme le panneau."""
        self._closed = True
        active.unregister(self)
        self._stop_watching()
        self._remove_watcher()
        if self.creating:
            self._restore_styles()  # dans la transaction de création : rien d'enregistré en plus
        self._release_display()
        withdrawn = (
            DISPLAY.withdraw()
        )  # sélection de ligne retirée de la transaction avant son solde
        abort = abort or (withdrawn and self._unchanged())
        close_transaction(self._transaction, abort=abort)
        self._restore_styles()  # modification : transaction close, aucune entrée d'annulation
        _close(self.doc)  # le recalcul peut rétablir la couleur des pièces usinées
        DISPLAY.flush()  # transaction close : sélection de ligne reposée en dernier

    def _on_closed_by_freecad(self) -> None:
        """Formulaire détruit sans « OK » ni « Annuler » (document fermé, objet supprimé,
        Édition > Annuler) : la suite est différée hors du signal qui a fermé le panneau."""
        if self._closed:
            return
        self._closed = True
        active.unregister(self)
        self._stop_watching()
        if self.creating:
            self._restore_styles()
        self._release_display()
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
        DISPLAY.withdraw()
        close_transaction(self._transaction, abort=self.creating)
        self._restore_styles()  # après la transaction : aucune entrée d'annulation
        DISPLAY.flush()
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
        self.sync_styles()  # une pièce usinée a pu apparaître au recalcul


def set_ok_enabled(form: Widget, enabled: bool) -> None:
    """Grise ou rétablit le bouton « OK » de la vue des tâches qui affiche ``form`` ; sans effet
    hors affichage. La classe de la vue est comparée en entier : ``Gui::TaskView::TaskBox`` et
    ``TaskPanel``, ancêtres du formulaire, portent aussi « TaskView » dans leur nom. Le bouton
    n'est jamais rendu : son enveloppe Python ne survivrait pas à celle de sa boîte."""
    view = form.parentWidget() if form is not None else None
    while view is not None and view.metaObject().className() != _TASK_VIEW:
        view = view.parentWidget()
    for box in view.findChildren(QtGui.QDialogButtonBox) if view is not None else []:
        button = box.button(QtGui.QDialogButtonBox.Ok)
        if button is not None:
            button.setEnabled(enabled)
            return


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


def length_spinbox(name: str, value: float) -> Widget:
    """Champ de cote en mm (``Gui::QuantitySpinBox``) de 0 à ``MAX_DIMENSION_MM``, à ``value``."""
    field = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    field.setKeyboardTracking(False)  # aperçu à la fin de la saisie, pas à chaque touche
    field.setObjectName(name)
    field.setProperty("unit", "mm")
    field.setProperty("minimum", 0.0)
    field.setProperty("maximum", MAX_DIMENSION_MM)
    field.setProperty("rawValue", value)
    return field


def connect(sender: Widget, signature: str, slot: Callable[..., None]) -> None:
    """Connexion par signature Qt : les champs de FreeCAD (``Gui::QuantitySpinBox``) n'ont pas
    d'attribut de signal en Python, et la connexion par attribut garde en vie l'enveloppe
    Python des widgets après leur destruction (enveloppe réutilisée à tort ensuite)."""
    QtCore.QObject.connect(sender, QtCore.SIGNAL(signature), slot)


def weak_callback(callback: Callable[[], None]) -> Callable[[], None]:
    """``callback`` sans le garder en vie quand c'est une méthode : un groupe de lignes qui
    rappelle son panneau ne forme pas avec lui un cycle, que le ramasse-miettes ne romprait
    qu'à un moment imprévisible, en pleine destruction de widgets (SIGSEGV sous FreeCAD)."""
    if not hasattr(callback, "__self__"):
        return callback
    target = WeakMethod(callback)

    def call() -> None:
        method = target()
        if method is not None:
            method()

    return call


def _close(doc: Document) -> None:
    """Recalcule le document, quitte le mode édition et ferme le panneau."""
    doc.recompute()
    Gui.getDocument(doc.Name).resetEdit()
    Gui.Control.closeDialog()
