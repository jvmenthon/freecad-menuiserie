# SPDX-License-Identifier: LGPL-2.1-or-later
"""Citation sûre, dans un message, d'un texte venu d'un fichier (bibliothèque, document).

Module public : ``core/`` l'utilise pour ses anomalies, ``features/`` pour la vue rapport.
"""

from __future__ import annotations

from typing import Final

__all__ = ["MAX_QUOTED_LENGTH", "quoted_value"]

MAX_QUOTED_LENGTH: Final = 32


def quoted_value(value: object) -> str:
    """Valeur fournie par un fichier, raccourcie et échappée pour être citée dans un message.

    Au plus ``MAX_QUOTED_LENGTH`` caractères (suivis de « … » si elle est tronquée) ; les
    caractères non imprimables sont échappés (``\\n``, ``\\u202e``…). Ne lève jamais d'exception.
    """
    if isinstance(value, str):
        text = value
    else:
        try:
            text = repr(value)
        except ValueError:  # entier trop long pour être converti en texte
            return "?"
    escaped = repr(text[:MAX_QUOTED_LENGTH])[1:-1]
    return escaped + "…" if len(text) > MAX_QUOTED_LENGTH else escaped
