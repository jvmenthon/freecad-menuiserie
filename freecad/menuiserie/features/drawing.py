# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan de l'ouvrage dans une page TechDraw standard (issue #153, ADR 0053, lot P-a).

Une ``TechDraw::DrawPage`` ordinaire, sans proxy, marquée par la propriété booléenne masquée
``MenuiserieDrawing`` : face, coupe verticale A-A à droite, coupe horizontale B-B dessous et
perspective à la même échelle, plus trois cotes hors tout (``TechDraw::DrawViewDimExtent``, qui
suivent la géométrie des vues). Un document ouvert sans l'atelier garde une page ordinaire.

Les vues suivent le modèle toutes seules (ce sont des vues TechDraw). Relancer la fabrique refait
l'échelle et la mise en page ; une page que le menuisier a modifiée (vue ajoutée ou retirée) n'est
pas touchée : une nouvelle page est créée. ``TechDraw`` est importé à l'appel seulement : l'atelier
se charge sans lui.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie import TEMPLATES_DIR
from freecad.menuiserie.core.drawing import (
    OverallLayout,
    PageSize,
    overall_layout,
    page_size,
    pick_template,
    template_file_name,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing_details import front_details, global_shape
from freecad.menuiserie.features.drawing_dims import overall_band_mm
from freecad.menuiserie.features.drawing_scope import NOTHING, document_scope, drawing_sources
from freecad.menuiserie.features.drawing_settings import DrawingOptions
from freecad.menuiserie.features.drawing_title import STORED, fill_title_block
from freecad.menuiserie.features.drawing_views import (
    PAGE_NAME,
    VIEW_TYPE,
    add_overall_views,
    removal_rank,
    techdraw,
)
from freecad.menuiserie.features.freecad_types import HIDDEN, Document, DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated, translated_errors

__all__ = [
    "KIND",
    "MARKER",
    "PAGE_NAME",
    "PAGE_TYPE",
    "PART_KIND",
    "TITLE",
    "DrawingOptions",
    "apply_template",
    "clear_page",
    "create_page",
    "document_scope",
    "drawing_sources",
    "drawing_transaction",
    "find_overall_drawing",
    "global_box",
    "global_shape",
    "is_page",
    "is_untouched",
    "is_workshop_drawing",
    "make_overall_drawing",
    "overall_dimensions",
    "owned_names",
    "require_techdraw",
    "set_owned",
    "techdraw_available",
    "title_inputs",
    "warn_if_unfitted",
]

MARKER: Final = "MenuiserieDrawing"
OWNED: Final = "MenuiserieDrawingViews"  # noms des vues et cotes posées par l'atelier
EXTENT_TYPE: Final = "TechDraw::DrawViewDimExtent"  # cotes hors tout (d'étendue)
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
_KIND_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Genre du plan construit par l'atelier Menuiserie (vide : de l'ouvrage)."
)
_STORED_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Saisie du cartouche de ce plan (atelier Menuiserie)."
)


def techdraw_available() -> bool:
    """Vrai si le module TechDraw de FreeCAD s'importe (il peut être désactivé ou absent)."""
    try:
        techdraw()
    except ImportError:
        return False
    return True


def is_page(obj: object) -> bool:
    """Vrai si ``obj`` est une page TechDraw (un plan, de l'atelier ou non)."""
    return getattr(obj, "TypeId", None) == PAGE_TYPE


def is_workshop_drawing(obj: object) -> bool:
    """Vrai si ``obj`` est une page de plan construite par l'atelier (même renommée)."""
    return is_page(obj) and getattr(obj, MARKER, False) is True


def global_box(sources: Sequence[DocumentObject]) -> Any:
    """Boîte englobante des ``sources`` dans le repère global du document."""
    box = App.BoundBox()
    for obj in sources:
        shape = global_shape(obj)
        if shape.isNull():
            continue
        box.add(shape.BoundBox)
    if not box.isValid():
        raise ValueError(translated(NOTHING))
    return box


_TOO_BIG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Plan : le dessin dépasse de la feuille même à la plus petite échelle ; "
    "choisissez un format plus grand.",
)


def warn_if_unfitted(fits: bool) -> None:
    """Prévient dans la vue rapport quand les vues ne tiennent pas sur la feuille."""
    if not fits:
        report_warning(translated(_TOO_BIG))


def _template_path(options: DrawingOptions) -> str | None:
    """Gabarit de page pour ``options`` : celui de l'atelier (cartouche en français), à défaut
    celui de TechDraw ; ``None`` si aucun ne convient."""
    fmt, orientation = options.resolved_format(), options.resolved_orientation()
    with translated_errors():
        page_size(fmt, orientation)  # format connu, quel que soit l'appelant
    own = TEMPLATES_DIR / template_file_name(fmt, orientation)
    if own.is_file():
        return str(own)
    folder = Path(App.getResourceDir()) / "Mod" / "TechDraw" / "Templates"
    if not folder.is_dir():
        return None
    paths = sorted(str(path) for path in islice(folder.rglob("*.svg"), MAX_TEMPLATES))
    return pick_template(paths, fmt, orientation)


def require_techdraw() -> None:
    """``ValueError`` traduite si l'atelier TechDraw n'est pas disponible."""
    if not techdraw_available():
        raise ValueError(translated(_NO_TECHDRAW))


@contextmanager
def drawing_transaction(doc: Document, title: str) -> Iterator[None]:
    """Une transaction ``title`` (déjà traduit) : validée à la fin, annulée sur une erreur."""
    doc.openTransaction(title)
    try:
        yield
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()


def owned_names(page: DocumentObject) -> list[str]:
    """Noms des vues et cotes que l'atelier a posées sur ``page``."""
    return [name for name in str(getattr(page, OWNED, "")).split(";") if name]


def is_untouched(page: DocumentObject) -> bool:
    """Vrai si ``page`` ne contient que ce que l'atelier y a posé, au complet."""
    return sorted(view.Name for view in page.Views) == sorted(owned_names(page))


def _front_view(page: DocumentObject) -> DocumentObject | None:
    owned = set(owned_names(page))
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
        if not is_workshop_drawing(obj) or not is_untouched(obj):
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
    names = set(owned_names(page))
    # Seules les vues de la page sont retirées, même si la liste enregistrée a été modifiée.
    owned = [view for view in page.Views if view.Name in names]
    for obj in sorted(owned, key=removal_rank):
        page.removeView(obj)
        doc.removeObject(obj.Name)
    setattr(page, OWNED, "")


def set_owned(page: DocumentObject, names: Sequence[str]) -> None:
    """Enregistre sur ``page`` les vues et cotes posées par l'atelier (l'appelant recalcule le
    document une fois, à la fin)."""
    setattr(page, OWNED, ";".join(names))


@dataclass(frozen=True)
class _Placed:
    """Mise en page du plan de l'ouvrage, et ses chaînes de cotes de détail ou non."""

    layout: OverallLayout
    chains: bool


def _placed(box: Any, size: PageSize) -> _Placed:
    """Les chaînes de cotes de détail sont omises quand leur place ferait passer les vues
    cotées à une échelle plus petite."""
    dimensions = (box.XLength, box.YLength, box.ZLength)
    full = overall_layout(dimensions, size, band=overall_band_mm())
    plain = overall_layout(dimensions, size, band=overall_band_mm(chains=False))
    return _Placed(plain, False) if plain.scale > full.scale else _Placed(full, True)


def _fill(
    page: DocumentObject, sources: Sequence[DocumentObject], placed: _Placed, frame: tuple[Any, Any]
) -> None:
    """Pose les vues et les cotes ; ``frame`` : (encombrement des objets, attente des vues)."""
    box, settle = frame
    page.Scale = placed.layout.scale
    warn_if_unfitted(placed.layout.fits)
    sizes = (float(box.XLength), float(box.ZLength), float(box.YLength))
    details = front_details(sources)
    if not placed.chains:
        details = details.without_chains()
    views = (box.Center, sizes, details)
    set_owned(page, add_overall_views(page, sources, placed.layout, views, settle))


def make_overall_drawing(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> DocumentObject:
    """Crée ou refait le plan de l'ouvrage de ``objects`` dans ``doc`` et renvoie sa page.

    Une seule transaction « Plan de l'ouvrage ». ``ValueError`` traduite, avant toute
    modification, si TechDraw manque, s'il n'y a rien à dessiner, pour un objet d'un autre
    document ou un format de page inconnu."""
    require_techdraw()
    chosen = options or DrawingOptions()
    sources = drawing_sources(doc, objects)
    box = global_box(sources)
    with translated_errors():
        size = page_size(chosen.resolved_format(), chosen.resolved_orientation())
        placed = _placed(box, size)
    with drawing_transaction(doc, translated(TITLE)):
        page = find_overall_drawing(doc, sources)
        if page is None:
            page = create_page(doc)
        else:
            clear_page(page)
        apply_template(page, chosen)
        fill_title_block(page, list(objects), title_inputs(chosen), placed.layout.scale)
        _fill(page, sources, placed, (box, chosen.settle))
        doc.recompute()
    return page


def overall_dimensions(page: DocumentObject) -> list[DocumentObject]:
    """Cotes hors tout de ``page`` posées par l'atelier, dans l'ordre largeur, profondeur,
    hauteur."""
    owned = owned_names(page)
    found = [obj for obj in page.Views if obj.Name in owned and obj.TypeId == EXTENT_TYPE]
    return sorted(found, key=lambda obj: owned.index(obj.Name))
