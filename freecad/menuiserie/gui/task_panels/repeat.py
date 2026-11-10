# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche « Répéter » et « Modifier la répétition » (ADR 0043, 0045 et 0047).

Réglage d'une répétition en grille : un mode de saisie (« nombre sur une longueur » par défaut),
trois lignes X, Y, Z (:mod:`.repeat_rows`, une butée par axe : :mod:`.repeat_stops`, choisie dès
l'ouverture en création, l'axe s'en déduit), options. Chaque saisie validée recalcule l'aperçu par
l'api dans la transaction du panneau : « OK » la valide, « Annuler » l'abandonne. Une saisie
refusée s'affiche en rouge (« OK » grisé, aperçu gardé) ; un chevauchement n'est qu'un
avertissement. Champs : norme « Entrées utilisateur » (``CONTRIBUTING.md``).
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
from freecad.menuiserie.features.repeat_joints import not_copied_warning
from freecad.menuiserie.features.repeat_stop import Stops, bounded_params, stored_stops
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
from freecad.menuiserie.gui.task_panels.repeat_stops import StopControls, collision_text
from freecad.menuiserie.gui.task_panels.repeat_texts import (
    COPY_JOINTS,
    COPY_JOINTS_TIP,
    DEDUCT,
    DEDUCT_TIP,
    FOLLOW,
    FOLLOW_DISABLED_TIP,
    FOLLOW_TIP,
    SPACING,
    SPACING_TIP,
    SPACINGS,
    UNEXPECTED,
    checkbox,
)
from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

__all__ = ["RepeatTaskPanel", "open_panel", "start_editing"]

FORM_NAME: Final = "RepeatTaskPanel"
ICON: Final = "Menuiserie_Repeat.svg"
CREATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier la répétition")
DEFAULT_COUNT: Final = 1  # copies proposées à l'ouverture (2 éléments sur X)
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter « {label} »")
_PIECES: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} pièces")
_WARNING_STYLE: Final = "color: #b35c00;"
_AXES: Final = (RepeatAxis.X, RepeatAxis.Y, RepeatAxis.Z)


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
        self._overlapping = False  # copies qui se chevauchent (avertissement)
        self._steps_edited: set[RepeatAxis] = set()  # pas saisis : ils ne suivent plus la cote
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        label = self._sources_label() if repeat is None else quoted_value(repeat.Label)
        self.form.setWindowTitle(base.panel_title(label, repeat is None, _TITLE))
        self._rows = {axis: AxisRow(axis) for axis in _AXES}
        self._stops = StopControls(doc.Name, self._rows, self._update, self._sources_now)
        self._captions: dict[str, Widget] = {}
        self._build()
        self._stops.settle_with(self._deduct, lambda: (self._refused, self._overlapping))
        self._fill(repeat)
        self._connect()
        if repeat is None:
            self._update()  # aperçu des valeurs par défaut
            self._stops.pick_auto()  # le premier clic dans la vue 3D est la butée

    # --- Construction ---------------------------------------------------------------------

    def _sources_label(self) -> str:
        if len(self._sources) == 1:
            return quoted_value(self._sources[0].Label)
        return translated(_PIECES, {"count": str(len(self._sources))})

    def _build(self) -> None:
        layout = QtGui.QFormLayout(self.form)
        self._spacing = QtGui.QComboBox()
        self._spacing.setObjectName("spacing")
        self._spacing.setToolTip(translated(SPACING_TIP))
        for spacing, text in SPACINGS.items():
            self._spacing.addItem(translated(text), spacing.value)
        caption = QtGui.QLabel(translated(SPACING))
        caption.setToolTip(self._spacing.toolTip())
        layout.addRow(caption, self._spacing)
        layout.addRow(self._build_grid())
        self._copy_joints = checkbox("copyJoints", COPY_JOINTS, COPY_JOINTS_TIP, True)
        layout.addRow(self._copy_joints)
        self._follow = checkbox("followResize", FOLLOW, FOLLOW_TIP, False)
        layout.addRow(self._follow)
        self._deduct = checkbox("deductThickness", DEDUCT, DEDUCT_TIP, True)
        layout.addRow(self._deduct)
        self._summary = message_label("summaryLabel", hint=True)
        self._warning = message_label("warningLabel", hint=True)
        self._warning.setStyleSheet(_WARNING_STYLE)
        self._error = message_label("errorLabel", error=True)
        for label in (self._summary, self._warning, self._error):
            layout.addRow(label)
            label.setVisible(False)
        self.watch_widgets(self._summary, self._warning, self._error)

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
        self._follow.setToolTip(translated(FOLLOW_TIP if enabled else FOLLOW_DISABLED_TIP))
        with self._guard:
            if repeat is None:
                self._defaults()
            else:
                self._load(repeat)
            self._show_rows()

    def _defaults(self) -> None:
        """« Nombre sur une longueur », X actif avec ``DEFAULT_COUNT`` copies, Y et Z inactifs ;
        pas = cote des pièces."""
        self._spacing.setCurrentIndex(self._spacing.findData(SpacingMode.COUNT_ON_SPAN.value))
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
        self._deduct.setChecked(bool(getattr(repeat, "DeductThickness", True)))
        self._stops.stops = stored_stops(repeat)
        self._follow.setChecked(bool(repeat.FollowResize) and self._follow.isEnabled())

    def _connect(self) -> None:
        connect(self._spacing, "currentIndexChanged(int)", self._update)
        for axis, row in self._rows.items():
            connect(row.active, "toggled(bool)", partial(self._axis_toggled, axis))
            connect(row.count, "valueChanged(int)", self._update)
            connect(row.step, "valueChanged(double)", partial(self._step_changed, axis))
            connect(row.span, "valueChanged(double)", self._update)
            connect(row.reverse, "toggled(bool)", self._update)
            connect(row.stop, "clicked()", partial(self._stops.pick, axis))
            connect(row.stop_clear, "clicked()", partial(self._stops.clear, axis))
        for box in (self._copy_joints, self._follow, self._deduct):
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
                deduct_thickness=self._deduct.isChecked(),
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
        for axis, row in self._rows.items():
            row.show_for(spacing)
            self._stops.show(axis)
        self._deduct.setVisible(spacing is not SpacingMode.COUNT_AND_STEP)

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
        self._overlapping = False
        try:
            params = self.params()
            sources = self._sources_now()
            stops = self._stops.active(params)
            params = bounded_params(sources, params, stops, self._repeat())
            grid = resolve_for(sources, params)
            self._apply(sources, params, stops)
            self._show_resolved(params, grid)
            summary = summary_text(grid)
            warning = overlap_text(grid, source_extents(sources, [a.axis for a in grid.axes]))
            self._overlapping = bool(warning)
            warning = "\n".join(
                filter(None, (warning, collision_text(params, stops), self._not_copied()))
            )
        except (TypeError, ValueError, KeyError) as refusal:
            error = str(refusal.args[0] if isinstance(refusal, KeyError) else refusal)
        except Exception as failure:  # OCC, objet en erreur : aperçu abandonné, rien ne reste
            self._restart()
            error = translated(UNEXPECTED, {"reason": str(failure) or type(failure).__name__})
        self._refused = bool(error)
        show_message(self._summary, summary)
        show_message(self._warning, warning)
        show_message(self._error, error)
        self._refresh_ok()

    def _release_display(self) -> None:
        """Fermeture : l'observateur de sélection n'est jamais laissé en place."""
        self._stops.close()

    def _not_copied(self) -> str:
        """Avertissement des assemblages impossibles, donc non recopiés (vide sinon)."""
        repeat = self._repeat()
        return "" if repeat is None else not_copied_warning(repeat)

    def _show_resolved(self, params: RepeatParams, grid: ResolvedGrid) -> None:
        """Valeur calculée par le mode de saisie (pas ou nombre), gardée dans son champ masqué :
        elle est reprise si l'on change de mode. Une longueur donnée par une butée est affichée
        (lecture seule)."""
        with self._guard:
            for resolved in grid.axes:
                row = self._rows[resolved.axis]
                if params.spacing is SpacingMode.COUNT_ON_SPAN:
                    row.step.setProperty("rawValue", resolved.step)
                elif params.spacing is SpacingMode.STEP_ON_SPAN:
                    row.count.setValue(max(DEFAULT_CELLS, resolved.cells))
            for line in params.lines:
                if line.axis in self._stops.stops:
                    self._rows[line.axis].span.setProperty("rawValue", line.span)

    def _apply(self, sources: Sequence[DocumentObject], params: RepeatParams, stops: Stops) -> None:
        """Copies de l'aperçu : répétition créée à la première saisie acceptée, ajustée ensuite
        (copies ajoutées ou retirées, pas et expressions réécrits) ; dans la transaction du
        panneau, un seul recalcul."""
        repeat = self._repeat()
        if repeat is None:
            repeat = api.make_repeat(sources, params, transaction=False, stops=stops)
            self._repeat_name = repeat.Name
        else:
            api.edit_repeat(repeat, params, transaction=False, stops=stops)
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
