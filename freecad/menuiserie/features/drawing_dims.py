# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes des plans : place qu'elles prennent d'après la taille du texte réglée dans TechDraw
(lue, jamais changée) et pose d'une cote par les fabriques de TechDraw dans le bon document."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated

__all__ = [
    "DIMENSION_CLEARANCE_MM",
    "Settle",
    "added_by",
    "dimension_font_mm",
    "dimension_row_mm",
    "has_geometry",
    "overall_band_mm",
    "part_band_mm",
    "section_clearance_mm",
    "text_height_mm",
    "wait_for_geometry",
]

DIMENSION_CLEARANCE_MM: Final = 4.0  # du bord de la vue au texte d'une cote, plus le texte
# Taille du texte des cotes quand la préférence n'est pas écrite : celle de TechDraw
# (``Preferences::DefaultFontSizeInMM``), qui sert aussi aux lettres des traits de coupe.
DIMENSION_FONT_MM: Final = 5.0
_MIN_SECTION_CLEARANCE_MM: Final = 14.0
_DIMENSION_PARAMS: Final = "User parameter:BaseApp/Preferences/Mod/TechDraw/Dimensions"


def added_by(page: DocumentObject, make: Callable[[], object]) -> list[str]:
    """Noms des objets que ``make`` ajoute à la page. Les fabriques de cotes de TechDraw écrivent
    dans le document actif de FreeCAD : celui de la page est activé le temps de l'appel, puis le
    précédent est remis (sauf s'il a été fermé entre-temps ; sans document actif au départ,
    celui de la page le reste)."""
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


def text_height_mm() -> float:
    """Place d'un texte de cote, de sa ligne et de ses flèches, perpendiculairement à la cote."""
    return 1.5 * dimension_font_mm()


def section_clearance_mm() -> float:
    """Écart du bord de la face au texte d'une cote qui doit passer au-delà des traits de coupe :
    TechDraw prolonge le trait de deux tailles de texte hors de la vue et y pose la lettre (une
    taille de plus), à la taille du texte des cotes."""
    return max(_MIN_SECTION_CLEARANCE_MM, 3.2 * dimension_font_mm() + 2.0)


def dimension_row_mm() -> float:
    """Écart entre deux rangées de cotes parallèles."""
    return text_height_mm() + DIMENSION_CLEARANCE_MM


def overall_band_mm(chains: bool = True) -> float:
    """Place des cotes au-dessus et à gauche de la face du plan de l'ouvrage : traits de coupe,
    cotes de détail (si ``chains``), cotes hors tout."""
    return section_clearance_mm() + (2 if chains else 1) * dimension_row_mm()


def part_band_mm() -> float:
    """Place des cotes au-dessus et à gauche de la face d'un plan de pièce."""
    return dimension_row_mm() + dimension_font_mm()


Settle = Callable[[Sequence[DocumentObject]], None]  # attente de la géométrie (interface)
_NOT_READY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Plan : TechDraw n'a pas fini de calculer les vues, certaines cotes sont omises. "
    "Relancez la commande pour les poser.",
)


def has_geometry(view: DocumentObject) -> bool:
    """La vue ``view`` a-t-elle sa géométrie (arêtes visibles) : une cote peut s'y poser."""
    try:
        return bool(view.getVisibleEdges())
    except (AttributeError, RuntimeError):
        return False


def wait_for_geometry(views: Sequence[DocumentObject], settle: Settle | None) -> bool:
    """Attend avec ``settle`` (l'interface, où TechDraw calcule les vues en tâche de fond ;
    sans interface, elles le sont pendant le recalcul) que ``views`` aient leur géométrie ;
    vrai si elles l'ont toutes, sinon l'utilisateur est averti que des cotes manquent."""
    if settle is not None:
        settle(views)
    ready = all(has_geometry(view) for view in views)
    if not ready:
        report_warning(translated(_NOT_READY))
    return ready
