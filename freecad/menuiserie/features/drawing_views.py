# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vues du plan de l'ouvrage : face, coupes au milieu du meuble, perspective et cotes hors tout,
en objets TechDraw standard (ADR 0053). Choix de jv du 2026-11-13 : les menuisiers lisent un
meuble en coupe, la vue de dessus et la vue de gauche cèdent la place à deux coupes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from typing import Any, Final, NamedTuple

import FreeCAD as App

from freecad.menuiserie.core.drawing import (
    CHAR_WIDTH_RATIO,
    OverallLayout,
    Spot,
    chain_segments,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing_details import FrontDetails
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "HORIZONTAL",
    "PAGE_NAME",
    "SECTION_TYPE",
    "VERTICAL",
    "VIEW_TYPE",
    "add_exploded_view",
    "add_overall_views",
    "add_part_views",
    "overall_band_mm",
    "part_band_mm",
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
    "Edge": QT_TRANSLATE_NOOP("Menuiserie", "Chant"),
    "End": QT_TRANSLATE_NOOP("Menuiserie", "Bout"),
    "Notes": QT_TRANSLATE_NOOP("Menuiserie", "Usinages"),
    "Angle": QT_TRANSLATE_NOOP("Menuiserie", "Angle"),
    "Exploded": QT_TRANSLATE_NOOP("Menuiserie", "Vue éclatée"),
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
    "Exploded": ((1.0, -1.0, 1.0), (1.0, 1.0, 0.0)),
}
# Plan de pièce : mêmes vues dans le repère local de la pièce (X longueur, Y largeur, Z
# épaisseur), face vue de dessus de son épaisseur ; tournées ensuite par le placement de la pièce.
_PART_DIRECTIONS: Final = {
    "Front": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "Edge": ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
    "End": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "Iso": ((1.0, 1.0, 1.0), (1.0, 0.0, -1.0)),
}
# Cotes d'une pièce : longueur, largeur sur la face, épaisseur sur le chant.
_PART_DIMENSIONS: Final = (("Front", HORIZONTAL), ("Front", VERTICAL), ("Edge", VERTICAL))
DIMENSION_CLEARANCE_MM: Final = 4.0  # du bord de la vue au texte d'une cote, plus le texte
SECTION_CLEARANCE_MM: Final = 14.0  # idem, au-delà des flèches et lettres d'un trait de coupe
CHAIN_TEXT_CHARS: Final = 7  # largeur d'une cote de détail (« 1349,92 »), en caractères
DIMENSION_FONT_MM: Final = 3.5  # taille du texte des cotes si TechDraw n'en donne pas
_DIMENSION_PARAMS: Final = "User parameter:BaseApp/Preferences/Mod/TechDraw/Dimensions"
# Cotes (largeur, hauteur, profondeur) qui font la largeur et la hauteur de chaque vue.
_VIEW_AXES: Final = {
    "Front": (0, 1),
    "CutH": (0, 2),
    "Edge": (0, 2),
    "CutV": (2, 1),
    "End": (2, 1),
}
ANNOTATION_TYPE: Final = "TechDraw::DrawViewAnnotation"
NOTE_SIZE_MM: Final = 3.5
_SECTIONS: Final = {"CutV": "A", "CutH": "B"}  # repère du trait de coupe sur la face
# Cotes hors tout : (vue, sens) pour la largeur (X), la profondeur (Y) et la hauteur (Z). La
# profondeur se lit sur la coupe verticale, qui garde le plateau qu'une coupe horizontale ôte.
_OVERALL: Final = (("Front", HORIZONTAL), ("CutV", HORIZONTAL), ("Front", VERTICAL))


def techdraw() -> Any:
    """Module TechDraw, importé à l'appel : l'atelier se charge sans lui."""
    import TechDraw

    return TechDraw


def _add_view(
    page: DocumentObject,
    key: str,
    sources: Sequence[DocumentObject],
    spot: Spot,
    rotation: Any = None,
) -> DocumentObject:
    view = page.Document.addObject(VIEW_TYPE, f"{PAGE_NAME}{key}")
    page.addView(view)
    view.Source = list(sources)
    _place(view, key, spot, rotation)
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


def _place(view: DocumentObject, key: str, spot: Spot, rotation: Any = None) -> None:
    """Oriente et place ``view`` ; ``rotation`` : celle d'une pièce dont on fait le plan."""
    if rotation is None:
        direction, x_direction = _DIRECTIONS[key]
        view.Direction = App.Vector(*direction)
        view.XDirection = App.Vector(*x_direction)
    else:
        direction, x_direction = _PART_DIRECTIONS[key]
        view.Direction = rotation.multVec(App.Vector(*direction))
        view.XDirection = rotation.multVec(App.Vector(*x_direction))
    view.X = spot.x
    view.Y = spot.y
    view.Label = translated(_VIEW_LABELS[key])


def _added_by(page: DocumentObject, make: Callable[[], object]) -> list[str]:
    """Noms des objets que ``make`` ajoute à la page. Les fabriques de cotes de TechDraw écrivent
    dans le document actif de FreeCAD : celui de la page est activé le temps de l'appel, puis le
    précédent est remis."""
    doc = page.Document
    before = {obj.Name for obj in page.Views}
    previous = App.ActiveDocument
    App.setActiveDocument(doc.Name)
    try:
        make()
    finally:
        if previous is not None and previous != doc:
            App.setActiveDocument(previous.Name)
    return [obj.Name for obj in page.Views if obj.Name not in before]


def _add_extent(page: DocumentObject, view: DocumentObject, direction: int) -> list[str]:
    """Pose une cote d'étendue de toute la vue (elle suit la géométrie) ; renvoie les noms des
    objets ajoutés à la page."""
    return _added_by(page, lambda: techdraw().makeExtentDim(view, [], direction))


def removal_rank(obj: DocumentObject) -> int:
    """Ordre de retrait : cotes, puis coupes, puis les vues dont elles dépendent."""
    return {SECTION_TYPE: 1, VIEW_TYPE: 2}.get(obj.TypeId, 0)


def add_overall_views(
    page: DocumentObject,
    sources: Sequence[DocumentObject],
    layout: OverallLayout,
    frame: tuple[Any, tuple[float, float, float], FrontDetails],
) -> list[str]:
    """Pose sur ``page`` la face, les coupes verticale et horizontale par le centre de
    l'ouvrage, la perspective, les cotes hors tout et, sur la face, les cotes de détail et les
    angles ; ``frame`` : (centre, cotes largeur, hauteur, profondeur en mm réels, détails de la
    face). Renvoie les noms des objets posés."""
    doc = page.Document
    center, sizes, details = frame
    front = _add_view(page, "Front", sources, layout.front)
    views = {
        "Front": front,
        "CutV": _add_section(page, "CutV", front, center, layout.side),
        "CutH": _add_section(page, "CutH", front, center, layout.top),
        "Iso": _add_view(page, "Iso", sources, layout.iso),
    }
    doc.recompute()  # les cotes d'étendue lisent la géométrie des vues
    names = [view.Name for view in views.values()]
    half = _half_size("Front", sizes, layout.scale)
    chained = add_front_details(page, front, details, (center, half, layout.scale))
    names.extend(chained.names)
    for key, direction in _OVERALL:
        added = _add_extent(page, views[key], direction)
        # La face porte les traits de coupe A-A et B-B (et ses cotes de détail) : ses cotes
        # hors tout passent au-delà.
        clearance = DIMENSION_CLEARANCE_MM
        if key == "Front":
            clearance = SECTION_CLEARANCE_MM + chained.rows[direction] * dimension_row_mm()
        _clear_of_view(doc, added, _half_size(key, sizes, layout.scale), direction, clearance)
        names.extend(added)
    return names


def _half_size(key: str, sizes: tuple[float, float, float], scale: float) -> tuple[float, float]:
    """Demi-largeur et demi-hauteur de la vue ``key`` sur la feuille."""
    across, up = _VIEW_AXES[key]
    return sizes[across] * scale / 2, sizes[up] * scale / 2


def dimension_font_mm() -> float:
    """Taille du texte des cotes réglée dans les préférences de TechDraw (lue, jamais changée) :
    l'écart des cotes à leur vue en dépend."""
    size = App.ParamGet(_DIMENSION_PARAMS).GetFloat("FontSize", DIMENSION_FONT_MM)
    return size if 1.0 <= size <= 20.0 else DIMENSION_FONT_MM


def dimension_row_mm() -> float:
    """Écart entre deux rangées de cotes parallèles."""
    return 1.5 * dimension_font_mm() + DIMENSION_CLEARANCE_MM


def overall_band_mm() -> float:
    """Place des cotes au-dessus et à gauche de la face du plan de l'ouvrage : traits de coupe,
    cotes de détail, cotes hors tout."""
    return SECTION_CLEARANCE_MM + 2 * dimension_row_mm()


def part_band_mm() -> float:
    """Place des cotes au-dessus et à gauche de la face d'un plan de pièce."""
    return dimension_row_mm() + dimension_font_mm()


class Chained(NamedTuple):
    """Objets posés par :func:`add_front_details` et rangées de cotes de détail ajoutées, par
    sens (horizontal, vertical)."""

    names: list[str]
    rows: tuple[int, int]


def add_front_details(
    page: DocumentObject,
    front: DocumentObject,
    details: FrontDetails,
    frame: tuple[Any, tuple[float, float], float],
) -> Chained:
    """Pose sur la face ``front`` les chaînes de cotes de détail (au-dessus, à gauche, juste
    hors des traits de coupe) et l'angle des pièces en biais ; ``frame`` : (centre de
    l'ouvrage, demi-taille de la face sur la feuille, échelle). Rien si TechDraw ne sait pas
    coter entre deux points."""
    make = getattr(techdraw(), "makeDistanceDim3d", None)
    center, (half_width, half_height), scale = frame
    names = [
        _add_angle(page, front, angle, middle, (center, scale)) for angle, middle in details.angles
    ]
    if make is None:
        return Chained(names, (0, 0))
    font = dimension_font_mm()
    min_gap = CHAIN_TEXT_CHARS * CHAR_WIDTH_RATIO * font / scale  # une cote lisible
    offset = SECTION_CLEARANCE_MM + 1.5 * font
    rows = []
    for direction, points in ((HORIZONTAL, details.xs), (VERTICAL, details.zs)):
        segments = chain_segments(points, min_gap)
        for low, high in segments:
            if direction == HORIZONTAL:
                ends = (App.Vector(low, center.y, center.z), App.Vector(high, center.y, center.z))
                spot = (((low + high) / 2 - center.x) * scale, half_height + offset)
            else:
                ends = (App.Vector(center.x, center.y, low), App.Vector(center.x, center.y, high))
                spot = (-(half_width + offset), ((low + high) / 2 - center.z) * scale)
            kind = "DistanceX" if direction == HORIZONTAL else "DistanceY"
            added = _added_by(page, partial(make, front, kind, *ends))
            for name in added:
                dim = page.Document.getObject(name)
                if dim is not None and "X" in dim.PropertiesList:
                    dim.X, dim.Y = spot
            names.extend(added)
        rows.append(1 if segments else 0)
    return Chained(names, (rows[0], rows[1]))


def _add_angle(
    page: DocumentObject,
    front: DocumentObject,
    angle: float,
    middle: Any,
    frame: tuple[Any, float],
) -> str:
    """Angle d'une pièce en biais écrit en son milieu sur la face ; renvoie le nom du texte."""
    center, scale = frame
    note = page.Document.addObject(ANNOTATION_TYPE, f"{PAGE_NAME}Angle")
    page.addView(note)
    note.Text = [f"{round(angle, 1):g}°".replace(".", ",")]
    note.TextSize = dimension_font_mm()
    note.X = front.X + (middle.x - center.x) * scale
    note.Y = front.Y + (middle.z - center.z) * scale
    note.Label = translated(_VIEW_LABELS["Angle"])
    return str(note.Name)


def _clear_of_view(
    doc: Any,
    names: Sequence[str],
    half: tuple[float, float],
    direction: int,
    clearance: float = DIMENSION_CLEARANCE_MM,
) -> None:
    """Écarte le texte des cotes ``names`` du bord de leur vue (demi-taille ``half`` sur la
    feuille) : au-dessus pour une cote horizontale, à gauche pour une verticale (position
    relative au centre de la vue, en mm de la feuille), pour qu'il ne chevauche ni la vue ni
    l'autre cote."""
    half_width, half_height = half
    clearance += 1.5 * dimension_font_mm()  # le texte, sa ligne et ses flèches
    for name in names:
        dim = doc.getObject(name)
        if dim is None or "X" not in dim.PropertiesList:
            continue
        if direction == HORIZONTAL:
            dim.X, dim.Y = 0.0, half_height + clearance
        else:
            dim.X, dim.Y = -(half_width + clearance), 0.0


def _add_notes(page: DocumentObject, lines: Sequence[str], spot: Spot) -> DocumentObject:
    """Tableau des usinages : texte TechDraw, une ligne par usinage."""
    note = page.Document.addObject(ANNOTATION_TYPE, f"{PAGE_NAME}Notes")
    page.addView(note)
    note.Text = list(lines)
    note.TextSize = NOTE_SIZE_MM
    note.X = spot.x
    note.Y = spot.y
    note.Label = translated(_VIEW_LABELS["Notes"])
    return note


def add_part_views(
    page: DocumentObject,
    part: DocumentObject,
    rotation: Any,
    layout: OverallLayout,
    notes: tuple[Sequence[str], Spot],
    frame: tuple[tuple[float, float, float], tuple[float, Spot] | None],
) -> list[str]:
    """Pose sur ``page`` le plan de ``part`` tournée de ``rotation`` (celle de sa brute) : face,
    chant dessous, bout à droite, arêtes cachées en pointillés pour montrer les usinages, le
    tableau des usinages ``notes`` (lignes, place) et ses cotes. ``frame`` : (longueur, largeur
    et épaisseur en mm réels ; perspective à sa propre échelle, (échelle, place) ou ``None`` s'il
    n'y a pas la place). Renvoie les noms des objets posés."""
    doc = page.Document
    sizes, iso = frame
    views = {
        "Front": _add_view(page, "Front", [part], layout.front, rotation),
        "Edge": _add_view(page, "Edge", [part], layout.top, rotation),
        "End": _add_view(page, "End", [part], layout.side, rotation),
    }
    for view in views.values():
        view.HardHidden = True  # mortaises, perçages et rainures cachés en pointillés
    if iso is not None:
        iso_scale, iso_spot = iso
        perspective = _add_view(page, "Iso", [part], iso_spot, rotation)
        perspective.ScaleType = "Custom"
        perspective.Scale = iso_scale
    doc.recompute()
    names = [view.Name for view in views.values()]
    if iso is not None:
        names.append(perspective.Name)
    for key, direction in _PART_DIMENSIONS:
        added = _add_extent(page, views[key], direction)
        _clear_of_view(doc, added, _half_size(key, sizes, layout.scale), direction)
        names.extend(added)
    names.append(_add_notes(page, *notes).Name)
    return names


def add_exploded_view(page: DocumentObject, exploded: DocumentObject, spot: Spot) -> list[str]:
    """Pose sur ``page`` la perspective de ``exploded`` (la forme éclatée de l'ouvrage) ;
    renvoie le nom de la vue."""
    return [_add_view(page, "Exploded", [exploded], spot).Name]
