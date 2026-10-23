# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture d'une pièce brute, de ses ajouts d'assemblage et des tourillons (J2c, D4 à D8).

Lecture seule : aucune écriture dans le document, aucun recalcul. Les anomalies ne bloquent
jamais la liste : elles deviennent des avertissements (:class:`CollectNoticeKind`).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Final

from freecad.menuiserie.core.cutlist import NO_ADDITIONS, CutEntry, Hardware, HardwareKind
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.core.part_model import Allowances, GrainDirection, PartRecord
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import templated_message
from freecad.menuiserie.features.joints.base import is_joint, resolved_for
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import machined_part_of
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
    "dowel_hardware",
    "entry_of",
    "is_dowel_joint",
    "local_shape",
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
        "Menuiserie", "Assemblage « {label} » : tourillons non comptés ({reason})"
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
    """Entrée de débit de la brute ``blank`` vue ``quantity`` fois, ajouts compris ; ``None`` et
    un avertissement qui la nomme si ses propriétés sont inutilisables (cote invalide…)."""
    try:
        record = _record(blank, notices)
        additions = additions_of(blank, notices)
        owner = furniture_of(blank)
        label = str(owner.Label) if owner is not None else ""
        rough = _rough_thicknesses(record)
        return CutEntry(record, quantity, additions, label, str(blank.Name), rough)
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


def additions_of(blank: DocumentObject, notices: list[Notice]) -> Allowances:
    """Ajouts (mm) le long de L, l, e : étendue de la pièce usinée de ``blank`` au-delà de la
    brute : tenon, et invitée prolongée dans l'hôte d'une feuillure, d'un mi-bois ou d'un onglet
    entre pièces au contact (ADR 0014) ; les retraits seuls ne donnent rien (ADR 0006). Sans pièce
    usinée : rien ; forme absente ou invalide : rien et un avertissement."""
    machined = machined_part_of(blank)
    if machined is None:
        return NO_ADDITIONS
    box = _local_box(machined)
    if box is None:
        notices.append(notice(CollectNoticeKind.NO_MACHINED_SHAPE, machined))
        return NO_ADDITIONS
    size = dimensions_of(blank)
    return Allowances(
        _excess(box.XMin, box.XMax, size.length),
        _excess(box.YMin, box.YMax, size.width),
        _excess(box.ZMin, box.ZMax, size.thickness),
    )


# --- Tourillons (D5) ---------------------------------------------------------------------


def is_dowel_joint(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est un assemblage par tourillons de l'atelier."""
    return is_joint(obj) and obj.Proxy.KIND is JointKind.DOWELS


def dowel_hardware(joint: DocumentObject, times: int, notices: list[Notice]) -> Hardware | None:
    """Fourniture de l'assemblage ``joint``, répétée ``times`` fois : ``count`` tourillons de
    ``diameter`` sur ``dowel_length`` effectifs (valeurs automatiques résolues). ``None`` et un
    avertissement si l'assemblage est impossible."""
    try:
        values: Any = resolved_for(joint)
        return Hardware(
            HardwareKind.DOWEL, values.diameter, values.dowel_length, values.count * times
        )
    except ValueError as error:
        notices.append(notice(CollectNoticeKind.UNREADABLE_DOWELS, joint, reason=_reason(error)))
        return None
