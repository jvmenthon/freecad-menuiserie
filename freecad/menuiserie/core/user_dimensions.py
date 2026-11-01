# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseurs et formats de panneaux ajoutés par l'utilisateur, partagés entre projets (ADR 0028).

Modèle pur : lecture stricte d'un texte JSON ``{"format": 1, "thicknesses": [mm...], "sheets":
[[longueur, largeur]...]}``, ajout d'une valeur, sérialisation. Le fichier est lu et écrit par
:mod:`freecad.menuiserie.features.user_dimensions`. Toutes les longueurs sont en mm.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Final

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.materials import MAX_THICKNESS_MM, MAX_THICKNESSES

__all__ = [
    "DEFAULT_SHEETS",
    "FORMAT_VERSION",
    "MAX_FILE_BYTES",
    "MAX_SHEETS",
    "UserDimensions",
    "dimensions_from_text",
    "dimensions_to_text",
    "with_sheet",
    "with_thickness",
]

FORMAT_VERSION: Final = 1
MAX_FILE_BYTES: Final = 65_536
MAX_SHEETS: Final = 50
# Formats courants du commerce (longueur x largeur), proposés avec ceux de l'utilisateur.
DEFAULT_SHEETS: Final = ((2500.0, 1250.0), (2440.0, 1220.0), (3050.0, 1525.0))
_SAME_MM: Final = 0.05  # deux valeurs plus proches sont la même

INVALID_FILE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Fichier des dimensions personnelles invalide : {reason}."
)
THICKNESS_OUT_OF_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'épaisseur doit être comprise entre {min} et {max} mm."
)
SHEET_OUT_OF_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La longueur et la largeur du format doivent être comprises entre {min} et {max} mm.",
)
TOO_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Trop de valeurs personnelles ({max} au plus) : retirez-en du fichier."
)


@dataclass(frozen=True)
class UserDimensions:
    """Épaisseurs (triées, sans doublon) et formats de panneaux (longueur, largeur) en mm."""

    thicknesses: tuple[float, ...] = ()
    sheets: tuple[tuple[float, float], ...] = ()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _thickness(value: Any) -> float | None:
    number = _number(value)
    ok = number is not None and MIN_DIMENSION_MM <= number <= MAX_THICKNESS_MM
    return number if ok else None


def _in_dimension_range(number: float | None) -> bool:
    return number is not None and MIN_DIMENSION_MM <= number <= MAX_DIMENSION_MM


def _unique(values: list[float]) -> tuple[float, ...]:
    kept: list[float] = []
    for value in sorted(values):
        if not kept or value - kept[-1] > _SAME_MM:
            kept.append(value)
    return tuple(kept)


def _invalid(reason: str) -> TemplatedError:
    return TemplatedError(INVALID_FILE, {"reason": reason})


def _document(text: str) -> dict[str, Any]:
    """Objet JSON du fichier, ``format`` 1 vérifié."""
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise _invalid("fichier trop volumineux")

    def refuse_constant(name: str) -> Any:
        raise ValueError(name)

    try:
        document = json.loads(text, parse_constant=refuse_constant)
    except (ValueError, RecursionError) as error:
        raise _invalid(f"JSON illisible ({type(error).__name__})") from None
    if not isinstance(document, dict):
        raise _invalid("un objet JSON est attendu")
    version = document.get("format")
    if isinstance(version, bool) or version != FORMAT_VERSION:
        raise _invalid("« format » doit valoir 1")
    return dict(document)


def _sheet(item: Any) -> tuple[float, float]:
    """Format ``[longueur, largeur]`` du fichier, ou erreur."""
    if isinstance(item, list) and len(item) == 2:
        length, width = _number(item[0]), _number(item[1])
        if (
            length is not None
            and width is not None
            and _in_dimension_range(length)
            and _in_dimension_range(width)
        ):
            return (length, width)
    raise _invalid("format de panneau : [longueur, largeur] en mm attendu")


def dimensions_from_text(text: str) -> UserDimensions:
    """Dimensions du fichier JSON ``text`` ; ``TemplatedError`` si le fichier est invalide
    (texte trop long, JSON illisible, mauvais format ou valeur hors bornes)."""
    document = _document(text)
    raw_thicknesses = document.get("thicknesses", [])
    raw_sheets = document.get("sheets", [])
    if not isinstance(raw_thicknesses, list) or not isinstance(raw_sheets, list):
        raise _invalid("« thicknesses » et « sheets » sont des listes")
    if len(raw_thicknesses) > MAX_THICKNESSES or len(raw_sheets) > MAX_SHEETS:
        raise _invalid("trop de valeurs")
    thicknesses: list[float] = []
    for value in raw_thicknesses:
        number = _thickness(value)
        if number is None:
            raise _invalid(f"épaisseur hors de {MIN_DIMENSION_MM:g} à {MAX_THICKNESS_MM:g} mm")
        thicknesses.append(number)
    sheets = [_sheet(item) for item in raw_sheets]
    return UserDimensions(_unique(thicknesses), _unique_sheets(sheets))


def _unique_sheets(sheets: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    kept: list[tuple[float, float]] = []
    for sheet in sorted(sheets):
        if not any(
            abs(sheet[0] - k[0]) <= _SAME_MM and abs(sheet[1] - k[1]) <= _SAME_MM for k in kept
        ):
            kept.append(sheet)
    return tuple(kept)


def dimensions_to_text(dimensions: UserDimensions) -> str:
    """Texte JSON du fichier (UTF-8, indenté, terminé par un retour à la ligne)."""
    document = {
        "format": FORMAT_VERSION,
        "thicknesses": list(dimensions.thicknesses),
        "sheets": [list(sheet) for sheet in dimensions.sheets],
    }
    return json.dumps(document, indent=2) + "\n"


def with_thickness(dimensions: UserDimensions, thickness: float) -> UserDimensions:
    """``dimensions`` avec ``thickness`` (mm) en plus ; ``TemplatedError`` hors bornes ou si la
    liste est pleine ; sans changement si la valeur y est déjà."""
    if _thickness(thickness) is None:
        raise TemplatedError(
            THICKNESS_OUT_OF_RANGE, {"min": f"{MIN_DIMENSION_MM:g}", "max": f"{MAX_THICKNESS_MM:g}"}
        )
    values = _unique([*dimensions.thicknesses, float(thickness)])
    if len(values) > MAX_THICKNESSES:
        raise TemplatedError(TOO_MANY, {"max": str(MAX_THICKNESSES)})
    return UserDimensions(values, dimensions.sheets)


def with_sheet(dimensions: UserDimensions, length: float, width: float) -> UserDimensions:
    """``dimensions`` avec le format ``length`` x ``width`` (mm) en plus ; mêmes règles que
    :func:`with_thickness`."""
    if not (_in_dimension_range(_number(length)) and _in_dimension_range(_number(width))):
        raise TemplatedError(
            SHEET_OUT_OF_RANGE, {"min": f"{MIN_DIMENSION_MM:g}", "max": f"{MAX_DIMENSION_MM:g}"}
        )
    sheets = _unique_sheets([*dimensions.sheets, (float(length), float(width))])
    if len(sheets) > MAX_SHEETS:
        raise TemplatedError(TOO_MANY, {"max": str(MAX_SHEETS)})
    return UserDimensions(dimensions.thicknesses, sheets)
