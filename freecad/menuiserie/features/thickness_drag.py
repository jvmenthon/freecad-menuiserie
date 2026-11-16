# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur tirée à la souris : l'autre pièce d'un assemblage suit la face (ADR 0060, souris B).

La poignée tirée dit le côté : celle de la face haute la déplace, celle de la face basse (poignée
de début) aussi, de l'autre côté. Une pièce assemblée qui arrivait **à fleur** de cette face, et
dont l'assemblage serait défait par une face qui bouge (queue d'aronde, par exemple), est
prolongée en direct du même écart. Si elle ne peut pas l'être (copie de répétition, membre d'un
ensemble, pièce en bois, cote ou position pilotée par une expression), la poignée s'arrête à
l'épaisseur du début (butée) et la raison s'affiche près de la souris.

Les pièces à suivre sont choisies une fois au début, par un essai sans écriture (plan de
l'assemblage avec une épaisseur de :data:`_PROBE_MM` de plus) : un écart minuscule au premier pas
ne suffit pas à défaire un assemblage. Chaque pas repart de l'état du début (Memento) : rien ne
s'accumule. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM, Dimensions
from freecad.menuiserie.core.thickness_side import Extension, flush_extension, other_side_shift
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.furniture_entry import write_placement
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import placed_blank
from freecad.menuiserie.features.joints.plan_cache import cached_plan
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.thickness_common import (
    PLACEMENT,
    SIZE_PROPS,
    TOO_SHORT,
    blocker,
    extend_part,
    has_joints,
    joints_of,
    length_text,
    other_part,
    quoted,
    restore_state,
    shift_part,
    size_state,
)
from freecad.menuiserie.features.thickness_follow import follow_plan

__all__ = ["DragFollow", "FaceFollows", "drag_follow"]

_PROBE_MM: Final = 5.0
_FOLLOWED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} suit l'épaisseur de {part} : {change} de {delta} pour rester à fleur."
)
_LONGER: Final = QT_TRANSLATE_NOOP("Menuiserie", "allongée")
_SHORTER: Final = QT_TRANSLATE_NOOP("Menuiserie", "raccourcie")
_STOP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Butée : {reason}")

Recompute = Callable[[DocumentObject], None]


@dataclass(frozen=True)
class _Follower:
    part: DocumentObject
    extension: Extension
    placement: App.Placement
    sizes: tuple[float, float, float]
    reason: str | None  # pourquoi elle ne peut pas suivre, None si elle le peut


def _fails(joint: DocumentObject, blocks: dict[str, PlacedBlock]) -> bool:
    """Vrai si ``joint`` est impossible avec les pièces ``blocks`` (par nom), sans écriture."""
    proxy = joint.Proxy
    try:
        with translated_errors():
            strategy = strategy_for(proxy.KIND)
            host = blocks.get(joint.HostPart.Name)
            if host is None:
                host = placed_blank(joint.HostPart, proxy.KIND is JointKind.FOOT)
            guest = blocks.get(joint.GuestPart.Name) or placed_blank(joint.GuestPart)
            cached_plan(strategy, host, guest, proxy.params(joint))
    except ValueError:
        return True
    return False


class DragFollow:
    """Pièces qui suivent la face tirée de ``part`` (``lowered`` : sa face basse)."""

    def __init__(self, part: DocumentObject, lowered: bool) -> None:
        self.part = part
        self.lowered = lowered
        self.old = float(part.Thickness.Value)
        self._before = placed_blank(part)
        self._delta = 0.0
        self.followers = self._find()
        names = {follower.part.Name for follower in self.followers}
        plan = follow_plan(part, self.old, lowered=lowered)  # posées sur la face (#133)
        self._plan = plan
        self._resting = {  # placement du début des pièces qui suivent la face sans s'allonger
            piece.Name: (piece, App.Placement(piece.Placement))
            for piece in (plan.moved if plan is not None else ())
            if piece.Name not in names
        }

    def _probe(self) -> PlacedBlock:
        """``part`` épaissie de :data:`_PROBE_MM` du côté de la face tirée."""
        size = self._before.dimensions
        thicker = Dimensions(size.length, size.width, size.thickness + _PROBE_MM)
        placement = self._before.placement
        if self.lowered:
            shift = other_side_shift(self._before, _PROBE_MM)
            moved = App.Placement(self.part.Placement)
            moved.Base = moved.Base + App.Vector(shift.x, shift.y, shift.z)
            placement = rigid_transform(moved)
        return PlacedBlock(thicker, placement)

    def _find(self) -> list[_Follower]:
        probe = self._probe()
        found: dict[str, _Follower] = {}
        for joint in joints_of(self.part):
            other = other_part(joint, self.part)
            if other is None or other.Name in found:
                continue
            try:
                block = placed_blank(other)
            except ValueError:
                continue
            extension = flush_extension(self._before, block, lowered=self.lowered)
            now = {self.part.Name: self._before}
            if extension is None or _fails(joint, now):
                continue
            if not _fails(joint, {self.part.Name: probe}):
                continue  # une face qui bouge ne défait pas cet assemblage
            props = [SIZE_PROPS[extension.axis]]
            if not extension.at_end:
                props.append(PLACEMENT)
            found[other.Name] = _Follower(
                other,
                extension,
                App.Placement(other.Placement),
                size_state(other),
                blocker(other, props),
            )
        return list(found.values())

    def restore(self) -> None:
        """Pièces suivies rendues à leur état du début."""
        for follower in self.followers:
            restore_state(follower.part, follower.sizes, follower.placement)
        for piece, placement in self._resting.values():
            if not piece.Placement.isSame(placement, 1e-9):
                write_placement(piece, placement)
        self._delta = 0.0

    @property
    def parts(self) -> list[DocumentObject]:
        """Pièces que le suivi écrit : prolongées ou déplacées (à recalculer pour l'aperçu)."""
        return [f.part for f in self.followers] + [p for p, _ in self._resting.values()]

    def follow(self, delta: float) -> str:
        """Écart ``delta`` (mm) de l'épaisseur tirée : les pièces suivent ; renvoie la raison de
        la butée (traduite) si l'une ne le peut pas, rien n'étant alors prolongé."""
        self.restore()
        if delta == 0.0 or not self.parts:
            return ""
        for follower in self.followers:
            reason = follower.reason
            size = follower.sizes[follower.extension.axis] + delta
            if reason is None and size < MIN_DIMENSION_MM:
                reason = translated(TOO_SHORT, {"label": quoted(follower.part)})
            if reason is not None:
                return translated(_STOP, {"reason": reason})
        for follower in self.followers:
            extend_part(follower.part, follower.extension, delta)
        if self._resting and self._plan is not None:  # posées sur la face : elles la suivent
            shift = self._plan.shift(delta)
            for piece, _ in self._resting.values():
                shift_part(piece, shift)
        self._delta = delta
        return ""

    def note(self) -> str:
        """Texte à montrer près de la souris : « « H » +12 mm »."""
        if self._delta == 0.0:
            return ""
        sign = "+" if self._delta > 0 else "-"
        text = length_text(self._delta)
        return "\n".join(f"{quoted(f.part)} {sign}{text}" for f in self.followers)

    def messages(self) -> list[str]:
        """Messages de la vue rapport au relâchement."""
        if self._delta == 0.0:
            return []
        delta = length_text(self._delta)
        change = translated(_LONGER if self._delta > 0 else _SHORTER)
        resting = self._plan.messages(self.part) if self._plan is not None else []
        return resting + [
            translated(
                _FOLLOWED,
                {
                    "label": quoted(f.part),
                    "part": quoted(self.part),
                    "change": change,
                    "delta": delta,
                },
            )
            for f in self.followers
        ]


def drag_follow(part: DocumentObject, lowered: bool) -> DragFollow | None:
    """Suivi pour une épaisseur tirée de ``part`` ; ``None`` pour un membre d'ensemble (l'ensemble
    relie ses membres) ou une pièce sans assemblage."""
    if furniture_of(part) is not None or not has_joints(part):
        return None
    return DragFollow(part, lowered)


class FaceFollows:
    """Suivis d'un glissement (mémento), un par face tirée : choisis une fois, sur la pièce
    encore à son épaisseur du début."""

    def __init__(self) -> None:
        self._by_face: dict[bool, DragFollow | None] = {}

    def _all(self) -> list[DragFollow]:
        return [follow for follow in self._by_face.values() if follow is not None]

    def prepare(self, part: DocumentObject, lowered: bool) -> DragFollow | None:
        """Suivi de la face tirée de ``part`` (``lowered`` : face basse), créé au premier appel :
        à faire avant d'écrire l'épaisseur."""
        if lowered not in self._by_face:
            self._by_face[lowered] = drag_follow(part, lowered)
        return self._by_face[lowered]

    def follow_dragged_face(
        self, part: DocumentObject, delta: float, lowered: bool, recompute: Recompute
    ) -> str:
        """Pièces à fleur de la face tirée prolongées de ``delta`` mm, aperçu par ``recompute`` ;
        renvoie la raison traduite d'une butée (rien n'est alors prolongé)."""
        for other in self._all():  # autre face tirée plus tôt : rien ne la suit plus
            if other.lowered != lowered:
                other.restore()
        follow = self.prepare(part, lowered)
        if follow is None:
            return ""
        try:
            stop = follow.follow(delta)
            for piece in follow.parts:
                recompute(piece)
        except Exception:  # jamais de pièce suivie à moitié prolongée
            self.restore(recompute)
            raise
        return stop

    def restore(self, recompute: Recompute) -> None:
        """Échap : pièces suivies rendues à leur état du début, aperçu par ``recompute``."""
        for follow in self._all():
            follow.restore()
            for piece in follow.parts:
                recompute(piece)

    def parts(self) -> list[DocumentObject]:
        """Pièces que les suivis écrivent (aperçu)."""
        return [piece for follow in self._all() for piece in follow.parts]

    def messages(self) -> list[str]:
        """Messages de la vue rapport au relâchement : pièces qui ont suivi."""
        return [message for follow in self._all() for message in follow.messages()]

    def note(self) -> str:
        """Pièces qui suivent l'épaisseur tirée et leur écart, à montrer près de la souris."""
        return "\n".join(note for follow in self._all() if (note := follow.note()))
