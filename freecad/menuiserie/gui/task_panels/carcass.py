# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche du gabarit « Caisson » (J4d, critère K6 ; ADR 0010).

Le panneau règle les paramètres du caisson (cotes, épaisseurs, étagères, matériaux, assemblage
des côtés) et montre aussitôt le caisson obtenu (aperçu). Chaque saisie abandonne la
transaction « Créer un caisson » (le caisson précédent disparaît), la rouvre et recrée le
caisson par :func:`freecad.menuiserie.api.make_carcass` : il n'y a jamais qu'un caisson et
qu'une transaction. « OK » la valide (une entrée d'annulation), « Annuler » l'abandonne
(aucun objet ne reste). Des paramètres refusés s'affichent dans le panneau ; « OK » reste
alors sans effet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM
from freecad.menuiserie.core.templates.carcass import MAX_SHELVES, CarcassJoinery, CarcassParams
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.gui.task_panels.base import Widget, close_transaction, connect

FORM_NAME: Final = "CarcassTaskPanel"
ICON: Final = "Menuiserie_Carcass.svg"
CREATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Créer un caisson")
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouveau caisson")
_LENGTHS: Final = {  # champ de CarcassParams → libellé
    "width": QT_TRANSLATE_NOOP("Menuiserie", "Largeur"),
    "depth": QT_TRANSLATE_NOOP("Menuiserie", "Profondeur"),
    "height": QT_TRANSLATE_NOOP("Menuiserie", "Hauteur"),
    "thickness": QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur des panneaux"),
    "back_thickness": QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur du fond"),
    "rabbet_depth": QT_TRANSLATE_NOOP("Menuiserie", "Profondeur de la feuillure"),
}
_SHELVES: Final = QT_TRANSLATE_NOOP("Menuiserie", "Étagères")
_MATERIALS: Final = {
    "material_id": QT_TRANSLATE_NOOP("Menuiserie", "Matériau des panneaux"),
    "back_material_id": QT_TRANSLATE_NOOP("Menuiserie", "Matériau du fond"),
}
_JOINERY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblage des côtés")
_JOINERIES: Final = {
    CarcassJoinery.DOWELS: QT_TRANSLATE_NOOP("Menuiserie", "Tourillons"),
    CarcassJoinery.NONE: QT_TRANSLATE_NOOP("Menuiserie", "Aucun (pièces aboutées)"),
}
_UNEXPECTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le caisson n'a pas pu être construit avec ces paramètres ({reason}). Modifiez une cote ou "
    "une épaisseur.",
)
_ERROR_STYLE: Final = "color: #c0392b;"


class CarcassTaskPanel:
    """Paramètres du caisson et aperçu, dans la transaction ouverte par la commande."""

    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.furniture: DocumentObject | None = None
        self._closed = False
        self._transaction = App.getActiveTransaction()
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(_TITLE))
        layout = QtGui.QFormLayout(self.form)
        defaults = CarcassParams()
        self._lengths = {
            name: _length_field(layout, name, label, getattr(defaults, name), self.rebuild)
            for name, label in _LENGTHS.items()
        }
        self._shelves = QtGui.QSpinBox()
        self._shelves.setObjectName("shelf_count")
        self._shelves.setRange(0, MAX_SHELVES)
        self._shelves.setKeyboardTracking(False)  # aperçu à la fin de la saisie
        self._shelves.setValue(defaults.shelf_count)
        connect(self._shelves, "valueChanged(int)", self.rebuild)
        layout.addRow(translated(_SHELVES), self._shelves)
        self._choices = {
            name: _material_box(layout, name, label, getattr(defaults, name), self.rebuild)
            for name, label in _MATERIALS.items()
        }
        self._choices["joinery"] = _combo(
            layout, "joinery", _JOINERY, {k.value: translated(v) for k, v in _JOINERIES.items()}
        )
        connect(self._choices["joinery"], "currentIndexChanged(int)", self.rebuild)
        self._error = QtGui.QLabel()
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)
        self._error.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._error.setStyleSheet(_ERROR_STYLE)
        layout.addRow(self._error)
        self.rebuild()

    # --- Aperçu ---------------------------------------------------------------------------

    def values(self) -> dict[str, Any]:
        """Paramètres saisis, par champ de :class:`CarcassParams`."""
        values: dict[str, Any] = {
            name: float(field.property("rawValue")) for name, field in self._lengths.items()
        }
        values["shelf_count"] = int(self._shelves.value())
        for name, box in self._choices.items():
            values[name] = str(box.itemData(box.currentIndex()))
        return values

    def rebuild(self, *_changed: object) -> None:
        """Caisson précédent abandonné avec sa transaction, puis recréé dans une transaction
        rouverte ; un refus s'affiche sous les champs. Une erreur inattendue (noyau
        géométrique) ou un objet créé en erreur abandonne aussi l'aperçu : rien ne reste."""
        self._restart()
        before = {obj.Name for obj in self.doc.Objects}
        self.furniture, message = None, ""
        try:
            with translated_errors():
                params = CarcassParams(**self.values())
            self.furniture, notices = api.make_carcass(self.doc, params)
            message = "\n".join(notices)
            failed = [
                str(obj.Label)
                for obj in self.doc.Objects
                if obj.Name not in before and not obj.isValid()
            ]
            if failed:
                raise RuntimeError(", ".join(failed))
        except (TypeError, ValueError) as error:
            message = str(error)
        except Exception as error:  # OCC, objet en erreur : aperçu abandonné
            self._restart()
            self.furniture = None
            message = translated(_UNEXPECTED, {"reason": str(error) or type(error).__name__})
        self._error.setText(message)
        self._error.setVisible(bool(message))

    def _restart(self) -> None:
        """Transaction abandonnée (l'aperçu disparaît) puis rouverte, vide."""
        close_transaction(self._transaction, abort=True)
        self.doc.openTransaction(translated(CREATE_TRANSACTION))
        self._transaction = App.getActiveTransaction()

    # --- Cycle de vie (FreeCAD) -----------------------------------------------------------

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation ; sans caisson
        (paramètres refusés), le panneau reste ouvert."""
        if self.furniture is None:
            return False
        self._finish(abort=False)
        return True

    def reject(self) -> bool:
        """« Annuler » : abandon de la transaction, aucun objet ne reste."""
        self._finish(abort=True)
        return True

    def getStandardButtons(self) -> int:
        """Boutons « OK » et « Annuler »."""
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))  # énumérations de PySide6 ou PySide2

    def watch_document(self) -> None:
        """Panneau affiché : FreeCAD le ferme si le document est fermé ou si la transaction change
        (Annuler, Rétablir) ; la transaction est alors abandonnée."""
        dialog = Gui.Control.activeTaskDialog()
        dialog.setDocumentName(self.doc.Name)
        dialog.setAutoCloseOnDeletedDocument(True)
        dialog.setAutoCloseOnTransactionChange(True)
        connect(self.form, "destroyed()", self._on_closed_by_freecad)

    def _finish(self, *, abort: bool) -> None:
        self._closed = True
        close_transaction(self._transaction, abort=abort)
        if not abort:
            self.doc.recompute()
        Gui.Control.closeDialog()

    def _on_closed_by_freecad(self) -> None:
        if not self._closed:
            self._closed = True
            QtCore.QTimer.singleShot(0, self._abandon)

    def _abandon(self) -> None:
        close_transaction(self._transaction, abort=True)


def _length_field(
    layout: Widget, name: str, label: str, value: float, slot: Callable[..., None]
) -> Widget:
    """Champ de cote en mm (``Gui::QuantitySpinBox``) ajouté au formulaire."""
    field = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    field.setKeyboardTracking(False)  # aperçu à la fin de la saisie, pas à chaque touche
    field.setObjectName(name)
    field.setProperty("unit", "mm")
    field.setProperty("minimum", 0.0)
    field.setProperty("maximum", MAX_DIMENSION_MM)
    field.setProperty("rawValue", value)
    connect(field, "valueChanged(double)", slot)
    layout.addRow(translated(label), field)
    return field


def _combo(layout: Widget, name: str, label: str, items: dict[str, str]) -> Widget:
    """Liste déroulante (identifiant → texte affiché) ajoutée au formulaire."""
    box = QtGui.QComboBox()
    box.setObjectName(name)
    for key, text in items.items():
        box.addItem(text, key)
    layout.addRow(translated(label), box)
    return box


def _material_box(
    layout: Widget, name: str, label: str, wanted: str, slot: Callable[..., None]
) -> Widget:
    """Matériaux de la bibliothèque ; ``wanted`` choisi s'il existe, sinon le matériau par
    défaut."""
    library = get_library()
    names = {material.id: material.name(display_language()) for material in library}
    box = _combo(layout, name, label, names)
    chosen = wanted if wanted in names else library.default_material().id
    box.setCurrentIndex(box.findData(chosen))
    connect(box, "currentIndexChanged(int)", slot)
    return box


def show_panel(doc: Document) -> None:
    """Ouvre le panneau dans la transaction de la commande ; une exception l'abandonne."""
    try:
        panel = CarcassTaskPanel(doc)
        Gui.Control.showDialog(panel)
        panel.watch_document()
    except BaseException:
        close_transaction(App.getActiveTransaction(), abort=True)
        raise
