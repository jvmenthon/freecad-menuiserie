# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Renommer » dans le panneau « Structure » (ADR 0046) : contrôle du nom saisi, sans FreeCAD ni
Qt. Partagé par le panneau et par ``api.rename``."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core._validation import has_forbidden_character
from freecad.menuiserie.core.furniture import FurnitureError, label_reference
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_decision import Decision, refuse

__all__ = ["MAX_NAME_LENGTH", "cleaned_name", "decide_rename"]

MAX_NAME_LENGTH: Final = 120  # nom d'une pièce ou d'un ensemble, en caractères

_EMPTY_NAME: Final = QT_TRANSLATE_NOOP("Menuiserie", "Le nom ne peut pas être vide.")
_FORBIDDEN_NAME: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le nom ne peut pas contenir de saut de ligne, de tabulation ni de caractère de contrôle.",
)
_NAME_TOO_LONG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le nom est trop long ({count} caractères, {maximum} au plus)."
)


def cleaned_name(text: str) -> str:
    """Nom saisi, sans les espaces autour."""
    return text.strip()


def decide_rename(old: str, text: str, *, furniture: bool) -> Decision:
    """« Renommer » en ``text`` : refusé s'il est vide, trop long, avec un caractère de contrôle,
    ou (ensemble) inutilisable dans une expression (le libellé d'un ensemble y est cité) ; sans
    message s'il ne change pas."""
    name = cleaned_name(text)
    if not name:
        return refuse(_EMPTY_NAME)
    if len(name) > MAX_NAME_LENGTH:
        return refuse(_NAME_TOO_LONG, count=str(len(name)), maximum=str(MAX_NAME_LENGTH))
    if has_forbidden_character(name):
        return refuse(_FORBIDDEN_NAME)
    if furniture:
        try:
            label_reference(name)
        except FurnitureError as error:
            return Decision(False, error.template, dict(error.params))
    if name == old:
        return Decision(False)
    return Decision(True)
