# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre d'aperçu de la liste de débit avant l'export (J2, § 10, demande de jv du 2026-10-22).

Une ``QDialog`` **non modale** (le travail continue dans FreeCAD pendant qu'elle est ouverte) qui
affiche dans un ``QTextBrowser`` le HTML exact de l'export PDF, miniatures comprises : le HTML est
rendu par le même ``QTextDocument`` que celui qui dessine le PDF, les images SVG sont des URI
``data:`` (aucune ressource externe, aucun lien suivi). Les boutons « Actualiser », « Exporter en
PDF… », « Exporter en CSV… » et « Fermer » appellent les actions fournies par la commande : la
fenêtre ne connaît ni le document ni l'api. Aucune référence à la fenêtre n'est gardée (ni
``findChild`` sur la fenêtre principale, qui garderait son enveloppe Python en vie) : elle
appartient à la fenêtre principale et se détruit à sa fermeture.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "BROWSER_NAME",
    "BUTTON_NAMES",
    "DIALOG_NAME",
    "PreviewActions",
    "show_preview",
]

DIALOG_NAME: Final = "MenuiserieCutListPreview"
BROWSER_NAME: Final = "MenuiserieCutListPreviewBrowser"
# Noms d'objet des boutons (pour les tests d'interface), dans l'ordre d'affichage.
BUTTON_NAMES: Final = {
    "refresh": "MenuiserieCutListPreviewRefresh",
    "pdf": "MenuiserieCutListPreviewPdf",
    "csv": "MenuiserieCutListPreviewCsv",
    "close": "MenuiserieCutListPreviewClose",
}
_INITIAL_SIZE: Final = (1100, 720)
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aperçu de la liste de débit")
_LABELS: Final = {
    "refresh": QT_TRANSLATE_NOOP("Menuiserie", "Actualiser"),
    "pdf": QT_TRANSLATE_NOOP("Menuiserie", "Exporter en PDF…"),
    "csv": QT_TRANSLATE_NOOP("Menuiserie", "Exporter en CSV…"),
    "close": QT_TRANSLATE_NOOP("Menuiserie", "Fermer"),
}


@dataclass(frozen=True)
class PreviewActions:
    """Actions de la commande appelées par les boutons ; ``refresh`` renvoie le HTML à jour, ou
    ``None`` (refus) pour garder l'affichage."""

    refresh: Callable[[], str | None]
    export_pdf: Callable[[QtGui.QWidget], None]
    export_csv: Callable[[QtGui.QWidget], None]


def _button(dialog: QtGui.QDialog, key: str, action: Callable[[], None]) -> QtGui.QPushButton:
    button = QtGui.QPushButton(translated(_LABELS[key]), dialog)
    button.setObjectName(BUTTON_NAMES[key])
    button.setAutoDefault(False)
    button.clicked.connect(lambda _checked=False: action())
    return button


def _browser(dialog: QtGui.QDialog, html: str) -> QtGui.QTextBrowser:
    browser = QtGui.QTextBrowser(dialog)
    browser.setObjectName(BROWSER_NAME)
    browser.setOpenLinks(False)  # aucun lien suivi, aucune ressource externe chargée
    browser.setOpenExternalLinks(False)
    browser.setStyleSheet("QTextBrowser { background: #ffffff; }")
    # Coupure entre les mots seulement, comme le PDF (par défaut : aussi au milieu d'un mot).
    browser.setWordWrapMode(QtGui.QTextOption.WordWrap)
    browser.setHtml(html)
    return browser


def show_preview(parent: QtGui.QWidget, subtitle: str, html: str, actions: PreviewActions) -> None:
    """Ouvre l'aperçu de ``html`` (non modal, fils de ``parent``) sous le titre « Aperçu de la
    liste de débit - <subtitle> ». Rien n'est renvoyé ni gardé : la fenêtre appartient à
    ``parent`` et se détruit à sa fermeture (plusieurs aperçus peuvent être ouverts)."""
    dialog = QtGui.QDialog(parent)
    dialog.setObjectName(DIALOG_NAME)
    title = translated(_TITLE)
    dialog.setWindowTitle(f"{title} - {subtitle}" if subtitle else title)
    dialog.setModal(False)
    dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    dialog.resize(*_INITIAL_SIZE)
    browser = _browser(dialog, html)

    def refresh() -> None:
        updated = actions.refresh()
        if updated is not None:
            browser.setHtml(updated)

    buttons = QtGui.QHBoxLayout()
    buttons.addWidget(_button(dialog, "refresh", refresh))
    buttons.addStretch(1)
    buttons.addWidget(_button(dialog, "pdf", lambda: actions.export_pdf(dialog)))
    buttons.addWidget(_button(dialog, "csv", lambda: actions.export_csv(dialog)))
    buttons.addWidget(_button(dialog, "close", dialog.close))
    layout = QtGui.QVBoxLayout(dialog)
    layout.addWidget(browser, 1)
    layout.addLayout(buttons)
    dialog.show()
