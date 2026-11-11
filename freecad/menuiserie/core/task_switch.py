# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ouvrir une autre pièce pendant qu'un panneau de tâche est ouvert (ADR 0046), sans FreeCAD ni Qt.

Le double-clic d'une ligne du panneau « Structure » demande d'ouvrir une pièce. Selon la tâche en
cours, :func:`plan` répond : l'ouvrir (aucune tâche), fermer la tâche inchangée puis l'ouvrir,
demander quoi faire des modifications (tâche modifiée ou de création, dont l'objet n'existe
que par elle) ou refuser (tâche d'un autre atelier). :func:`resolve` traduit la réponse de
l'utilisateur à la question.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = [
    "APPLY_LABEL",
    "ASK_TEXT",
    "ASK_TITLE",
    "DISCARD_LABEL",
    "FOREIGN_TASK",
    "STAY_LABEL",
    "Action",
    "Choice",
    "plan",
    "resolve",
]

ASK_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tâche en cours")
ASK_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La tâche en cours a des modifications. Que faire avant d'ouvrir cette pièce ?"
)
APPLY_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Appliquer les modifications")
DISCARD_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Annuler les modifications")
STAY_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Poursuivre la tâche en cours")
FOREIGN_TASK: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Une tâche d'un autre atelier est ouverte : terminez-la (OK ou Annuler) avant d'ouvrir "
    "cette pièce.",
)


class Action(Enum):
    """Ce que le panneau « Structure » fait du double-clic."""

    OPEN = "open"  # aucune tâche : ouvrir la pièce
    DISCARD_THEN_OPEN = "discard_then_open"  # tâche fermée (abandonnée), puis la pièce
    APPLY_THEN_OPEN = "apply_then_open"  # tâche validée, puis la pièce
    ASK = "ask"  # demander : appliquer, annuler ou poursuivre
    REFUSE = "refuse"  # tâche d'un autre atelier : message
    NOTHING = "nothing"  # on reste sur la tâche en cours


class Choice(Enum):
    """Réponse de l'utilisateur ; fermer la boîte (Échap) vaut ``STAY``."""

    APPLY = "apply"
    DISCARD = "discard"
    STAY = "stay"


def plan(*, task_open: bool, ours: bool, creating: bool, changed: bool) -> Action:
    """Action du double-clic. ``ours`` : la tâche est un panneau de l'atelier ; ``creating`` :
    panneau de création (« Annuler » supprimerait l'objet : toujours à confirmer) ; ``changed`` :
    le document a été modifié depuis l'ouverture de la tâche."""
    if not task_open:
        return Action.OPEN
    if not ours:
        return Action.REFUSE
    if creating or changed:
        return Action.ASK
    return Action.DISCARD_THEN_OPEN


_BY_CHOICE: Final = {
    Choice.APPLY: Action.APPLY_THEN_OPEN,
    Choice.DISCARD: Action.DISCARD_THEN_OPEN,
    Choice.STAY: Action.NOTHING,
}


def resolve(choice: Choice | None) -> Action:
    """Action qui suit la réponse ``choice`` (``None`` : boîte fermée, on ne fait rien)."""
    return Action.NOTHING if choice is None else _BY_CHOICE[choice]
