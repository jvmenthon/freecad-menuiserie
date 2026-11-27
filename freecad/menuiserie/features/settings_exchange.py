# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export et import des réglages et des dimensions personnelles de l'atelier (ADR 0069).

Fichier ``atelier.json`` du dossier de l'atelier : réglages du catalogue et section
« dimensions » (même validation que ``dimensions.json``). Un import se fait en trois temps :
:func:`load_workshop` lit et valide sans rien écrire, l'appelant montre les changements et
reprend ceux que l'utilisateur coche (la page les écrit à OK ou Appliquer). Les refus sont des
:class:`ExchangeError` ; :func:`error_message`
en donne le texte traduit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.user_dimensions import (
    FORMAT_VERSION,
    UserDimensions,
    dimensions_from_text,
)
from freecad.menuiserie.features.i18n import translate_text, translated, translated_errors
from freecad.menuiserie.features.settings import CATALOG, settings, workshop_folder
from freecad.menuiserie.features.user_dimensions import read_dimensions
from freecad.menuiserie.kit.config import exchange
from freecad.menuiserie.kit.config.exchange import (
    Change,
    ExchangeError,
    ExchangeReason,
    ImportResult,
)
from freecad.menuiserie.kit.config.page_model import printable

__all__ = [
    "FILE_NAME",
    "error_message",
    "export_workshop",
    "load_workshop",
    "workshop_file",
]

FILE_NAME: Final = "atelier.json"
DIMENSIONS: Final = "dimensions"
MAX_DETAIL_LENGTH: Final = 120  # caractères du détail d'un refus montrés à l'utilisateur

_MESSAGES: Final[dict[ExchangeReason, str]] = {
    ExchangeReason.UNREADABLE: QT_TRANSLATE_NOOP(
        "Menuiserie", "Le fichier est illisible : {detail}."
    ),
    ExchangeReason.NOT_WRITTEN: QT_TRANSLATE_NOOP(
        "Menuiserie", "Impossible d'enregistrer le fichier : {detail}."
    ),
    ExchangeReason.TOO_LARGE: QT_TRANSLATE_NOOP(
        "Menuiserie", "Le fichier dépasse la taille maximale de {detail} octets."
    ),
    ExchangeReason.NOT_JSON: QT_TRANSLATE_NOOP(
        "Menuiserie", "Le fichier n'est pas un document JSON valide ({detail})."
    ),
    ExchangeReason.NOT_STRICT: QT_TRANSLATE_NOOP(
        "Menuiserie", "Le fichier contient une valeur non numérique ({detail})."
    ),
    ExchangeReason.DUPLICATE_KEY: QT_TRANSLATE_NOOP(
        "Menuiserie", "Le fichier contient deux fois la clé « {detail} »."
    ),
    ExchangeReason.NOT_AN_OBJECT: QT_TRANSLATE_NOOP(
        "Menuiserie", "Un objet JSON est attendu ({detail})."
    ),
    ExchangeReason.BAD_FORMAT: QT_TRANSLATE_NOOP(
        "Menuiserie", "Le fichier n'est pas un export de l'atelier (format : {detail})."
    ),
    ExchangeReason.NEWER_FORMAT: QT_TRANSLATE_NOOP(
        "Menuiserie",
        "Ce fichier vient d'une version plus récente de l'atelier (format {detail}).",
    ),
    ExchangeReason.INVALID_SETTING: QT_TRANSLATE_NOOP(
        "Menuiserie", "Valeur refusée pour le réglage « {detail} »."
    ),
    ExchangeReason.INCONSISTENT: QT_TRANSLATE_NOOP(
        "Menuiserie", "Les réglages « {detail} » sont incompatibles entre eux."
    ),
    ExchangeReason.INVALID_SECTION: QT_TRANSLATE_NOOP("Menuiserie", "Section invalide : {detail}."),
}
_PREFIX: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fichier refusé, aucun réglage n'est modifié. ")


def workshop_file() -> Path:
    """Fichier d'échange par défaut, dans le dossier de l'atelier."""
    return workshop_folder() / FILE_NAME


def _label(key: str) -> str:
    """Libellé traduit du réglage ``key`` (la clé elle-même si elle n'est pas au catalogue)."""
    return translate_text(CATALOG.get(key).label) if key in CATALOG else key


def error_message(error: ExchangeError) -> str:
    """Texte traduit du refus ``error``, avec le réglage ou la section en cause."""
    detail = error.detail
    if error.reason is ExchangeReason.INCONSISTENT:
        keys = detail.split(", ")
        detail = ", ".join(
            translate_text(CATALOG.get(k).label) if k in CATALOG else k for k in keys
        )
    # Le détail peut venir du fichier (clé, message système) : court et sans caractère de contrôle.
    reason = translated(_MESSAGES[error.reason], {"detail": printable(detail, MAX_DETAIL_LENGTH)})
    return translated(_PREFIX) + reason


def _validate_dimensions(raw: dict[str, Any]) -> UserDimensions:
    """Section « dimensions » : mêmes règles que ``dimensions.json`` (``ValueError`` traduite)."""
    text = json.dumps({**raw, "format": FORMAT_VERSION})
    with translated_errors():
        return dimensions_from_text(text)


def _dimensions_section() -> dict[str, Any]:
    dimensions = read_dimensions()
    return {
        "thicknesses": list(dimensions.thicknesses),
        "sheets": [list(sheet) for sheet in dimensions.sheets],
    }


def export_workshop(path: Path) -> None:
    """Écrit réglages et dimensions dans ``path`` ; :class:`ExchangeError` si l'écriture échoue."""
    payload = exchange.export_payload(CATALOG, settings(), {DIMENSIONS: _dimensions_section()})
    exchange.write_export(path, payload)


def load_workshop(path: Path) -> tuple[ImportResult, list[Change]]:
    """Fichier lu et validé en entier, sans rien écrire, avec les changements qu'il ferait ;
    :class:`ExchangeError` s'il est refusé."""
    result = exchange.read_import(path, CATALOG, {DIMENSIONS: _validate_dimensions})
    exchange.check_relations(CATALOG, settings(), result)
    return result, exchange.preview(CATALOG, settings(), result)
