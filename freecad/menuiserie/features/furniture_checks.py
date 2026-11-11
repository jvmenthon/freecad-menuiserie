# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôles communs des opérations sur les ensembles (objet membre, ensemble, libellé cité)."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["NOT_IN_FURNITURE", "checked_furniture", "member_object", "quoted_label"]

_NOT_A_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'est ni une pièce de bois, ni une pièce en bois, ni une pièce usinée, ni un "
    "ensemble.",
)
NOT_IN_FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est membre d'aucun ensemble."
)
_NOT_FURNITURE: Final = QT_TRANSLATE_NOOP("Menuiserie", "« {label} » n'est pas un ensemble.")


def quoted_label(obj: DocumentObject) -> dict[str, str]:
    return {"label": quoted_value(getattr(obj, "Label", obj))}


def member_object(obj: DocumentObject) -> DocumentObject:
    """Objet qui porte les propriétés de membre : l'ensemble lui-même, ou la brute d'une pièce
    (de bois, en bois ou usinée) ; ``TypeError`` traduite sinon."""
    if is_furniture(obj) or is_timber(obj):
        return obj
    try:
        return blank_of(obj)
    except TypeError:
        raise TypeError(translated(_NOT_A_MEMBER, quoted_label(obj))) from None


def checked_furniture(obj: DocumentObject) -> DocumentObject:
    """``obj`` s'il est un ensemble ; ``TypeError`` traduite sinon."""
    if not is_furniture(obj):
        raise TypeError(translated(_NOT_FURNITURE, quoted_label(obj)))
    return obj
