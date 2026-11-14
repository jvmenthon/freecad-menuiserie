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
    MachiningItem,
    MachiningKind,
    NoteLine,
    bevel_line,
    capped,
    corner_iso_layout,
    joint_note_lines,
    machining_lines,
    machining_name,
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
    global_shape,
    require_techdraw,
    set_owned,
    title_inputs,
    warn_if_unfitted,
)
from freecad.menuiserie.features.drawing_title import fill_title_block
from freecad.menuiserie.features.drawing_views import NOTE_SIZE_MM, add_part_views, part_band_mm
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint, plan_for, resolved_for
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
)
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["distinct_parts", "make_part_drawings", "part_details", "part_machinings"]

PART_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de pièce")
_KIND: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de pièce, {count} ex.")
_HEADER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinages, en mm (x, y : depuis le coin bas gauche de la vue de face) :"
)
_NONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun usinage.")
_MORE: Final = QT_TRANSLATE_NOOP("Menuiserie", "… et {count} autres usinages")
_NO_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan de pièce impossible : aucune pièce de bois dans la sélection."
)
_KEY_DECIMALS: Final = 1
_WITH: Final = QT_TRANSLATE_NOOP("Menuiserie", "{kind} avec « {other} »")
_WORDS: Final = ("name", "face", "end")  # valeurs qui sont elles-mêmes des textes à traduire
Details = tuple[list[Machining], list[NoteLine]]  # usinages, lignes propres aux assemblages


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


def _joint_label(joint: DocumentObject, blank: DocumentObject) -> str:
    """« Queue d'aronde avec « Côté » » : le type d'assemblage et l'autre pièce."""
    other = joint.GuestPart if joint.HostPart == blank else joint.HostPart
    kind = translated(str(getattr(joint.Proxy, "LABEL", "")))
    return translated(_WITH, {"kind": kind, "other": str(getattr(other, "Label", ""))})


def _groups(plan: Any, joint: DocumentObject, blank: DocumentObject) -> list[tuple[str, Any]]:
    """Groupes de formes du plan qui usinent ``blank`` : (nom du groupe, formes)."""
    names: list[str] = []
    if joint.HostPart == blank:
        names += ["host_cuts", "host_additions"]
    if joint.GuestPart == blank:
        names += ["guest_cuts", "guest_trims", "guest_additions"]
    return [(name, getattr(plan, name)) for name in names]


_KINDS: Final = {
    "host_cuts": MachiningKind.CUT,
    "host_additions": MachiningKind.ADDED,
    "guest_cuts": MachiningKind.CUT,
    "guest_trims": MachiningKind.CUT,
    "guest_additions": MachiningKind.ADDED,
}


def part_details(blank: DocumentObject) -> tuple[list[Machining], list[NoteLine]]:
    """Usinages de la pièce de bois ``blank`` d'après les plans de ses assemblages, et les
    lignes propres à chaque assemblage (angle des queues d'aronde, onglet, tourillons, bouts
    coupés en biais). Un assemblage impossible est ignoré (il signale lui-même son erreur)."""
    machined = machined_part_of(blank)
    if machined is None:
        return [], []
    items: list[MachiningItem] = []
    notes: list[NoteLine] = []
    for joint in machined.Joints:
        if not is_joint(joint):
            continue
        try:
            plan = plan_for(joint)
            values = resolved_for(joint)
        except ValueError:
            continue
        label = _joint_label(joint, blank)
        kind = joint.Proxy.KIND
        for group, solids in _groups(plan, joint, blank):
            name = machining_name(kind, group)
            items.extend((label, solid, _KINDS[group], name) for solid in solids)
        notes.extend(joint_note_lines(label, values, joint.HostPart == blank))
        if joint.GuestPart == blank:
            for bevel in plan.guest_bevels:
                face = (bevel.face.index, bevel.face.sign)
                line = bevel_line(label, face, bevel.saw_angles())
                if line is not None:
                    notes.append(line)
    return machinings(items, _size(blank)), notes


def part_machinings(blank: DocumentObject) -> list[Machining]:
    """Usinages de la pièce de bois ``blank`` (voir :func:`part_details`)."""
    return part_details(blank)[0]


def _key(
    blank: DocumentObject, found: Sequence[Machining], notes: Sequence[NoteLine]
) -> tuple[object, ...]:
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
    texts = tuple(sorted(str(sorted(values.items())) for _, values in notes))
    return str(getattr(blank, "Material", "")), size, shape, texts


def distinct_parts(
    doc: Document, objects: Sequence[DocumentObject]
) -> list[tuple[DocumentObject, int, Details]]:
    """Pièces distinctes de ``objects`` (tout le document s'il est vide) : (première pièce,
    nombre, (usinages, lignes propres aux assemblages)), dans l'ordre des repères puis des
    noms. Deux pièces sont les mêmes si elles ont même matériau, mêmes cotes, mêmes usinages
    aux mêmes places et mêmes réglages. ``ValueError`` traduite s'il n'y a aucune pièce de
    bois."""
    scope = list(objects) or document_scope(doc)
    blanks = sorted(
        _blanks(scope, set()), key=lambda obj: (str(getattr(obj, "Mark", "")), obj.Name)
    )
    groups: dict[tuple[object, ...], list[Any]] = {}
    for blank in blanks:
        found, notes = part_details(blank)
        entry = groups.setdefault(_key(blank, found, notes), [blank, 0, found, notes])
        entry[1] += 1
    if not groups:
        raise ValueError(translated(_NO_PART))
    return [(blank, count, (found, notes)) for blank, count, found, notes in groups.values()]


def _line(template: str, values: dict[str, str]) -> str:
    """Ligne traduite ; ses valeurs « name », « face » et « end » sont des textes à traduire."""
    words: dict[str, str] = {key: translated(values[key]) for key in _WORDS if key in values}
    return translated(template, {**values, **words})


def _notes(details: Details, sheet: Any) -> tuple[list[str], Any]:
    """Lignes du tableau des usinages (usinages, puis lignes propres aux assemblages), coupées à
    la largeur de la bande, et leur place."""
    found, extra = details
    if not found and not extra:
        lines = [translated(_NONE)]
    else:
        rows = [*machining_lines(found), *extra]
        lines = [translated(_HEADER)] + [_line(template, values) for template, values in rows]
    wrapped, spot = notes_layout(sheet, lines, NOTE_SIZE_MM)
    # « {count} » reste à remplir par capped : on le réécrit tel quel.
    return capped(wrapped, translated(_MORE, {"count": "{count}"})), spot


def _extent(shown: DocumentObject, blank: DocumentObject) -> tuple[float, float, float]:
    """Étendue (longueur, largeur, épaisseur) de la pièce dessinée ``shown`` dans le repère de
    sa brute : plus que les cotes de la brute quand des tenons ou des queues dépassent ; ses
    vues sont mises en page et leurs cotes écartées d'après elle."""
    shape = global_shape(shown)
    if shape.isNull():
        return _size(blank)
    local = shape.copy()
    local.transformShape(blank.getGlobalPlacement().inverse().toMatrix())
    box = local.BoundBox
    return float(box.XLength), float(box.YLength), float(box.ZLength)


def _title(blank: DocumentObject) -> str:
    mark = str(getattr(blank, "Mark", "")).strip()
    label = str(blank.Label)
    return f"{mark} - {label}" if mark and mark not in label else label


def _draw_part(
    doc: Document,
    blank: DocumentObject,
    count: int,
    details: Details,
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
        length, width, thickness = _extent(shown, blank)
        reserve = notes_band(sheet)[1]
        layout = overall_layout(
            (length, thickness, width), sheet, reserve=reserve, iso=False, band=part_band_mm()
        )
        corner = corner_iso_layout((length, thickness, width), layout, sheet, reserve)
    apply_template(page, options)
    inputs = {**title_inputs(options), "title": _title(blank)}
    kind = translated(_KIND, {"count": str(count)})
    fill_title_block(page, [blank], inputs, layout.scale, kind)
    page.Scale = layout.scale
    warn_if_unfitted(layout.fits)
    rotation = blank.getGlobalPlacement().Rotation
    notes = _notes(details, sheet)
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
        pages = [_draw_part(doc, blank, count, details, chosen) for blank, count, details in parts]
        doc.recompute()
    return pages
