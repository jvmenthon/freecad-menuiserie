# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture d'une pièce brute, de ses ajouts d'assemblage et des tourillons (J2c, D4 à D8).

Lecture seule : aucune écriture dans le document, aucun recalcul. Les anomalies ne bloquent
jamais la liste : elles deviennent des avertissements (:class:`CollectNoticeKind`).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from enum import Enum
from typing import Any, Final

from freecad.menuiserie.core.cutlist import (
    NO_ADDITIONS,
    BevelCut,
    CutEntry,
    Hardware,
    HardwareKind,
)
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box
from freecad.menuiserie.core.hardware import HARDWARE_JOINT_KINDS
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.joints import Bevel, JointKind, JointPlan
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.core.part_model import Allowances, Dimensions, GrainDirection, PartRecord
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.hardware import get_catalog
from freecad.menuiserie.features.i18n import templated_message
from freecad.menuiserie.features.joints.base import is_joint, plan_for, resolved_for
from freecad.menuiserie.features.joints.hardware_reference import HARDWARE_REFERENCE_PROPERTY
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.shaped_part import is_shaped_part, signature_of
from freecad.menuiserie.features.wood_part import dimensions_of
from freecad.menuiserie.features.wood_part_record import (
    GRAIN_BY_VALUE,
    UnsupportedPartError,
    allowances_of,
    record_of,
)
from freecad.menuiserie.features.wood_part_schema import density_kg_m3, part_kind

__all__ = [
    "UNKNOWN_MATERIAL_PREFIX",
    "CollectNoticeKind",
    "entry_of",
    "hardware_of",
    "is_hardware_joint",
    "local_shape",
    "machined_extent",
]

UNKNOWN_MATERIAL_PREFIX: Final = "? "
_EPSILON_MM: Final = 1e-3  # en deçà, l'écart vient de la tolérance de la boîte englobante
_ADDITION_DECIMALS: Final = 3


class CollectNoticeKind(Enum):
    """Nature d'un avertissement de la collecte (en plus de ceux de ``core.cutlist``)."""

    UNREADABLE_PART = "UnreadablePart"
    IGNORED_PART = "IgnoredPart"
    NO_MACHINED_SHAPE = "NoMachinedShape"
    UNREADABLE_DOWELS = "UnreadableDowels"
    LINK_TOO_DEEP = "LinkTooDeep"
    TRUNCATED = "Truncated"
    QUANTITY_CAPPED = "QuantityCapped"

    @property
    def template(self) -> str:
        """Gabarit français marqué pour la traduction."""
        return _TEMPLATES[self]


_TEMPLATES: Final = {
    CollectNoticeKind.UNREADABLE_PART: QT_TRANSLATE_NOOP(
        "Menuiserie",
        "Pièce « {label} » : catégorie ou sens du fil inconnu (document d'une version plus "
        "récente de l'atelier ?), listée avec le matériau « ? ».",
    ),
    CollectNoticeKind.IGNORED_PART: QT_TRANSLATE_NOOP(
        "Menuiserie", "Pièce « {label} » ignorée de la liste : {reason}"
    ),
    CollectNoticeKind.NO_MACHINED_SHAPE: QT_TRANSLATE_NOOP(
        "Menuiserie",
        "Pièce usinée « {label} » : forme absente, invalide ou à recalculer, les ajouts des "
        "assemblages (tenons, languettes) ne sont pas comptés dans le débit.",
    ),
    CollectNoticeKind.UNREADABLE_DOWELS: QT_TRANSLATE_NOOP(
        "Menuiserie", "Assemblage « {label} » : fournitures non comptées ({reason})"
    ),
    CollectNoticeKind.LINK_TOO_DEEP: QT_TRANSLATE_NOOP(
        "Menuiserie",
        "« {label} » : liens ou conteneurs imbriqués trop profondément (ou en boucle), lecture "
        "interrompue.",
    ),
    CollectNoticeKind.TRUNCATED: QT_TRANSLATE_NOOP(
        "Menuiserie",
        "« {label} » : document trop vaste ou trop imbriqué (liens multiples), liste tronquée : "
        "la lecture s'est arrêtée après {limit} objets visités.",
    ),
    CollectNoticeKind.QUANTITY_CAPPED: QT_TRANSLATE_NOOP(
        "Menuiserie",
        "« {label} » : nombre d'occurrences trop grand (tableau de liens), quantité plafonnée "
        "à {limit}.",
    ),
}


def _label(obj: DocumentObject) -> str:
    return quoted_value(getattr(obj, "Label", obj))


def _reason(error: ValueError) -> str:
    return templated_message(error) if isinstance(error, TemplatedError) else str(error)


def notice(kind: CollectNoticeKind, obj: DocumentObject, **extra: str) -> Notice:
    """Avertissement ``kind`` qui nomme ``obj`` (libellé cité sans risque)."""
    return Notice(kind, {"label": _label(obj), **extra})


# --- Pièce brute -------------------------------------------------------------------------


def _unknown_record(obj: DocumentObject) -> PartRecord:
    """Pièce d'après ses propriétés seules quand la catégorie ou le fil est inconnu : massif ou
    sans fil à défaut, matériau précédé de « ? » (D8)."""
    return PartRecord(
        mark=obj.Mark,
        material_id=obj.MaterialId,
        material_name=UNKNOWN_MATERIAL_PREFIX + str(obj.Material),
        kind=part_kind(obj, None),
        finished=dimensions_of(obj),
        allowances=allowances_of(obj),
        grain=GRAIN_BY_VALUE.get(obj.GrainDirection, GrainDirection.NONE),
        density=density_kg_m3(obj),
    )


def _record(blank: DocumentObject, notices: list[Notice]) -> PartRecord:
    try:
        return record_of(blank)
    except UnsupportedPartError:
        notices.append(notice(CollectNoticeKind.UNREADABLE_PART, blank))
        return _unknown_record(blank)


def _rough_thicknesses(record: PartRecord) -> tuple[float, ...]:
    """Épaisseurs de brut du matériau de la pièce dans la bibliothèque (ADR 0015) ; aucune si
    le matériau est introuvable."""
    material = get_library().find(record.material_id)
    return () if material is None else material.rough_thicknesses


def entry_of(blank: DocumentObject, quantity: int, notices: list[Notice]) -> CutEntry | None:
    """Entrée de débit de la brute ou de la pièce en bois ``blank`` vue ``quantity`` fois, ajouts
    compris (cotes finies = encombrement pour une pièce en bois, qui porte aussi son empreinte de
    forme) ; ``None`` et un avertissement qui la nomme si ses propriétés sont inutilisables (cote
    invalide, forme absente…)."""
    try:
        record = _record(blank, notices)
        finished, additions = machined_extent(blank, notices)
        if finished != record.finished:  # pièce dessinée hors tout, raccourcie (ADR 0016)
            record = replace(record, finished=finished)
        owner = furniture_of(blank)
        label = str(owner.Label) if owner is not None else ""
        rough = _rough_thicknesses(record)
        shape = signature_of(blank) if is_shaped_part(blank) else None
        return CutEntry(
            record, quantity, additions, label, str(blank.Name), rough, shape, bevels_of(blank)
        )
    except (ValueError, AttributeError, TypeError) as error:
        reason = _reason(error) if isinstance(error, ValueError) else type(error).__name__
        notices.append(notice(CollectNoticeKind.IGNORED_PART, blank, reason=reason))
        return None


# --- Ajouts des assemblages (D4) ---------------------------------------------------------


def local_shape(machined: DocumentObject) -> Any | None:
    """Forme de la pièce usinée dans le repère de sa brute, ``None`` si elle est absente,
    invalide ou à recalculer (un assemblage en échec laisse la pièce « Touched » avec la forme de
    la brute). La forme porte son ``Placement`` (celui de la brute) : on le défait."""
    if "Invalid" in machined.State or "Touched" in machined.State:
        return None
    shape = machined.Shape
    if shape.isNull() or not shape.Solids or not shape.isValid():
        return None
    return shape.transformed(shape.Placement.inverse().toMatrix())


def _local_box(machined: DocumentObject) -> Any | None:
    """Boîte englobante de :func:`local_shape`, ``None`` sans forme utilisable."""
    shape = local_shape(machined)
    return None if shape is None else shape.BoundBox


def _excess(low: float, high: float, size: float) -> float:
    """Matière au-delà de ``[0, size]``, des deux côtés cumulés, arrondie au millième."""
    value = round(max(0.0, -low) + max(0.0, high - size), _ADDITION_DECIMALS)
    return value if value >= _EPSILON_MM else 0.0


def _guest_plans(blank: DocumentObject, machined: DocumentObject) -> Iterator[JointPlan]:
    """Plans des assemblages dont ``blank`` est l'invitée ; un assemblage impossible n'en donne
    aucun."""
    for joint in getattr(machined, "Joints", ()):
        if not is_joint(joint) or joint.GuestPart != blank:
            continue
        try:
            yield plan_for(joint)
        except ValueError:
            continue


def _trims(blank: DocumentObject, machined: DocumentObject) -> Iterator[Box]:
    """Parties retirées de ``blank`` par les assemblages dont elle est l'invitée (ADR 0016) ;
    un assemblage impossible n'en retire aucune. Les coins retirés en biais (polyèdres) sont
    pris en compte par :func:`bevels_of`."""
    for plan in _guest_plans(blank, machined):
        yield from (trim for trim in plan.guest_trims if isinstance(trim, Box))


def _bevels(blank: DocumentObject, machined: DocumentObject) -> Iterator[Bevel]:
    for plan in _guest_plans(blank, machined):
        yield from plan.guest_bevels


def bevels_of(blank: DocumentObject) -> tuple[BevelCut, ...]:
    """Coupes en biais des bouts de ``blank`` (réglages de la scie, ADR 0024), vide sans
    assemblage en biais."""
    machined = machined_part_of(blank)
    if machined is None:
        return ()
    return tuple(BevelCut(*bevel.saw_angles()) for bevel in _bevels(blank, machined))


def _spans(trim: Box, ranges: list[list[float]], axis: int) -> bool:
    low, high = ranges[axis]
    tolerance = CONTACT_TOLERANCE_MM
    return trim.lo(axis) <= low + tolerance and trim.hi(axis) >= high - tolerance


def _kept_box(blank: DocumentObject, machined: DocumentObject, size: Dimensions) -> Box:
    """Boîte de la brute moins ses parties retirées (repère de la brute) : chacune part d'une
    face et couvre la pièce sur les deux autres axes, la pièce est raccourcie d'autant."""
    ranges = [[0.0, size.length], [0.0, size.width], [0.0, size.thickness]]
    for trim in _trims(blank, machined):
        for axis in range(3):
            if not all(_spans(trim, ranges, other) for other in range(3) if other != axis):
                continue
            low, high = ranges[axis]
            if trim.lo(axis) <= low + CONTACT_TOLERANCE_MM < trim.hi(axis) < high:
                ranges[axis][0] = trim.hi(axis)
            elif low < trim.lo(axis) < high - CONTACT_TOLERANCE_MM <= trim.hi(axis):
                ranges[axis][1] = trim.lo(axis)
    for bevel in _bevels(blank, machined):  # bout biais : cote finie au long point
        ranges[bevel.face.index][1 if bevel.face.sign > 0 else 0] = bevel.long_point
    return Box.from_ranges([(low, high) for low, high in ranges])


def machined_extent(blank: DocumentObject, notices: list[Notice]) -> tuple[Dimensions, Allowances]:
    """Cotes finies réelles de ``blank`` et ses ajouts (mm, le long de L, l, e).

    Cotes : celles de la brute, moins les parties retirées d'une invitée dessinée hors tout qui
    chevauchait l'hôte (ADR 0016). Ajouts : étendue de la pièce usinée au-delà de ces cotes :
    tenon, et invitée prolongée dans l'hôte d'une feuillure, d'un mi-bois ou d'un onglet entre
    pièces au contact (ADR 0014) ; les autres retraits ne donnent rien (ADR 0006). Sans pièce
    usinée : la brute, sans ajout ; forme absente ou invalide : de même, et un avertissement."""
    size = dimensions_of(blank)
    machined = machined_part_of(blank)
    if machined is None:
        return size, NO_ADDITIONS
    box = _local_box(machined)
    if box is None:
        notices.append(notice(CollectNoticeKind.NO_MACHINED_SHAPE, machined))
        return size, NO_ADDITIONS
    kept = _kept_box(blank, machined, size)
    bounds = ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))
    excess = [
        _excess(low - kept.lo(axis), high - kept.lo(axis), kept.size(axis))
        for axis, (low, high) in enumerate(bounds)
    ]
    finished = Dimensions(kept.size(0), kept.size(1), kept.size(2))
    return (size if finished == size else finished), Allowances(*excess)


def additions_of(blank: DocumentObject, notices: list[Notice]) -> Allowances:
    """Ajouts de ``blank`` (mm, le long de L, l, e), d'après :func:`machined_extent`."""
    return machined_extent(blank, notices)[1]


# --- Fournitures : tourillons (D5), faux tenons, biscuits, pieds, coulisses, charnières ------


def is_hardware_joint(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est un assemblage à pièces rapportées (tourillons, faux tenons, biscuits,
    pieds, coulisses, charnières)."""
    return is_joint(obj) and obj.Proxy.KIND in HARDWARE_JOINT_KINDS


def _hardware(joint: DocumentObject, values: Any, quantity: int) -> Hardware | None:
    """Fourniture d'après les valeurs effectives de l'assemblage (son type se lit à leurs
    champs)."""
    if hasattr(values, "pin_projection"):  # perçage LR32 : valeurs de ShelfPinsValues
        length = values.hole_depth + values.pin_projection
        shelf_pin = Hardware(HardwareKind.SHELF_PIN, values.hole_diameter, length, quantity)
        return shelf_pin if quantity else None
    if hasattr(values, "dowel_length"):  # tourillons : valeurs de DowelValues
        return Hardware(HardwareKind.DOWEL, values.diameter, values.dowel_length, quantity)
    if hasattr(values, "base_diameter"):  # pieds : valeurs de FootValues
        return Hardware(
            HardwareKind.FOOT,
            values.stem_diameter,
            values.height,
            quantity,
            material=values.foot_material,
        )
    if hasattr(values, "hole_positions"):  # coulisse : valeurs de SlideValues
        return Hardware(HardwareKind.DRAWER_SLIDE, values.thickness, values.length, quantity)
    if hasattr(values, "cup_diameter"):  # charnières : valeurs de HingeValues
        return Hardware(HardwareKind.HINGE, values.cup_diameter, values.cup_depth, quantity)
    kind = (
        HardwareKind.LOOSE_TENON
        if joint.Proxy.KIND is JointKind.LOOSE_TENON
        else HardwareKind.BISCUIT
    )
    return Hardware(kind, values.thickness, values.total_depth, quantity, values.along)


def _with_reference(joint: DocumentObject, item: Hardware) -> Hardware:
    """``item`` avec le fabricant et la référence de la référence du catalogue posée (liste
    d'achat) ; une référence disparue du catalogue garde son identifiant, sans fabricant."""
    reference_id = str(getattr(joint, HARDWARE_REFERENCE_PROPERTY, ""))
    if not reference_id:
        return item
    found = get_catalog().find(reference_id)
    if found is None:
        return replace(item, reference=reference_id)
    return replace(item, manufacturer=found.manufacturer, reference=found.purchase_reference)


def hardware_of(joint: DocumentObject, times: int, notices: list[Notice]) -> Hardware | None:
    """Fourniture de l'assemblage ``joint``, répétée ``times`` fois : le nombre de pièces
    rapportées de leurs cotes effectives (valeurs automatiques résolues). ``None`` et un
    avertissement si l'assemblage est impossible ; ``None`` sans avertissement si l'assemblage
    n'apporte aucune pièce (perçage sans taquets)."""
    try:
        values: Any = resolved_for(joint)
        item = _hardware(joint, values, values.count * times)
        return item if item is None else _with_reference(joint, item)
    except ValueError as error:
        notices.append(notice(CollectNoticeKind.UNREADABLE_DOWELS, joint, reason=_reason(error)))
        return None
