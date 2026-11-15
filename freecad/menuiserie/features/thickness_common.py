# SPDX-License-Identifier: LGPL-2.1-or-later
"""Outils communs aux pièces qui suivent une épaisseur modifiée (issue #133, ADR 0060).

Utilisés par le suivi de la face haute (:mod:`~freecad.menuiserie.features.thickness_follow`), les
choix du panneau (:mod:`~freecad.menuiserie.features.thickness_choice`) et le suivi à la souris
(:mod:`~freecad.menuiserie.features.thickness_drag`) : assemblages d'une pièce et pièces assemblées
de proche en proche, une seule raison « ne peut pas changer » (:func:`blocker`), écritures sans
réaction de ``onChanged`` (déplacement, prolongement, état rendu) et textes partagés. Aucun import
de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.core.thickness_side import Extension
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    has_expression,
    placement_expression,
)
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_entry import write_placement
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.shaped_part import is_shaped_part

__all__ = [
    "SIZE_PROPS",
    "TOO_SHORT",
    "attached",
    "blocker",
    "extend_part",
    "has_joints",
    "is_assembled_isolated",
    "joints_of",
    "length_text",
    "other_part",
    "quoted",
    "quoted_parts",
    "restore_state",
    "shift_part",
    "size_state",
]

SIZE_PROPS: Final = ("Length", "Width", "Thickness")  # axes 0, 1 et 2 de la pièce
PLACEMENT: Final = "Placement"

TOO_SHORT: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} deviendrait trop courte.")
_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est une copie : elle suit sa répétition et ne peut pas être modifiée."
)
_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est membre d'un ensemble : l'ensemble la place et fixe ses cotes."
)
_SHAPED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est une pièce en bois : ses cotes sont celles du dessin."
)
_BOUND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : cote ou position pilotée par une expression."
)


def joints_of(part: DocumentObject) -> list[DocumentObject]:
    """Assemblages de l'atelier qui citent ``part``."""
    return [obj for obj in part.InList if is_joint(obj)]


def has_joints(part: DocumentObject) -> bool:
    """Vrai si ``part`` porte au moins un assemblage."""
    return bool(joints_of(part))


def is_assembled_isolated(part: DocumentObject) -> bool:
    """Vrai pour une pièce assemblée hors de tout ensemble : son épaisseur peut défaire un
    assemblage et le panneau propose où l'ajouter (ADR 0060)."""
    return furniture_of(part) is None and has_joints(part)


def other_part(joint: DocumentObject, part: DocumentObject) -> DocumentObject | None:
    """Autre pièce de ``joint`` que ``part`` ; ``None`` si elle manque ou si c'est ``part``."""
    other = joint.GuestPart if joint.HostPart == part else joint.HostPart
    return other if other is not None and other != part else None


def attached(root: DocumentObject, excluded: DocumentObject | None = None) -> list[DocumentObject]:
    """``root`` et les pièces qui lui sont assemblées de proche en proche, sans passer par
    ``excluded``."""
    found = [root]
    pending = [root]
    while pending:
        part = pending.pop()
        for joint in joints_of(part):
            other = other_part(joint, part)
            if other is not None and other != excluded and other not in found:
                found.append(other)
                pending.append(other)
    return found


def quoted(part: DocumentObject) -> str:
    """Nom de ``part`` entre guillemets : « H »."""
    return f"« {quoted_value(part.Label)} »"


def quoted_parts(parts: Sequence[DocumentObject]) -> str:
    """Noms de ``parts`` entre guillemets, séparés par des virgules."""
    return ", ".join(quoted(part) for part in parts)


def length_text(value: float) -> str:
    """Longueur ``value`` (mm, valeur absolue) dans l'unité de l'utilisateur."""
    text: str = App.Units.Quantity(abs(value), App.Units.Length).UserString
    return text


def _is_copy(part: DocumentObject) -> bool:
    # import différé : repeat → furniture_edits → thickness_follow → ce module
    from freecad.menuiserie.features.repeat import is_copy

    return is_copy(part)


def blocker(part: DocumentObject, props: Sequence[str]) -> str | None:
    """Pourquoi ``part`` ne peut pas voir changer ses propriétés ``props`` (cotes de
    :data:`SIZE_PROPS`, ``Placement``), ``None`` si elle le peut. Message traduit."""
    label = {"label": quoted(part)}
    sizes = [prop for prop in props if prop != PLACEMENT]
    if _is_copy(part):
        return translated(_COPY, label)
    if furniture_of(part) is not None:
        return translated(_MEMBER, label)
    if sizes and is_shaped_part(part):
        return translated(_SHAPED, label)
    bound = any(has_expression(part, prop) for prop in sizes)
    if bound or (PLACEMENT in props and placement_expression(part) is not None):
        return translated(_BOUND, label)
    return None


def shift_part(part: DocumentObject, shift: App.Vector) -> None:
    """Translation de ``part`` sans réaction de ``onChanged``, arrondie au nm (pas de 1e-15
    écrit par une rotation)."""
    placement = App.Placement(part.Placement)
    moved = placement.Base + shift
    placement.Base = App.Vector(round(moved.x, 6), round(moved.y, 6), round(moved.z, 6))
    write_placement(part, placement)


def extend_part(part: DocumentObject, extension: Extension, delta: float) -> None:
    """Prolonge ``part`` de ``delta`` mm selon ``extension`` (cote et, bout de début, origine),
    sans réaction de ``onChanged``."""
    prop = SIZE_PROPS[extension.axis]
    with writing(part):
        setattr(part, prop, getattr(part, prop).Value + delta)
    local = extension.origin_shift(delta)
    if local.component(extension.axis) != 0.0:
        shift_part(part, part.Placement.Rotation.multVec(App.Vector(local.x, local.y, local.z)))


def size_state(part: DocumentObject) -> tuple[float, float, float]:
    """Cotes de ``part`` (longueur, largeur, épaisseur), en mm."""
    return (float(part.Length.Value), float(part.Width.Value), float(part.Thickness.Value))


def restore_state(
    part: DocumentObject, sizes: tuple[float, float, float], placement: App.Placement
) -> None:
    """Cotes ``sizes`` et ``placement`` rendus à ``part`` s'ils ont changé, sans réaction de
    ``onChanged`` ; une cote pilotée par une expression n'est pas écrite."""
    with writing(part):
        for prop, value in zip(SIZE_PROPS, sizes, strict=True):
            if getattr(part, prop).Value != value and not has_expression(part, prop):
                setattr(part, prop, value)
    if not part.Placement.isSame(placement, 1e-9):
        write_placement(part, placement)
