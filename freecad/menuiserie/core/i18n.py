# SPDX-License-Identifier: LGPL-2.1-or-later
"""Marquage des chaînes traduisibles produites par ``core/``.

``core/`` ne peut pas importer Qt : les messages y sont des gabarits français à
paramètres nommés, marqués par :func:`QT_TRANSLATE_NOOP` pour ``lupdate``. La
couche ``features/`` les traduit avec ``translate(CONTEXT, gabarit).format(**params)``.
"""

from typing import Final

CONTEXT: Final = "Menuiserie"


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:
    """Marque une chaîne pour lupdate sans la traduire (core/ ne peut pas importer Qt)."""
    del context
    return text
