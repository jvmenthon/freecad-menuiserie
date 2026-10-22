# SPDX-License-Identifier: LGPL-2.1-or-later
"""Robustesse de la commande et du panneau de la pièce de bois (lot J1c, audit de sécurité A1).

Une exception à l'ouverture du panneau, en création comme en modification, ne laisse ni pièce
ni transaction ouverte ; la pièce supprimée depuis la console ferme le panneau. Module importé
par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import FreeCADGui as Gui

from freecad.menuiserie.gui.commands.wood_part import CreateWoodPartCommand
from freecad.menuiserie.gui.task_panels import wood_part as task_panel
from tests.gui.verifications_panneau import (
    COMMAND,
    CREATE,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    piece_validee,
    saisir,
)
from tests.gui.verifications_panneau_limites import transaction_ouverte


class PanneauDefaillant:
    """Panneau dont la construction échoue, comme sur un formulaire illisible."""

    def __init__(self, obj: Any, *, creating: bool, **_options: Any) -> None:
        del obj, creating
        raise RuntimeError("panneau défaillant (vérification A1)")


@contextmanager
def panneau_defaillant() -> Iterator[None]:
    """Remplace le panneau de la pièce de bois par :class:`PanneauDefaillant` le temps du bloc."""
    original = task_panel.WoodPartTaskPanel
    task_panel.WoodPartTaskPanel = PanneauDefaillant  # type: ignore[misc,assignment]
    try:
        yield
    finally:
        task_panel.WoodPartTaskPanel = original  # type: ignore[misc]


def echec_signale(action: Callable[[], object]) -> list[str]:
    """``action`` doit propager l'exception du panneau."""
    try:
        action()
    except RuntimeError:
        return []
    return ["exception du panneau non propagée"]


def panneau_et_transaction_soldes() -> list[str]:
    """Ni panneau ni transaction ; la commande est de nouveau disponible."""
    return [
        *ecarts("panneau ouvert", Gui.Control.activeDialog(), False),
        *ecarts("transaction close", transaction_ouverte(), None),
        *ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
    ]


def verifier_exception_a_la_creation() -> list[str]:
    """A1 : la commande dont le panneau échoue ne laisse ni pièce ni transaction."""

    def verification(doc: Any) -> list[str]:
        with panneau_defaillant():
            problemes = echec_signale(CreateWoodPartCommand().Activated)
        return [
            *problemes,
            *panneau_et_transaction_soldes(),
            *ecarts("pièces", len(doc.Objects), 0),
            *ecarts("entrées d'annulation", doc.UndoNames, []),
        ]

    return avec_document("VerifExceptionCreation", verification)


def verifier_exception_a_la_modification() -> list[str]:
    """A1 : le double-clic dont le panneau échoue ne laisse pas de transaction ouverte."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        with panneau_defaillant():
            problemes = echec_signale(lambda: task_panel.start_editing(obj))
        return [
            *problemes,
            *panneau_et_transaction_soldes(),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
        ]

    return avec_document("VerifExceptionModification", verification)


def verifier_piece_supprimee_par_la_console() -> list[str]:
    """Pièce en création supprimée par ``doc.removeObject`` : panneau fermé, rien ne reste."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        saisir(formulaire().lengthEdit, 1000.0)
        doc.removeObject(obj.Name)
        Gui.updateGui()  # suites différées de la fermeture du panneau
        return [
            *panneau_et_transaction_soldes(),
            *ecarts("pièces", len(doc.Objects), 0),
            *ecarts("entrées d'annulation", doc.UndoNames, []),
        ]

    return avec_document("VerifSuppressionConsole", verification)


VERIFICATIONS_ROBUSTESSE: tuple[Callable[[], list[str]], ...] = (
    verifier_exception_a_la_creation,
    verifier_exception_a_la_modification,
    verifier_piece_supprimee_par_la_console,
)
