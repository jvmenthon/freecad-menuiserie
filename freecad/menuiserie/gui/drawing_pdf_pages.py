# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plusieurs plans dans un seul PDF (issue #153, retour de jv du 24/11, maquette B).

TechDraw n'écrit qu'une page par PDF. Chaque page est donc exportée en SVG par TechDraw
(``TechDrawGui.exportPageAsSvg`` : rendu d'export, sans cadres ni sélection), puis dessinée en
vectoriel par Qt (``QSvgRenderer``) sur une page de ``QPdfWriter`` à la taille de sa feuille.
Rien n'est installé ; le fichier est mis en place d'un coup (écriture atomique) une fois écrit.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import FreeCADGui as Gui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.cutlist_export import (
    PDF_SUFFIX,
    replace_atomically,
    validated_path,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.drawing_pdf import is_page, show_page

__all__ = ["export_pages_pdf", "proposed_plans_path", "sheet_mm"]

PDF_MAGIC: Final = b"%PDF"
RESOLUTION_DPI: Final = 600
DEFAULT_SHEET_MM: Final = (420.0, 297.0)  # A3 paysage, si la page ne donne pas sa taille
_FORBIDDEN_IN_NAME: Final = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_FILE_NAME: Final = QT_TRANSLATE_NOOP("Menuiserie", "{document} - plans")
_NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Export impossible : aucun plan à exporter.")
_NOT_A_PAGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : « {label} » n'est pas une page TechDraw."
)
_NOT_WRITTEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : le fichier « {path} » n'a pas pu être écrit."
)


def proposed_plans_path(doc: Document, home: Path | None = None) -> Path:
    """« <document> - plans.pdf » à côté du fichier du document, sinon dans le dossier
    personnel ; les caractères interdits dans un nom de fichier sont remplacés par « _ »."""
    folder = Path(doc.FileName).parent if doc.FileName else (home or Path.home())
    cleaned = _FORBIDDEN_IN_NAME.sub("_", str(doc.Label)).strip().rstrip(".").strip()
    return folder / (translated(_FILE_NAME, {"document": cleaned or "Document"}) + PDF_SUFFIX)


def _length(value: object) -> float:
    number = float(getattr(value, "Value", value))  # type: ignore[arg-type]
    if not 1.0 <= number <= 10_000.0:
        raise ValueError(number)
    return number


def sheet_mm(page: DocumentObject) -> tuple[float, float]:
    """Largeur et hauteur de la feuille de ``page`` en mm (celles de son gabarit), A3 paysage
    si elles manquent ou sont invalides."""
    template = getattr(page, "Template", None)
    try:
        return _length(template.Width), _length(template.Height)  # type: ignore[union-attr]
    except (AttributeError, TypeError, ValueError):
        return DEFAULT_SHEET_MM


def _enum(owner: Any, group: str, name: str) -> Any:
    """Valeur d'énumération Qt, nommée à l'ancienne (PySide2) ou rangée (PySide6)."""
    return getattr(owner, name, None) or getattr(getattr(owner, group), name)


def _layout(qt_core: Any, qt_gui: Any, size: tuple[float, float]) -> Any:
    millimeter = _enum(qt_gui.QPageSize, "Unit", "Millimeter")
    exact = _enum(qt_gui.QPageSize, "SizeMatchPolicy", "ExactMatch")
    page_size = qt_gui.QPageSize(qt_core.QSizeF(*size), millimeter, "", exact)
    portrait = _enum(qt_gui.QPageLayout, "Orientation", "Portrait")
    return qt_gui.QPageLayout(page_size, portrait, qt_core.QMarginsF(0, 0, 0, 0))


def _draw(pages: Sequence[DocumentObject], temporary: Path, folder: Path) -> None:
    """Écrit ``pages`` dans le PDF ``temporary`` (SVG intermédiaires dans ``folder``) ;
    ``OSError`` si une page ou le fichier n'a pas été produit."""
    import TechDrawGui
    from PySide import QtCore, QtGui, QtSvg

    writer = QtGui.QPdfWriter(str(temporary))
    writer.setResolution(RESOLUTION_DPI)
    writer.setCreator("FreeCAD Menuiserie")
    painter = None
    try:
        for index, page in enumerate(pages):
            show_page(page)  # TechDraw exporte une page depuis sa vue
            Gui.updateGui()
            svg = folder / f"page-{index}.svg"
            TechDrawGui.exportPageAsSvg(page, str(svg))
            renderer = QtSvg.QSvgRenderer(str(svg))
            if not renderer.isValid():
                raise OSError(str(svg))
            writer.setPageLayout(_layout(QtCore, QtGui, sheet_mm(page)))
            if painter is None:  # la première page prend sa taille avant le peintre
                painter = QtGui.QPainter(writer)
            elif not writer.newPage():
                raise OSError(str(temporary))
            area = writer.pageLayout().paintRectPixels(writer.resolution())
            renderer.render(painter, QtCore.QRectF(area))
    finally:
        if painter is not None:
            painter.end()
    del painter, writer  # fermeture du fichier avant relecture
    with temporary.open("r+b") as written:  # écriture permise : fsync l'exige sous Windows
        if written.read(len(PDF_MAGIC)) != PDF_MAGIC:
            raise OSError(str(temporary))
        os.fsync(written.fileno())


def export_pages_pdf(pages: Sequence[DocumentObject], path: str | Path) -> Path:
    """Écrit ``pages`` (pages TechDraw), une par feuille et dans l'ordre, dans le PDF ``path``
    et renvoie le chemin. ``ValueError`` traduite s'il n'y a rien à écrire, pour un objet qui
    n'est pas une page, un chemin refusé ou un fichier non écrit ; un fichier déjà là n'est
    remplacé qu'en cas de succès."""
    if not pages:
        raise ValueError(translated(_NOTHING))
    for page in pages:
        if not is_page(page):
            raise ValueError(translated(_NOT_A_PAGE, {"label": str(getattr(page, "Label", page))}))
    target = validated_path(path, PDF_SUFFIX)

    def produce(temporary: Path) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _draw(pages, temporary, Path(folder))

    try:
        replace_atomically(target, produce)
    except OSError as error:
        raise ValueError(translated(_NOT_WRITTEN, {"path": str(target)})) from error
    return target
