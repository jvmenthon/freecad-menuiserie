# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre « Assemblage défait » au relâchement d'un déplacement (ADR 0026, B7 modifié).

Quand le déplacement d'une pièce (flèches ou poignées de la vue 3D, panneau « Définir une
distance ») rend un ou plusieurs assemblages impossibles, :func:`choose` propose :

- « Annuler le déplacement » (choix par défaut, Échap, fermeture de la fenêtre) ;
- « Supprimer l'assemblage » (« les assemblages » au pluriel), avec leurs noms dans le texte.

La même fenêtre, avec ses propres textes, est proposée à la suppression d'une pièce usinée qui
porte des assemblages (:func:`choose_removal`, ``part_chooser``).

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
from freecad.menuiserie.features.drag_joints import JointChoice, RemovalChoice
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "ask",
    "ask_removal",
    "choose",
    "choose_removal",
    "chooser",
    "message_for",
    "part_chooser",
    "removal_message_for",
]

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
_REMOVAL_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : assemblage lié")
_REMOVAL_TITLE_MANY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : assemblages liés")
_REMOVAL_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La pièce usinée {part} porte encore l'assemblage {labels}."
)
_REMOVAL_TEXT_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La pièce usinée {part} porte encore {count} assemblages :\n{labels}"
)
_REMOVAL_ADVICE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Supprimer l'assemblage supprime aussi la pièce usinée ; la pièce de bois brute "
    "réapparaît. Annuler ne change rien.",
)
_REMOVAL_ADVICE_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Supprimer les assemblages supprime aussi la pièce usinée ; la pièce de bois brute "
    "réapparaît. Annuler ne change rien.",
)
_CANCEL_REMOVAL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Annuler")
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


def removal_message_for(part: str, labels: Sequence[str]) -> str:
    """Texte de la fenêtre de suppression d'une pièce usinée (``part`` et ``labels`` entre
    guillemets) : ses assemblages, au singulier ou au pluriel, puis ce que chaque bouton fait."""
    if len(labels) == 1:
        head = translated(_REMOVAL_TEXT, {"part": part, "labels": labels[0]})
        return f"{head}\n\n{translated(_REMOVAL_ADVICE)}"
    listed = "\n".join(f"- {label}" for label in labels)
    head = translated(
        _REMOVAL_TEXT_MANY, {"part": part, "count": str(len(labels)), "labels": listed}
    )
    return f"{head}\n\n{translated(_REMOVAL_ADVICE_MANY)}"


def _ask_box(title: str, text: str, cancel_label: str, remove_label: str) -> bool:
    """Fenêtre modale à deux boutons ; vrai si le bouton de suppression est cliqué, faux pour
    l'autre (choix par défaut), Échap ou la fermeture de la fenêtre."""
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    cancel = box.addButton(cancel_label, QtGui.QMessageBox.RejectRole)
    remove = box.addButton(remove_label, QtGui.QMessageBox.DestructiveRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is remove


def ask(labels: Sequence[str]) -> bool:
    """Ouvre la fenêtre modale ; vrai si « Supprimer » est cliqué, faux pour « Annuler le
    déplacement », Échap ou la fermeture de la fenêtre."""
    many = len(labels) > 1
    return _ask_box(
        translated(_TITLE_MANY if many else _TITLE),
        message_for(labels),
        translated(_CANCEL),
        translated(_REMOVE_MANY if many else _REMOVE),
    )


def ask_removal(part: str, labels: Sequence[str]) -> bool:
    """Fenêtre « assemblage lié » à la suppression d'une pièce usinée : vrai si « Supprimer
    l'assemblage » (« les assemblages ») est cliqué, faux pour « Annuler », Échap ou fermeture."""
    many = len(labels) > 1
    return _ask_box(
        translated(_REMOVAL_TITLE_MANY if many else _REMOVAL_TITLE),
        removal_message_for(part, labels),
        translated(_CANCEL_REMOVAL),
        translated(_REMOVE_MANY if many else _REMOVE),
    )


# Fonction de choix en service : les tests la remplacent (hors écran, rien ne se clique).
chooser: JointChoice = ask


def choose(labels: Sequence[str]) -> bool:
    """Fonction de choix de l'atelier (``JointChoice``) : délègue à ``chooser``, lu à l'appel."""
    return bool(chooser(labels))


# Fonction de choix de la suppression d'une pièce usinée : remplaçable par les tests.
part_chooser: RemovalChoice = ask_removal


def choose_removal(part: str, labels: Sequence[str]) -> bool:
    """Fonction de choix de la suppression (``RemovalChoice``) : délègue à ``part_chooser``, lu à
    l'appel."""
    return bool(part_chooser(part, labels))
