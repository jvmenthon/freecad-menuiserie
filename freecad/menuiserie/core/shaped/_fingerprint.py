# SPDX-License-Identifier: LGPL-2.1-or-later
"""Empreinte textuelle d'un solide d'une forme importée (``SolidSignature``, B11).

Une forme importée à plusieurs solides donne une pièce par solide, repérée par son indice. Pour ne
jamais prendre un solide pour un autre si la forme est remplacée par un script, la pièce garde
l'empreinte (volume, aire, inertie, centre de masse) du solide converti. L'empreinte est un texte
(propriété ``App::PropertyString``) ; la comparaison tolère l'arrondi de l'écriture et de
l'enregistrement du document.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

SEPARATOR: Final = ";"
SIGNIFICANT_DIGITS: Final = 9
RELATIVE_TOLERANCE: Final = 1e-6
ABSOLUTE_TOLERANCE: Final = 1e-6
MAX_VALUES: Final = 32


def encode_fingerprint(values: Sequence[float]) -> str:
    """Texte des ``values`` (au plus ``MAX_VALUES`` nombres finis), à ``SIGNIFICANT_DIGITS``
    chiffres significatifs. ``ValueError`` citant le champ sinon."""
    if not values or len(values) > MAX_VALUES:
        raise ValueError(f"values : de 1 à {MAX_VALUES} nombres attendus")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("values : nombres finis attendus")
    return SEPARATOR.join(f"{value:.{SIGNIFICANT_DIGITS - 1}e}" for value in values)


def _parsed(text: str) -> list[float] | None:
    """Nombres finis du texte, ``None`` si le texte n'est pas une empreinte lisible."""
    parts = text.split(SEPARATOR)
    if len(parts) > MAX_VALUES:
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    return numbers if all(math.isfinite(number) for number in numbers) else None


def fingerprint_matches(text: str, values: Sequence[float]) -> bool:
    """Vrai si l'empreinte ``text`` est celle de ``values`` (même nombre de valeurs, chacune à
    ``RELATIVE_TOLERANCE`` près). Faux pour un texte illisible ou vide."""
    stored = _parsed(text)
    if stored is None or len(stored) != len(values):
        return False
    return all(
        math.isclose(old, new, rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE)
        for old, new in zip(stored, values, strict=True)
    )
