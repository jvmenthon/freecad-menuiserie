# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin du PDF de la liste de débit (J2g, critère P2, spécification J2 § 10).

Qt (``QTextDocument`` et ``QPdfWriter``, via le PySide de FreeCAD) exige une application
graphique (polices) : ce module n'est utilisable qu'avec l'interface, d'où sa place côté ``gui``.
Le HTML vient de ``features/cutlist_export.pdf_html`` ; la page est un A4 paysage de marges 10 mm.
Le fichier est écrit de façon atomique (``replace_atomically``) : un échec laisse l'ancien fichier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.cutlist_export import replace_atomically
from freecad.menuiserie.features.i18n import translated

__all__ = ["MARGIN_MM", "PDF_MAGIC", "write_pdf"]

MARGIN_MM: Final = 10.0
PDF_MAGIC: Final = b"%PDF"
_RESOLUTION_DPI: Final = 150

_NOT_WRITTEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : le PDF de « {path} » n'a pas pu être écrit."
)


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
    document.setHtml(html)
    document.print_(writer)
    del document, writer  # fermeture du fichier avant relecture
    with temporary.open("rb") as written:
        if written.read(len(PDF_MAGIC)) != PDF_MAGIC:
            raise OSError


def write_pdf(html: str, target: Path) -> Path:
    """Écrit le PDF de ``html`` dans ``target`` (dossier et extension déjà validés par
    ``validated_path``) et renvoie le chemin. ``ValueError`` traduite si l'écriture échoue."""
    try:
        replace_atomically(target, lambda temporary: _draw(html, temporary))
    except OSError as error:
        raise ValueError(translated(_NOT_WRITTEN, {"path": str(target)})) from error
    return target
