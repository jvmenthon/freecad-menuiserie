# SPDX-License-Identifier: LGPL-2.1-or-later
"""Confirmation avant « Dissocier la répétition » (demande de jv du 2026-11-24) : la commande et
le menu du panneau « Structure » demandent d'abord, dans une fenêtre modale, « Annuler » (choix
par défaut, Échap, fermeture) ou « Dissocier ». ``confirmer`` est un attribut de module que les
tests remplacent par une fonction ``(libellés, copies) -> bool`` : la fenêtre ne se clique pas
hors écran."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat import copies_of

__all__ = ["ask", "confirmed", "confirmer", "message_for"]

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : dissocier la répétition")
_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Dissocier {labels} ? Ses {count} copies deviennent des pièces libres, avec leurs valeurs "
    "actuelles : l'original ne les pilote plus et la répétition est supprimée.",
)
_TEXT_ONE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Dissocier {labels} ? Sa copie devient une pièce libre, avec ses valeurs actuelles : "
    "l'original ne la pilote plus et la répétition est supprimée.",
)
_TEXT_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Dissocier les répétitions {labels} ? Leurs {count} copies deviennent des pièces libres, "
    "avec leurs valeurs actuelles : les originaux ne les pilotent plus et les répétitions "
    "sont supprimées.",
)
_CANCEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Annuler")
_DISSOCIATE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Dissocier")

Confirmer = Callable[[Sequence[str], int], bool]


def _template(repeats: int, copies: int) -> str:
    """Gabarit du texte : plusieurs répétitions, une seule copie, ou plusieurs copies."""
    if repeats > 1:
        return _TEXT_MANY
    if copies == 1:
        return _TEXT_ONE
    return _TEXT


def message_for(labels: Sequence[str], copies: int) -> str:
    """Texte de la fenêtre : les répétitions (``labels``, entre guillemets) et leur nombre total
    de copies, au singulier ou au pluriel."""
    return translated(
        _template(len(labels), copies), {"labels": ", ".join(labels), "count": str(copies)}
    )


def ask(labels: Sequence[str], copies: int) -> bool:
    """Fenêtre modale ; vrai si « Dissocier » est cliqué, faux pour « Annuler » (choix par
    défaut), Échap ou la fermeture de la fenêtre."""
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Question)
    box.setWindowTitle(translated(_TITLE))
    box.setTextFormat(QtCore.Qt.PlainText)  # libellés du document : jamais lus comme HTML
    box.setText(message_for(labels, copies))
    cancel = box.addButton(translated(_CANCEL), QtGui.QMessageBox.RejectRole)
    dissociate = box.addButton(translated(_DISSOCIATE), QtGui.QMessageBox.AcceptRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is dissociate


# Fonction de confirmation en service : les tests la remplacent (hors écran, rien ne se clique).
confirmer: Confirmer = ask


def confirmed(repeats: Sequence[DocumentObject]) -> bool:
    """Demande à ``confirmer`` (lu à l'appel) s'il faut dissocier ``repeats`` ; rien à
    dissocier : faux, sans fenêtre."""
    if not repeats:
        return False
    labels = [f"« {quoted_value(rep.Label)} »" for rep in repeats]
    return bool(confirmer(labels, sum(len(copies_of(rep)) for rep in repeats)))
