# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vue éclatée de l'ouvrage (issue #153, demande de jv du 2026-11-13) : une page TechDraw.

Chaque pièce dessinée s'écarte du centre de l'ouvrage (``exploded_offset``) ; les formes écartées
sont réunies dans un seul objet ``Part::Feature`` masqué, que la page projette en perspective.
Cet objet est une photographie : il ne suit pas le modèle, relancer la commande le refait (comme
la page, laissée telle quelle si le menuisier l'a modifiée à la main).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.drawing import exploded_offset, page_size, single_view_layout
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing import (
    KIND,
    DrawingOptions,
    apply_template,
    clear_page,
    create_page,
    drawing_sources,
    drawing_transaction,
    global_box,
    global_shape,
    is_untouched,
    is_workshop_drawing,
    owned_names,
    require_techdraw,
    set_owned,
    title_inputs,
    warn_if_unfitted,
)
from freecad.menuiserie.features.drawing_title import fill_title_block
from freecad.menuiserie.features.drawing_views import add_exploded_view
from freecad.menuiserie.features.freecad_types import HIDDEN, Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors

__all__ = ["EXPLODED_KIND", "make_exploded_drawing"]

EXPLODED_KIND: Final = "exploded"
PARTS: Final = "MenuiserieDrawingParts"  # pièces de la vue éclatée, par nom, séparées par « ; »
SHAPE_NAME: Final = "MenuiserieEclate"
SHAPE_MARKER: Final = "MenuiserieExplodedShape"  # marque l'objet porteur de la forme éclatée
_SHAPE_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Forme de vue éclatée construite par l'atelier Menuiserie."
)
TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Vue éclatée")
_SHAPE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Forme de la vue éclatée")
_PARTS_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Pièces dessinées par cette vue éclatée (atelier Menuiserie)."
)


def _exploded_shape(sources: Sequence[DocumentObject]) -> Any:
    """Formes globales des ``sources`` écartées du centre de l'ouvrage, en un composé."""
    center = global_box(sources).Center
    shapes = []
    for obj in sources:
        shape = global_shape(obj)
        if shape.isNull():
            continue
        middle = shape.BoundBox.Center
        offset = exploded_offset((center.x, center.y, center.z), (middle.x, middle.y, middle.z))
        shape.translate(App.Vector(*offset))
        shapes.append(shape)
    return Part.makeCompound(shapes)


def _names(sources: Sequence[DocumentObject]) -> str:
    return ";".join(sorted(obj.Name for obj in sources))


def _owned_views(page: DocumentObject) -> list[DocumentObject]:
    names = set(owned_names(page))
    return [view for view in page.Views if view.Name in names]


def _is_holder(obj: DocumentObject) -> bool:
    return obj.TypeId == "Part::Feature" and bool(getattr(obj, SHAPE_MARKER, False))


def _find(doc: Document, sources: Sequence[DocumentObject]) -> DocumentObject | None:
    """Page de vue éclatée de ces pièces que le menuisier n'a pas modifiée."""
    wanted = _names(sources)
    for obj in doc.Objects:
        if not is_workshop_drawing(obj) or str(getattr(obj, KIND, "")) != EXPLODED_KIND:
            continue
        if str(getattr(obj, PARTS, "")) == wanted and is_untouched(obj):
            return obj
    return None


def _shape_object(doc: Document, page: DocumentObject | None) -> DocumentObject:
    """Objet porteur de la forme éclatée : celui de la page refaite, sinon un porteur que plus
    aucune vue n'utilise (sa page a été supprimée), sinon un nouveau, masqué."""
    if page is not None:
        for view in _owned_views(page):
            for source in getattr(view, "Source", []):
                if _is_holder(source):
                    return source
    for obj in doc.Objects:
        if _is_holder(obj) and not obj.InList:
            return obj
    holder = doc.addObject("Part::Feature", SHAPE_NAME)
    holder.Label = translated(_SHAPE_LABEL)
    holder.addProperty("App::PropertyBool", SHAPE_MARKER, "Menuiserie", _SHAPE_TOOLTIP)
    holder.setEditorMode(SHAPE_MARKER, HIDDEN)
    setattr(holder, SHAPE_MARKER, True)
    holder.Visibility = False
    return holder


def make_exploded_drawing(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> DocumentObject:
    """Crée ou refait la vue éclatée de ``objects`` (ensembles, pièces) et renvoie sa page.
    Une seule transaction « Vue éclatée ». ``ValueError`` traduite, avant toute modification,
    si TechDraw manque, s'il n'y a rien à dessiner ou pour un format de page inconnu."""
    require_techdraw()
    chosen = options or DrawingOptions()
    sources = drawing_sources(doc, objects)
    exploded = _exploded_shape(sources)
    box = exploded.BoundBox
    with translated_errors():
        sheet = page_size(chosen.resolved_format(), chosen.resolved_orientation())
        scale, spot, fits = single_view_layout(box.XLength, box.YLength, box.ZLength, sheet)
    with drawing_transaction(doc, translated(TITLE)):
        page = _find(doc, sources)
        holder = _shape_object(doc, page)
        holder.Shape = exploded
        if page is None:
            page = create_page(doc, EXPLODED_KIND)
            page.Label = translated(TITLE)
            page.addProperty("App::PropertyString", PARTS, "Menuiserie", _PARTS_TOOLTIP)
            page.setEditorMode(PARTS, HIDDEN)
            setattr(page, PARTS, _names(sources))
        else:
            clear_page(page)
        apply_template(page, chosen)
        fill_title_block(page, list(objects), title_inputs(chosen), scale, translated(TITLE))
        page.Scale = scale
        warn_if_unfitted(fits)
        set_owned(page, add_exploded_view(page, holder, spot))
        doc.recompute()
    return page
