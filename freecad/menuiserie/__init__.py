# SPDX-License-Identifier: LGPL-2.1-or-later
"""Atelier FreeCAD « Menuiserie ».

Ce module ne doit rien importer de lourd : il est chargé au démarrage de
FreeCAD, y compris en mode console (freecadcmd).
"""

from pathlib import Path

__version__ = "0.1.0"

PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PACKAGE_DIR / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
TRANSLATIONS_DIR = RESOURCES_DIR / "translations"
DATA_DIR = PACKAGE_DIR / "data"


def icon_path(name: str) -> str:
    """Retourne le chemin absolu d'une icône du workbench, sous forme de chaîne."""
    return str(ICONS_DIR / name)
