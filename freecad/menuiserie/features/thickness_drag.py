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
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.core.thickness_side import Extension, flush_extension, other_side_shift
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_entry import write_placement
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint, placed_blank
from freecad.menuiserie.features.joints.plan_cache import cached_plan
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.thickness_choice import SIZE_PROPS, blocker, extend_part

__all__ = [
    "DragFollow",
    "Follows",
    "drag_follow",
    "follow_for",
    "follow_messages",
    "follow_thickness",
    "restore_follows",
    "thickness_note",
]

_PROBE_MM: Final = 5.0
_FOLLOWED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} suit l'épaisseur de {part} : {change} de {delta} pour rester à fleur."
)
_LONGER: Final = QT_TRANSLATE_NOOP("Menuiserie", "allongée")
_SHORTER: Final = QT_TRANSLATE_NOOP("Menuiserie", "raccourcie")
_TOO_SHORT: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} deviendrait trop courte.")
_STOP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Butée : {reason}")


@dataclass(frozen=True)
class _Follower:
    part: DocumentObject
    extension: Extension
    placement: App.Placement
    sizes: tuple[float, float, float]
    reason: str | None  # pourquoi elle ne peut pas suivre, None si elle le peut


def _quoted(part: DocumentObject) -> str:
    return f"« {quoted_value(part.Label)} »"


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
        for joint in (obj for obj in self.part.InList if is_joint(obj)):
            other = joint.GuestPart if joint.HostPart == self.part else joint.HostPart
            if other is None or other == self.part or other.Name in found:
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
                props.append("Placement")
            sizes = (float(other.Length.Value), float(other.Width.Value))
            found[other.Name] = _Follower(
                other,
                extension,
                App.Placement(other.Placement),
                (*sizes, float(other.Thickness.Value)),
                blocker(other, props),
            )
        return list(found.values())

    def restore(self) -> None:
        """Pièces suivies rendues à leur état du début."""
        for follower in self.followers:
            part = follower.part
            with writing(part):
                for prop, value in zip(SIZE_PROPS, follower.sizes, strict=True):
                    if getattr(part, prop).Value != value:
                        setattr(part, prop, value)
            if not part.Placement.isSame(follower.placement, 1e-9):
                write_placement(part, follower.placement)
        self._delta = 0.0

    def follow(self, delta: float) -> str:
        """Écart ``delta`` (mm) de l'épaisseur tirée : les pièces suivent ; renvoie la raison de
        la butée (traduite) si l'une ne le peut pas, rien n'étant alors prolongé."""
        self.restore()
        if delta == 0.0 or not self.followers:
            return ""
        for follower in self.followers:
            reason = follower.reason
            size = follower.sizes[follower.extension.axis] + delta
            if reason is None and size < MIN_DIMENSION_MM:
                reason = translated(_TOO_SHORT, {"label": _quoted(follower.part)})
            if reason is not None:
                return translated(_STOP, {"reason": reason})
        for follower in self.followers:
            extend_part(follower.part, follower.extension, delta)
        self._delta = delta
        return ""

    def note(self) -> str:
        """Texte à montrer près de la souris : « « H » +12 mm »."""
        if self._delta == 0.0:
            return ""
        text = App.Units.Quantity(self._delta, App.Units.Length).UserString
        sign = "+" if self._delta > 0 else ""
        return "\n".join(f"{_quoted(f.part)} {sign}{text}" for f in self.followers)

    def messages(self) -> list[str]:
        """Messages de la vue rapport au relâchement."""
        if self._delta == 0.0:
            return []
        delta = App.Units.Quantity(abs(self._delta), App.Units.Length).UserString
        change = translated(_LONGER if self._delta > 0 else _SHORTER)
        return [
            translated(
                _FOLLOWED,
                {
                    "label": _quoted(f.part),
                    "part": _quoted(self.part),
                    "change": change,
                    "delta": delta,
                },
            )
            for f in self.followers
        ]


def drag_follow(part: DocumentObject, lowered: bool) -> DragFollow | None:
    """Suivi pour une épaisseur tirée de ``part`` ; ``None`` pour un membre d'ensemble (l'ensemble
    relie ses membres) ou une pièce sans assemblage."""
    if furniture_of(part) is not None or not any(is_joint(obj) for obj in part.InList):
        return None
    return DragFollow(part, lowered)


Follows = dict[bool, DragFollow | None]


def follow_for(follows: Follows, part: DocumentObject, lowered: bool) -> DragFollow | None:
    """Suivi de l'épaisseur tirée de ``part``, choisi une fois par glissement et par face, sur la
    pièce encore à son épaisseur du début ; gardé dans ``follows`` (mémento du glissement)."""
    if lowered not in follows:
        follows[lowered] = drag_follow(part, lowered)
    return follows[lowered]


def follow_thickness(
    follows: Follows,
    part: DocumentObject,
    delta: float,
    lowered: bool,
    recompute: Callable[[DocumentObject], None],
) -> str:
    """Pièces à fleur de la face tirée prolongées de ``delta`` mm, aperçu par ``recompute`` ;
    renvoie la raison traduite d'une butée (rien n'est alors prolongé)."""
    for other in follows.values():  # autre face tirée plus tôt : rien ne la suit plus
        if other is not None and other.lowered != lowered:
            other.restore()
    follow = follow_for(follows, part, lowered)
    if follow is None:
        return ""
    try:
        stop = follow.follow(delta)
        for follower in follow.followers:
            recompute(follower.part)
    except Exception:  # jamais de pièce suivie à moitié prolongée
        restore_follows(follows, recompute)
        raise
    return stop


def restore_follows(follows: Follows, recompute: Callable[[DocumentObject], None]) -> None:
    """Échap : pièces suivies rendues à leur état du début, aperçu par ``recompute``."""
    for follow in follows.values():
        if follow is not None:
            follow.restore()
            for follower in follow.followers:
                recompute(follower.part)


def follow_messages(follows: Follows) -> list[str]:
    """Messages de la vue rapport au relâchement : pièces qui ont suivi."""
    return [message for f in follows.values() if f is not None for message in f.messages()]


def thickness_note(follows: Follows) -> str:
    """Pièces qui suivent l'épaisseur tirée et leur écart, à montrer près de la souris."""
    return "\n".join(f.note() for f in follows.values() if f is not None and f.note())
