# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin du PDF de la liste de débit (J2g, critère P2, spécification J2 § 10).

Qt (``QTextDocument`` et ``QPdfWriter``, via le PySide de FreeCAD) exige une application
graphique (polices) : ce module n'est utilisable qu'avec l'interface, d'où sa place côté ``gui``.
Le HTML vient de ``features/cutlist_export.pdf_html`` ; la page est un A4 paysage de marges 10 mm.
Le fichier est écrit de façon atomique (``replace_atomically``) : un échec laisse l'ancien fichier.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.cutlist_export import replace_atomically
from freecad.menuiserie.features.i18n import translated

__all__ = ["MARGIN_MM", "PDF_MAGIC", "write_pdf"]

MARGIN_MM: Final = 10.0
PDF_MAGIC: Final = b"%PDF"
_RESOLUTION_DPI: Final = 150
# Largeur de mise en page (pixels logiques, comme l'aperçu) ramenée à la largeur utile de la page,
# et hauteur du pied de page (numéro de page) dans ces mêmes pixels.
_LAYOUT_WIDTH_PX: Final = 1250
_FOOTER_PX: Final = 24
_FOOTER_COLOR: Final = "#7a6f66"
_FOOTER_POINTS: Final = 7.0

_NOT_WRITTEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : le PDF de « {path} » n'a pas pu être écrit."
)


def _word_wrap(qt_gui: Any) -> Any:
    """Retour à la ligne entre les mots seulement : par défaut, ``QTextDocument`` coupe aussi au
    milieu d'un mot (« Longueu-r ») quand une colonne est étroite."""
    option = qt_gui.QTextOption()
    option.setWrapMode(qt_gui.QTextOption.WordWrap)
    return option


def _paint_pages(document: Any, writer: Any, qt_core: Any, qt_gui: Any) -> None:
    """Dessine ``document`` mis en page sur ``_LAYOUT_WIDTH_PX`` pixels (la largeur de l'aperçu),
    réduit à la largeur de la page : tout le tableau tient en largeur, comme à l'écran
    (``print_`` garderait la taille de l'écran et couperait les dernières colonnes). Chaque page
    porte « n / total » en pied, dans la marge du bas réservée au numéro."""
    area = writer.pageLayout().paintRectPixels(writer.resolution())
    scale = area.width() / _LAYOUT_WIDTH_PX
    footer = _FOOTER_PX * scale
    page_height = (area.height() - footer) / scale
    document.setPageSize(qt_core.QSizeF(_LAYOUT_WIDTH_PX, page_height))
    count = document.pageCount()
    painter = qt_gui.QPainter(writer)
    font = painter.font()
    font.setPointSizeF(_FOOTER_POINTS)
    painter.setFont(font)
    try:
        for index in range(count):
            if index:
                writer.newPage()
            painter.save()
            painter.scale(scale, scale)
            painter.translate(0, -index * page_height)
            document.drawContents(
                painter, qt_core.QRectF(0, index * page_height, _LAYOUT_WIDTH_PX, page_height)
            )
            painter.restore()
            painter.setPen(qt_gui.QColor(_FOOTER_COLOR))
            painter.drawText(
                qt_core.QRectF(0, area.height() - footer, area.width(), footer),
                int(qt_core.Qt.AlignRight | qt_core.Qt.AlignBottom),
                f"{index + 1} / {count}",
            )
    finally:
        painter.end()


def _draw(html: str, temporary: Path) -> None:
    """Écrit ``html`` en PDF A4 paysage dans ``temporary`` ; ``OSError`` si rien de valide
    n'a été produit (``QPdfWriter`` ne signale pas ses échecs)."""
    from PySide import QtCore, QtGui

    # Les objets Qt vivent le temps de cet appel : aucune référence n'est gardée ensuite.
    writer = QtGui.QPdfWriter(str(temporary))
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.A4))
    writer.setPageOrientation(QtGui.QPageLayout.Landscape)
    writer.setPageMargins(
        QtCore.QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM), QtGui.QPageLayout.Millimeter
    )
    writer.setResolution(_RESOLUTION_DPI)
    document = QtGui.QTextDocument()
    document.setDefaultTextOption(_word_wrap(QtGui))
    document.setDocumentMargin(0)
    document.setHtml(html)
    _paint_pages(document, writer, QtCore, QtGui)
    del document, writer  # fermeture du fichier avant relecture
    with temporary.open("r+b") as written:  # écriture permise : fsync l'exige sous Windows
        if written.read(len(PDF_MAGIC)) != PDF_MAGIC:
            raise OSError
        os.fsync(written.fileno())  # sur disque avant le remplacement du fichier d'export


def write_pdf(html: str, target: Path) -> Path:
    """Écrit le PDF de ``html`` dans ``target`` (dossier et extension déjà validés par
    ``validated_path``) et renvoie le chemin. ``ValueError`` traduite si l'écriture échoue."""
    try:
        replace_atomically(target, lambda temporary: _draw(html, temporary))
    except OSError as error:
        raise ValueError(translated(_NOT_WRITTEN, {"path": escaped_text(str(target))})) from error
    return target
