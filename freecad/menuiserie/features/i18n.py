# SPDX-License-Identifier: LGPL-2.1-or-later
"""Traduction, côté ``features/``, des gabarits français de l'atelier.

Les gabarits (marqués par ``QT_TRANSLATE_NOOP`` dans ``core/`` ou ``features/``) sont traduits
par ``App.Qt.translate``, disponible sans interface : aucun import de Qt ici.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import FreeCAD as App

from freecad.menuiserie.core.i18n import CONTEXT, TemplatedError

__all__ = ["templated_message", "translated", "translated_errors"]


def translated(template: str, params: Mapping[str, str] | None = None) -> str:
    """Gabarit français traduit (contexte « Menuiserie »), puis rempli avec ``params``."""
    text: str = App.Qt.translate(CONTEXT, template)
    return text.format_map(params or {})


def templated_message(error: TemplatedError) -> str:
    """Message traduit d'une erreur de ``core`` ; le champ cité (``{field}``), lui-même un
    gabarit traduisible ou un nom de propriété, est traduit aussi."""
    params = dict(error.params)
    if "field" in params:
        params["field"] = translated(params["field"])
    return translated(error.template, params)


@contextmanager
def translated_errors() -> Iterator[None]:
    """Les erreurs de ``core`` (gabarits ``TemplatedError``) deviennent des ``ValueError`` au
    message traduit."""
    try:
        yield
    except TemplatedError as error:
        raise ValueError(templated_message(error)) from error
