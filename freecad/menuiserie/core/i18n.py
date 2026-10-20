# SPDX-License-Identifier: LGPL-2.1-or-later
"""Marquage des chaînes traduisibles produites par ``core/``.

``core/`` ne peut pas importer Qt : les messages y sont des gabarits français à
paramètres nommés, marqués par :func:`QT_TRANSLATE_NOOP` pour ``lupdate``. La
couche ``features/`` les traduit avec ``translate(CONTEXT, gabarit).format(**params)``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

CONTEXT: Final = "Menuiserie"


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:
    """Marque une chaîne pour lupdate sans la traduire (core/ ne peut pas importer Qt)."""
    del context
    return text


class TemplatedError(ValueError):
    """Erreur dont le message est un gabarit français marqué pour la traduction, rempli.

    ``features/`` le traduit avec ``translate(CONTEXT, template).format(**params)``.
    """

    def __init__(self, template: str, params: Mapping[str, str]) -> None:
        self.template = template
        self.params: Mapping[str, str] = MappingProxyType(dict(params))
        super().__init__(template.format_map(self.params))
