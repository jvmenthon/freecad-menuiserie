# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vues du plan de l'ouvrage : face, coupes au milieu du meuble, perspective et cotes hors tout,
en objets TechDraw standard (ADR 0053). Choix de jv du 2026-11-13 : les menuisiers lisent un
meuble en coupe, la vue de dessus et la vue de gauche cèdent la place à deux coupes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.drawing import OverallLayout, Spot
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "HORIZONTAL",
    "PAGE_NAME",
    "SECTION_TYPE",
    "VERTICAL",
    "VIEW_TYPE",
    "add_overall_views",
    "removal_rank",
    "techdraw",
]

PAGE_NAME: Final = "MenuiseriePlan"
VIEW_TYPE: Final = "TechDraw::DrawViewPart"
SECTION_TYPE: Final = "TechDraw::DrawViewSection"
HORIZONTAL: Final = 0  # sens d'une cote d'étendue de TechDraw
VERTICAL: Final = 1
_VIEW_LABELS: Final = {
    "Front": QT_TRANSLATE_NOOP("Menuiserie", "Face"),
    "CutH": QT_TRANSLATE_NOOP("Menuiserie", "Coupe horizontale"),
    "CutV": QT_TRANSLATE_NOOP("Menuiserie", "Coupe verticale"),
    "Iso": QT_TRANSLATE_NOOP("Menuiserie", "Perspective"),
}
# Direction de vue (vers l'observateur) et axe horizontal de la feuille, dans le repère global.
# Une coupe retire la moitié du côté de sa direction : la coupe verticale (à droite de la face)
# montre la moitié droite vue de gauche, la coupe horizontale (sous la face) la moitié basse vue
# de dessus, comme les vues de gauche et de dessus de la disposition européenne.
_DIRECTIONS: Final = {
    "Front": ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    "CutH": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "CutV": ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    "Iso": ((1.0, -1.0, 1.0), (1.0, 1.0, 0.0)),
}
_SECTIONS: Final = {"CutV": "A", "CutH": "B"}  # repère du trait de coupe sur la face
# Cotes hors tout : (vue, sens) pour la largeur (X), la profondeur (Y) et la hauteur (Z). La
# profondeur se lit sur la coupe verticale, qui garde le plateau qu'une coupe horizontale ôte.
_OVERALL: Final = (("Front", HORIZONTAL), ("CutV", HORIZONTAL), ("Front", VERTICAL))


def techdraw() -> Any:
    """Module TechDraw, importé à l'appel : l'atelier se charge sans lui."""
    import TechDraw

    return TechDraw


def _add_view(
    page: DocumentObject, key: str, sources: Sequence[DocumentObject], spot: Spot
) -> DocumentObject:
    view = page.Document.addObject(VIEW_TYPE, f"{PAGE_NAME}{key}")
    page.addView(view)
    view.Source = list(sources)
    _place(view, key, spot)
    return view


def _add_section(
    page: DocumentObject, key: str, base: DocumentObject, center: Any, spot: Spot
) -> DocumentObject:
    """Coupe de ``base`` par le plan qui passe par ``center`` (milieu de l'ouvrage), repérée
    « A-A » ou « B-B » sur la vue de face. La coupe ne suit pas un changement de taille de
    l'ouvrage : relancer la commande la replace au milieu."""
    section = page.Document.addObject(SECTION_TYPE, f"{PAGE_NAME}{key}")
    page.addView(section)
    section.BaseView = base
    section.Source = list(base.Source)
    section.ScaleType = base.ScaleType
    section.Scale = base.Scale
    section.SectionSymbol = _SECTIONS[key]
    section.SectionOrigin = center
    _place(section, key, spot)
    section.SectionNormal = section.Direction  # après Direction, que TechDraw peut recalculer
    return section


def _place(view: DocumentObject, key: str, spot: Spot) -> None:
    direction, x_direction = _DIRECTIONS[key]
    view.Direction = App.Vector(*direction)
    view.XDirection = App.Vector(*x_direction)
    view.X = spot.x
    view.Y = spot.y
    view.Label = translated(_VIEW_LABELS[key])


def _add_extent(page: DocumentObject, view: DocumentObject, direction: int) -> list[str]:
    """Pose une cote d'étendue de toute la vue (elle suit la géométrie) ; renvoie les noms des
    objets ajoutés à la page. ``makeExtentDim`` écrit dans le document actif de FreeCAD : celui de
    la page est activé le temps de l'appel, puis le précédent est remis."""
    doc = page.Document
    before = {obj.Name for obj in page.Views}
    previous = App.ActiveDocument
    App.setActiveDocument(doc.Name)
    try:
        techdraw().makeExtentDim(view, [], direction)
    finally:
        if previous is not None and previous != doc:
            App.setActiveDocument(previous.Name)
    return [obj.Name for obj in page.Views if obj.Name not in before]


def removal_rank(obj: DocumentObject) -> int:
    """Ordre de retrait : cotes, puis coupes, puis les vues dont elles dépendent."""
    return {SECTION_TYPE: 1, VIEW_TYPE: 2}.get(obj.TypeId, 0)


def add_overall_views(
    page: DocumentObject, sources: Sequence[DocumentObject], layout: OverallLayout, center: Any
) -> list[str]:
    """Pose sur ``page`` la face, les coupes verticale et horizontale par ``center`` (milieu de
    l'ouvrage), la perspective et les cotes hors tout ; renvoie les noms des objets posés."""
    doc = page.Document
    front = _add_view(page, "Front", sources, layout.front)
    views = {
        "Front": front,
        "CutV": _add_section(page, "CutV", front, center, layout.side),
        "CutH": _add_section(page, "CutH", front, center, layout.top),
        "Iso": _add_view(page, "Iso", sources, layout.iso),
    }
    doc.recompute()  # les cotes d'étendue lisent la géométrie des vues
    names = [view.Name for view in views.values()]
    for key, direction in _OVERALL:
        names.extend(_add_extent(page, views[key], direction))
    return names
