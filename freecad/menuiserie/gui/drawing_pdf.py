# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export d'une page TechDraw en PDF (issue #153, ADR 0053).

Le PDF est produit par TechDraw lui-même (``TechDrawGui.exportPageAsPdf``) dans un fichier
temporaire, puis mis en place d'un coup (même écriture atomique que la liste de débit) ; le chemin
est validé avant (extension, dossier existant et accessible).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.cutlist_export import (
    PDF_SUFFIX,
    replace_atomically,
    validated_path,
    with_suffix,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.commands.cutlist import show_status

__all__ = ["ask_pdf_path", "export_page_pdf", "proposed_pdf_path", "show_page"]

_FORBIDDEN_IN_NAME: Final = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_FILE_NAME: Final = QT_TRANSLATE_NOOP("Menuiserie", "{page} - plan")
_EXPORTED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan exporté dans « {path} ».")
_DIALOG_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Exporter le plan")
_PDF_FILTER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fichiers PDF (*.pdf)")
_NOT_A_PAGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : « {label} » n'est pas une page TechDraw."
)
_NOT_WRITTEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : TechDraw n'a pas écrit le fichier « {path} »."
)


def proposed_pdf_path(page: DocumentObject, home: Path | None = None) -> Path:
    """« <document> - plan.pdf » à côté du fichier du document, sinon dans le dossier personnel.
    Les caractères interdits dans un nom de fichier sont remplacés par « _ »."""
    doc = page.Document
    folder = Path(doc.FileName).parent if doc.FileName else (home or Path.home())
    cleaned = _FORBIDDEN_IN_NAME.sub("_", str(doc.Label)).strip().rstrip(".").strip()
    return folder / (translated(_FILE_NAME, {"page": cleaned or "Document"}) + PDF_SUFFIX)


def ask_pdf_path(page: DocumentObject, parent: Any = None) -> Path | None:
    """Boîte d'enregistrement (filtre ``*.pdf``) ; ``None`` si l'utilisateur annule."""
    answer: Any = QtGui.QFileDialog.getSaveFileName(
        parent or Gui.getMainWindow(),
        translated(_DIALOG_TITLE),
        str(proposed_pdf_path(page)),
        translated(_PDF_FILTER),
    )
    chosen = answer[0] if isinstance(answer, tuple) else answer
    return Path(with_suffix(chosen, PDF_SUFFIX)) if chosen else None


def show_page(page: DocumentObject) -> None:
    """Ouvre ``page`` dans son onglet, comme un double-clic dans l'arbre."""
    view_object = getattr(page, "ViewObject", None)
    if view_object is None:
        return
    try:
        view_object.doubleClicked()
    except (AttributeError, RuntimeError):
        Gui.ActiveDocument.setEdit(page.Name)


def export_page_pdf(page: DocumentObject, path: str | Path) -> Path:
    """Écrit ``page`` (une ``TechDraw::DrawPage``) en PDF dans ``path`` et renvoie le chemin.
    ``ValueError`` traduite pour un chemin refusé, un objet qui n'est pas une page ou un fichier
    que TechDraw n'a pas écrit ; un fichier déjà là n'est remplacé qu'en cas de succès."""
    if getattr(page, "TypeId", None) != "TechDraw::DrawPage":
        raise ValueError(translated(_NOT_A_PAGE, {"label": str(getattr(page, "Label", page))}))
    target = validated_path(path, PDF_SUFFIX)
    import TechDrawGui

    show_page(page)  # TechDraw exporte la page depuis sa vue
    Gui.updateGui()

    def produce(temporary: Path) -> None:
        TechDrawGui.exportPageAsPdf(page, str(temporary))
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise ValueError(translated(_NOT_WRITTEN, {"path": str(target)}))

    replace_atomically(target, produce)
    return target


def export_with_dialog(page: DocumentObject) -> None:
    """Fichier demandé (rien si l'on annule), PDF écrit ; confirmation ou refus affichés."""
    path = ask_pdf_path(page)
    if path is None:
        return
    try:
        written = export_page_pdf(page, path)
    except (OSError, ValueError) as error:
        report_refusal(str(error))
        return
    show_status(translated(_EXPORTED, {"path": escaped_text(str(written))}))
