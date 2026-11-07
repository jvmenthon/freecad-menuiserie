# SPDX-License-Identifier: LGPL-2.1-or-later
"""Accès au catalogue de quincaillerie depuis FreeCAD : chemins, cache de session, journal.

Le catalogue (intégré + fichier personnel ``quincaillerie.json`` du dossier de l'atelier) est lu
une fois par session (:func:`get_catalog`) ; :func:`reload_catalog` le relit. Les anomalies sont
écrites, traduites, dans la vue rapport à chaque lecture. Aucun accès réseau (ADR 0033).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Final

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.hardware import Catalog, CatalogSource, load_catalog
from freecad.menuiserie.features.library import report_issues, user_library_path

__all__ = ["builtin_catalog_path", "get_catalog", "reload_catalog", "user_catalog_path"]

CATALOG_FILE_NAME: Final = "quincaillerie.json"


def builtin_catalog_path() -> Path:
    """Fichier du catalogue intégré à l'atelier."""
    return DATA_DIR / CATALOG_FILE_NAME


def user_catalog_path() -> Path:
    """Catalogue personnel : à côté du fichier de matériaux de l'utilisateur (même dossier)."""
    return user_library_path().with_name(CATALOG_FILE_NAME)


@cache
def _session_catalog() -> Catalog:
    user = user_catalog_path()
    catalog, issues = load_catalog(builtin_catalog_path(), [CatalogSource(user, str(user))])
    report_issues(issues)
    return catalog


def get_catalog() -> Catalog:
    """Catalogue de la session, lu au premier appel (anomalies signalées une fois)."""
    return _session_catalog()


def reload_catalog() -> Catalog:
    """Relit le catalogue intégré et le fichier personnel, et signale leurs anomalies."""
    _session_catalog.cache_clear()
    return _session_catalog()
