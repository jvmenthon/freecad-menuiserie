# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce isolée qui défait un de ses assemblages : où ajouter l'écart (ADR 0060).

Le panneau de la pièce ouvre une :class:`ThicknessEdit` à la première épaisseur saisie : elle
garde l'état de départ (placements et cotes des pièces assemblées de proche en proche) et chaque
nouvelle saisie repart de cet état, jamais de la saisie d'avant. Pour une épaisseur donnée,
:meth:`ThicknessEdit.conflict` essaie, sans recalcul du document, l'épaisseur telle que saisie
(face haute déplacée, pièces posées dessus qui suivent : issue #133). Si un assemblage est défait,
il essaie aussi :

- ``OTHER_SIDE`` : l'écart est ajouté du côté de la face basse ; la pièce recule, sa face haute
  ne bouge pas, les pièces posées contre sa face basse la suivent ;
- ``EXTEND`` : l'épaisseur telle que saisie, et chaque autre pièce de l'assemblage défait qui
  arrivait à fleur de la face haute est prolongée de l'écart ;
- ``REVERT`` : l'ancienne épaisseur.

Un choix est proposé s'il ne défait aucun assemblage qui tenait, sinon grisé avec sa raison
(:func:`blocker`). Écritures sous :func:`writing` ; aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM, Dimensions
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.core.thickness_side import (
    Extension,
    flush_extension,
    grows_toward,
    other_side_shift,
)
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    has_expression,
    placement_expression,
)
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_entry import write_placement
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.joints.feasible import plan_error
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.thickness_follow import follow_thickness
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = [
    "Choice",
    "Conflict",
    "Option",
    "ThicknessEdit",
    "UnavailableError",
    "blocker",
    "extend_part",
    "has_joints",
]

SIZE_PROPS: Final = ("Length", "Width", "Thickness")


class Choice(Enum):
    """Où ajouter l'écart d'épaisseur."""

    AS_TYPED = "as_typed"
    OTHER_SIDE = "other_side"
    EXTEND = "extend"
    REVERT = "revert"


_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblée à {partners} ({kind}).")
_ADD: Final = QT_TRANSLATE_NOOP("Menuiserie", "Où ajouter les {delta} ?")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Où retirer les {delta} ?")
_INWARD: Final = QT_TRANSLATE_NOOP("Menuiserie", "Vers l'intérieur")
_OUTWARD: Final = QT_TRANSLATE_NOOP("Menuiserie", "Vers l'extérieur")
_INSIDE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Côté intérieur")
_OUTSIDE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Côté extérieur")
_STAYS_FLUSH: Final = QT_TRANSLATE_NOOP("Menuiserie", "{side} (reste à fleur)")
_LENGTHEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "{side} et allonger {partners} de {delta}")
_SHORTEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "{side} et raccourcir {partners} de {delta}")
_REVERT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Revenir à {thickness}")
_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est une copie : elle suit sa répétition et ne peut pas être modifiée."
)
_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est membre d'un ensemble : ses cotes sont celles de l'ensemble."
)
_SHAPED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} est une pièce en bois : ses cotes sont celles du dessin."
)
_BOUND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : cote ou position pilotée par une expression."
)
_NOT_FLUSH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} n'arrive pas à fleur de la face qui bouge."
)
_TOO_SHORT: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} deviendrait trop courte.")
_STILL_BROKEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Défait encore : {joints}.")


class UnavailableError(ValueError):
    """Choix impossible ; message traduit qui dit pourquoi."""


@dataclass(frozen=True)
class Option:
    """Choix proposé : ``reason`` est ``None`` s'il est possible, sinon pourquoi il ne l'est pas."""

    choice: Choice
    text: str
    reason: str | None = None


@dataclass(frozen=True)
class Conflict:
    """Assemblage défait par l'épaisseur saisie, et choix proposés (``OTHER_SIDE``, ``EXTEND``,
    ``REVERT`` dans cet ordre)."""

    title: str
    question: str
    options: tuple[Option, ...]

    def preferred(self) -> Choice | None:
        """Premier choix possible qui garde l'épaisseur saisie, ``None`` s'il n'y en a pas."""
        for option in self.options:
            if option.reason is None and option.choice is not Choice.REVERT:
                return option.choice
        return None


@dataclass(frozen=True)
class _PartState:
    placement: App.Placement
    sizes: tuple[float, float, float]


def _quoted(parts: Sequence[DocumentObject]) -> str:
    return ", ".join(f"« {quoted_value(part.Label)} »" for part in parts)


def _length(value: float) -> str:
    text: str = App.Units.Quantity(abs(value), App.Units.Length).UserString
    return text


def _joints_of(part: DocumentObject) -> list[DocumentObject]:
    return [obj for obj in part.InList if is_joint(obj)]


def has_joints(part: DocumentObject) -> bool:
    """Vrai si ``part`` porte au moins un assemblage."""
    return bool(_joints_of(part))


def _component(part: DocumentObject) -> list[DocumentObject]:
    """``part`` et les pièces qui lui sont assemblées de proche en proche."""
    found = [part]
    pending = [part]
    while pending:
        current = pending.pop()
        for joint in _joints_of(current):
            for other in (joint.HostPart, joint.GuestPart):
                if other is not None and other not in found:
                    found.append(other)
                    pending.append(other)
    return found


def _broken(parts: Sequence[DocumentObject]) -> dict[str, DocumentObject]:
    """Assemblages de ``parts`` impossibles aux placements et cotes actuels, par nom."""
    joints = {joint.Name: joint for part in parts for joint in _joints_of(part)}
    return {
        name: joint
        for name, joint in joints.items()
        if plan_error(joint, joint.HostPart, joint.GuestPart) is not None
    }


def blocker(part: DocumentObject, props: Sequence[str]) -> str | None:
    """Pourquoi ``part`` ne peut pas voir changer ses propriétés ``props`` (cotes,
    ``Placement``), ``None`` si elle le peut."""
    from freecad.menuiserie.features.repeat import is_copy  # import circulaire sinon

    label = {"label": f"« {quoted_value(part.Label)} »"}
    if is_copy(part):
        return translated(_COPY, label)
    if furniture_of(part) is not None:
        return translated(_MEMBER, label)
    if is_shaped_part(part):
        return translated(_SHAPED, label)
    bound = any(has_expression(part, prop) for prop in props if prop != "Placement")
    if bound or ("Placement" in props and placement_expression(part) is not None):
        return translated(_BOUND, label)
    return None


def _side(adding: bool, inward: bool) -> str:
    """« Vers l'intérieur », « Côté extérieur »… selon le sens de l'écart et le côté."""
    if adding:
        return translated(_INWARD if inward else _OUTWARD)
    return translated(_INSIDE if inward else _OUTSIDE)


def _shift(part: DocumentObject, shift: App.Vector) -> None:
    """Translation de ``part``, arrondie au nm (pas de 1e-15 écrit par une rotation)."""
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
        _shift(part, part.Placement.Rotation.multVec(App.Vector(local.x, local.y, local.z)))


class ThicknessEdit:
    """Suite de saisies d'épaisseur de la pièce isolée ``part`` dans un panneau : état de départ
    gardé, chaque saisie repart de lui."""

    def __init__(self, part: DocumentObject) -> None:
        self.part = part
        self.old = float(part.Thickness.Value)
        self._parts = _component(part)
        self._states = {
            obj.Name: _PartState(
                App.Placement(obj.Placement),
                (float(obj.Length.Value), float(obj.Width.Value), float(obj.Thickness.Value)),
            )
            for obj in self._parts
        }
        self._before = self._block(self.old)
        self._already_broken = set(_broken(self._parts))
        self._broken_as_typed: list[DocumentObject] = []  # lu par EXTEND, écrit par conflict

    def _block(self, thickness: float) -> PlacedBlock:
        size = dimensions_of(self.part)
        dimensions = Dimensions(size.length, size.width, thickness)
        return PlacedBlock(dimensions, rigid_transform(self._states[self.part.Name].placement))

    def _start_block(self, obj: DocumentObject) -> PlacedBlock:
        """Pièce ``obj`` (assemblée de proche en proche) telle qu'au départ."""
        state = self._states[obj.Name]
        return PlacedBlock(Dimensions(*state.sizes), rigid_transform(state.placement))

    def restore(self) -> None:
        """Placements et cotes de départ rendus aux pièces qui en ont changé."""
        for obj in self._parts:
            state = self._states[obj.Name]
            with writing(obj):
                for prop, value in zip(SIZE_PROPS, state.sizes, strict=True):
                    if getattr(obj, prop).Value != value and not has_expression(obj, prop):
                        setattr(obj, prop, value)
            if not obj.Placement.isSame(state.placement, 1e-9):
                write_placement(obj, state.placement)

    def _new_breaks(self) -> list[DocumentObject]:
        return [j for n, j in _broken(self._parts).items() if n not in self._already_broken]

    def _write_thickness(self, value: float) -> None:
        with writing(self.part):
            self.part.Thickness = value

    def apply(self, new: float, choice: Choice) -> list[str]:
        """Repart de l'état de départ et applique l'épaisseur ``new`` selon ``choice`` ; renvoie
        les messages pour la vue rapport. :class:`UnavailableError` (état de départ rendu) si le
        choix est impossible."""
        self.restore()
        if choice is Choice.REVERT or new == self.old:
            return []
        try:
            return self._apply(new, choice)
        except Exception:  # choix impossible ou erreur : jamais de document à moitié écrit
            self.restore()
            raise

    def _apply(self, new: float, choice: Choice) -> list[str]:
        delta = new - self.old
        if choice is Choice.OTHER_SIDE:
            reason = blocker(self.part, ("Placement",))
            if reason is not None:
                raise UnavailableError(reason)
            self._write_thickness(new)
            messages = follow_thickness(self.part, self.old, new, lowered=True)
            shift = other_side_shift(self._before, delta)
            _shift(self.part, App.Vector(shift.x, shift.y, shift.z))
            return messages
        self._write_thickness(new)
        messages = follow_thickness(self.part, self.old, new)
        if choice is Choice.EXTEND:
            self._extend(delta)
        return messages

    def _partners(self, joints: Sequence[DocumentObject]) -> list[DocumentObject]:
        found: list[DocumentObject] = []
        for joint in joints:
            other = joint.GuestPart if joint.HostPart == self.part else joint.HostPart
            if other is not None and other != self.part and other not in found:
                found.append(other)
        return found

    def _extensions(self, delta: float) -> list[tuple[DocumentObject, Extension]]:
        """Pièces à prolonger : les autres pièces des assemblages défaits par l'épaisseur
        telle que saisie, chacune à fleur de la face haute d'avant."""
        found = []
        for other in self._partners(self._broken_as_typed):
            state = self._states[other.Name]
            extension = flush_extension(self._before, self._start_block(other))
            label = {"label": f"« {quoted_value(other.Label)} »"}
            if extension is None:
                raise UnavailableError(translated(_NOT_FLUSH, label))
            props = [SIZE_PROPS[extension.axis]]
            if not extension.at_end:
                props.append("Placement")
            reason = blocker(other, props)
            if reason is not None:
                raise UnavailableError(reason)
            if state.sizes[extension.axis] + delta < MIN_DIMENSION_MM:
                raise UnavailableError(translated(_TOO_SHORT, label))
            found.append((other, extension))
        return found

    def _extend(self, delta: float) -> None:
        for other, extension in self._extensions(delta):
            extend_part(other, extension, delta)

    def conflict(self, new: float) -> Conflict | None:
        """Essaie l'épaisseur ``new`` telle que saisie : ``None`` si elle ne défait aucun
        assemblage (elle reste alors écrite), sinon les choix proposés (l'état de départ est
        alors rendu ; au panneau d'appliquer le choix retenu)."""
        self.apply(new, Choice.AS_TYPED)
        broken = self._new_breaks()
        if not broken:
            return None
        self._broken_as_typed = broken
        try:
            options = (
                self._option(new, Choice.OTHER_SIDE),
                self._option(new, Choice.EXTEND),
                Option(Choice.REVERT, translated(_REVERT, {"thickness": _length(self.old)})),
            )
        finally:
            self.restore()
        return Conflict(self._title(broken), self._question(new), options)

    def _option(self, new: float, choice: Choice) -> Option:
        text = self._text(new, choice)
        try:
            self.apply(new, choice)
        except UnavailableError as error:
            return Option(choice, text, str(error))
        broken = self._new_breaks()
        if broken:
            joints = _quoted(broken)
            return Option(choice, text, translated(_STILL_BROKEN, {"joints": joints}))
        return Option(choice, text)

    def _inward(self) -> bool:
        """Vrai si la face basse est du côté de l'autre pièce du premier assemblage défait."""
        other = self._partners(self._broken_as_typed)[0]
        return grows_toward(self._before, self._start_block(other))

    def _text(self, new: float, choice: Choice) -> str:
        adding = new > self.old
        inward = self._inward()
        if choice is Choice.OTHER_SIDE:
            return translated(_STAYS_FLUSH, {"side": _side(adding, inward)})
        params = {
            "side": _side(adding, not inward),
            "partners": _quoted(self._partners(self._broken_as_typed)),
            "delta": _length(new - self.old),
        }
        return translated(_LENGTHEN if adding else _SHORTEN, params)

    def _title(self, broken: Sequence[DocumentObject]) -> str:
        kinds = []
        for joint in broken:
            kind = translated(joint.Proxy.LABEL)
            kind = kind[:1].lower() + kind[1:]
            if kind not in kinds:
                kinds.append(kind)
        params = {"partners": _quoted(self._partners(broken)), "kind": ", ".join(kinds)}
        return translated(_TITLE, params)

    def _question(self, new: float) -> str:
        template = _ADD if new > self.old else _REMOVE
        return translated(template, {"delta": _length(new - self.old)})
