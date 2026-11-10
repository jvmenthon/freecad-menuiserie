# SPDX-License-Identifier: LGPL-2.1-or-later
"""Menu contextuel du panneau « Structure » (ADR 0046, lot 3), décrit sans FreeCAD ni Qt.

:func:`menu_entries` donne, pour les lignes choisies, la liste ordonnée des entrées du menu avec
la décision (permise ou refusée avec sa raison) de chacune : l'interface grise une entrée refusée
et affiche la raison en infobulle. Rien n'est modifié ici ; l'exécution est dans
``gui/structure_actions.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_actions import (
    Decision,
    MoveFacts,
    creates_sub_furniture,
    decide_create,
    decide_delete,
    decide_drop,
    decide_open,
    decide_rename_target,
    decide_selection,
)

__all__ = ["Action", "MenuEntry", "menu_entries"]


class Action(Enum):
    """Ce que fait une entrée du menu."""

    OPEN = "open"
    RENAME = "rename"
    ADD_TO = "add_to"  # sous-menu des ensembles d'accueil
    MOVE_INTO = "move_into"  # un ensemble d'accueil du sous-menu
    LEAVE = "leave"
    CREATE = "create"
    DELETE = "delete"


_OPEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ouvrir")
_RENAME: Final = QT_TRANSLATE_NOOP("Menuiserie", "Renommer…")
_ADD_TO: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ajouter à l'ensemble")
_LEAVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Sortir de l'ensemble")
_CREATE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Créer un ensemble depuis la sélection")
_CREATE_SUB: Final = QT_TRANSLATE_NOOP("Menuiserie", "Créer un sous-ensemble depuis la sélection")
_DELETE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Supprimer")
_NO_FURNITURE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun ensemble dans le document.")


@dataclass(frozen=True)
class MenuEntry:
    """Une entrée : ``label`` est un gabarit à traduire (ou le libellé d'un ensemble si
    ``verbatim``), ``decision`` dit si elle est active et, sinon, pourquoi. ``target`` est
    l'ensemble d'accueil d'une entrée ``MOVE_INTO`` ; ``children`` les entrées d'un sous-menu."""

    action: Action
    label: str
    decision: Decision
    target: str | None = None
    children: tuple[MenuEntry, ...] = ()
    verbatim: bool = False


def _destinations(facts: MoveFacts, keys: Sequence[str]) -> tuple[MenuEntry, ...]:
    ordered = sorted(
        facts.furnitures - facts.copies, key=lambda key: (facts.labels.get(key, key), key)
    )
    return tuple(
        MenuEntry(
            Action.MOVE_INTO,
            facts.labels.get(key, key),
            decide_drop(facts, keys, key),
            target=key,
            verbatim=True,
        )
        for key in ordered
    )


def _add_to(facts: MoveFacts, keys: Sequence[str]) -> MenuEntry:
    decision = decide_selection(facts, keys)
    if decision.allowed and not facts.furnitures - facts.copies:
        decision = Decision(False, _NO_FURNITURE)
    children = _destinations(facts, keys) if decision.allowed else ()
    return MenuEntry(Action.ADD_TO, _ADD_TO, decision, children=children)


def menu_entries(facts: MoveFacts, keys: Sequence[str]) -> list[MenuEntry]:
    """Entrées du menu pour les lignes choisies (``keys`` : clé de chacune) : Ouvrir, Renommer,
    Ajouter à l'ensemble (un sous-menu), Sortir de l'ensemble, Créer un (sous-)ensemble depuis la
    sélection, Supprimer. Les entrées impossibles sont là aussi, avec leur refus."""
    sub = creates_sub_furniture(facts, keys)
    return [
        MenuEntry(Action.OPEN, _OPEN, decide_open(keys, busy=facts.busy, foreign=facts.foreign)),
        MenuEntry(Action.RENAME, _RENAME, decide_rename_target(facts, keys)),
        _add_to(facts, keys),
        MenuEntry(Action.LEAVE, _LEAVE, decide_drop(facts, keys, None)),
        MenuEntry(Action.CREATE, _CREATE_SUB if sub else _CREATE, decide_create(facts, keys)),
        MenuEntry(
            Action.DELETE, _DELETE, decide_delete(keys, busy=facts.busy, foreign=facts.foreign)
        ),
    ]
