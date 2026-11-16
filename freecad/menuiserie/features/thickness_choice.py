# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce isolée qui défait un de ses assemblages : où ajouter l'écart (ADR 0060).

Le panneau de la pièce ouvre une :class:`ThicknessEdit` à la première épaisseur saisie : elle
garde l'état de départ (placements et cotes des pièces assemblées de proche en proche) et chaque
nouvelle saisie repart de cet état, jamais de la saisie d'avant. Pour une épaisseur donnée,
:meth:`ThicknessEdit.probe` essaie, sans recalcul du document, l'épaisseur telle que saisie
(face haute déplacée, pièces posées dessus qui suivent : issue #133). Si un assemblage est défait,
il essaie aussi :

- ``OTHER_SIDE`` : l'écart est ajouté du côté de la face basse ; la pièce recule, sa face haute
  ne bouge pas, les pièces posées contre sa face basse la suivent ;
- ``EXTEND`` : l'épaisseur telle que saisie, et chaque autre pièce de l'assemblage défait qui
  arrivait à fleur de la face haute est prolongée de l'écart ;
- ``REVERT`` : l'ancienne épaisseur.

Un choix est proposé s'il ne défait aucun assemblage qui tenait, sinon grisé avec sa raison
(:func:`~freecad.menuiserie.features.thickness_common.blocker`). Écritures sous :func:`writing` ;
aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

import FreeCAD as App

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM, Dimensions
from freecad.menuiserie.core.thickness_side import (
    Extension,
    flush_extension,
    grows_toward,
    other_side_shift,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import writing
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.feasible import plan_error
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.thickness_common import (
    PLACEMENT,
    SIZE_PROPS,
    TOO_SHORT,
    attached,
    blocker,
    extend_part,
    joints_of,
    other_part,
    quoted,
    restore_state,
    shift_part,
    size_state,
)
from freecad.menuiserie.features.thickness_follow import follow_thickness
from freecad.menuiserie.features.thickness_texts import (
    extend_text,
    keep_text,
    not_flush_text,
    other_side_text,
    question_text,
    revert_text,
    still_broken_text,
    title_text,
)
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = [
    "Choice",
    "Conflict",
    "Option",
    "ThicknessEdit",
    "UnavailableError",
]


class Choice(Enum):
    """Où ajouter l'écart d'épaisseur."""

    AS_TYPED = "as_typed"
    OTHER_SIDE = "other_side"
    EXTEND = "extend"
    REVERT = "revert"


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
    """Assemblages de la pièce dont l'épaisseur change, et choix proposés (``AS_TYPED`` si rien
    n'est défait, puis ``OTHER_SIDE``, ``EXTEND``, ``REVERT`` dans cet ordre)."""

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


def _broken(parts: Sequence[DocumentObject]) -> dict[str, DocumentObject]:
    """Assemblages de ``parts`` impossibles aux placements et cotes actuels, par nom."""
    joints = {joint.Name: joint for part in parts for joint in joints_of(part)}
    return {
        name: joint
        for name, joint in joints.items()
        if plan_error(joint, joint.HostPart, joint.GuestPart) is not None
    }


class ThicknessEdit:
    """Suite de saisies d'épaisseur de la pièce isolée ``part`` dans un panneau : état de départ
    gardé, chaque saisie repart de lui."""

    def __init__(self, part: DocumentObject) -> None:
        self.part = part
        self.old = float(part.Thickness.Value)
        self._parts = attached(part)
        self._states = {
            obj.Name: _PartState(App.Placement(obj.Placement), size_state(obj))
            for obj in self._parts
        }
        self._before = self._block(self.old)
        self._already_broken = set(_broken(self._parts))
        self._concerned: list[DocumentObject] = []  # assemblages en cause, écrits par probe
        self.messages: list[str] = []  # vue rapport : saisie écrite telle quelle par probe

    @property
    def parts(self) -> list[DocumentObject]:
        """La pièce et les pièces qui lui sont assemblées de proche en proche (celles qu'un choix
        peut écrire)."""
        return list(self._parts)

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
            restore_state(obj, state.sizes, state.placement)

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
            reason = blocker(self.part, (PLACEMENT,))
            if reason is not None:
                raise UnavailableError(reason)
            self._write_thickness(new)
            messages = follow_thickness(self.part, self.old, new, lowered=True)
            shift = other_side_shift(self._before, delta)
            shift_part(self.part, App.Vector(shift.x, shift.y, shift.z))
            return messages
        self._write_thickness(new)
        messages = follow_thickness(self.part, self.old, new)
        if choice is Choice.EXTEND:
            self._extend(delta)
        return messages

    def _partners(self, joints: Sequence[DocumentObject]) -> list[DocumentObject]:
        found: list[DocumentObject] = []
        for joint in joints:
            other = other_part(joint, self.part)
            if other is not None and other not in found:
                found.append(other)
        return found

    def _extensions(self, delta: float) -> list[tuple[DocumentObject, Extension]]:
        """Pièces à prolonger : les autres pièces des assemblages défaits par l'épaisseur
        telle que saisie, chacune à fleur de la face haute d'avant."""
        found = []
        for other in self._partners(self._concerned):
            state = self._states[other.Name]
            extension = flush_extension(self._before, self._start_block(other))
            if extension is None:
                raise UnavailableError(not_flush_text(other))
            props = [SIZE_PROPS[extension.axis]]
            if not extension.at_end:
                props.append(PLACEMENT)
            reason = blocker(other, props)
            if reason is not None:
                raise UnavailableError(reason)
            if state.sizes[extension.axis] + delta < MIN_DIMENSION_MM:
                raise UnavailableError(translated(TOO_SHORT, {"label": quoted(other)}))
            found.append((other, extension))
        return found

    def _extend(self, delta: float) -> None:
        for other, extension in self._extensions(delta):
            extend_part(other, extension, delta)

    def probe(self, new: float) -> Conflict | None:
        """Essaie l'épaisseur ``new`` telle que saisie et renvoie les choix proposés (l'état de
        départ est alors rendu ; au panneau d'appliquer le choix retenu). Si elle ne défait aucun
        assemblage, « Laisser en l'état » (``AS_TYPED``) vient en tête (jv, 2026-11-15) et les
        autres choix portent sur tous les assemblages de la pièce. ``None`` (saisie écrite telle
        quelle, messages dans :attr:`messages`) pour l'épaisseur de départ ou une pièce sans
        assemblage."""
        self.messages = self.apply(new, Choice.AS_TYPED)
        try:
            joints = joints_of(self.part)
            broken = self._new_breaks() if joints and new != self.old else []
        except Exception:  # jamais de saisie à moitié essayée laissée écrite
            self.restore()
            raise
        if new == self.old or not joints:
            return None
        self._concerned = broken or joints
        if not self._partners(self._concerned):  # autre pièce disparue : rien à proposer
            if broken:
                self.restore()
                raise UnavailableError(still_broken_text(broken))
            return None
        try:
            options = self._options(new, keep=not broken)
        finally:
            self.restore()
        title = title_text(self._concerned, self._partners(self._concerned))
        return Conflict(title, question_text(self.old, new), options)

    def _options(self, new: float, *, keep: bool) -> tuple[Option, ...]:
        """Choix proposés pour ``new`` (chacun essayé puis défait) ; « Laisser en l'état » en
        tête si ``keep``."""
        kept = (Option(Choice.AS_TYPED, keep_text()),) if keep else ()
        return (
            *kept,
            self._option(new, Choice.OTHER_SIDE),
            self._option(new, Choice.EXTEND),
            Option(Choice.REVERT, revert_text(self.old)),
        )

    def _option(self, new: float, choice: Choice) -> Option:
        text = self._text(new, choice)
        try:
            self.apply(new, choice)
        except UnavailableError as error:
            return Option(choice, text, str(error))
        broken = self._new_breaks()
        if broken:
            return Option(choice, text, still_broken_text(broken))
        return Option(choice, text)

    def _text(self, new: float, choice: Choice) -> str:
        """Texte du choix ; « intérieur » : le côté de l'autre pièce du premier assemblage défait
        (face basse pour ``OTHER_SIDE``, face haute pour ``EXTEND``)."""
        adding = new > self.old
        partners = self._partners(self._concerned)
        lower_inward = grows_toward(self._before, self._start_block(partners[0]))
        if choice is Choice.OTHER_SIDE:
            return other_side_text(adding, lower_inward)
        return extend_text(adding, not lower_inward, partners, new - self.old)
