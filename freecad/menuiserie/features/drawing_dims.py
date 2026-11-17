# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes des plans : place qu'elles prennent d'après la taille du texte réglée dans TechDraw
(lue, jamais changée) et pose d'une cote par les fabriques de TechDraw dans le bon document."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import DocumentObject

__all__ = [
    "DIMENSION_CLEARANCE_MM",
    "SECTION_CLEARANCE_MM",
    "added_by",
    "dimension_font_mm",
    "dimension_row_mm",
    "has_geometry",
    "overall_band_mm",
    "part_band_mm",
    "set_geometry_waiter",
    "wait_for_geometry",
]

DIMENSION_CLEARANCE_MM: Final = 4.0  # du bord de la vue au texte d'une cote, plus le texte
SECTION_CLEARANCE_MM: Final = 14.0  # idem, au-delà des flèches et lettres d'un trait de coupe
DIMENSION_FONT_MM: Final = 3.5  # taille du texte des cotes si TechDraw n'en donne pas
_DIMENSION_PARAMS: Final = "User parameter:BaseApp/Preferences/Mod/TechDraw/Dimensions"


def added_by(page: DocumentObject, make: Callable[[], object]) -> list[str]:
    """Noms des objets que ``make`` ajoute à la page. Les fabriques de cotes de TechDraw écrivent
    dans le document actif de FreeCAD : celui de la page est activé le temps de l'appel, puis le
    précédent est remis."""
    doc = page.Document
    before = {obj.Name for obj in page.Views}
    active = App.ActiveDocument
    previous = active.Name if active is not None else ""
    App.setActiveDocument(doc.Name)
    try:
        make()
    finally:
        if previous and previous != doc.Name and previous in App.listDocuments():
            App.setActiveDocument(previous)
    return [obj.Name for obj in page.Views if obj.Name not in before]


def dimension_font_mm() -> float:
    """Taille du texte des cotes réglée dans les préférences de TechDraw (lue, jamais changée) :
    l'écart des cotes à leur vue en dépend."""
    size = App.ParamGet(_DIMENSION_PARAMS).GetFloat("FontSize", DIMENSION_FONT_MM)
    return size if 1.0 <= size <= 20.0 else DIMENSION_FONT_MM


def dimension_row_mm() -> float:
    """Écart entre deux rangées de cotes parallèles."""
    return 1.5 * dimension_font_mm() + DIMENSION_CLEARANCE_MM


def overall_band_mm(chains: bool = True) -> float:
    """Place des cotes au-dessus et à gauche de la face du plan de l'ouvrage : traits de coupe,
    cotes de détail (si ``chains``), cotes hors tout."""
    return SECTION_CLEARANCE_MM + (2 if chains else 1) * dimension_row_mm()


def part_band_mm() -> float:
    """Place des cotes au-dessus et à gauche de la face d'un plan de pièce."""
    return dimension_row_mm() + dimension_font_mm()


# Attente de la géométrie des vues, branchée par l'interface (gui/drawing_hlr.py) : sans
# interface, TechDraw calcule les vues pendant le recalcul et rien n'est à attendre.
_WAITER: list[Callable[[Sequence[DocumentObject]], None]] = []


def set_geometry_waiter(waiter: Callable[[Sequence[DocumentObject]], None] | None) -> None:
    """Fonction qui attend que des vues aient leur géométrie (``None`` : aucune)."""
    _WAITER[:] = [] if waiter is None else [waiter]


def has_geometry(view: DocumentObject) -> bool:
    """La vue ``view`` a-t-elle sa géométrie (arêtes visibles) : une cote peut s'y poser."""
    try:
        return bool(view.getVisibleEdges())
    except (AttributeError, RuntimeError):
        return False


def wait_for_geometry(views: Sequence[DocumentObject]) -> bool:
    """Attend, si l'interface sait le faire, que ``views`` aient leur géométrie ; vrai si elles
    l'ont toutes."""
    if _WAITER:
        _WAITER[0](views)
    return all(has_geometry(view) for view in views)
