# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan de l'ouvrage dans une page TechDraw standard (issue #153, ADR 0053, lot P-a).

Une ``TechDraw::DrawPage`` ordinaire, sans proxy, marquée par la propriété booléenne masquée
``MenuiserieDrawing`` : face, dessus, vue de gauche et perspective à la même échelle, plus trois
cotes hors tout (``TechDraw::DrawViewDimExtent``, qui suivent la géométrie des vues). Un document
ouvert sans l'atelier garde une page ordinaire.

Les vues suivent le modèle toutes seules (ce sont des vues TechDraw). Relancer la fabrique refait
l'échelle et la mise en page ; une page que le menuisier a modifiée (vue ajoutée ou retirée) n'est
pas touchée : une nouvelle page est créée. ``TechDraw`` est importé à l'appel seulement : l'atelier
se charge sans lui.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.drawing import (
    DEFAULT_FORMAT,
    Orientation,
    OverallLayout,
    Spot,
    overall_layout,
    page_size,
    pick_template,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import HIDDEN, Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "MARKER",
    "PAGE_NAME",
    "TITLE",
    "DrawingOptions",
    "drawing_sources",
    "find_overall_drawing",
    "is_workshop_drawing",
    "make_overall_drawing",
    "overall_dimensions",
    "techdraw_available",
]

PAGE_NAME: Final = "MenuiseriePlan"
MARKER: Final = "MenuiserieDrawing"
OWNED: Final = "MenuiserieDrawingViews"  # noms des vues et cotes posées par l'atelier
PAGE_TYPE: Final = "TechDraw::DrawPage"
TEMPLATE_TYPE: Final = "TechDraw::DrawSVGTemplate"
VIEW_TYPE: Final = "TechDraw::DrawViewPart"
MAX_TEMPLATES: Final = 2000  # plafond du balayage du dossier de gabarits de TechDraw
HORIZONTAL: Final = 0  # sens d'une cote d'étendue de TechDraw
VERTICAL: Final = 1

TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de l'ouvrage")
_MARKER_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Page de plan construite par l'atelier Menuiserie."
)
_OWNED_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Vues et cotes de cette page posées par l'atelier Menuiserie."
)
_NO_TECHDRAW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : l'atelier TechDraw de FreeCAD n'est pas disponible."
)
_NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan impossible : aucune pièce à dessiner.")
_FOREIGN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : « {label} » appartient à un autre document."
)
_VIEW_LABELS: Final = {
    "Front": QT_TRANSLATE_NOOP("Menuiserie", "Face"),
    "Top": QT_TRANSLATE_NOOP("Menuiserie", "Dessus"),
    "Side": QT_TRANSLATE_NOOP("Menuiserie", "Gauche"),
    "Iso": QT_TRANSLATE_NOOP("Menuiserie", "Perspective"),
}
# Direction de vue (vers l'observateur) et axe horizontal de la feuille, dans le repère global.
_DIRECTIONS: Final = {
    "Front": ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    "Top": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "Side": ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    "Iso": ((1.0, -1.0, 1.0), (1.0, 1.0, 0.0)),
}
# Cotes hors tout : (vue, sens) pour la largeur (X), la profondeur (Y) et la hauteur (Z).
_OVERALL: Final = (("Front", HORIZONTAL), ("Top", VERTICAL), ("Front", VERTICAL))


@dataclass(frozen=True)
class DrawingOptions:
    """Feuille du plan : format ISO (« A3 »…) et sens."""

    page_format: str = DEFAULT_FORMAT
    orientation: Orientation = Orientation.LANDSCAPE


def _techdraw() -> Any:
    """Module TechDraw, importé à l'appel : l'atelier se charge sans lui."""
    import TechDraw

    return TechDraw


def techdraw_available() -> bool:
    """Vrai si le module TechDraw de FreeCAD s'importe (il peut être désactivé ou absent)."""
    try:
        _techdraw()
    except ImportError:
        return False
    return True


def is_workshop_drawing(obj: object) -> bool:
    """Vrai si ``obj`` est une page de plan construite par l'atelier (même renommée)."""
    return getattr(obj, "TypeId", None) == PAGE_TYPE and getattr(obj, MARKER, False) is True


def _expanded(obj: DocumentObject, seen: set[str]) -> Iterator[DocumentObject]:
    """Objets à projeter pour ``obj`` : les membres d'un ensemble (sous-ensembles compris), la
    pièce usinée d'une pièce de bois assemblée, sinon l'objet lui-même s'il a une forme."""
    if obj.Name in seen:
        return
    seen.add(obj.Name)
    if is_furniture(obj):
        for member in members_of(obj):
            yield from _expanded(member, seen)
        return
    shown = (machined_part_of(obj) or obj) if is_timber(obj) else obj
    shape = getattr(shown, "Shape", None)
    if shown.Name != obj.Name and shown.Name in seen:
        return
    seen.add(shown.Name)
    if obj.TypeId == "App::Part" or (shape is not None and not shape.isNull()):
        yield shown


def drawing_sources(doc: Document, objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Objets à projeter pour dessiner ``objects`` (ensembles, pièces, Std Part, solides d'autres
    ateliers), sans doublon et dans l'ordre donné. ``ValueError`` traduite pour un objet d'un autre
    document ou s'il n'y a rien à dessiner."""
    for obj in objects:
        if getattr(obj, "Document", None) != doc:
            raise ValueError(translated(_FOREIGN, {"label": str(getattr(obj, "Label", obj))}))
    seen: set[str] = set()
    sources = [shown for obj in objects for shown in _expanded(obj, seen)]
    if not sources:
        raise ValueError(translated(_NOTHING))
    return sources


def _global_box(sources: Sequence[DocumentObject]) -> Any:
    """Boîte englobante des ``sources`` dans le repère global du document."""
    box = App.BoundBox()
    for obj in sources:
        shape = Part.getShape(obj)
        if shape.isNull():
            continue
        outer = obj.getGlobalPlacement().multiply(obj.Placement.inverse())
        shape.Placement = outer.multiply(shape.Placement)
        box.add(shape.BoundBox)
    if not box.isValid():
        raise ValueError(translated(_NOTHING))
    return box


def _template_path(options: DrawingOptions) -> str | None:
    """Gabarit de page fourni par TechDraw pour ``options``, ``None`` si le dossier manque."""
    folder = Path(App.getResourceDir()) / "Mod" / "TechDraw" / "Templates"
    if not folder.is_dir():
        return None
    paths = sorted(str(path) for path in islice(folder.rglob("*.svg"), MAX_TEMPLATES))
    return pick_template(paths, options.page_format, options.orientation)


def _owned(page: DocumentObject) -> list[str]:
    return [name for name in getattr(page, OWNED, "").split(";") if name]


def _untouched(page: DocumentObject) -> bool:
    """Vrai si ``page`` ne contient que ce que l'atelier y a posé, au complet."""
    return sorted(view.Name for view in page.Views) == sorted(_owned(page))


def _front_view(page: DocumentObject) -> DocumentObject | None:
    owned = set(_owned(page))
    return next(
        (v for v in page.Views if v.Name in owned and v.TypeId == VIEW_TYPE),
        None,
    )


def find_overall_drawing(doc: Document, sources: Sequence[DocumentObject]) -> DocumentObject | None:
    """Page de plan de l'atelier qui dessine exactement ``sources`` et que le menuisier n'a pas
    modifiée ; ``None`` s'il n'y en a pas."""
    wanted = sorted(obj.Name for obj in sources)
    for obj in doc.Objects:
        if not is_workshop_drawing(obj) or not _untouched(obj):
            continue
        front = _front_view(obj)
        if front is not None and sorted(source.Name for source in front.Source) == wanted:
            return obj
    return None


def _create_page(doc: Document, options: DrawingOptions) -> DocumentObject:
    page = doc.addObject(PAGE_TYPE, PAGE_NAME)
    page.addProperty("App::PropertyBool", MARKER, "Menuiserie", _MARKER_TOOLTIP)
    page.addProperty("App::PropertyString", OWNED, "Menuiserie", _OWNED_TOOLTIP)
    setattr(page, MARKER, True)
    for name in (MARKER, OWNED):
        page.setEditorMode(name, HIDDEN)
    page.Label = translated(TITLE)
    template = doc.addObject(TEMPLATE_TYPE, f"{PAGE_NAME}Gabarit")
    path = _template_path(options)
    if path is not None:
        template.Template = path
    page.Template = template
    return page


def _add_view(
    page: DocumentObject, key: str, sources: Sequence[DocumentObject], spot: Spot
) -> DocumentObject:
    view = page.Document.addObject(VIEW_TYPE, f"{PAGE_NAME}{key}")
    page.addView(view)
    view.Source = list(sources)
    direction, x_direction = _DIRECTIONS[key]
    view.Direction = App.Vector(*direction)
    view.XDirection = App.Vector(*x_direction)
    view.X = spot.x
    view.Y = spot.y
    view.Label = translated(_VIEW_LABELS[key])
    return view


def _add_extent(page: DocumentObject, view: DocumentObject, direction: int) -> list[str]:
    """Pose une cote d'étendue de toute la vue (elle suit la géométrie) ; renvoie les noms des
    objets ajoutés à la page. ``makeExtentDim`` écrit dans le document actif de FreeCAD : celui de
    la page est activé le temps de l'appel, puis le précédent est remis."""
    doc = page.Document
    before = {obj.Name for obj in page.Views}
    previous = App.ActiveDocument
    App.setActiveDocument(doc.Name)
    try:
        _techdraw().makeExtentDim(view, [], direction)
    finally:
        if previous is not None and previous != doc:
            App.setActiveDocument(previous.Name)
    return [obj.Name for obj in page.Views if obj.Name not in before]


def _clear(page: DocumentObject) -> None:
    """Retire de ``page`` les vues et cotes posées par l'atelier (les cotes d'abord)."""
    doc = page.Document
    owned = [doc.getObject(name) for name in _owned(page)]
    for obj in sorted(
        (obj for obj in owned if obj is not None), key=lambda obj: obj.TypeId == VIEW_TYPE
    ):
        page.removeView(obj)
        doc.removeObject(obj.Name)
    setattr(page, OWNED, "")


def _fill(page: DocumentObject, sources: Sequence[DocumentObject], layout: OverallLayout) -> None:
    doc = page.Document
    page.Scale = layout.scale
    spots = {"Front": layout.front, "Top": layout.top, "Side": layout.side, "Iso": layout.iso}
    views = {key: _add_view(page, key, sources, spot) for key, spot in spots.items()}
    doc.recompute()  # les cotes d'étendue lisent la géométrie des vues
    names = [view.Name for view in views.values()]
    for key, direction in _OVERALL:
        names.extend(_add_extent(page, views[key], direction))
    setattr(page, OWNED, ";".join(names))
    doc.recompute()


def make_overall_drawing(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> DocumentObject:
    """Crée ou refait le plan de l'ouvrage de ``objects`` dans ``doc`` et renvoie sa page.

    Une seule transaction « Plan de l'ouvrage ». ``ValueError`` traduite, avant toute
    modification, si TechDraw manque, s'il n'y a rien à dessiner, pour un objet d'un autre
    document ou un format de page inconnu."""
    if not techdraw_available():
        raise ValueError(translated(_NO_TECHDRAW))
    chosen = options or DrawingOptions()
    sources = drawing_sources(doc, objects)
    box = _global_box(sources)
    with translated_errors():
        layout = overall_layout(
            box.XLength,
            box.YLength,
            box.ZLength,
            page_size(chosen.page_format, chosen.orientation),
        )
    doc.openTransaction(translated(TITLE))
    try:
        page = find_overall_drawing(doc, sources)
        if page is None:
            page = _create_page(doc, chosen)
        else:
            _clear(page)
        _fill(page, sources, layout)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return page


def overall_dimensions(page: DocumentObject) -> list[DocumentObject]:
    """Cotes hors tout de ``page`` posées par l'atelier, dans l'ordre largeur, profondeur,
    hauteur."""
    owned = _owned(page)
    found = [obj for obj in page.Views if obj.Name in owned and obj.TypeId != VIEW_TYPE]
    return sorted(found, key=lambda obj: owned.index(obj.Name))
