# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche de la pièce de bois : création (commande) et modification (double-clic).

Chaque modification est écrite aussitôt dans l'objet, puis l'objet est recalculé (aperçu en
direct). « OK » valide la transaction ouverte par la commande ou par :func:`start_editing`,
« Annuler » l'abandonne : la pièce créée disparaît, la pièce modifiée retrouve ses valeurs.
Une cote pilotée par une expression est affichée par le champ (icône d'expression) et n'est
jamais écrite par le panneau.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind
from freecad.menuiserie.core.part_model import (
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    GrainDirection,
    is_nonstandard_panel_thickness,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.wood_part import set_material, shows_grain
from freecad.menuiserie.gui.view_providers.wood_part import ICON

Widget = Any  # widgets Qt créés par FreeCAD, sans annotations de type

UI_FILE: Final = Path(__file__).with_name("wood_part.ui")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier une pièce de bois")
_CREATE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouvelle pièce de bois")
_EDIT_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier « {label} »")
_INDEX_CHANGED: Final = "currentIndexChanged(int)"

# Filtre « Type » : libellé, puis familles retenues (aucune : tous les matériaux).
KIND_FILTERS: Final[tuple[tuple[str, tuple[MaterialKind, ...]], ...]] = (
    (QT_TRANSLATE_NOOP("Menuiserie", "Tous"), ()),
    (QT_TRANSLATE_NOOP("Menuiserie", "Massif"), (MaterialKind.SOLID,)),
    (QT_TRANSLATE_NOOP("Menuiserie", "Contreplaqué"), (MaterialKind.PLYWOOD,)),
    (QT_TRANSLATE_NOOP("Menuiserie", "MDF"), (MaterialKind.MDF,)),
    (QT_TRANSLATE_NOOP("Menuiserie", "Mélaminé"), (MaterialKind.MELAMINE,)),
)
# Sens du fil : valeur stable écrite dans l'objet, libellé traduit affiché.
GRAIN_LABELS: Final = (
    (GrainDirection.LENGTH, QT_TRANSLATE_NOOP("Menuiserie", "Longueur")),
    (GrainDirection.WIDTH, QT_TRANSLATE_NOOP("Menuiserie", "Largeur")),
    (GrainDirection.NONE, QT_TRANSLATE_NOOP("Menuiserie", "Sans fil")),
)


@dataclass(frozen=True)
class LengthField:
    """Champ de cote du formulaire, lié à une propriété ``App::PropertyLength``."""

    widget: str
    prop: str
    minimum: float


# Champs sans liaison d'expression possible : inactifs si leur propriété est pilotée (C6).
DRIVEN_FIELDS: Final = (
    ("markEdit", "Mark"),
    ("materialCombo", "Material"),
    ("grainCombo", "GrainDirection"),
)
LENGTH_FIELDS: Final = (
    LengthField("lengthEdit", "Length", MIN_DIMENSION_MM),
    LengthField("widthEdit", "Width", MIN_DIMENSION_MM),
    LengthField("thicknessEdit", "Thickness", MIN_DIMENSION_MM),
    LengthField("lengthAllowanceEdit", "LengthAllowance", 0.0),
    LengthField("widthAllowanceEdit", "WidthAllowance", 0.0),
    LengthField("thicknessAllowanceEdit", "ThicknessAllowance", 0.0),
)


class WoodPartTaskPanel:
    """Panneau de tâche d'une pièce de bois, en création (``creating``) ou en modification."""

    def __init__(self, obj: DocumentObject, *, creating: bool) -> None:
        self.obj = obj
        self.doc = obj.Document
        self.creating = creating
        self._updating = False
        self._closed = False
        self._transaction = App.getActiveTransaction()
        self._watcher = DeletionWatcher(obj, Gui.Control.closeDialog)
        self.form = Gui.PySideUic.loadUi(str(UI_FILE))
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(_title(obj, creating))
        self._bindings = [self._bind(field) for field in LENGTH_FIELDS]
        self._thickness_menu = QtGui.QMenu(self.form.standardThicknessButton)
        self.form.standardThicknessButton.setMenu(self._thickness_menu)
        self._fill_fixed_choices()
        self._fill_materials()
        self._show_values()
        self._show_allowances(False)
        self._lock_driven_fields()
        self._connect_signals()

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation."""
        self._finish(abort=False)
        return True

    def reject(self) -> bool:
        """« Annuler » : abandon de la transaction (pièce supprimée ou valeurs rétablies)."""
        self._finish(abort=True)
        return True

    def watch_document(self) -> None:
        """Panneau affiché : FreeCAD le ferme si le document est fermé (sans quoi FreeCAD 1.0
        plante en détruisant les liaisons d'expression) ou si Édition > Annuler / Rétablir
        change la transaction ; le mode édition et la transaction sont alors soldés."""
        dialog = Gui.Control.activeTaskDialog()
        dialog.setDocumentName(self.doc.Name)
        dialog.setAutoCloseOnDeletedDocument(True)
        dialog.setAutoCloseOnTransactionChange(True)
        _connect(self.form, "destroyed()", self._on_closed_by_freecad)
        App.addDocumentObserver(self._watcher)

    def getStandardButtons(self) -> int:
        """Boutons « OK » et « Annuler »."""
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))  # énumérations de PySide6 ou PySide2

    # --- Fermeture ------------------------------------------------------------------------

    def _finish(self, *, abort: bool) -> None:
        """Solde la transaction du panneau, sans entrée parasite, puis ferme le panneau."""
        self._closed = True
        self._watcher.stop()
        App.removeDocumentObserver(self._watcher)
        close_transaction(self._transaction, abort=abort)
        _close(self.doc)

    def _on_closed_by_freecad(self) -> None:
        """Formulaire détruit sans « OK » ni « Annuler » (document fermé, pièce supprimée,
        Édition > Annuler) : la suite est différée hors du signal qui a fermé le panneau."""
        if self._closed:
            return
        self._closed = True
        self._watcher.stop()
        QtCore.QTimer.singleShot(0, self._clean_up_after_forced_close)

    def _clean_up_after_forced_close(self) -> None:
        """Observateur retiré, transaction du panneau abandonnée en création (validée en
        modification, après recalcul comme avec « OK ») si elle est encore ouverte, mode
        édition quitté."""
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
        if in_edit is not None and in_edit.Object.Name == self._watcher.object_name:
            gui_doc.resetEdit()

    # --- Construction du formulaire -------------------------------------------------------

    def _bind(self, field: LengthField) -> Any:
        """Bornes du champ et liaison à la propriété (affichage et édition des expressions)."""
        widget = getattr(self.form, field.widget)
        widget.setProperty("minimum", field.minimum)
        widget.setProperty("maximum", MAX_DIMENSION_MM)
        binding = Gui.ExpressionBinding(widget)
        binding.bind(self.obj, field.prop)
        binding.setAutoApply(True)
        return binding

    def _fill_fixed_choices(self) -> None:
        for label, _kinds in KIND_FILTERS:
            self.form.kindCombo.addItem(translated(label))
        for grain, label in GRAIN_LABELS:
            self.form.grainCombo.addItem(translated(label), grain.value)

    def _lock_driven_fields(self) -> None:
        """Repère, matériau ou fil pilotés par une expression : champ inactif (C6)."""
        for widget, prop in DRIVEN_FIELDS:
            if has_expression(self.obj, prop):
                getattr(self.form, widget).setEnabled(False)

    def _connect_signals(self) -> None:
        form = self.form
        _connect(form.markEdit, "textEdited(QString)", self._on_mark_edited)
        _connect(form.kindCombo, _INDEX_CHANGED, self._on_kind_chosen)
        _connect(form.materialCombo, _INDEX_CHANGED, self._on_material_chosen)
        _connect(form.grainCombo, _INDEX_CHANGED, self._on_grain_chosen)
        _connect(form.allowancesToggle, "toggled(bool)", self._show_allowances)
        for field in LENGTH_FIELDS:
            slot = partial(self._on_length_changed, field.prop)
            _connect(getattr(form, field.widget), "valueChanged(double)", slot)

    @contextmanager
    def _quiet(self) -> Iterator[None]:
        """Mise à jour des widgets par le panneau : rien n'est réécrit dans l'objet."""
        previous, self._updating = self._updating, True
        try:
            yield
        finally:
            self._updating = previous

    # --- Affichage ------------------------------------------------------------------------

    def _fill_materials(self) -> None:
        """Matériaux du type choisi ; hors filtre, le premier de la liste est appliqué."""
        combo = self.form.materialCombo
        kinds = KIND_FILTERS[max(self.form.kindCombo.currentIndex(), 0)][1]
        with self._quiet():
            combo.clear()
            for material in get_library().by_kind(*kinds):
                combo.addItem(material.name(display_language()), material.id)
            if not kinds and combo.findData(self.obj.MaterialId) < 0:
                # Matériau inconnu de la bibliothèque locale : son libellé enregistré reste affiché.
                combo.addItem(self.obj.Material, self.obj.MaterialId)
            combo.setCurrentIndex(combo.findData(self.obj.MaterialId))
        if combo.currentIndex() < 0 and combo.count() and not has_expression(self.obj, "Material"):
            combo.setCurrentIndex(0)

    def _show_values(self) -> None:
        """Valeurs de l'objet dans les champs (après ouverture ou changement de matériau)."""
        with self._quiet():
            self.form.markEdit.setText(self.obj.Mark)
            grain = self.form.grainCombo.findData(self.obj.GrainDirection)
            self.form.grainCombo.setCurrentIndex(grain)
            self._show_grain_row(shows_grain(self.obj))
            for field in LENGTH_FIELDS:
                value = getattr(self.obj, field.prop).Value
                getattr(self.form, field.widget).setProperty("rawValue", value)
        self._show_thickness_tools()

    def _show_grain_row(self, shown: bool) -> None:
        """Ligne « Sens du fil » masquée pour un matériau sans fil."""
        self.form.grainLabel.setVisible(shown)
        self.form.grainCombo.setVisible(shown)

    def _show_thickness_tools(self) -> None:
        """Menu des épaisseurs standard et avertissement « hors standard » (panneaux)."""
        material = get_library().find(self.obj.MaterialId)
        self._fill_thickness_menu(material)
        button = self.form.standardThicknessButton
        button.setEnabled(material is not None and not has_expression(self.obj, "Thickness"))
        thickness = self.obj.Thickness.Value
        warn = material is not None and is_nonstandard_panel_thickness(material, thickness)
        self.form.thicknessWarning.setVisible(warn)

    def _fill_thickness_menu(self, material: Material | None) -> None:
        self._thickness_menu.clear()
        for thickness in material.thicknesses if material is not None else ():
            action = self._thickness_menu.addAction(_length_text(thickness))
            _connect(action, "triggered()", partial(self._choose_thickness, thickness))

    def _show_allowances(self, shown: bool) -> None:
        """Zone « Surcotes de débit » repliée ou dépliée."""
        arrow = QtCore.Qt.ArrowType.DownArrow if shown else QtCore.Qt.ArrowType.RightArrow
        self.form.allowancesBox.setVisible(shown)
        self.form.allowancesToggle.setArrowType(arrow)

    # --- Modifications de l'utilisateur ---------------------------------------------------

    def _on_mark_edited(self, text: str) -> None:
        if not has_expression(self.obj, "Mark"):
            self.obj.Mark = text

    def _on_kind_chosen(self, _index: int) -> None:
        self._fill_materials()

    def _on_material_chosen(self, index: int) -> None:
        if self._updating or index < 0 or has_expression(self.obj, "Material"):
            return
        material_id = self.form.materialCombo.itemData(index)
        if material_id == self.obj.MaterialId or get_library().find(material_id) is None:
            return
        set_material(self.obj, material_id)
        self._show_values()  # le fil et les surcotes suivent le matériau
        self._recompute()

    def _on_grain_chosen(self, index: int) -> None:
        if not self._updating and index >= 0 and not has_expression(self.obj, "GrainDirection"):
            self.obj.GrainDirection = self.form.grainCombo.itemData(index)

    def _on_length_changed(self, prop: str, value: float) -> None:
        if self._updating or has_expression(self.obj, prop):
            return
        if getattr(self.obj, prop).Value != value:
            setattr(self.obj, prop, value)
            self._recompute()

    def _choose_thickness(self, thickness: float) -> None:
        """Épaisseur standard choisie dans le menu : écrite par le champ lui-même."""
        self.form.thicknessEdit.setProperty("rawValue", thickness)

    def _recompute(self) -> None:
        self.obj.recompute()
        self._show_thickness_tools()


def start_editing(obj: DocumentObject) -> bool:
    """Ouvre le panneau sur une pièce existante, dans la transaction « Modifier une pièce de
    bois » ; faux si un autre panneau de tâche est déjà ouvert."""
    if Gui.Control.activeDialog():
        return False
    obj.Document.openTransaction(translated(EDIT_TRANSACTION))
    show_panel(obj, creating=False)
    return True


def show_panel(obj: DocumentObject, *, creating: bool) -> None:
    """Construit puis affiche le panneau, dans la transaction déjà ouverte. Une exception
    abandonne cette transaction (pièce en création comprise) avant d'être propagée."""
    try:
        panel = WoodPartTaskPanel(obj, creating=creating)
        Gui.Control.showDialog(panel)
        panel.watch_document()
    except BaseException:
        close_transaction(App.getActiveTransaction(), abort=True)
        raise


def close_transaction(transaction: tuple[str, int] | None, *, abort: bool) -> None:
    """Valide ou abandonne ``transaction`` (``(nom, identifiant)``) si elle est encore la
    transaction active. Passe par l'application : une transaction encore vide est aussi
    refermée, sans quoi le recalcul suivant y serait enregistré (entrée parasite)."""
    active = App.getActiveTransaction()
    if transaction is not None and active == transaction:
        App.closeActiveTransaction(abort, transaction[1])


class DeletionWatcher:
    """Observateur de document : ferme le panneau quand sa pièce est supprimée (Édition >
    Supprimer, console). Rendu inerte par :meth:`stop` (retrait différé de l'observateur)."""

    def __init__(self, obj: DocumentObject, on_deleted: Callable[[], None]) -> None:
        self.document_name: str = obj.Document.Name
        self.object_name: str = obj.Name
        self._on_deleted: Callable[[], None] | None = on_deleted

    def stop(self) -> None:
        """Panneau fermé : l'observateur ne réagit plus (il peut être retiré plus tard)."""
        self._on_deleted = None

    def slotDeletedObject(self, obj: DocumentObject) -> None:
        """Pièce du panneau supprimée : le panneau est fermé."""
        if self._on_deleted is None:
            return
        if (obj.Document.Name, obj.Name) == (self.document_name, self.object_name):
            self._on_deleted()


def finish_editing() -> None:
    """Fin de l'édition (``unsetEdit``) : le panneau est fermé."""
    Gui.Control.closeDialog()


def has_expression(obj: DocumentObject, prop: str) -> bool:
    """Vrai si la propriété ``prop`` de ``obj`` est pilotée par une expression."""
    return any(path.lstrip(".") == prop for path, _expression in obj.ExpressionEngine)


def _connect(sender: Widget, signature: str, slot: Callable[..., None]) -> None:
    """Connexion par signature Qt : les champs de FreeCAD (``Gui::QuantitySpinBox``) n'ont pas
    d'attribut de signal en Python, et la connexion par attribut garde en vie l'enveloppe
    Python des widgets après leur destruction (enveloppe réutilisée à tort ensuite)."""
    QtCore.QObject.connect(sender, QtCore.SIGNAL(signature), slot)


def _title(obj: DocumentObject, creating: bool) -> str:
    if creating:
        return translated(_CREATE_TITLE)
    return translated(_EDIT_TITLE, {"label": str(obj.Label)})


def _length_text(length_mm: float) -> str:
    """Longueur dans le système d'unités choisi par l'utilisateur (« 22 mm », « 0,87 in »…)."""
    text: str = App.Units.Quantity(length_mm, App.Units.Length).UserString
    return text


def _close(doc: Document) -> None:
    """Recalcule le document, quitte le mode édition et ferme le panneau."""
    doc.recompute()
    Gui.getDocument(doc.Name).resetEdit()
    Gui.Control.closeDialog()
