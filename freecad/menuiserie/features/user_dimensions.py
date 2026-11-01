# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fichier des épaisseurs et formats de panneaux personnels, dans le dossier utilisateur (ADR 0028).

Le fichier ``dimensions.json`` est à côté de la bibliothèque personnelle de matériaux, donc
partagé entre tous les projets. Lecture bornée en taille, écriture atomique (fichier temporaire
puis remplacement). Un fichier illisible ou invalide est ignoré avec un avertissement : l'atelier
fonctionne sans.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.user_dimensions import (
    MAX_FILE_BYTES,
    UserDimensions,
    dimensions_from_text,
    dimensions_to_text,
    with_sheet,
    with_thickness,
)
from freecad.menuiserie.features.i18n import console_text, translated, translated_errors
from freecad.menuiserie.features.library import user_library_path

__all__ = ["add_sheet", "add_thickness", "dimensions_path", "read_dimensions"]

FILE_NAME: Final = "dimensions.json"
_UNREADABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Dimensions personnelles ignorées : {path} est illisible ({error})."
)
_NOT_WRITTEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Impossible d'enregistrer {path} ({error}).")


def dimensions_path() -> Path:
    """Fichier des dimensions personnelles, dans le dossier de la bibliothèque personnelle."""
    return user_library_path().parent / FILE_NAME


def read_dimensions() -> UserDimensions:
    """Dimensions du fichier ; vides s'il n'existe pas, ou s'il est illisible ou invalide
    (avertissement dans la vue rapport)."""
    path = dimensions_path()
    try:
        if not path.is_file():
            return UserDimensions()
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        with translated_errors():
            return dimensions_from_text(data.decode("utf-8"))
    except (OSError, ValueError) as error:
        text = translated(_UNREADABLE, {"path": str(path), "error": str(error)})
        App.Console.PrintWarning(console_text(text))
        return UserDimensions()


def _write(dimensions: UserDimensions) -> None:
    """Écrit le fichier de façon atomique ; ``ValueError`` traduite si l'écriture échoue."""
    path = dimensions_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".dimensions-")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(dimensions_to_text(dimensions))
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except OSError as error:
        raise ValueError(
            translated(_NOT_WRITTEN, {"path": str(path), "error": str(error)})
        ) from None


def add_thickness(thickness: float) -> UserDimensions:
    """Ajoute ``thickness`` (mm) aux épaisseurs personnelles et enregistre ; ``ValueError``
    traduite si elle est refusée ou si l'écriture échoue."""
    with translated_errors():
        updated = with_thickness(read_dimensions(), thickness)
    _write(updated)
    return updated


def add_sheet(length: float, width: float) -> UserDimensions:
    """Ajoute le format ``length`` x ``width`` (mm) aux formats personnels et enregistre ;
    mêmes refus que :func:`add_thickness`."""
    with translated_errors():
        updated = with_sheet(read_dimensions(), length, width)
    _write(updated)
    return updated
