# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ligne « Réglages de l'atelier » de la page : boutons Exporter… et Importer… (ADR 0069).

Qt par la couche ``PySide`` de FreeCAD. Le module ne connaît ni le catalogue ni le format du
fichier : l'atelier fournit des :class:`ExchangeActions` (écrire, lire, reprendre) et, au besoin,
d'autres :class:`~.page_dialogs.Dialogs`. L'import ne modifie rien : les lignes cochées sont
confiées à ``take``, qui les reprend dans les champs de la page (écrits à OK ou Appliquer).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide import QtGui

from . import import_model as model
from .exchange import ExchangeError
from .import_model import ImportOffer, ImportRow
from .page_dialogs import Dialogs, qt_dialogs
from .page_model import ExtraRow, Translate, format_text, identity
from .page_rows import ignoring_arguments

__all__ = ["ExchangeActions", "ExchangeRow"]


@dataclass(frozen=True)
class ExchangeActions:
    """Ce que l'atelier fait pour l'échange. ``export_to`` et ``load`` lèvent
    :class:`~.exchange.ExchangeError` ; ``load`` ne modifie rien ; ``take`` reprend les lignes
    cochées dans la page ; ``has_unsaved`` dit si la page a des modifications non écrites."""

    default_file: Callable[[], Path]
    export_to: Callable[[Path], None]
    load: Callable[[Path], ImportOffer]
    error_message: Callable[[ExchangeError], str]
    take: Callable[[Sequence[ImportRow]], None]
    has_unsaved: Callable[[], bool]


class ExchangeRow:
    """Boutons Exporter… et Importer…, et leurs deux parcours."""

    def __init__(
        self,
        actions: ExchangeActions,
        group: str,
        translate: Translate = identity,
        dialogs: Dialogs | None = None,
    ) -> None:
        self._actions = actions
        self._group = group
        self._tr = translate
        self.dialogs = dialogs or qt_dialogs(translate)
        self.widget = QtGui.QWidget()
        layout = QtGui.QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.export_button = self._button(model.EXPORT, "exportButton", self.export_settings)
        self.import_button = self._button(model.IMPORT, "importButton", self.import_settings)
        layout.addWidget(self.export_button)
        layout.addWidget(self.import_button)
        layout.addStretch(1)

    def _button(self, text: str, name: str, slot: Callable[[], None]) -> QtGui.QPushButton:
        button = QtGui.QPushButton(self._tr(text))
        button.setObjectName(name)
        button.clicked.connect(ignoring_arguments(slot))
        return button

    def extra_row(self, before_group: str | None = None) -> ExtraRow:
        """Ligne à donner à la page, dans le groupe ``group`` donné à la construction."""
        return ExtraRow(
            self._group,
            model.EXCHANGE_LABEL,
            self.widget,
            model.EXCHANGE_TIP,
            before_group,
        )

    def _error(self, error: ExchangeError) -> None:
        self.dialogs.message(self.widget, self._actions.error_message(error), True)

    def export_settings(self) -> None:
        """Écrit les réglages enregistrés dans le fichier choisi. Les modifications de la page
        pas encore enregistrées n'y sont pas : le message de confirmation le rappelle."""
        title = self._tr(model.EXPORT_TITLE)
        path = self.dialogs.save_file(self.widget, title, self._actions.default_file())
        if path is None:
            return
        if not path.suffix:
            path = path.with_suffix(".json")
        try:
            self._actions.export_to(path)
        except ExchangeError as error:
            self._error(error)
            return
        text = format_text(self._tr(model.EXPORTED), path=path)
        if self._actions.has_unsaved():
            text += " " + self._tr(model.UNSAVED)
        self.dialogs.message(self.widget, text, False)

    def import_settings(self) -> None:
        """Lit le fichier choisi, montre l'aperçu et confie les lignes cochées à ``take``. Un
        fichier refusé ne change rien ; sans différence, un message le dit."""
        title = self._tr(model.IMPORT_FILE_TITLE)
        path = self.dialogs.open_file(self.widget, title, self._actions.default_file())
        if path is None:
            return
        try:
            offer = self._actions.load(path)
        except ExchangeError as error:
            self._error(error)
            return
        warning = model.ignored_text(offer.ignored, self._tr)
        if not offer.rows:
            text = " ".join(part for part in (self._tr(model.NO_CHANGE), warning) if part)
            self.dialogs.message(self.widget, text, False)
            return
        header = model.changes_header(str(path), len(offer.rows), self._tr)
        keys = self.dialogs.preview(self.widget, list(offer.rows), header, warning)
        if keys is None:
            return
        rows = model.chosen(offer.rows, keys)
        if rows:
            self._actions.take(rows)
