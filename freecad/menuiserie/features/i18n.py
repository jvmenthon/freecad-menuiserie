# SPDX-License-Identifier: LGPL-2.1-or-later
"""Traduction, côté ``features/``, des gabarits français de l'atelier.

Les gabarits (marqués par ``QT_TRANSLATE_NOOP`` dans ``core/`` ou ``features/``) sont traduits
par ``App.Qt.translate``, disponible sans interface : aucun import de Qt ici. Les messages de
la vue rapport portent le préfixe « Menuiserie : » (:func:`console_text`).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import FreeCAD as App

from freecad.menuiserie.core.i18n import CONTEXT, TemplatedError

__all__ = [
    "console_text",
    "report_warning",
    "templated_message",
    "translate_text",
    "translated",
    "translated_errors",
]


def translated(template: str, params: Mapping[str, str] | None = None) -> str:
    """Gabarit français traduit (contexte « Menuiserie »), puis rempli avec ``params``."""
    text: str = App.Qt.translate(CONTEXT, template)
    return text.format_map(params or {})


def translate_text(text: str) -> str:
    """Gabarit français traduit (contexte « Menuiserie »), sans le remplir : pour les gabarits
    de ``core`` que l'appelant remplit lui-même (``to_csv``, ``additions_remark``)."""
    translated_text: str = App.Qt.translate(CONTEXT, text)
    return translated_text


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
    message traduit. L'erreur d'origine n'est pas chaînée (``from None``) : FreeCAD imprime la
    trace d'une exception levée par ``execute()`` avec ses causes, et le même message (gabarit
    puis texte traduit) y paraîtrait deux fois."""
    try:
        yield
    except TemplatedError as error:
        raise ValueError(templated_message(error)) from None


def console_text(message: str) -> str:
    """Ligne de la vue rapport : ``message`` précédé de « Menuiserie : »."""
    return f"Menuiserie : {message}\n"


def report_warning(message: str) -> None:
    """Avertissement dans la vue rapport (``App.Console`` lu à l'appel : remplaçable)."""
    App.Console.PrintWarning(console_text(message))
