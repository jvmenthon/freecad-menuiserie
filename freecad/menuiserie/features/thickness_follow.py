# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces assemblées qui suivent l'épaisseur d'une pièce modifiée (issue #133).

Changer l'épaisseur d'une pièce déplace sa face haute : les pièces posées dessus (tenon dans une
mortaise de cette face, par exemple) ne la touchaient plus et l'assemblage était défait. Elles
suivent maintenant la face, du même écart, avec toutes les pièces qui leur sont assemblées (sans
repasser par la pièce modifiée). Une pièce qui ne peut pas bouger est laissée où elle est et
signalée (:func:`~freecad.menuiserie.features.thickness_common.blocker`) : copie de répétition,
membre d'un ensemble, ``Placement`` piloté par une expression, ou assemblée à la pièce modifiée
par un autre contact que sa face haute. Les cotes des assemblages sont recalculées par FreeCAD ;
une cote devenue impossible (tenon plus épais que la pièce) est signalée par l'assemblage
lui-même. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import FreeCAD as App

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.core.thickness_follow import follow_shift, touches_raised_face
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.joints.base import placed_blank
from freecad.menuiserie.features.joints.frames import direction_in_frame_of
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.thickness_common import (
    PLACEMENT,
    attached,
    blocker,
    has_joints,
    joints_of,
    other_part,
    quoted,
    quoted_parts,
    shift_part,
)
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["follow_thickness"]

_FOLLOWED: str = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'épaisseur de « {label} » a changé : {followers} suivent sa face pour garder l'assemblage.",
)
_KEPT: str = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'épaisseur de « {label} » a changé : {kept} restent en place ; l'assemblage peut être "
    "défait. {reason}",
)
_OTHER_CONTACT: str = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est assemblée aussi par un autre contact."
)


def _partners(
    part: DocumentObject, before: PlacedBlock, lowered: bool
) -> list[tuple[DocumentObject, bool]]:
    """Pièces assemblées à ``part`` : vrai si tous leurs contacts sont avec sa face haute
    (épaisseur d'avant, ``before``), ou sa face basse si ``lowered``."""
    raised_by_name: dict[str, bool] = {}
    objects: dict[str, DocumentObject] = {}  # par nom : les objets FreeCAD ne servent pas de clé
    for joint in joints_of(part):
        other = other_part(joint, part)
        if other is None:
            continue
        try:
            raised = touches_raised_face(
                before, placed_blank(other, frame_of=part), lowered=lowered
            )
        except ValueError:  # pièce invalide : elle ne suit pas
            raised = False
        objects[other.Name] = other
        raised_by_name[other.Name] = raised_by_name.get(other.Name, True) and raised
    return [(objects[name], raised) for name, raised in raised_by_name.items()]


def _blocker(
    group: Sequence[DocumentObject],
    fixed: Sequence[DocumentObject],
    free: DocumentObject | None,
) -> str | None:
    """Raison pour laquelle ``group`` ne peut pas bouger, ``None`` s'il le peut. ``fixed`` :
    pièces assemblées à la pièce modifiée ailleurs que sur sa face haute ; ``free`` : voir
    :func:`~freecad.menuiserie.features.thickness_common.blocker`."""
    for part in group:
        reason = blocker(part, (PLACEMENT,), free)
        if reason is not None:
            return reason
    for part in group:
        if part in fixed:
            return translated(_OTHER_CONTACT, {"label": quoted(part)})
    return None


@dataclass(frozen=True)
class FollowPlan:
    """Pièces qui suivent la face d'une pièce dont l'épaisseur change, choisies sur la pièce à son
    épaisseur et son placement d'avant (``before``) : ``moved`` les pièces qui suivent (groupes
    assemblés de proche en proche), ``kept`` les racines laissées en place, par raison."""

    part: DocumentObject
    before: PlacedBlock
    lowered: bool
    moved: tuple[DocumentObject, ...]
    kept: Mapping[str, tuple[DocumentObject, ...]]

    def shift(self, delta: float) -> App.Vector:
        """Translation des pièces qui suivent pour un écart d'épaisseur ``delta`` mm."""
        vector = follow_shift(self.before, -delta if self.lowered else delta)
        return App.Vector(vector.x, vector.y, vector.z)

    def apply(self, delta: float, pieces: Iterable[DocumentObject] | None = None) -> None:
        """Pièces qui suivent (``pieces`` : certaines d'entre elles seulement) déplacées de
        l'écart ``delta``, depuis leur placement actuel."""
        if delta == 0.0:
            return
        shift = self.shift(delta)
        for piece in self.moved if pieces is None else pieces:  # repère de son conteneur (0054)
            shift_part(piece, direction_in_frame_of(shift, self.part, piece))

    def messages(self, part: DocumentObject) -> list[str]:
        """Messages de la vue rapport : pièces qui ont suivi, pièces laissées en place."""
        label = quoted_value(part.Label)
        messages = [
            translated(_KEPT, {"label": label, "kept": quoted_parts(roots), "reason": reason})
            for reason, roots in self.kept.items()
        ]
        if self.moved:
            followers = quoted_parts(self.moved)
            messages.insert(0, translated(_FOLLOWED, {"label": label, "followers": followers}))
        return messages


def follow_plan(
    part: DocumentObject,
    thickness: float,
    *,
    lowered: bool = False,
    free: DocumentObject | None = None,
) -> FollowPlan | None:
    """Pièces posées sur la face haute de ``part`` (face basse si ``lowered``), prise à
    l'épaisseur ``thickness`` et à son placement actuel ; ``None`` sans assemblage. ``free`` :
    ensemble dont les membres peuvent suivre (liaisons mises de côté)."""
    if not has_joints(part):
        return None
    size = dimensions_of(part)
    dimensions = Dimensions(size.length, size.width, thickness)
    before = PlacedBlock(dimensions, rigid_transform(part.Placement))
    partners = _partners(part, before, lowered)
    fixed = [other for other, raised in partners if not raised]
    moved: list[DocumentObject] = []
    kept: dict[str, list[DocumentObject]] = {}
    for root in (other for other, raised in partners if raised):
        group = attached(root, part)
        reason = _blocker(group, fixed, free)
        if reason is not None:
            kept.setdefault(reason, []).append(root)
        else:
            moved.extend(piece for piece in group if piece not in moved)
    frozen = {reason: tuple(roots) for reason, roots in kept.items()}
    return FollowPlan(part, before, lowered, tuple(moved), frozen)


def follow_thickness(
    part: DocumentObject,
    old: float,
    new: float,
    *,
    lowered: bool = False,
    free: DocumentObject | None = None,
) -> list[str]:
    """Les pièces posées sur la face haute de ``part`` (épaisseur ``old`` avant, ``new`` après)
    suivent la face ; renvoie les messages (vue rapport) : pièces qui ont suivi, pièces laissées
    en place avec la raison. ``lowered`` : l'épaisseur est ajoutée du côté de la face basse
    (ADR 0060) ; ce sont les pièces posées contre elle qui la suivent, ``part`` étant encore à
    son placement d'avant. Sans effet si rien ne change ou si ``part`` n'a pas d'assemblage.
    ``free`` : voir :func:`follow_plan`."""
    plan = follow_plan(part, old, lowered=lowered, free=free) if old != new else None
    if plan is None:
        return []
    plan.apply(new - old)
    return plan.messages(part)


def report_following(part: DocumentObject, old: float, new: float) -> None:
    """:func:`follow_thickness`, messages dans la vue rapport."""
    for message in follow_thickness(part, old, new):
        report_warning(message)
