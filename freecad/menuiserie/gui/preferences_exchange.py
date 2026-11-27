# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export et import des réglages depuis la page « Menuiserie » (ADR 0069).

Branche les boutons génériques (:mod:`freecad.menuiserie.kit.config.page_exchange`) sur
``features/settings_exchange.py`` : fichier proposé, écriture, lecture avec l'aperçu des changements
(réglages du catalogue et « Épaisseurs et formats personnels »), message d'erreur traduit.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

from freecad.menuiserie.core.user_dimensions import UserDimensions
from freecad.menuiserie.features import dimensions_edit as edit
from freecad.menuiserie.features.i18n import translate_text
from freecad.menuiserie.features.settings import CATALOG
from freecad.menuiserie.features.settings_exchange import (
    DIMENSIONS,
    error_message,
    export_workshop,
    load_workshop,
    workshop_file,
)
from freecad.menuiserie.features.user_dimensions import read_dimensions
from freecad.menuiserie.kit.config import import_model as model
from freecad.menuiserie.kit.config.page_exchange import ExchangeActions
from freecad.menuiserie.kit.config.page_model import Choices

__all__ = ["actions", "import_offer"]


def import_offer(path: Path, choices: Choices) -> model.ImportOffer:
    """Ce que le fichier ``path`` changerait (rien n'est écrit) : réglages du catalogue, puis les
    dimensions personnelles ; ``ExchangeError`` si le fichier est refusé."""
    result, changes = load_workshop(path)
    rows = model.build_rows(CATALOG, changes, translate_text, choices)
    imported = result.sections.get(DIMENSIONS)
    if isinstance(imported, UserDimensions):
        extra = edit.import_row(read_dimensions(), imported)
        if extra is not None:
            rows.append(extra)
    return model.ImportOffer(tuple(rows), result.ignored)


def actions(
    choices: Choices,
    take: Callable[[Sequence[model.ImportRow]], None],
    has_unsaved: Callable[[], bool],
) -> ExchangeActions:
    """Actions de l'échange : ``take`` reprend les lignes cochées dans la page, ``has_unsaved`` dit
    si la page a des modifications non enregistrées."""
    return ExchangeActions(
        workshop_file,
        export_workshop,
        partial(import_offer, choices=choices),
        error_message,
        take,
        has_unsaved,
    )
