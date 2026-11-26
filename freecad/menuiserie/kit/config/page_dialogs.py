# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dialogues de l'échange de réglages, remplaçables (ADR 0069).

Qt par la couche ``PySide`` de FreeCAD. :class:`Dialogs` regroupe les quatre dialogues dont
l'échange a besoin (choix d'un fichier à écrire, à lire, aperçu, message) ; :func:`qt_dialogs`
donne les vrais, un test donne les siens et n'ouvre jamais de fenêtre modale.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide import QtGui

from . import import_model as model
from .import_model import ImportRow
from .page_import import ImportPreview
from .page_model import Translate, Widget

__all__ = ["Dialogs", "qt_dialogs"]


@dataclass(frozen=True)
class Dialogs:
    """Dialogues de l'échange. ``save_file`` et ``open_file`` (parent, titre, fichier proposé)
    rendent le fichier choisi, ``None`` si l'utilisateur annule ; ``preview`` (parent, lignes,
    en-tête, avertissement) rend les clés cochées, ``None`` s'il annule ; ``message`` (parent,
    texte, erreur ?) informe."""

    save_file: Callable[[Widget, str, Path], Path | None]
    open_file: Callable[[Widget, str, Path], Path | None]
    preview: Callable[[Widget, list[ImportRow], str, str], list[str] | None]
    message: Callable[[Widget, str, bool], None]


def qt_dialogs(translate: Translate) -> Dialogs:
    """Les dialogues Qt, textes traduits par ``translate``."""
    json_filter = translate(model.JSON_FILTER)
    title = translate(model.EXCHANGE_LABEL)

    def save_file(parent: Widget, caption: str, start: Path) -> Path | None:
        name, _filter = QtGui.QFileDialog.getSaveFileName(parent, caption, str(start), json_filter)
        return Path(name) if name else None

    def open_file(parent: Widget, caption: str, start: Path) -> Path | None:
        name, _filter = QtGui.QFileDialog.getOpenFileName(parent, caption, str(start), json_filter)
        return Path(name) if name else None

    def preview(
        parent: Widget, rows: list[ImportRow], header: str, warning: str
    ) -> list[str] | None:
        dialog = ImportPreview(rows, header, warning, translate, parent)
        return dialog.checked_keys() if dialog.exec() else None

    def message(parent: Widget, text: str, error: bool) -> None:
        box = QtGui.QMessageBox.warning if error else QtGui.QMessageBox.information
        box(parent, title, text)

    return Dialogs(save_file, open_file, preview, message)
