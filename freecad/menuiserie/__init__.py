# SPDX-License-Identifier: LGPL-2.1-or-later
"""Atelier FreeCAD « Menuiserie ».

Ce module ne doit rien importer de lourd : il est chargé au démarrage de
FreeCAD, y compris en mode console (freecadcmd).
"""

from freecad.menuiserie.core.result import (
    Result,
    ResultError,
    combine,
    error,
    failure,
    success,
    validate,
)

__all__ = [
    "Result",
    "ResultError",
    "combine",
    "error",
    "failure",
    "success",
    "validate",
]