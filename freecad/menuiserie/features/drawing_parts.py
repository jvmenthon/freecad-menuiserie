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
from dataclasses import dataclass, field
from typing import Any, Final

from freecad.menuiserie.core.drawing import (
    TRANSLATED_VALUES,
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
from freecad.menuiserie.features.drawing_dims import part_band_mm
from freecad.menuiserie.features.drawing_scope import (
    MAX_LINK_DEPTH,
    TOO_NESTED,
    LinkWalk,
    children_of,
    link_occurrences,
    link_target,
    object_key,
    workshop_inside,
)
from freecad.menuiserie.features.drawing_title import fill_title_block
from freecad.menuiserie.features.drawing_views import NOTE_SIZE_MM, add_part_views
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint, plan_for, resolved_for
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
)
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "blanks_of",
    "distinct_parts",
    "make_part_drawings",
    "part_count",
    "part_details",
    "part_groups",
]

MAX_QUANTITY: Final = 1_000_000  # exemplaires d'une pièce au plus (tableaux de liens imbriqués)
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
_TOO_MANY_COPIES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan de pièce impossible : plus de {limit} exemplaires d'une même pièce."
)
_KEY_DECIMALS: Final = 1
Blanks = list[tuple[DocumentObject, int]]  # pièces (brutes) et leur nombre
_WITH: Final = QT_TRANSLATE_NOOP("Menuiserie", "{kind} avec « {other} »")
Details = tuple[list[Machining], list[NoteLine]]  # usinages, lignes propres aux assemblages
_KINDS: Final = {
    "host_cuts": MachiningKind.CUT,
    "host_additions": MachiningKind.ADDED,
    "guest_cuts": MachiningKind.CUT,
    "guest_trims": MachiningKind.CUT,
    "guest_additions": MachiningKind.ADDED,
}


@dataclass
class _BlankWalk(LinkWalk):
    """Parcours des liens qui garde aussi les pièces que montre chaque cible (par clé)."""

    blanks: dict[tuple[str, str], Blanks] = field(default_factory=dict)


def _quantity(count: int) -> int:
    """``count`` exemplaires, ``ValueError`` traduite au-delà de ``MAX_QUANTITY``."""
    if count > MAX_QUANTITY:
        raise ValueError(translated(_TOO_MANY_COPIES, {"limit": str(MAX_QUANTITY)}))
    return count


def _blanks(
    objects: Sequence[DocumentObject], seen: set[str], walk: _BlankWalk, depth: int = 0
) -> Iterator[tuple[DocumentObject, int]]:
    """Pièces de bois (brutes) de ``objects`` et leur nombre : membres des ensembles et copies
    par lien de leur Std Part, brute d'une pièce usinée, sans doublon ; un lien (copie d'un
    meuble ou d'une pièce) redonne les pièces qu'il montre, autant de fois qu'il a de copies
    (pièces d'une cible calculées une fois par parcours)."""
    for obj in objects:
        if obj.Name in seen:
            continue
        seen.add(obj.Name)
        target = link_target(obj)
        if target is not None:
            times = link_occurrences(obj)
            for blank, count in _linked_blanks(target, walk, depth):
                yield blank, _quantity(count * times)
        elif is_furniture(obj):
            yield from _blanks(children_of(obj, walk), seen, walk, depth)
        elif is_machined_part(obj):
            yield from _blanks([blank_of(obj)], seen, walk, depth)
        elif is_timber(obj):
            yield obj, 1


def _linked_blanks(target: DocumentObject, walk: _BlankWalk, depth: int) -> Blanks:
    """Pièces (et nombre) que montre une copie de ``target``, mémorisées dans ``walk`` ;
    ``ValueError`` traduite au-delà de ``MAX_LINK_DEPTH`` liens imbriqués. Une boucle de liens
    (document piégé) n'ajoute rien : correction mineure pc1."""
    key = object_key(target)
    if key in walk.blanks:
        return walk.blanks[key]
    if depth >= MAX_LINK_DEPTH:
        raise ValueError(translated(TOO_NESTED, {"limit": str(MAX_LINK_DEPTH)}))
    walk.blanks[key] = []  # en cours : une boucle n'ajoute rien
    found = list(_blanks(workshop_inside(target, walk), set(), walk, depth + 1))
    walk.blanks[key] = found
    return found


def part_count(objects: Sequence[DocumentObject]) -> int:
    """Nombre d'exemplaires des pièces de bois de ``objects`` (copies par lien comprises) ;
    ``ValueError`` traduite pour un document démesuré."""
    return sum(count for _, count in _blanks(objects, set(), _BlankWalk()))


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
            name = machining_name(kind, group, bool(getattr(joint, "TailsOnHost", False)))
            items.extend((label, solid, _KINDS[group], name) for solid in solids)
        notes.extend(joint_note_lines(label, values, joint.HostPart == blank))
        if joint.GuestPart == blank:
            for bevel in plan.guest_bevels:
                face = (bevel.face.index, bevel.face.sign)
                line = bevel_line(label, face, bevel.saw_angles())
                if line is not None:
                    notes.append(line)
    return machinings(items, _size(blank)), notes


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
    # Réglages des assemblages sans leur libellé : deux pieds identiques assemblés à deux
    # traverses de noms différents restent une seule pièce distincte.
    texts = tuple(
        sorted(
            template + str(sorted((k, v) for k, v in values.items() if k != "label"))
            for template, values in notes
        )
    )
    return str(getattr(blank, "Material", "")), size, shape, texts


@dataclass
class _PartGroup:
    """Pièce distincte : première pièce, nombre, usinages, lignes et pièces du groupe."""

    blank: DocumentObject
    found: list[Machining]
    notes: list[NoteLine]
    count: int = 0
    members: list[DocumentObject] = field(default_factory=list)


def _grouped(doc: Document, objects: Sequence[DocumentObject]) -> list[_PartGroup]:
    """Pièces distinctes de ``objects`` (tout le document s'il est vide), par repère et nom."""
    scope = list(objects) or document_scope(doc)
    blanks = sorted(
        _blanks(scope, set(), _BlankWalk()),
        key=lambda item: (str(getattr(item[0], "Mark", "")), item[0].Name),
    )
    groups: dict[tuple[object, ...], _PartGroup] = {}
    for blank, times in blanks:
        found, notes = part_details(blank)
        group = groups.setdefault(_key(blank, found, notes), _PartGroup(blank, found, notes))
        group.count = _quantity(group.count + times)
        group.members.append(blank)
    return list(groups.values())


def distinct_parts(
    doc: Document, objects: Sequence[DocumentObject]
) -> list[tuple[DocumentObject, int, Details]]:
    """Pièces distinctes de ``objects`` (tout le document s'il est vide) : (première pièce,
    nombre, (usinages, lignes propres aux assemblages)), dans l'ordre des repères puis des
    noms. Deux pièces sont les mêmes si elles ont même matériau, mêmes cotes, mêmes usinages
    aux mêmes places et mêmes réglages. ``ValueError`` traduite s'il n'y a aucune pièce de
    bois."""
    groups = _grouped(doc, objects)
    if not groups:
        raise ValueError(translated(_NO_PART))
    return [(group.blank, group.count, (group.found, group.notes)) for group in groups]


def part_groups(doc: Document, objects: Sequence[DocumentObject]) -> list[list[DocumentObject]]:
    """Pièces de bois (brutes) de ``objects`` (tout le document s'il est vide), par pièce
    distincte : les pièces d'un groupe partagent un plan de pièce. Vide s'il n'y en a pas."""
    return [list(group.members) for group in _grouped(doc, objects)]


def blanks_of(objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Pièces de bois (brutes) que montrent ``objects`` (ensembles, pièces, copies), uniques."""
    found = {blank.Name: blank for blank, _ in _blanks(objects, set(), _BlankWalk())}
    return list(found.values())


def _line(template: str, values: dict[str, str]) -> str:
    """Ligne traduite ; ses valeurs « name », « face » et « end » sont des textes à traduire."""
    words: dict[str, str] = {
        key: translated(values[key]) for key in TRANSLATED_VALUES if key in values
    }
    return translated(template, {**values, **words})


def _notes(details: Details, sheet: Any) -> tuple[list[str], Any]:
    """Lignes du tableau des usinages (lignes propres aux assemblages, réglages des outils que
    la limite du tableau ne doit pas couper, puis usinages), coupées à la largeur de la bande,
    et leur place."""
    found, extra = details
    if not found and not extra:
        lines = [translated(_NONE)]
    else:
        rows = [*extra, *machining_lines(found)]
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
    set_owned(
        page, add_part_views(page, shown, rotation, layout, notes, (sizes, corner, options.settle))
    )
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
