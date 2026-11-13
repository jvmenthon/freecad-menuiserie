# SPDX-License-Identifier: LGPL-2.1-or-later
"""Machine à états de la session de glissement (SM-c, ADR 0021 ; anneaux : ADR 0025).

:class:`Idle` (rien sous la souris), :class:`Hover` (une flèche, une poignée ou un anneau sous la
souris), :class:`Moving` (flèche tirée), :class:`Resizing` (poignée tirée) et :class:`Rotating`
(anneau tiré). Chaque état répond aux évènements de la souris que lui passe
:class:`~freecad.menuiserie.gui.drag.session.DragSession` (vrai : évènement consommé).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from PySide import QtCore

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import (
    DragResult,
    Guide,
    Handle,
    ResizeResult,
    axis_param,
    magnet,
    resize,
)
from freecad.menuiserie.core.rotation import (
    align_offsets,
    aligned_turn,
    angles_of,
    plane_point,
    ring_angle,
    snapped_turn,
)
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.i18n import report_warning, translate_text
from freecad.menuiserie.features.part_drag import DragCancelledError
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.drag.geometry import (
    HOVER_COLOR,
    REFUSAL_COLOR,
    Label,
    Throttle,
    parse_key,
)
from freecad.menuiserie.gui.drag.parts import Grab, Turn
from freecad.menuiserie.gui.drag.rings import Sweep, advance, ring_basis, ring_key, ring_ray
from freecad.menuiserie.gui.drag.target import Memento, Step, Target
from freecad.menuiserie.gui.drag.view import Point

if TYPE_CHECKING:
    from freecad.menuiserie.gui.drag.session import DragSession

_ALIGNED_TEXT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Alignée sur une pièce voisine")

__all__ = ["Dragging", "Gesture", "Hover", "Idle", "Moving", "Resizing", "Rotating", "State"]


class State:
    """État de la session : réponse (vrai = évènement consommé) à chaque évènement de la souris."""

    dragging = False
    key: str | None = None
    sweep: Sweep | None = None  # secteur parcouru et angle, pendant la rotation par un anneau
    ghost: Vec3 | None = None  # décalage du fantôme (repère de la pièce), pendant une copie
    note: Label | None = None  # cote tirée et message d'un refus, près de la souris (ensemble)

    def press(self, session: DragSession, point: Point, shift: bool, copy: bool = False) -> bool:
        """Clic gauche enfoncé (``copy`` : Ctrl enfoncé)."""
        del session, point, shift, copy
        return False

    def move(self, session: DragSession, point: Point, shift: bool) -> bool:
        """Souris déplacée."""
        del session, point, shift
        return False

    def release(self, session: DragSession, point: Point) -> bool:
        """Clic gauche relâché."""
        del session, point
        return False

    def escape(self, session: DragSession) -> bool:
        """Échap."""
        del session
        return False

    def shift_changed(self, session: DragSession, shift: bool) -> None:
        """Maj enfoncée ou relâchée."""


class Idle(State):
    """Rien sous la souris : les évènements sont rendus à FreeCAD (sauf après un Échap, jusqu'au
    relâchement du bouton)."""

    def press(self, session: DragSession, point: Point, shift: bool, copy: bool = False) -> bool:
        session.sync()
        key = session.target_at(point)
        if key is None:
            return False
        return session.begin_copy(key, point, shift) if copy else session.begin(key, point, shift)

    def move(self, session: DragSession, point: Point, shift: bool) -> bool:
        if session.swallow_release:
            return True
        session.sync()
        key = session.target_at(point)
        if key != self.key:
            session.enter(Hover(key) if key else Idle())
        return False

    def release(self, session: DragSession, point: Point) -> bool:
        del point
        consumed, session.swallow_release = session.swallow_release, False
        return consumed


class Hover(Idle):
    """Une flèche ou une poignée (``key``) est sous la souris : surbrillance."""

    def __init__(self, key: str) -> None:
        self.key = key


class Gesture(State):
    """Geste en cours (flèche, poignée ou anneau tiré ; Template Method : les sous-classes écrivent
    la pièce). Tous les évènements sont consommés jusqu'au relâchement ou à Échap."""

    dragging = True

    def __init__(self, memento: Memento, start: Point, own: bool, target: Target) -> None:
        self.memento = memento
        self.target = target
        self.cursor = start
        self.own = own  # transaction ouverte par le geste
        self.shift = False

    def move(self, session: DragSession, point: Point, shift: bool) -> bool:
        self.cursor, self.shift = point, shift
        self._follow(session)
        return True

    def shift_changed(self, session: DragSession, shift: bool) -> None:
        self.shift = shift
        self._follow(session)

    def release(self, session: DragSession, point: Point) -> bool:
        self.cursor = point
        self._follow(session)
        self.flush(session)
        self._finish(session)
        return True

    def escape(self, session: DragSession) -> bool:
        """Échap : la pièce revient où elle était au début du geste (le panneau, s'il est ouvert,
        reste) ; le relâchement du bouton est consommé."""
        self.target.restore(self.memento)
        if self.own:
            self.target.document.abortTransaction()
        session.swallow_release = True
        session.leave()
        return True

    def _finish(self, session: DragSession) -> None:
        """Relâchement : ensemble relié et document recalculé une fois (``end_drag``),
        avertissements dans la vue rapport. Si le déplacement défait des assemblages, la fenêtre
        de choix s'ouvre avant le recalcul (``gui/joint_choice``, ADR 0026) : annuler remet la
        pièce, supprimer garde le déplacement."""
        try:
            warnings = self.end(joint_choice.choose)
        except DragCancelledError:  # assemblages défaits, « Annuler le déplacement » (ADR 0026)
            self._close(session, commit=False)
            return
        except ValueError as error:
            report_warning(str(error))
            self._close(session, commit=False)
            return
        for warning in warnings:
            report_warning(warning)
        self._close(session, commit=True)

    def _close(self, session: DragSession, *, commit: bool) -> None:
        """Fin du geste : transaction validée (``commit``) ou abandonnée."""
        document = self.target.document
        if self.own:
            if commit:
                document.commitTransaction()
            else:
                document.abortTransaction()
        session.leave()

    def _follow(self, session: DragSession) -> None:
        """Pièce placée d'après le curseur."""
        raise NotImplementedError

    def flush(self, session: DragSession) -> None:
        """Écrit ce qui attendait la cadence (poignée)."""

    def end(self, choose: JointChoice) -> list[str]:
        """Fin du geste au relâchement : recalcul du document, avertissements."""
        return self.target.end_move(self.memento, choose)


class Dragging(Gesture):
    """Flèche ou poignée tirée."""

    def __init__(self, grab: Grab) -> None:
        super().__init__(grab.memento, grab.start, grab.own, grab.target)
        self.key = self.grabbed = grab.key
        self.line = grab.line  # axe au début : les flèches suivent la pièce, pas lui
        self.origin = grab.origin  # paramètre de l'axe sous le curseur au début
        self.guides = grab.guides
        self.tolerance = grab.tolerance
        self.box = grab.target.box()
        # repère de la pièce au début : celui des guides, qui ne suivent pas la pièce
        self.frame = grab.target.frame()

    def _follow(self, session: DragSession) -> None:
        """Pièce placée d'après le curseur ; rayon parallèle à l'axe : elle reste."""
        value = axis_param(session.ray(self.cursor), self.line)
        if value is not None:
            self.apply(session, value - self.origin)

    def apply(self, session: DragSession, delta: float) -> None:
        """Écrit la pièce pour un déplacement ``delta`` mm du curseur le long de l'axe."""
        raise NotImplementedError


class Moving(Dragging):
    """Flèche tirée : la pièce suit la souris le long de l'axe, aimantée sauf Maj."""

    def solve(self, axis: int, delta: float) -> DragResult:
        """Déplacement voulu de ``delta`` mm sur l'axe ``axis``, aimanté sauf Maj."""
        wanted = Vec3(0.0, 0.0, 0.0).with_component(axis, delta)
        if self.shift:
            return DragResult(wanted)
        return magnet(self.box, self.guides, wanted, self.tolerance, [axis])

    def apply(self, session: DragSession, delta: float) -> None:
        axis = parse_key(self.grabbed)
        if not isinstance(axis, int):  # clé d'une poignée : rien à faire ici
            return
        result = self.solve(axis, delta)
        self.target.move(self.memento, result.delta)
        session.written([self.guides[hit.guide] for hit in result.hits], self.frame)


@dataclass(frozen=True)
class _Pending:
    """Cote à écrire à la prochaine application de la cadence : poignée, cote obtenue, guide
    aimanté et point de l'axe sous la souris (où la cote s'écrit)."""

    handle: Handle
    result: ResizeResult
    hit: list[Guide]
    anchor: Vec3


class Resizing(Dragging):
    """Poignée tirée : la cote suit, l'autre bout ne bouge pas ; brute recalculée 30 fois par
    seconde au plus (10 pour un ensemble, dont la cote est écrite près de la souris)."""

    def __init__(self, grab: Grab) -> None:
        super().__init__(grab)
        self.throttle = Throttle(grab.target.resize_rate)
        self.pending: _Pending | None = None
        self.scheduled = False

    def apply(self, session: DragSession, delta: float) -> None:
        handle = parse_key(self.grabbed)
        if not isinstance(handle, Handle):  # clé d'une flèche : rien à faire ici
            return
        guides = () if self.shift else self.guides
        result = resize(self.box, handle, delta, guides, self.tolerance, self.target.min_size)
        hit = [] if result.hit is None else [self.guides[result.hit.guide]]
        anchor = self.line.origin + self.line.direction.scaled(self.origin + delta)
        self.pending = _Pending(handle, result, hit, anchor)
        now = time.monotonic()
        if self.throttle.ready(now):
            self.flush(session)
        elif not self.scheduled:
            self.scheduled = True
            wait = round(self.throttle.wait(now) * 1000) + 1
            QtCore.QTimer.singleShot(wait, lambda: self._later(session))

    def _later(self, session: DragSession) -> None:
        self.scheduled = False
        if session.state is self:
            self.flush(session)

    def flush(self, session: DragSession) -> None:
        pending, self.pending = self.pending, None
        if pending is None:
            return
        step = self.target.resize(self.memento, pending.handle, pending.result)
        if self.target.shows_size:
            self.note = _size_note(step, pending.anchor)
        session.written([] if step.message else pending.hit, self.frame)


def _size_note(step: Step, anchor: Vec3) -> Label:
    """Cote écrite (puis, si le pas est arrêté, le message du refus) près de la souris."""
    text = f"{step.size:.1f} mm"
    if not step.message:
        return Label(HOVER_COLOR, text, anchor)
    return Label(REFUSAL_COLOR, f"{text}\n{step.message}", anchor)


class Rotating(Gesture):
    """Anneau tiré : la pièce tourne autour de l'axe de l'anneau, par son centre, depuis son
    orientation du début (RO-b, ``rotate_by``). L'angle **obtenu** (et non le seul angle parcouru)
    est aimanté tous les 15° (libre avec Maj, au dixième de degré) ; l'angle parcouru s'ajoute
    d'un demi-tour à l'autre (plusieurs tours possibles). Seul le ``Placement`` est écrit, sans
    recalcul."""

    def __init__(self, grab: Turn) -> None:
        super().__init__(grab.memento, grab.start, grab.own, grab.target)
        self.ring = grab.ring
        self.key = ring_key(grab.ring.axis)
        self.first = grab.first
        self.from_center = grab.from_center
        self.last = 0.0  # angle lu au dernier mouvement (]-180, 180])
        self.total = 0.0  # angle parcouru depuis la saisie, tours compris
        # angle de la pièce autour de l'anneau au début : l'aimant vise l'angle obtenu
        self.base = angles_of(rigid_transform(grab.memento.placement).rotation)[self.ring.axis]
        self.frame = grab.target.frame()
        u, v = ring_basis(self.ring.normal)
        # rotations qui alignent une arête de la pièce sur celle d'une voisine (à 90° près)
        self.offsets = align_offsets(
            self.frame.to_transform().rotation, grab.target.neighbor_rotations(), u, v
        )

    def _follow(self, session: DragSession) -> None:
        """Pièce tournée d'après le curseur ; rayon rasant le plan de l'anneau : elle reste."""
        ray = ring_ray(session.ray(self.cursor), self.ring)
        raw = ring_angle(ray, self.ring, self.first)
        if raw is not None:
            self.total, self.last = advance(self.total, self.last, raw), raw
        aligned = None if self.shift else aligned_turn(self.total, self.offsets)
        angle = (
            aligned if aligned is not None else snapped_turn(self.base, self.total, free=self.shift)
        )
        if not self.target.rotate(self.memento, self.ring.axis, angle):
            self.note = None
            return
        anchor = plane_point(ray, self.ring) or self.ring.center
        self.sweep = Sweep(self.ring, self.from_center, angle, anchor)
        self.note = (
            None if aligned is None else Label(HOVER_COLOR, translate_text(_ALIGNED_TEXT), anchor)
        )
        session.written((), self.frame)

    def end(self, choose: JointChoice) -> list[str]:
        return self.target.end_rotation(self.memento, choose)
