# SPDX-License-Identifier: LGPL-2.1-or-later
"""Accès à la bibliothèque de matériaux depuis FreeCAD : chemins, cache de session, journal.

La bibliothèque est lue une fois par session (:func:`get_library`) ; :func:`reload_library`
la relit, par exemple depuis la console après avoir modifié le fichier utilisateur. Les
anomalies sont écrites dans la vue rapport, traduites, à chaque lecture.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path
from typing import Final

import FreeCAD as App

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import (
    BUILTIN_SOURCE,
    LibraryIssue,
    MaterialLibrary,
    Severity,
    load_library,
)
from freecad.menuiserie.features.i18n import console_text, translated

PARAM_PATH: Final = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
USER_LIBRARY_PARAM: Final = "UserLibraryPath"
USER_LIBRARY_FOLDER: Final = "Menuiserie"
LIBRARY_FILE_NAME: Final = "materiaux.json"
_DISPLAY_LANGUAGE: Final = "fr"


def builtin_library_path() -> Path:
    """Fichier de la bibliothèque intégrée à l'atelier."""
    return DATA_DIR / LIBRARY_FILE_NAME


def user_library_path() -> Path:
    """Fichier de l'utilisateur : paramètre ``UserLibraryPath`` s'il est renseigné, sinon
    ``<dossier de données utilisateur>/Menuiserie/materiaux.json``."""
    custom = App.ParamGet(PARAM_PATH).GetString(USER_LIBRARY_PARAM, "").strip()
    if custom:
        return Path(custom).expanduser()
    return Path(App.getUserAppDataDir()) / USER_LIBRARY_FOLDER / LIBRARY_FILE_NAME


def display_language() -> str:
    """Langue des libellés de matériaux : toujours le français en J1 (choix de la langue : J5)."""
    return _DISPLAY_LANGUAGE


def issue_message(issue: LibraryIssue) -> str:
    """Message traduit d'une anomalie ; la source « intégrée » est traduite elle aussi."""
    params = dict(issue.params)
    if issue.source == BUILTIN_SOURCE:
        params["source"] = translated(BUILTIN_SOURCE)
    return translated(issue.template, params)


def _console_writer(severity: Severity) -> Callable[[str], None]:
    """Méthode de la vue rapport adaptée à la gravité (lue à l'appel, remplaçable en test)."""
    writers: dict[Severity, Callable[[str], None]] = {
        Severity.ERROR: App.Console.PrintError,
        Severity.WARNING: App.Console.PrintWarning,
        Severity.INFO: App.Console.PrintLog,
    }
    return writers[severity]


def report_issues(issues: Iterable[LibraryIssue]) -> None:
    """Écrit chaque anomalie dans la vue rapport : erreur, avertissement ou journal."""
    for issue in issues:
        _console_writer(issue.severity)(console_text(issue_message(issue)))


@cache
def _session_library() -> MaterialLibrary:
    """Cache explicite de la session, vidé par :func:`reload_library`."""
    library, issues = load_library(builtin_library_path(), user_library_path())
    report_issues(issues)
    return library


def get_library() -> MaterialLibrary:
    """Bibliothèque de la session, lue au premier appel (anomalies signalées une fois)."""
    return _session_library()


def reload_library() -> MaterialLibrary:
    """Relit la bibliothèque intégrée et le fichier utilisateur, et signale leurs anomalies."""
    _session_library.cache_clear()
    return _session_library()
