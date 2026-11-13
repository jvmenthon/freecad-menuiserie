# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans de pièce (issue #153, lot P-c, ADR 0053) : une page TechDraw par pièce distincte.

Chaque pièce de bois de la portée (sélection ou document) est dessinée dans son propre repère :
face (longueur vers la droite, largeur vers le haut), chant dessous, bout à droite et
perspective, avec ses trois cotes. Les usinages, lus dans les plans des assemblages de sa pièce
usinée, forment un tableau dans la bande à gauche du cartouche ; leurs positions se mesurent
depuis le coin bas gauche de la vue de face. Des pièces de même matériau, mêmes cotes et mêmes
usinages partagent une page ; leur nombre est écrit au cartouche.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, Final

from freecad.menuiserie.core.drawing import (
    Machining,
    MachiningKind,
    capped,
    corner_iso_layout,
    machining_lines,
    machinings,
    notes_band,
    notes_layout,
    overall_layout,
    page_size,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing import (
    PART_KIND,
    DrawingOptions,
    apply_template,
    clear_page,
    create_page,
    document_scope,
    drawing_transaction,
    find_overall_drawing,
    require_techdraw,
    set_owned,
    title_inputs,
    warn_if_unfitted,
)
from freecad.menuiserie.features.drawing_title import fill_title_block
from freecad.menuiserie.features.drawing_views import NOTE_SIZE_MM, add_part_views
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint, plan_for
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
)
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["distinct_parts", "make_part_drawings", "part_machinings"]

PART_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de pièce")
_KIND: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de pièce, {count} ex.")
_HEADER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinages (x, y depuis le coin bas gauche de la face, en mm) :"
)
_NONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun usinage.")
_MORE: Final = QT_TRANSLATE_NOOP("Menuiserie", "… et {count} autres usinages")
_NO_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan de pièce impossible : aucune pièce de bois dans la sélection."
)
_KEY_DECIMALS: Final = 1


def _blanks(objects: Sequence[DocumentObject], seen: set[str]) -> Iterator[DocumentObject]:
    """Pièces de bois (brutes) de ``objects`` : membres des ensembles, brute d'une pièce
    usinée, sans doublon."""
    for obj in objects:
        if obj.Name in seen:
            continue
        seen.add(obj.Name)
        if is_furniture(obj):
            yield from _blanks(members_of(obj), seen)
        elif is_machined_part(obj):
            yield from _blanks([blank_of(obj)], seen)
        elif is_timber(obj):
            yield obj


def _size(blank: DocumentObject) -> tuple[float, float, float]:
    return (
        float(blank.Length.Value),
        float(blank.Width.Value),
        float(blank.Thickness.Value),
    )


def part_machinings(blank: DocumentObject) -> list[Machining]:
    """Usinages de la pièce de bois ``blank`` d'après les plans de ses assemblages ; un
    assemblage impossible est ignoré (il signale lui-même son erreur)."""
    machined = machined_part_of(blank)
    if machined is None:
        return []
    items: list[tuple[str, Any, MachiningKind]] = []
    for joint in machined.Joints:
        if not is_joint(joint):
            continue
        try:
            plan = plan_for(joint)
        except ValueError:
            continue
        label = str(joint.Label)
        groups: list[tuple[Sequence[Any], MachiningKind]] = []
        if joint.HostPart == blank:
            groups += [
                (plan.host_cuts, MachiningKind.CUT),
                (plan.host_additions, MachiningKind.ADDED),
            ]
        if joint.GuestPart == blank:
            groups += [
                (plan.guest_cuts, MachiningKind.CUT),
                (plan.guest_trims, MachiningKind.CUT),
                (plan.guest_additions, MachiningKind.ADDED),
            ]
        items.extend((label, solid, kind) for solids, kind in groups for solid in solids)
    return machinings(items, _size(blank))


def _key(blank: DocumentObject, found: Sequence[Machining]) -> tuple[object, ...]:
    shape = tuple(
        sorted(
            (
                item.kind.value,
                tuple(round(value, _KEY_DECIMALS) for value in (*item.low, *item.high)),
                round(item.diameter, _KEY_DECIMALS),
            )
            for item in found
        )
    )
    size = tuple(round(value, _KEY_DECIMALS) for value in _size(blank))
    return str(getattr(blank, "Material", "")), size, shape


def distinct_parts(
    doc: Document, objects: Sequence[DocumentObject]
) -> list[tuple[DocumentObject, int, list[Machining]]]:
    """Pièces distinctes de ``objects`` (tout le document s'il est vide) : (première pièce,
    nombre, usinages), dans l'ordre des repères puis des noms. Deux pièces sont les mêmes si
    elles ont même matériau, mêmes cotes et mêmes usinages aux mêmes places. ``ValueError``
    traduite s'il n'y a aucune pièce de bois."""
    scope = list(objects) or document_scope(doc)
    blanks = sorted(
        _blanks(scope, set()), key=lambda obj: (str(getattr(obj, "Mark", "")), obj.Name)
    )
    groups: dict[tuple[object, ...], list[Any]] = {}
    for blank in blanks:
        found = part_machinings(blank)
        entry = groups.setdefault(_key(blank, found), [blank, 0, found])
        entry[1] += 1
    if not groups:
        raise ValueError(translated(_NO_PART))
    return [(blank, count, found) for blank, count, found in groups.values()]


def _notes(found: Sequence[Machining], sheet: Any) -> tuple[list[str], Any]:
    """Lignes du tableau des usinages, coupées à la largeur de la bande, et leur place."""
    if not found:
        lines = [translated(_NONE)]
    else:
        lines = [translated(_HEADER)] + [
            translated(template, {**values, "face": translated(values["face"])})
            for template, values in machining_lines(found)
        ]
    wrapped, spot = notes_layout(sheet, lines, NOTE_SIZE_MM)
    # « {count} » reste à remplir par capped : on le réécrit tel quel.
    return capped(wrapped, translated(_MORE, {"count": "{count}"})), spot


def _title(blank: DocumentObject) -> str:
    mark = str(getattr(blank, "Mark", "")).strip()
    label = str(blank.Label)
    return f"{mark} - {label}" if mark and mark not in label else label


def _draw_part(
    doc: Document,
    blank: DocumentObject,
    count: int,
    found: Sequence[Machining],
    options: DrawingOptions,
) -> DocumentObject:
    shown = machined_part_of(blank) or blank
    page = find_overall_drawing(doc, [shown], PART_KIND)
    if page is None:
        page = create_page(doc, PART_KIND)
        page.Label = f"{translated(PART_TITLE)} {_title(blank)}"
    else:
        clear_page(page)
    with translated_errors():
        sheet = page_size(options.resolved_format(), options.resolved_orientation())
        length, width, thickness = _size(blank)
        reserve = notes_band(sheet)[1]
        layout = overall_layout(length, thickness, width, sheet, reserve=reserve, iso=False)
        corner = corner_iso_layout((length, thickness, width), layout, sheet, reserve)
    apply_template(page, options)
    inputs = {**title_inputs(options), "title": _title(blank)}
    kind = translated(_KIND, {"count": str(count)})
    fill_title_block(page, [blank], inputs, layout.scale, kind)
    page.Scale = layout.scale
    warn_if_unfitted(layout.fits)
    rotation = blank.getGlobalPlacement().Rotation
    notes = _notes(found, sheet)
    sizes = (length, width, thickness)
    set_owned(page, add_part_views(page, shown, rotation, layout, notes, (sizes, corner)))
    return page


def make_part_drawings(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> list[DocumentObject]:
    """Crée ou refait une page par pièce distincte de ``objects`` (tout le document s'il est
    vide) et renvoie les pages. Une seule transaction « Plan de pièce » ; ``ValueError``
    traduite, avant toute modification, si TechDraw manque ou s'il n'y a aucune pièce de bois.
    Le titre saisi dans ``options`` est ignoré : chaque page porte le nom de sa pièce."""
    require_techdraw()
    chosen = options or DrawingOptions()
    parts = distinct_parts(doc, objects)
    with translated_errors():
        page_size(chosen.resolved_format(), chosen.resolved_orientation())
    with drawing_transaction(doc, translated(PART_TITLE)):
        pages = [_draw_part(doc, blank, count, found, chosen) for blank, count, found in parts]
        doc.recompute()
    return pages
