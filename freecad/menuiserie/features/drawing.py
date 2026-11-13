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

from freecad.menuiserie import TEMPLATES_DIR
from freecad.menuiserie.core.drawing import (
    Orientation,
    OverallLayout,
    overall_layout,
    page_size,
    pick_template,
    template_file_name,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import drawing_settings
from freecad.menuiserie.features.drawing_title import STORED, fill_title_block
from freecad.menuiserie.features.drawing_views import (
    PAGE_NAME,
    VIEW_TYPE,
    add_overall_views,
    removal_rank,
    techdraw,
)
from freecad.menuiserie.features.freecad_types import HIDDEN, Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "KIND",
    "MARKER",
    "PAGE_NAME",
    "PART_KIND",
    "TITLE",
    "DrawingOptions",
    "apply_template",
    "clear_page",
    "create_page",
    "document_scope",
    "drawing_sources",
    "find_overall_drawing",
    "global_box",
    "global_shape",
    "is_workshop_drawing",
    "make_overall_drawing",
    "overall_dimensions",
    "set_owned",
    "techdraw_available",
    "title_inputs",
]

MARKER: Final = "MenuiserieDrawing"
OWNED: Final = "MenuiserieDrawingViews"  # noms des vues et cotes posées par l'atelier
DIMENSION_TYPE: Final = "TechDraw::DrawViewDim"  # préfixe des types de cotes
KIND: Final = "MenuiserieDrawingKind"  # « part » : plan de pièce ; absent ou vide : de l'ouvrage
PART_KIND: Final = "part"
PAGE_TYPE: Final = "TechDraw::DrawPage"
TEMPLATE_TYPE: Final = "TechDraw::DrawSVGTemplate"
MAX_TEMPLATES: Final = 2000  # plafond du balayage du dossier de gabarits de TechDraw

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
_KIND_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Genre du plan construit par l'atelier Menuiserie (vide : de l'ouvrage)."
)
_STORED_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Saisie du cartouche de ce plan (atelier Menuiserie)."
)


@dataclass(frozen=True)
class DrawingOptions:
    """Feuille et cartouche du plan. ``None`` : le réglage de la configuration de l'atelier pour
    le format et le sens ; pour le titre, le client et le numéro de devis, la valeur déjà
    enregistrée sur la page que l'on refait, sinon le nom de l'ouvrage (titre) ou rien."""

    page_format: str | None = None
    orientation: Orientation | None = None
    title: str | None = None
    client: str | None = None
    quote: str | None = None

    def resolved_format(self) -> str:
        """Format demandé, sinon celui de la configuration."""
        return self.page_format or drawing_settings.default_format()

    def resolved_orientation(self) -> Orientation:
        """Sens demandé, sinon celui de la configuration."""
        return self.orientation or drawing_settings.default_orientation()


def techdraw_available() -> bool:
    """Vrai si le module TechDraw de FreeCAD s'importe (il peut être désactivé ou absent)."""
    try:
        techdraw()
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


def document_scope(doc: Document) -> list[DocumentObject]:
    """Ce que dessine le plan quand rien n'est sélectionné : les ensembles de plus haut niveau et
    les pièces de bois hors ensemble du document, par nom."""
    found = [
        obj
        for obj in doc.Objects
        if (is_furniture(obj) or is_timber(obj)) and furniture_of(obj) is None
    ]
    return sorted(found, key=lambda obj: obj.Name)


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


def global_shape(obj: DocumentObject) -> Any:
    """Forme de ``obj`` (copie) placée dans le repère global du document, conteneurs compris."""
    shape = Part.getShape(obj)
    if not shape.isNull():
        outer = obj.getGlobalPlacement().multiply(obj.Placement.inverse())
        shape.Placement = outer.multiply(shape.Placement)
    return shape


def global_box(sources: Sequence[DocumentObject]) -> Any:
    """Boîte englobante des ``sources`` dans le repère global du document."""
    box = App.BoundBox()
    for obj in sources:
        shape = global_shape(obj)
        if shape.isNull():
            continue
        box.add(shape.BoundBox)
    if not box.isValid():
        raise ValueError(translated(_NOTHING))
    return box


def _template_path(options: DrawingOptions) -> str | None:
    """Gabarit de page pour ``options`` : celui de l'atelier (cartouche en français), à défaut
    celui de TechDraw ; ``None`` si aucun ne convient."""
    fmt, orientation = options.resolved_format(), options.resolved_orientation()
    own = TEMPLATES_DIR / template_file_name(fmt, orientation)
    if own.is_file():
        return str(own)
    folder = Path(App.getResourceDir()) / "Mod" / "TechDraw" / "Templates"
    if not folder.is_dir():
        return None
    paths = sorted(str(path) for path in islice(folder.rglob("*.svg"), MAX_TEMPLATES))
    return pick_template(paths, fmt, orientation)


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


def find_overall_drawing(
    doc: Document, sources: Sequence[DocumentObject], kind: str = ""
) -> DocumentObject | None:
    """Page de plan de l'atelier du genre ``kind`` (« » : de l'ouvrage, ``PART_KIND`` : de
    pièce) qui dessine exactement ``sources`` et que le menuisier n'a pas modifiée ; ``None`` s'il
    n'y en a pas."""
    wanted = sorted(obj.Name for obj in sources)
    for obj in doc.Objects:
        if not is_workshop_drawing(obj) or not _untouched(obj):
            continue
        if str(getattr(obj, KIND, "")) != kind:
            continue
        front = _front_view(obj)
        if front is not None and sorted(source.Name for source in front.Source) == wanted:
            return obj
    return None


def create_page(doc: Document, kind: str = "") -> DocumentObject:
    """Nouvelle page de plan de l'atelier, du genre ``kind``, avec son gabarit (vide)."""
    page = doc.addObject(PAGE_TYPE, PAGE_NAME)
    page.addProperty("App::PropertyBool", MARKER, "Menuiserie", _MARKER_TOOLTIP)
    page.addProperty("App::PropertyString", OWNED, "Menuiserie", _OWNED_TOOLTIP)
    page.addProperty("App::PropertyString", KIND, "Menuiserie", _KIND_TOOLTIP)
    for name in STORED.values():
        page.addProperty("App::PropertyString", name, "Menuiserie", _STORED_TOOLTIP)
    setattr(page, MARKER, True)
    setattr(page, KIND, kind)
    for name in (MARKER, OWNED, KIND, *STORED.values()):
        page.setEditorMode(name, HIDDEN)
    page.Label = translated(TITLE)
    page.Template = doc.addObject(TEMPLATE_TYPE, f"{PAGE_NAME}Gabarit")
    return page


def title_inputs(options: DrawingOptions) -> dict[str, str | None]:
    """Saisies du cartouche venues de ``options``."""
    return {"title": options.title, "client": options.client, "quote": options.quote}


def apply_template(page: DocumentObject, options: DrawingOptions) -> None:
    """Donne à ``page`` le gabarit de TechDraw voulu par ``options`` (inchangé s'il l'a déjà)."""
    path = _template_path(options)
    template = page.Template
    if path is not None and template is not None and str(template.Template) != path:
        template.Template = path


def clear_page(page: DocumentObject) -> None:
    """Retire de ``page`` les vues et cotes posées par l'atelier (les cotes d'abord)."""
    doc = page.Document
    owned = [doc.getObject(name) for name in _owned(page)]
    for obj in sorted((obj for obj in owned if obj is not None), key=removal_rank):
        page.removeView(obj)
        doc.removeObject(obj.Name)
    setattr(page, OWNED, "")


def set_owned(page: DocumentObject, names: Sequence[str]) -> None:
    """Enregistre sur ``page`` les vues et cotes posées par l'atelier, puis la recalcule."""
    setattr(page, OWNED, ";".join(names))
    page.Document.recompute()


def _fill(
    page: DocumentObject, sources: Sequence[DocumentObject], layout: OverallLayout, box: Any
) -> None:
    page.Scale = layout.scale
    sizes = (float(box.XLength), float(box.ZLength), float(box.YLength))
    set_owned(page, add_overall_views(page, sources, layout, (box.Center, sizes)))


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
    box = global_box(sources)
    with translated_errors():
        size = page_size(chosen.resolved_format(), chosen.resolved_orientation())
        layout = overall_layout(box.XLength, box.YLength, box.ZLength, size)
    doc.openTransaction(translated(TITLE))
    try:
        page = find_overall_drawing(doc, sources)
        if page is None:
            page = create_page(doc)
        else:
            clear_page(page)
        apply_template(page, chosen)
        fill_title_block(page, list(objects), title_inputs(chosen), layout.scale)
        _fill(page, sources, layout, box)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return page


def overall_dimensions(page: DocumentObject) -> list[DocumentObject]:
    """Cotes hors tout de ``page`` posées par l'atelier, dans l'ordre largeur, profondeur,
    hauteur."""
    owned = _owned(page)
    found = [
        obj for obj in page.Views if obj.Name in owned and obj.TypeId.startswith(DIMENSION_TYPE)
    ]
    return sorted(found, key=lambda obj: owned.index(obj.Name))
