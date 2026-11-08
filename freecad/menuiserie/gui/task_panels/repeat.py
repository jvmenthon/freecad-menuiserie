# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche « Répéter » et « Modifier la répétition » (lot R-c, ADR 0043).

Le panneau règle une répétition linéaire (mode de saisie, nombre, pas, longueur, axe, sens,
assemblages recopiés, suivi du redimensionnement) et montre aussitôt les copies dans la vue 3D :
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
from freecad.menuiserie.core.joints import mm_text
from freecad.menuiserie.core.repeat import (
    MAX_COPIES,
    RepeatAxis,
    RepeatParams,
    Resolved,
    SpacingMode,
    overlaps,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.repeat import sources_of
from freecad.menuiserie.features.repeat_copies import resolve_for, source_extent
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
from freecad.menuiserie.gui.task_panels.furniture_widgets import (
    message_label,
    quantity_field,
    show_message,
)
from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

__all__ = ["RepeatTaskPanel", "open_panel", "start_editing"]

FORM_NAME: Final = "RepeatTaskPanel"
ICON: Final = "Menuiserie_Repeat.svg"
CREATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier la répétition")
DEFAULT_COUNT: Final = 3
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
    "Nombre et pas : vous donnez les deux. Nombre sur une longueur : le pas est calculé pour "
    "remplir la longueur. Pas sur une longueur : le nombre de copies est calculé.",
)
_COUNT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nombre de copies")
_COUNT_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Copies en plus de la pièce d'origine (de 1 à {max})."
)
_STEP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pas")
_STEP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance entre deux copies, mesurée sur l'axe (d'une face à la même face de la suivante).",
)
_SPAN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Longueur")
_SPAN_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Longueur à remplir sur l'axe, pièce d'origine comprise."
)
_AXIS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Axe")
_AXIS_TIP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Axe global de la répétition.")
_REVERSE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Inverser")
_REVERSE_TIP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répète dans le sens négatif de l'axe.")
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
    "Cochée : quand l'ensemble est redimensionné, le pas est recalculé et les copies se "
    "répartissent sur la nouvelle longueur ; leur nombre ne change pas. Décochée : le pas reste "
    "fixe.",
)
_FOLLOW_DISABLED_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Grisée : la pièce répétée n'est dans aucun ensemble, il n'y a pas de redimensionnement à "
    "suivre. Placez-la d'abord dans un ensemble.",
)
_SUMMARY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} copies en plus de l'original, pas de {step} mm."
)
_OVERLAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Attention : le pas de {step} mm est inférieur à la cote de la pièce ({extent} mm) sur cet "
    "axe, les copies se chevauchent.",
)
_UNEXPECTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La répétition n'a pas pu être construite avec ces valeurs ({reason}). Modifiez le nombre, "
    "le pas ou la longueur.",
)
_WARNING_STYLE: Final = "color: #b35c00;"
_AXES: Final = (RepeatAxis.X, RepeatAxis.Y, RepeatAxis.Z)


def _spacing_rows(spacing: SpacingMode) -> tuple[str, ...]:
    """Champs de saisie utilisés par le mode ``spacing``."""
    return {
        SpacingMode.COUNT_AND_STEP: ("count", "step"),
        SpacingMode.COUNT_ON_SPAN: ("count", "span"),
        SpacingMode.STEP_ON_SPAN: ("step", "span"),
    }[spacing]


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
        self._step_edited = repeat is not None
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        label = self._sources_label() if repeat is None else quoted_value(repeat.Label)
        self.form.setWindowTitle(base.panel_title(label, repeat is None, _TITLE))
        self._rows: dict[str, tuple[Widget, Widget]] = {}
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

    def _row(self, layout: Widget, name: str, label: str, tip: str, field: Widget) -> None:
        field.setToolTip(translated(tip, {"max": str(MAX_COPIES)}))
        caption = QtGui.QLabel(translated(label))
        caption.setToolTip(field.toolTip())
        layout.addRow(caption, field)
        self._rows[name] = (caption, field)

    def _build(self) -> None:
        layout = QtGui.QFormLayout(self.form)
        self._spacing = QtGui.QComboBox()
        self._spacing.setObjectName("spacing")
        for spacing, text in _SPACINGS.items():
            self._spacing.addItem(translated(text), spacing.value)
        self._row(layout, "spacing", _SPACING, _SPACING_TIP, self._spacing)
        self._count = QtGui.QSpinBox()
        self._count.setObjectName("count")
        self._count.setRange(1, MAX_COPIES)
        self._count.setKeyboardTracking(False)  # aperçu à la fin de la saisie
        self._row(layout, "count", _COUNT, _COUNT_TIP, self._count)
        self._step = quantity_field("step", 0.0)
        self._row(layout, "step", _STEP, _STEP_TIP, self._step)
        self._span = quantity_field("span", 0.0)
        self._row(layout, "span", _SPAN, _SPAN_TIP, self._span)
        self._build_axis(layout)
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

    def _build_axis(self, layout: Widget) -> None:
        """Axes X, Y, Z (boutons exclusifs) et case « Inverser » sur une ligne."""
        row = QtGui.QWidget()
        box = QtGui.QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        self._axes: dict[RepeatAxis, Widget] = {}
        for axis in _AXES:
            button = QtGui.QRadioButton(axis.value)
            button.setObjectName(f"axis{axis.value}")
            box.addWidget(button)
            self._axes[axis] = button
        self._axes[RepeatAxis.X].setChecked(True)
        self._reverse = _checkbox("reverse", _REVERSE, _REVERSE_TIP, False)
        box.addWidget(self._reverse)
        self._row(layout, "axis", _AXIS, _AXIS_TIP, row)

    def _fill(self, repeat: DocumentObject | None) -> None:
        """Champs aux valeurs de la répétition modifiée, ou aux valeurs par défaut."""
        enabled = any(furniture_of(source) is not None for source in self._sources_now())
        self._follow.setEnabled(enabled)
        self._follow.setToolTip(translated(_FOLLOW_TIP if enabled else _FOLLOW_DISABLED_TIP))
        with self._guard:
            if repeat is None:
                self._count.setValue(DEFAULT_COUNT)
                step = self._default_step(RepeatAxis.X)
                self._step.setProperty("rawValue", step)
                self._span.setProperty("rawValue", round(step * (DEFAULT_COUNT + 1), 6))
            else:
                self._load(repeat)
            self._show_rows()

    def _load(self, repeat: DocumentObject) -> None:
        self._spacing.setCurrentIndex(self._spacing.findData(str(repeat.Spacing)))
        self._count.setValue(max(1, min(MAX_COPIES, int(repeat.Count))))
        self._step.setProperty("rawValue", float(repeat.Step.Value))
        self._span.setProperty("rawValue", float(repeat.Span.Value))
        self._axes[RepeatAxis(str(repeat.Axis))].setChecked(True)
        self._reverse.setChecked(bool(repeat.Reverse))
        self._copy_joints.setChecked(bool(repeat.CopyJoints))
        self._follow.setChecked(bool(repeat.FollowResize) and self._follow.isEnabled())

    def _connect(self) -> None:
        connect(self._spacing, "currentIndexChanged(int)", self._update)
        connect(self._count, "valueChanged(int)", self._update)
        connect(self._step, "valueChanged(double)", self._step_changed)
        connect(self._span, "valueChanged(double)", self._update)
        for axis, button in self._axes.items():
            connect(button, "toggled(bool)", partial(self._axis_changed, axis))
        for box in (self._reverse, self._copy_joints, self._follow):
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

    def _axis(self) -> RepeatAxis:
        return next(axis for axis, button in self._axes.items() if button.isChecked())

    def _spacing_mode(self) -> SpacingMode:
        return SpacingMode(str(self._spacing.itemData(self._spacing.currentIndex())))

    def params(self) -> RepeatParams:
        """Paramètres saisis ; ``ValueError`` traduite si le noyau les refuse."""
        with translated_errors():
            return RepeatParams(
                spacing=self._spacing_mode(),
                count=int(self._count.value()),
                step=float(self._step.property("rawValue")),
                span=float(self._span.property("rawValue")),
                axis=self._axis(),
                reverse=self._reverse.isChecked(),
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
        used = _spacing_rows(self._spacing_mode())
        for name, (caption, field) in self._rows.items():
            visible = name not in ("count", "step", "span") or name in used
            caption.setVisible(visible)
            field.setVisible(visible)

    def _step_changed(self, *_value: object) -> None:
        if not self._guard.active:
            self._step_edited = True
        self._update()

    def _axis_changed(self, axis: RepeatAxis, checked: bool) -> None:
        """Nouvel axe : tant que le pas n'a pas été saisi, il suit la cote des pièces sur cet
        axe (aucun chevauchement par défaut)."""
        if not checked or self._guard.active:
            return
        if not self._step_edited:
            with self._guard:
                self._step.setProperty("rawValue", self._default_step(axis))
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
            resolved = resolve_for(sources, params)
            self._apply(sources, params)
            self._show_resolved(params.spacing, resolved)
            extent = source_extent(sources, params.axis)
            summary = translated(
                _SUMMARY, {"count": str(resolved.count), "step": mm_text(resolved.step)}
            )
            if overlaps(resolved, extent):
                warning = translated(
                    _OVERLAP, {"step": mm_text(resolved.step), "extent": mm_text(extent)}
                )
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

    def _show_resolved(self, spacing: SpacingMode, resolved: Resolved) -> None:
        """Valeur calculée par le mode de saisie (pas ou nombre), gardée dans son champ masqué :
        elle est reprise si l'on change de mode."""
        with self._guard:
            if spacing is SpacingMode.COUNT_ON_SPAN:
                self._step.setProperty("rawValue", resolved.step)
            elif spacing is SpacingMode.STEP_ON_SPAN:
                self._count.setValue(resolved.count)

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


def start_editing(repeat: DocumentObject) -> bool:
    """Ouvre le panneau prérempli de ``repeat`` dans la transaction « Modifier la répétition » ;
    faux si un autre panneau de tâche est déjà ouvert."""
    return base.start_editing(
        repeat.Document,
        EDIT_TRANSACTION,
        partial(RepeatTaskPanel, repeat.Document, sources_of(repeat), repeat),
        repeat,
    )
