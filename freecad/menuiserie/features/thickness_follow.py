# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces assemblées qui suivent l'épaisseur d'une pièce modifiée (issue #133).

Changer l'épaisseur d'une pièce déplace sa face haute : les pièces posées dessus (tenon dans une
mortaise de cette face, par exemple) ne la touchaient plus et l'assemblage était défait. Elles
suivent maintenant la face, du même écart, avec toutes les pièces qui leur sont assemblées (sans
repasser par la pièce modifiée). Une pièce qui ne peut pas bouger est laissée où elle est et
signalée : membre d'un ensemble (l'ensemble relie ses membres lui-même), ``Placement`` piloté par
une expression, ou assemblée à la pièce modifiée par un autre contact que sa face haute. Les cotes
des assemblages sont recalculées par FreeCAD ; une cote devenue impossible (tenon plus épais que la
pièce) est signalée par l'assemblage lui-même. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence

import FreeCAD as App

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.core.thickness_follow import follow_shift, touches_raised_face
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.joints.base import is_joint, placed_blank
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["follow_thickness"]

_FOLLOWED: str = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'épaisseur de « {label} » a changé : {followers} suivent sa face pour garder l'assemblage.",
)
_KEPT: str = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'épaisseur de « {label} » a changé : {kept} ne peuvent pas suivre ({reason}) et "
    "restent en place ; l'assemblage peut être défait.",
)
_MEMBER: str = QT_TRANSLATE_NOOP("Menuiserie", "membre d'un ensemble")
_BOUND: str = QT_TRANSLATE_NOOP("Menuiserie", "position pilotée par une expression")
_OTHER_CONTACT: str = QT_TRANSLATE_NOOP("Menuiserie", "assemblées aussi par un autre contact")


def _joints_of(part: DocumentObject) -> list[DocumentObject]:
    return [joint for joint in part.InList if is_joint(joint)]


def _other(joint: DocumentObject, part: DocumentObject) -> DocumentObject | None:
    other = joint.GuestPart if joint.HostPart == part else joint.HostPart
    return other if other != part else None


def _attached(root: DocumentObject, excluded: DocumentObject) -> list[DocumentObject]:
    """``root`` et les pièces qui lui sont assemblées de proche en proche, sans passer par
    ``excluded``."""
    found = [root]
    pending = [root]
    while pending:
        part = pending.pop()
        for joint in _joints_of(part):
            other = _other(joint, part)
            if other is not None and other != excluded and other not in found:
                found.append(other)
                pending.append(other)
    return found


def _labels(parts: Sequence[DocumentObject]) -> str:
    return ", ".join(f"« {quoted_value(part.Label)} »" for part in parts)


def _partners(part: DocumentObject, before: PlacedBlock) -> list[tuple[DocumentObject, bool]]:
    """Pièces assemblées à ``part`` : vrai si tous leurs contacts sont avec sa face haute
    (épaisseur d'avant, ``before``)."""
    raised_by_name: dict[str, bool] = {}
    objects: dict[str, DocumentObject] = {}  # par nom : les objets FreeCAD ne servent pas de clé
    for joint in _joints_of(part):
        other = _other(joint, part)
        if other is None:
            continue
        try:
            raised = touches_raised_face(before, placed_blank(other))
        except ValueError:  # pièce invalide : elle ne suit pas
            raised = False
        objects[other.Name] = other
        raised_by_name[other.Name] = raised_by_name.get(other.Name, True) and raised
    return [(objects[name], raised) for name, raised in raised_by_name.items()]


def _blocker(group: Sequence[DocumentObject], fixed: Sequence[DocumentObject]) -> str | None:
    """Raison pour laquelle ``group`` ne peut pas bouger, ``None`` s'il le peut. ``fixed`` :
    pièces assemblées à la pièce modifiée ailleurs que sur sa face haute."""
    if any(furniture_of(part) is not None for part in group):
        return translated(_MEMBER)
    if any(placement_expression(part) is not None for part in group):
        return translated(_BOUND)
    if any(part in fixed for part in group):
        return translated(_OTHER_CONTACT)
    return None


def _move(parts: Sequence[DocumentObject], shift: Sequence[float]) -> None:
    for part in parts:
        placement = App.Placement(part.Placement)
        placement.Base = placement.Base + App.Vector(*shift)
        part.Placement = placement


def follow_thickness(part: DocumentObject, old: float, new: float) -> list[str]:
    """Les pièces posées sur la face haute de ``part`` (épaisseur ``old`` avant, ``new`` après)
    suivent la face ; renvoie les messages (vue rapport) : pièces qui ont suivi, pièces laissées
    en place avec la raison. Sans effet si rien ne change ou si ``part`` n'a pas d'assemblage."""
    if old == new or not _joints_of(part):
        return []
    size = dimensions_of(part)
    before = PlacedBlock(Dimensions(size.length, size.width, old), rigid_transform(part.Placement))
    partners = _partners(part, before)
    fixed = [other for other, raised in partners if not raised]
    shift = follow_shift(before, new - old)
    moved: list[DocumentObject] = []
    kept: dict[str, list[DocumentObject]] = {}
    for root in (other for other, raised in partners if raised):
        group = _attached(root, part)
        reason = _blocker(group, fixed)
        if reason is not None:
            kept.setdefault(reason, []).append(root)
        elif root not in moved:
            _move([piece for piece in group if piece not in moved], (shift.x, shift.y, shift.z))
            moved.extend(piece for piece in group if piece not in moved)
    label = quoted_value(part.Label)
    messages = [
        translated(_KEPT, {"label": label, "kept": _labels(roots), "reason": reason})
        for reason, roots in kept.items()
    ]
    if moved:
        messages.insert(0, translated(_FOLLOWED, {"label": label, "followers": _labels(moved)}))
    return messages


def report_following(part: DocumentObject, old: float, new: float) -> None:
    """:func:`follow_thickness`, messages dans la vue rapport."""
    for message in follow_thickness(part, old, new):
        report_warning(message)
