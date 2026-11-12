# SPDX-License-Identifier: LGPL-2.1-or-later
"""Format du CSV de la liste de débit choisi dans la boîte d'enregistrement (issue #223).

Deux formats : international (``,`` et point décimal) et français (``;`` et virgule décimale,
celui qu'un Excel ou un LibreOffice en français ouvre directement). Le choix se fait par le
filtre de la boîte d'enregistrement ; ce module le traduit en dialecte et propose le format par
défaut. Aucune dépendance à FreeCAD : la mémorisation du choix est faite par la couche GUI.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.cutlist import FRENCH_CSV, INTERNATIONAL_CSV, CsvDialect
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = [
    "FILTERS",
    "FRENCH",
    "INTERNATIONAL",
    "dialect_of",
    "initial_format",
]

FRENCH: Final = "french"
INTERNATIONAL: Final = "international"

# Texte (à traduire) du filtre de chaque format ; l'ordre est celui de la boîte.
FILTERS: Final = {
    FRENCH: QT_TRANSLATE_NOOP("Menuiserie", "CSV français : « ; » et virgule décimale (*.csv)"),
    INTERNATIONAL: QT_TRANSLATE_NOOP(
        "Menuiserie", "CSV international : « , » et point décimal (*.csv)"
    ),
}
_DIALECTS: Final = {FRENCH: FRENCH_CSV, INTERNATIONAL: INTERNATIONAL_CSV}


def dialect_of(csv_format: str) -> CsvDialect:
    """Dialecte du format ``csv_format`` ; un nom inconnu donne le format international."""
    return _DIALECTS.get(csv_format, INTERNATIONAL_CSV)


def initial_format(remembered: str, language: str) -> str:
    """Format proposé d'abord : le dernier choix de l'utilisateur s'il est connu, sinon le
    français quand FreeCAD est en français (``language`` : nom ou code de la langue), sinon
    l'international."""
    if remembered in _DIALECTS:
        return remembered
    return FRENCH if language.strip().lower().startswith("fr") else INTERNATIONAL
