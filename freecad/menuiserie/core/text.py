# SPDX-License-Identifier: LGPL-2.1-or-later
"""Citation sûre, dans un message, d'un texte venu d'un fichier (bibliothèque, document).

Module public : ``core/`` l'utilise pour ses anomalies, ``features/`` pour la vue rapport.
"""

from __future__ import annotations

from typing import Final

__all__ = ["MAX_DETAIL_LENGTH", "MAX_QUOTED_LENGTH", "bounded_text", "escaped_text", "quoted_value"]

MAX_QUOTED_LENGTH: Final = 32
MAX_DETAIL_LENGTH: Final = 300


def escaped_text(text: str) -> str:
    """Texte entier, caractères non imprimables échappés (``\\n``, ``\\u202e``…), sans
    troncature : pour citer un chemin, qui doit rester reconnaissable en entier."""
    return repr(text)[1:-1]


def bounded_text(text: str, limit: int = MAX_DETAIL_LENGTH) -> str:
    """Phrase lue dans un document (raison d'une erreur…), caractères non imprimables échappés,
    coupée à ``limit`` caractères (« … » compris) : affichable entière dans un panneau quand
    elle vient de l'atelier, sans le déformer si le document a été retouché à la main."""
    text = escaped_text(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def quoted_value(value: object) -> str:
    """Valeur fournie par un fichier, raccourcie et échappée pour être citée dans un message.

    Au plus ``MAX_QUOTED_LENGTH`` caractères (suivis de « … » si elle est tronquée) ; les
    caractères non imprimables sont échappés (``\\n``, ``\\u202e``…). Une valeur qui n'est pas
    un texte est citée par ``repr()`` : seule ``ValueError`` y est rattrapée (entier trop long
    pour être converti en texte, cité « ? ») ; une autre exception levée par un ``__repr__``
    se propage.
    """
    if isinstance(value, str):
        text = value
    else:
        try:
            text = repr(value)
        except ValueError:  # entier trop long pour être converti en texte
            return "?"
    escaped = escaped_text(text[:MAX_QUOTED_LENGTH])
    return escaped + "…" if len(text) > MAX_QUOTED_LENGTH else escaped
