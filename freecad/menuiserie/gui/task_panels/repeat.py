# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche « Répéter » et « Modifier la répétition » (lot R-c, ADR 0043).

Le panneau règle une répétition en grille (ADR 0045) : un seul mode de saisie, puis trois lignes X,
Y et Z (case d'activation, nombre d'éléments original compris, pas ou longueur selon le mode, case
« Inverser » : :mod:`.repeat_rows`), les assemblages recopiés et le suivi du redimensionnement. Il
montre aussitôt toutes les copies dans la vue 3D :
chaque saisie validée (fin de frappe, flèches, case cochée) recalcule l'aperçu par l'api
(:func:`~freecad.menuiserie.api.make_repeat` à la première saisie acceptée, puis
:func:`~freecad.menuiserie.api.edit_repeat`), dans la transaction ouverte par la commande ou par
:func:`start_editing`. « OK » valide cette transaction (une entrée d'annulation), « Annuler »
l'abandonne (aucune copie ne reste, ou la répétition retrouve son réglage).

Une saisie refusée (``RepeatError`` du noyau, refus de l'api) s'affiche en rouge sous les champs :
« OK » est grisé et l'aperçu garde le dernier réglage accepté. Un chevauchement des copies n'est
qu'un avertissement. Les champs suivent la norme « Entrées utilisateur » (``CONTRIBUTING.md``) :
bornes de ``core.repeat``, saisie appliquée en fin de frappe, refus expliqué.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import (
    NO_AXIS,
    AxisRepeat,
    RepeatAxis,
    RepeatError,
    RepeatParams,
    ResolvedGrid,
    SpacingMode,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.repeat import sources_of, stored_lines
from freecad.menuiserie.features.repeat_copies import resolve_for, source_extent, source_extents
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    DeletionWatcher,
    TransactionTaskPanel,
    UpdateGuard,
    Widget,
    close_transaction,
    connect,
    set_ok_enabled,
)
from freecad.menuiserie.gui.task_panels.furniture_widgets import message_label, show_message
from freecad.menuiserie.gui.task_panels.repeat_messages import overlap_text, summary_text
from freecad.menuiserie.gui.task_panels.repeat_rows import (
    COLUMN_CAPTIONS,
    DEFAULT_CELLS,
    AxisRow,
    uses,
)
from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

__all__ = ["RepeatTaskPanel", "open_panel", "start_editing"]

FORM_NAME: Final = "RepeatTaskPanel"
ICON: Final = "Menuiserie_Repeat.svg"
CREATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier la répétition")
DEFAULT_COUNT: Final = 3  # copies proposées à l'ouverture (4 éléments sur X)
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter « {label} »")
_PIECES: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} pièces")
_SPACINGS: Final = {
    SpacingMode.COUNT_AND_STEP: QT_TRANSLATE_NOOP("Menuiserie", "Nombre et pas"),
    SpacingMode.COUNT_ON_SPAN: QT_TRANSLATE_NOOP("Menuiserie", "Nombre sur une longueur"),
    SpacingMode.STEP_ON_SPAN: QT_TRANSLATE_NOOP("Menuiserie", "Pas sur une longueur"),
}
_SPACING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Mode de saisie")
_SPACING_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Commun à tous les axes. Nombre et pas : vous donnez les deux. Nombre sur une longueur : le "
    "pas est calculé pour remplir la longueur. Pas sur une longueur : le nombre d'éléments est "
    "calculé.",
)
_COPY_JOINTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Recopier les assemblages")
_COPY_JOINTS_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochée : chaque copie reçoit les assemblages de la pièce d'origine, liés à ceux de "
    "l'original (modifier le premier modifie les autres). Décochée : seules les pièces sont "
    "copiées.",
)
_FOLLOW: Final = QT_TRANSLATE_NOOP("Menuiserie", "Suivre le redimensionnement")
_FOLLOW_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochée : quand l'ensemble est redimensionné, le pas de chaque axe est recalculé et les "
    "copies se répartissent sur la nouvelle longueur de l'ensemble sur cet axe ; leur nombre ne "
    "change pas. Décochée : les pas restent fixes.",
)
_FOLLOW_DISABLED_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Grisée : la pièce répétée n'est dans aucun ensemble, il n'y a pas de redimensionnement à "
    "suivre. Placez-la d'abord dans un ensemble.",
)
_UNEXPECTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La répétition n'a pas pu être construite avec ces valeurs ({reason}). Modifiez le nombre, "
    "le pas ou la longueur.",
)
_WARNING_STYLE: Final = "color: #b35c00;"
_AXES: Final = (RepeatAxis.X, RepeatAxis.Y, RepeatAxis.Z)


def _checkbox(name: str, label: str, tip: str, checked: bool) -> Widget:
    box = QtGui.QCheckBox(translated(label))
    box.setObjectName(name)
    box.setToolTip(translated(tip))
    box.setChecked(checked)
    return box


class RepeatTaskPanel(TransactionTaskPanel):
    """Réglage d'une répétition et aperçu en direct, dans la transaction ouverte par la commande
    (création : ``repeat`` est ``None``, ``sources`` les pièces à répéter) ou par
    :func:`start_editing` (modification de ``repeat``, panneau prérempli) ; transaction,
    fermeture et surveillance du document : :mod:`base`."""

    def __init__(
        self,
        doc: Document,
        sources: Sequence[DocumentObject],
        repeat: DocumentObject | None = None,
    ) -> None:
        watcher = None if repeat is None else DeletionWatcher(repeat, Gui.Control.closeDialog)
        super().__init__(doc, creating=repeat is None, watcher=watcher)
        self._guard = UpdateGuard()
        self._repeat_name: str | None = None if repeat is None else repeat.Name
        self._sources = list(sources)
        self._refused = False
        self._steps_edited: set[RepeatAxis] = set()  # pas saisis : ils ne suivent plus la cote
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        label = self._sources_label() if repeat is None else quoted_value(repeat.Label)
        self.form.setWindowTitle(base.panel_title(label, repeat is None, _TITLE))
        self._rows = {axis: AxisRow(axis) for axis in _AXES}
        self._captions: dict[str, Widget] = {}
        self._build()
        self._fill(repeat)
        self._connect()
        if repeat is None:
            self._update()  # aperçu des valeurs par défaut

    # --- Construction ---------------------------------------------------------------------

    def _sources_label(self) -> str:
        if len(self._sources) == 1:
            return quoted_value(self._sources[0].Label)
        return translated(_PIECES, {"count": str(len(self._sources))})

    def _build(self) -> None:
        layout = QtGui.QFormLayout(self.form)
        self._spacing = QtGui.QComboBox()
        self._spacing.setObjectName("spacing")
        self._spacing.setToolTip(translated(_SPACING_TIP))
        for spacing, text in _SPACINGS.items():
            self._spacing.addItem(translated(text), spacing.value)
        caption = QtGui.QLabel(translated(_SPACING))
        caption.setToolTip(self._spacing.toolTip())
        layout.addRow(caption, self._spacing)
        layout.addRow(self._build_grid())
        self._copy_joints = _checkbox("copyJoints", _COPY_JOINTS, _COPY_JOINTS_TIP, True)
        layout.addRow(self._copy_joints)
        self._follow = _checkbox("followResize", _FOLLOW, _FOLLOW_TIP, False)
        layout.addRow(self._follow)
        self._summary = message_label("summaryLabel", hint=True)
        self._warning = message_label("warningLabel", hint=True)
        self._warning.setStyleSheet(_WARNING_STYLE)
        self._error = message_label("errorLabel", error=True)
        for label in (self._summary, self._warning, self._error):
            layout.addRow(label)
            label.setVisible(False)

    def _build_grid(self) -> Widget:
        """Tableau des axes : une légende par colonne de saisie, puis une ligne par axe."""
        grid = QtGui.QWidget()
        table = QtGui.QGridLayout(grid)
        table.setContentsMargins(0, 0, 0, 0)
        for column, (name, text) in enumerate(COLUMN_CAPTIONS, start=1):
            caption = QtGui.QLabel(translated(text))
            table.addWidget(caption, 0, column)
            self._captions[name] = caption
        for line, row in enumerate(self._rows.values(), start=1):
            for column, widget in enumerate(row.widgets()):
                table.addWidget(widget, line, column)
        return grid

    def _fill(self, repeat: DocumentObject | None) -> None:
        """Champs aux valeurs de la répétition modifiée, ou aux valeurs par défaut."""
        enabled = any(furniture_of(source) is not None for source in self._sources_now())
        self._follow.setEnabled(enabled)
        self._follow.setToolTip(translated(_FOLLOW_TIP if enabled else _FOLLOW_DISABLED_TIP))
        with self._guard:
            if repeat is None:
                self._defaults()
            else:
                self._load(repeat)
            self._show_rows()

    def _defaults(self) -> None:
        """X actif avec ``DEFAULT_COUNT`` copies, Y et Z inactifs ; pas = cote des pièces."""
        for axis, row in self._rows.items():
            row.load(None, self._default_step(axis))
        step = self._default_step(RepeatAxis.X)
        cells = DEFAULT_COUNT + 1
        line = AxisRepeat(RepeatAxis.X, cells, step, round(step * cells, 6))
        self._rows[RepeatAxis.X].load(line, step)

    def _load(self, repeat: DocumentObject) -> None:
        self._spacing.setCurrentIndex(self._spacing.findData(str(repeat.Spacing)))
        lines = {line.axis: line for line in stored_lines(repeat)}
        for axis, row in self._rows.items():
            row.load(lines.get(axis), self._default_step(axis))
        self._steps_edited = set(lines)
        self._copy_joints.setChecked(bool(repeat.CopyJoints))
        self._follow.setChecked(bool(repeat.FollowResize) and self._follow.isEnabled())

    def _connect(self) -> None:
        connect(self._spacing, "currentIndexChanged(int)", self._update)
        for axis, row in self._rows.items():
            connect(row.active, "toggled(bool)", partial(self._axis_toggled, axis))
            connect(row.count, "valueChanged(int)", self._update)
            connect(row.step, "valueChanged(double)", partial(self._step_changed, axis))
            connect(row.span, "valueChanged(double)", self._update)
            connect(row.reverse, "toggled(bool)", self._update)
        for box in (self._copy_joints, self._follow):
            connect(box, "toggled(bool)", self._update)

    # --- Lecture des saisies --------------------------------------------------------------

    def _sources_now(self) -> list[DocumentObject]:
        """Pièces répétées : celles de la commande, ou celles de la répétition modifiée."""
        repeat = self._repeat()
        return sources_of(repeat) if repeat is not None else self._sources

    def _repeat(self) -> DocumentObject | None:
        """Répétition du panneau (créée par l'aperçu, ou modifiée), ``None`` avant la première."""
        name = self._repeat_name
        return self.doc.getObject(name) if name is not None else None

    def _spacing_mode(self) -> SpacingMode:
        return SpacingMode(str(self._spacing.itemData(self._spacing.currentIndex())))

    def params(self) -> RepeatParams:
        """Paramètres saisis ; ``ValueError`` traduite si le noyau les refuse (aucun axe actif,
        total de copies au-delà du maximum, pas nul…)."""
        lines = tuple(row.line() for row in self._rows.values() if row.checked())
        with translated_errors():
            if not lines:
                raise RepeatError(NO_AXIS, {})
            return RepeatParams(
                spacing=self._spacing_mode(),
                grid=lines,
                copy_joints=self._copy_joints.isChecked(),
                follow_resize=self._follow.isChecked() and self._follow.isEnabled(),
            )

    def _default_step(self, axis: RepeatAxis) -> float:
        """Cote des pièces sur ``axis`` : pas qui joint les copies sans les chevaucher."""
        try:
            return round(source_extent(self._sources_now(), axis), 6) or 100.0
        except ValueError:
            return 100.0

    # --- Aperçu ---------------------------------------------------------------------------

    def _show_rows(self) -> None:
        """Seuls les champs que le mode de saisie utilise sont visibles."""
        spacing = self._spacing_mode()
        used = uses(spacing)
        for name, caption in self._captions.items():
            caption.setVisible(name in used)
        for row in self._rows.values():
            row.show_for(spacing)

    def _step_changed(self, axis: RepeatAxis, *_value: object) -> None:
        if not self._guard.active:
            self._steps_edited.add(axis)
        self._update()

    def _axis_toggled(self, axis: RepeatAxis, checked: bool) -> None:
        """Axe activé : tant que son pas n'a pas été saisi, il suit la cote des pièces sur cet axe
        (aucun chevauchement par défaut)."""
        if self._guard.active:
            return
        if checked and axis not in self._steps_edited:
            with self._guard:
                self._rows[axis].step.setProperty("rawValue", self._default_step(axis))
        self._update()

    def _update(self, *_changed: object) -> None:
        """Aperçu recalculé pour la saisie : copies créées ou ajustées par l'api, résumé et
        avertissement de chevauchement, ou refus en rouge (aperçu inchangé, « OK » grisé)."""
        if self._guard.active or self.closed:
            return
        self._show_rows()
        summary, warning, error = "", "", ""
        try:
            params = self.params()
            sources = self._sources_now()
            grid = resolve_for(sources, params)
            self._apply(sources, params)
            self._show_resolved(params.spacing, grid)
            summary = summary_text(grid)
            warning = overlap_text(grid, source_extents(sources, [a.axis for a in grid.axes]))
        except (TypeError, ValueError, KeyError) as refusal:
            error = str(refusal.args[0] if isinstance(refusal, KeyError) else refusal)
        except Exception as failure:  # OCC, objet en erreur : aperçu abandonné, rien ne reste
            self._restart()
            error = translated(_UNEXPECTED, {"reason": str(failure) or type(failure).__name__})
        self._refused = bool(error)
        show_message(self._summary, summary)
        show_message(self._warning, warning)
        show_message(self._error, error)
        self._refresh_ok()

    def _show_resolved(self, spacing: SpacingMode, grid: ResolvedGrid) -> None:
        """Valeur calculée par le mode de saisie (pas ou nombre), gardée dans son champ masqué :
        elle est reprise si l'on change de mode."""
        with self._guard:
            for resolved in grid.axes:
                row = self._rows[resolved.axis]
                if spacing is SpacingMode.COUNT_ON_SPAN:
                    row.step.setProperty("rawValue", resolved.step)
                elif spacing is SpacingMode.STEP_ON_SPAN:
                    row.count.setValue(max(DEFAULT_CELLS, resolved.cells))

    def _apply(self, sources: Sequence[DocumentObject], params: RepeatParams) -> None:
        """Copies de l'aperçu : répétition créée à la première saisie acceptée, ajustée ensuite
        (copies ajoutées ou retirées, pas et expressions réécrits) ; dans la transaction du
        panneau, un seul recalcul."""
        repeat = self._repeat()
        if repeat is None:
            repeat = api.make_repeat(sources, params, transaction=False)
            self._repeat_name = repeat.Name
        else:
            api.edit_repeat(repeat, params, transaction=False)
        ensure_view_provider(repeat)

    def _restart(self) -> None:
        """Transaction abandonnée (aperçu et répétition créée disparaissent, la répétition
        modifiée retrouve son réglage) puis rouverte, vide."""
        close_transaction(self._transaction, abort=True)
        title = CREATE_TRANSACTION if self.creating else EDIT_TRANSACTION
        self.doc.openTransaction(translated(title))
        self._transaction = App.getActiveTransaction()
        if self.creating:
            self._repeat_name = None

    def _refresh_ok(self) -> None:
        """« OK » grisé tant que la saisie est refusée (sans effet panneau fermé ou pas affiché)."""
        if not self.closed:
            set_ok_enabled(self.form, not self._refused)

    # --- Cycle de vie (FreeCAD) -----------------------------------------------------------

    def watch_document(self, edited: DocumentObject | None = None) -> None:
        """Panneau affiché : surveillance du document, puis état du bouton « OK »."""
        super().watch_document(edited)
        self._refresh_ok()

    def accept(self) -> bool:
        """« OK » : la transaction devient une seule entrée d'annulation ; sans répétition ou
        avec une saisie refusée, le panneau reste ouvert."""
        if self._refused or self._repeat() is None:
            return False
        return super().accept()


def open_panel(sources: Sequence[DocumentObject]) -> None:
    """Ouvre le panneau de création, dans la transaction déjà ouverte par la commande ; une
    exception l'abandonne."""
    doc = sources[0].Document
    base.show_panel(partial(RepeatTaskPanel, doc, list(sources)))


def start_editing(repeat: DocumentObject, edited: DocumentObject | None = None) -> bool:
    """Ouvre le panneau prérempli de ``repeat`` dans la transaction « Modifier la répétition » ;
    ``edited`` : objet en mode édition si ce n'est pas la répétition (une de ses copies). Faux si
    un autre panneau de tâche est déjà ouvert."""
    return base.start_editing(
        repeat.Document,
        EDIT_TRANSACTION,
        partial(RepeatTaskPanel, repeat.Document, sources_of(repeat), repeat),
        edited or repeat,
    )
