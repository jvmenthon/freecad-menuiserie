# SPDX-License-Identifier: LGPL-2.1-or-later
"""Robustesse de la commande et du panneau de la pièce de bois (lot J1c).

La pièce supprimée depuis la console ferme le panneau. Module importé par
``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui

from tests.gui.verifications_panneau import (
    COMMAND,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    saisir,
)
from tests.gui.verifications_panneau_limites import transaction_ouverte


def panneau_et_transaction_soldes() -> list[str]:
    """Ni panneau ni transaction ; la commande est de nouveau disponible."""
    return [
        *ecarts("panneau ouvert", Gui.Control.activeDialog(), False),
        *ecarts("transaction close", transaction_ouverte(), None),
        *ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
    ]


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
    verifier_piece_supprimee_par_la_console,
)
