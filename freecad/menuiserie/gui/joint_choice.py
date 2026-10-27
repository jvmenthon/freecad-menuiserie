# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre « Assemblage défait » au relâchement d'un déplacement (ADR 0024, B7 modifié).

Quand le déplacement d'une pièce (flèches ou poignées de la vue 3D, panneau « Définir une
distance ») rend un ou plusieurs assemblages impossibles, :func:`choose` propose :

- « Annuler le déplacement » (choix par défaut, Échap, fermeture de la fenêtre) ;
- « Supprimer l'assemblage » (« les assemblages » au pluriel), avec leurs noms dans le texte.

La fenêtre est modale et ne peut pas être cliquée hors écran : ``chooser`` est un attribut de
module que les tests remplacent par une fonction ``labels -> bool`` ; ``features/part_drag``
reçoit :func:`choose` comme fonction de choix (``JointChoice``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.i18n import translated

__all__ = ["ask", "choose", "chooser", "message_for"]

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : assemblage défait")
_TITLE_MANY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : assemblages défaits")
_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Ce déplacement défait l'assemblage {labels} : ses pièces ne s'assemblent plus.",
)
_TEXT_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ce déplacement défait {count} assemblages :\n{labels}"
)
_ADVICE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Annuler le déplacement remet la pièce où elle était. Supprimer garde le déplacement.",
)
_CANCEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Annuler le déplacement")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Supprimer l'assemblage")
_REMOVE_MANY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Supprimer les assemblages")


def message_for(labels: Sequence[str]) -> str:
    """Texte de la fenêtre : les noms des assemblages défaits (``labels``, entre guillemets),
    au singulier ou au pluriel, puis ce que chaque bouton fait."""
    if len(labels) == 1:
        head = translated(_TEXT, {"labels": labels[0]})
    else:
        listed = "\n".join(f"- {label}" for label in labels)
        head = translated(_TEXT_MANY, {"count": str(len(labels)), "labels": listed})
    return f"{head}\n\n{translated(_ADVICE)}"


def ask(labels: Sequence[str]) -> bool:
    """Ouvre la fenêtre modale ; vrai si « Supprimer » est cliqué, faux pour « Annuler le
    déplacement », Échap ou la fermeture de la fenêtre."""
    many = len(labels) > 1
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Warning)
    box.setWindowTitle(translated(_TITLE_MANY if many else _TITLE))
    box.setText(message_for(labels))
    cancel = box.addButton(translated(_CANCEL), QtGui.QMessageBox.RejectRole)
    remove = box.addButton(
        translated(_REMOVE_MANY if many else _REMOVE), QtGui.QMessageBox.DestructiveRole
    )
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is remove


# Fonction de choix en service : les tests la remplacent (hors écran, rien ne se clique).
chooser: JointChoice = ask


def choose(labels: Sequence[str]) -> bool:
    """Fonction de choix de l'atelier (``JointChoice``) : délègue à ``chooser``, lu à l'appel."""
    return bool(chooser(labels))
