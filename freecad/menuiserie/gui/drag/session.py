# SPDX-License-Identifier: LGPL-2.1-or-later
"""Session de glissement d'une pièce dans la vue 3D (SM-c, ADR 0021, spécification § 4.3 ; anneaux
de rotation : RO-d, ADR 0025).

:class:`DragSession` (pattern State) garde la pièce qui porte les flèches et les anneaux, leur
dessin et l'état courant : :class:`Idle` (rien sous la souris), :class:`Hover` (une flèche, une
poignée ou un anneau sous la souris), :class:`Moving` (flèche tirée), :class:`Resizing` (poignée
tirée) et :class:`Rotating` (anneau tiré : la pièce tourne autour de son centre). Les évènements
de la souris arrivent en pixels de FreeCAD par :meth:`DragSession.press`,
:meth:`~DragSession.move`, :meth:`~DragSession.release` et :meth:`~DragSession.escape`
(``events.py`` les traduit depuis Qt) ; chaque méthode renvoie vrai si l'évènement est consommé.

Hors panneau, un glissement ouvre sa transaction « Déplacer la pièce » (« Tourner la pièce » pour
un anneau ; un Ctrl+Z) ; panneau ouvert, ou si une autre transaction est en cours, il écrit dans
la transaction déjà ouverte. Aucun recalcul pendant le glissement d'une flèche ou d'un anneau ;
une poignée recalcule la seule brute, au plus 30 fois par seconde ; ``end_drag`` (``end_rotation``
pour un anneau) fait le recalcul du document au relâchement, après avoir proposé (fenêtre de
``gui/joint_choice``) d'annuler le geste ou de supprimer les assemblages qu'il défait (ADR 0026).
Une pièce dont une expression pilote le ``Placement`` (membre d'ensemble, formule) ne porte pas
d'anneau (D6).
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import (
    DragResult,
    Guide,
    Handle,
    Ray,
    axis_param,
    handle_at,
    magnet,
    resize,
)
from freecad.menuiserie.core.rotation import Ring, plane_point, ring_angle, snapped_angle
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.magnet_guides import collect_guides
from freecad.menuiserie.features.part_drag import (
    SIZE_PROPS,
    DragCancelledError,
    DragMemento,
    begin_drag,
    drag_limits,
    end_drag,
    move_part,
    raw_part,
    resize_part,
    restore,
)
from freecad.menuiserie.features.part_rotate import end_rotation, rotate_by
from freecad.menuiserie.features.snap_geometry import to_vec3
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.drag.geometry import (
    ARROW_PX,
    MAGNET_PX,
    Layout,
    Throttle,
    build_drawing,
    build_layout,
    parse_key,
    pixel_targets,
    target_line,
)
from freecad.menuiserie.gui.drag.overlay import Overlay
from freecad.menuiserie.gui.drag.rings import (
    Sweep,
    advance,
    build_rings,
    ring_axis,
    ring_key,
    ring_ray,
    ring_under,
)
from freecad.menuiserie.gui.drag.view import ViewPort

__all__ = [
    "DragSession",
    "Dragging",
    "Gesture",
    "Hover",
    "Idle",
    "Moving",
    "PanelContext",
    "Resizing",
    "Rotating",
    "State",
    "Turn",
]

MOVE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déplacer la pièce")
ROTATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tourner la pièce")
_RESIZE_ERRORS: Final = (RuntimeError, ValueError, TypeError, AttributeError, ReferenceError)
Point = tuple[float, float]


@dataclass(frozen=True)
class PanelContext:
    """Panneau de tâche de la pièce ``part`` : ``refresh`` relit ses champs, ``is_open`` dit s'il
    est encore ouvert. Aucun widget n'est gardé ici."""

    part: DocumentObject
    refresh: Callable[[], None]
    is_open: Callable[[], bool]


def _frame_of(placement: App.Placement) -> Frame:
    rotation = placement.Rotation
    axes = [to_vec3(rotation.multVec(App.Vector(*v))) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    return Frame(to_vec3(placement.Base), *axes)


def _rings_of(part: DocumentObject, box: Box) -> tuple[Ring, ...]:
    """Anneaux de rotation de la brute ``part`` ; aucun si une expression pilote son ``Placement``
    (membre d'ensemble, formule : D6). Ils suivent les axes de son conteneur (B5)."""
    if placement_expression(part) is not None:
        return ()
    container = part.getGlobalPlacement() * part.Placement.inverse()
    return build_rings(box, rigid_transform(part.Placement), rigid_transform(container))


def _box_of(part: DocumentObject) -> Box:
    return Box(
        Vec3(0.0, 0.0, 0.0),
        Vec3(part.Length.Value, part.Width.Value, part.Thickness.Value),
    )


@dataclass(frozen=True)
class Grab:
    """Ce qu'il faut pour tirer une cible : clé de la flèche ou de la poignée, pixel de départ,
    paramètre de l'axe sous le curseur, début de l'écriture (Memento), guides, tolérance de
    l'aimant (mm) et transaction ouverte par le glissement (``own``)."""

    key: str
    start: Point
    line: Ray
    origin: float
    memento: DragMemento
    guides: tuple[Guide, ...]
    tolerance: float
    own: bool


@dataclass(frozen=True)
class Turn:
    """Ce qu'il faut pour tourner une pièce par un anneau : l'anneau (axe, centre, rayon), le rayon
    de la souris au départ (reculé devant le plan de l'anneau), le vecteur du centre au point
    saisi, pixel de départ, début de l'écriture (Memento) et transaction ouverte (``own``)."""

    ring: Ring
    first: Ray
    from_center: Vec3
    start: Point
    memento: DragMemento
    own: bool


class State:
    """État de la session : réponse (vrai = évènement consommé) à chaque évènement de la souris."""

    dragging = False
    key: str | None = None
    sweep: Sweep | None = None  # secteur parcouru et angle, pendant la rotation par un anneau

    def press(self, session: DragSession, point: Point, shift: bool) -> bool:
        """Clic gauche enfoncé."""
        del session, point, shift
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

    def press(self, session: DragSession, point: Point, shift: bool) -> bool:
        session.sync()
        key = session.target_at(point)
        return key is not None and session.begin(key, point, shift)

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

    def __init__(self, memento: DragMemento, start: Point, own: bool) -> None:
        self.memento = memento
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
        session.finish(self)
        return True

    def escape(self, session: DragSession) -> bool:
        session.cancel(self)
        return True

    def _follow(self, session: DragSession) -> None:
        """Pièce placée d'après le curseur."""
        raise NotImplementedError

    def flush(self, session: DragSession) -> None:
        """Écrit ce qui attendait la cadence (poignée)."""

    def end(self, choose: JointChoice) -> list[str]:
        """Fin du geste au relâchement : recalcul du document, avertissements."""
        return end_drag(self.memento, choose)


class Dragging(Gesture):
    """Flèche ou poignée tirée."""

    def __init__(self, grab: Grab) -> None:
        super().__init__(grab.memento, grab.start, grab.own)
        self.key = self.target = grab.key
        self.line = grab.line  # axe au début : les flèches suivent la pièce, pas lui
        self.origin = grab.origin  # paramètre de l'axe sous le curseur au début
        self.guides = grab.guides
        self.tolerance = grab.tolerance
        self.box = _box_of(grab.memento.part)
        # repère de la pièce au début : celui des guides, qui ne suivent pas la pièce
        self.frame = _frame_of(grab.memento.part.getGlobalPlacement())

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

    def apply(self, session: DragSession, delta: float) -> None:
        axis = parse_key(self.target)
        if not isinstance(axis, int):  # clé d'une poignée : rien à faire ici
            return
        wanted = Vec3(0.0, 0.0, 0.0).with_component(axis, delta)
        if self.shift:
            result = DragResult(wanted)
        else:
            result = magnet(self.box, self.guides, wanted, self.tolerance, [axis])
        move_part(self.memento, result.delta)
        session.written([self.guides[hit.guide] for hit in result.hits], self.frame)


class Resizing(Dragging):
    """Poignée tirée : la cote suit, l'autre bout ne bouge pas ; brute recalculée 30 fois par
    seconde au plus."""

    def __init__(self, grab: Grab) -> None:
        super().__init__(grab)
        self.throttle = Throttle()
        self.pending: tuple[str, float, Vec3, list[Guide]] | None = None
        self.scheduled = False

    def apply(self, session: DragSession, delta: float) -> None:
        handle = parse_key(self.target)
        if not isinstance(handle, Handle):  # clé d'une flèche : rien à faire ici
            return
        guides = () if self.shift else self.guides
        result = resize(self.box, handle, delta, guides, self.tolerance)
        hit = [] if result.hit is None else [self.guides[result.hit.guide]]
        self.pending = (SIZE_PROPS[handle.axis], result.size, result.origin_shift, hit)
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
        if self.pending is None:
            return
        prop, size, shift, guides = self.pending
        self.pending = None
        resize_part(self.memento, prop, size, shift)
        session.written(guides, self.frame)


class Rotating(Gesture):
    """Anneau tiré : la pièce tourne autour de l'axe de l'anneau, par son centre, depuis son
    orientation du début (RO-b, ``rotate_by``). L'angle est aimanté tous les 15° (libre avec Maj,
    au dixième de degré) ; il s'ajoute d'un demi-tour à l'autre (plusieurs tours possibles). Seul
    le ``Placement`` est écrit, sans recalcul."""

    def __init__(self, grab: Turn) -> None:
        super().__init__(grab.memento, grab.start, grab.own)
        self.ring = grab.ring
        self.key = ring_key(grab.ring.axis)
        self.first = grab.first
        self.from_center = grab.from_center
        self.last = 0.0  # angle lu au dernier mouvement (]-180, 180])
        self.total = 0.0  # angle parcouru depuis la saisie, tours compris
        self.frame = _frame_of(grab.memento.part.getGlobalPlacement())

    def _follow(self, session: DragSession) -> None:
        """Pièce tournée d'après le curseur ; rayon rasant le plan de l'anneau : elle reste."""
        ray = ring_ray(session.ray(self.cursor), self.ring)
        raw = ring_angle(ray, self.ring, self.first)
        if raw is not None:
            self.total, self.last = advance(self.total, self.last, raw), raw
        angle = snapped_angle(self.total, free=self.shift)
        if not rotate_by(self.memento, self.ring.axis, angle):
            return
        anchor = plane_point(ray, self.ring) or self.ring.center
        self.sweep = Sweep(self.ring, self.from_center, angle, anchor)
        session.written((), self.frame)

    def end(self, choose: JointChoice) -> list[str]:
        return end_rotation(self.memento, choose)


class DragSession:
    """Pièce qui porte les flèches et les anneaux (et les poignées si son panneau est ouvert),
    leur dessin dans la vue 3D et état courant du glissement."""

    def __init__(self) -> None:
        self.state: State = Idle()
        self.swallow_release = False  # après Échap, le relâchement du bouton est consommé
        self.part: DocumentObject | None = None
        self.layout: Layout | None = None
        self.port: ViewPort | None = None
        self.overlay: Overlay | None = None
        self.panel: PanelContext | None = None
        self._panel_shown = False
        self._size_mm = 0.0
        self.lit: tuple[Guide, ...] = ()  # guides allumés par l'aimant
        self.closed = False  # atelier quitté : plus rien n'est dessiné (minuteries en retard)

    # --- Ce qui est affiché -------------------------------------------------------------

    @property
    def active(self) -> bool:
        """Vrai si des flèches sont affichées."""
        return self.layout is not None

    @property
    def dragging(self) -> bool:
        """Vrai pendant le glissement d'une flèche ou d'une poignée, ou la rotation par un
        anneau."""
        return self.state.dragging

    def set_panel(self, panel: PanelContext) -> None:
        """Le panneau de la pièce s'ouvre : poignées et flèches sur sa pièce."""
        self.panel = panel
        self.refresh()

    def clear_panel(self, panel: PanelContext) -> None:
        """Le panneau ``panel`` est fermé (sans effet si un autre l'a remplacé)."""
        if self.panel is panel:
            self.panel = None
            self.refresh()

    def _panel_open(self) -> bool:
        try:
            return self.panel is not None and self.panel.is_open()
        except _RESIZE_ERRORS:
            return False

    def _target_part(self) -> DocumentObject | None:
        """Brute qui porte les flèches : celle du panneau ouvert, sinon la pièce de l'atelier
        sélectionnée seule (sans panneau d'une autre commande ouvert)."""
        try:
            if self._panel_open() and self.panel is not None:
                return raw_part(self.panel.part)
            if Gui.Control.activeDialog():
                return None
            selection = Gui.Selection.getSelection()
            return raw_part(selection[0]) if len(selection) == 1 else None
        except (TypeError, *_RESIZE_ERRORS):
            return None

    def _view(self, part: DocumentObject) -> ViewPort | None:
        view = Gui.activeView()
        document = Gui.activeDocument()
        if not hasattr(view, "getSceneGraph") or document is None:
            return None
        return ViewPort(view) if document.Document.Name == part.Document.Name else None

    def refresh(self) -> None:
        """Flèches (et poignées) remises d'après la sélection, le panneau et la vue active."""
        if self.dragging or self.closed:
            return
        self._remove_overlay()
        part, port = self._target_part(), None
        self.part = part
        if part is not None:
            try:
                port = self._view(part)
            except _RESIZE_ERRORS:
                port = None
        if part is None or port is None:
            self.part = self.layout = self.port = None
            self.enter(Idle())
            return
        self.port = port
        self.overlay = Overlay(port.scene_graph())
        self._panel_shown = self._panel_open()
        self._build()
        self.enter(Idle())

    def _remove_overlay(self) -> None:
        overlay, self.overlay = self.overlay, None
        if overlay is not None:
            overlay.remove()

    def _build(self, *, redraw: bool = True) -> None:
        """Disposition d'après le placement et les cotes actuels, redessinée si elle a changé
        (``redraw``)."""
        part, port = self.part, self.port
        if part is None or port is None:
            return
        try:
            limits = drag_limits(part)
            frame, box = _frame_of(part.getGlobalPlacement()), _box_of(part)
            center = frame.to_transform().apply(Vec3(*(box.center(i) for i in range(3))))
            self._size_mm = port.mm(center, ARROW_PX)
            resizable = limits.resizable_axes if self._panel_shown else frozenset()
            layout = build_layout(frame, box, self._size_mm, limits.fixed_axes, resizable)
            layout = replace(layout, rings=_rings_of(part, box))
        except _RESIZE_ERRORS:
            self.clear()
            return
        changed, self.layout = layout != self.layout, layout
        if changed and redraw:
            self.draw()

    def draw(self, guides: Sequence[Guide] = (), guides_frame: Frame | None = None) -> None:
        """Redessine la disposition, ``guides`` aimantés en surbrillance (lus dans le repère
        ``guides_frame`` de la pièce au début du glissement)."""
        self.lit = tuple(guides)
        if self.overlay is not None and self.layout is not None:
            drawing = build_drawing(
                self.layout, self.state.key, guides, guides_frame, self.state.sweep
            )
            self.overlay.draw(drawing)

    def sync(self) -> None:
        """Panneau fermé ou zoom changé : disposition remise à jour (rien pendant un glissement)."""
        if self.closed or self.dragging or self.part is None or self.port is None:
            return
        if self._panel_open() != self._panel_shown:
            self.refresh()
            return
        self._build()

    def clear(self) -> None:
        """Plus de flèches."""
        self.part = self.layout = self.port = None
        self._remove_overlay()
        self.state = Idle()

    def forget(self, document: str) -> None:
        """Le document ``document`` se ferme : s'il porte les flèches, elles sont oubliées avant
        que sa vue soit détruite (sinon la session garderait une vue détruite)."""
        try:
            mine = self.part is None or self.part.Document.Name == document
        except _RESIZE_ERRORS:  # pièce déjà détruite
            mine = True
        if mine and self.port is not None:
            self.clear()

    def shutdown(self) -> None:
        """Atelier quitté : glissement annulé, flèches enlevées pour de bon."""
        self.closed = True
        try:
            self.abort()
        finally:
            self.panel = None
            self.clear()

    def enter(self, state: State) -> None:
        """Passe à ``state`` (surbrillance mise à jour)."""
        self.state = state
        self.draw()

    # --- Évènements ---------------------------------------------------------------------

    def press(self, point: Point, shift: bool = False) -> bool:
        """Clic gauche enfoncé au pixel ``point`` ; vrai s'il saisit une flèche ou une poignée."""
        return self.state.press(self, point, shift)

    def move(self, point: Point, shift: bool = False) -> bool:
        """Souris au pixel ``point`` ; vrai pendant un glissement."""
        return self.state.move(self, point, shift)

    def release(self, point: Point) -> bool:
        """Clic gauche relâché ; vrai s'il termine un glissement."""
        return self.state.release(self, point)

    def escape(self) -> bool:
        """Échap ; vrai s'il annule un glissement."""
        return self.state.escape(self)

    def shift_changed(self, shift: bool) -> None:
        """Maj enfoncée ou relâchée : l'aimant se coupe ou revient aussitôt."""
        self.state.shift_changed(self, shift)

    def abort(self) -> None:
        """Annule le glissement en cours, quel que soit son état (erreur, atelier quitté)."""
        if isinstance(self.state, Gesture):
            self.cancel(self.state)

    # --- Rayon et cibles ----------------------------------------------------------------

    def ray(self, point: Point) -> Ray:
        """Rayon de la souris au pixel ``point``."""
        if self.port is None:
            raise RuntimeError("aucune vue 3D pour le glissement")
        return self.port.ray(point)

    def line(self, key: str) -> Ray:
        """Axe de la flèche ou de la poignée ``key``."""
        if self.layout is None:
            raise RuntimeError("aucune flèche affichée")
        return target_line(self.layout, key)

    def target_at(self, point: Point) -> str | None:
        """Flèche ou poignée sous le pixel ``point`` (à 8 pixels près), sinon l'anneau touché par
        le rayon de la souris (les flèches ont la priorité), sinon ``None``."""
        if self.layout is None or self.port is None:
            return None
        try:
            key = handle_at(pixel_targets(self.layout, self.port.project), point)
            return key if key is not None else self._ring_at(point)
        except _RESIZE_ERRORS:
            return None

    def _ring_at(self, point: Point) -> str | None:
        """Anneau sous le pixel ``point`` (à 8 pixels près, mesurés à l'écran) ; aucun s'il est vu
        par la tranche ou si son rayon à l'écran est inférieur à 16 pixels (pièce dézoomée)."""
        rings = () if self.layout is None else self.layout.rings
        if not rings or self.port is None:
            return None
        return ring_under(rings, self.port.ray(point), self.port.project, point)

    # --- Début, fin et annulation -------------------------------------------------------

    def begin(self, key: str, point: Point, shift: bool) -> bool:
        """Saisit la cible ``key`` (flèche, poignée ou anneau) au pixel ``point`` ; faux (rien
        n'est pris) si la flèche ou l'anneau est vu de bout ou si la pièce ne peut pas être lue."""
        axis = ring_axis(key)
        if axis is not None:
            return self._begin_rotation(axis, point, shift)
        part, port = self.part, self.port
        if part is None or port is None:
            return False
        line = self.line(key)
        origin = axis_param(port.ray(point), line)
        if origin is None:
            return False
        own = self._open(part, MOVE_TRANSACTION)
        try:
            memento = begin_drag(part)
            guides = collect_guides(part, part.getParentGeoFeatureGroup())
            tolerance = port.mm(_frame_of(part.getGlobalPlacement()).origin, MAGNET_PX)
        except (*_RESIZE_ERRORS, App.Base.FreeCADError):
            self._give_up(part, own)
            return False
        kind = Moving if isinstance(parse_key(key), int) else Resizing
        state = kind(Grab(key, point, line, origin, memento, guides, tolerance, own))
        state.shift = shift
        self.enter(state)
        return True

    @staticmethod
    def _open(part: DocumentObject, name: str) -> bool:
        """Ouvre la transaction ``name`` si aucune n'est en cours (celle du panneau, sinon) ; vrai
        si c'est le geste qui l'a ouverte."""
        own = App.getActiveTransaction() is None
        if own:
            part.Document.openTransaction(translated(name))
        return own

    @staticmethod
    def _give_up(part: DocumentObject, own: bool) -> None:
        """Début de geste raté : transaction du geste abandonnée, erreur dans la vue rapport."""
        if own:
            part.Document.abortTransaction()
        App.Console.PrintError(traceback.format_exc())

    def _begin_rotation(self, axis: int, point: Point, shift: bool) -> bool:
        """Saisit l'anneau de l'axe ``axis`` au pixel ``point`` : transaction « Tourner la pièce »
        hors panneau, état :class:`Rotating`. Faux si l'anneau est vu par la tranche."""
        part, port, layout = self.part, self.port, self.layout
        ring = next((r for r in layout.rings if r.axis == axis), None) if layout else None
        if part is None or port is None or ring is None:
            return False
        first = ring_ray(port.ray(point), ring)
        hit = plane_point(first, ring)
        if hit is None:
            return False
        from_center = Vec3(hit.x - ring.center.x, hit.y - ring.center.y, hit.z - ring.center.z)
        if from_center == Vec3(0.0, 0.0, 0.0):
            return False
        own = self._open(part, ROTATE_TRANSACTION)
        try:
            memento = begin_drag(part)
        except (*_RESIZE_ERRORS, App.Base.FreeCADError):
            self._give_up(part, own)
            return False
        state = Rotating(Turn(ring, first, from_center, point, memento, own))
        state.shift = shift
        self.enter(state)
        return True

    def written(self, guides: Sequence[Guide], guides_frame: Frame) -> None:
        """La pièce a été écrite : flèches redessinées avec les ``guides`` aimantés (dans le repère
        ``guides_frame`` de départ), champs du panneau relus."""
        self._build(redraw=False)
        self.draw(guides, guides_frame)
        if self.panel is not None and self._panel_open():
            self.panel.refresh()

    def _close(self, state: Gesture, *, commit: bool) -> None:
        """Fin du glissement : transaction validée (``commit``) ou abandonnée."""
        document = state.memento.part.Document
        if state.own:
            if commit:
                document.commitTransaction()
            else:
                document.abortTransaction()
        self.state = Idle()
        self.refresh()
        if self.panel is not None and self._panel_open():
            self.panel.refresh()

    def finish(self, state: Gesture) -> None:
        """Relâchement : ensemble relié et document recalculé une fois (``end_drag``),
        avertissements dans la vue rapport. Si le déplacement défait des assemblages, la fenêtre
        de choix s'ouvre avant le recalcul (``gui/joint_choice``, ADR 0026) : annuler remet la
        pièce, supprimer garde le déplacement."""
        try:
            warnings = state.end(joint_choice.choose)
        except DragCancelledError:  # assemblages défaits, « Annuler le déplacement » (ADR 0026)
            self._close(state, commit=False)
            return
        except ValueError as error:
            report_warning(str(error))
            self._close(state, commit=False)
            return
        for warning in warnings:
            report_warning(warning)
        self._close(state, commit=True)

    def cancel(self, state: Gesture) -> None:
        """Échap : la pièce revient où elle était au début du glissement (le panneau, s'il est
        ouvert, reste) ; le relâchement du bouton est consommé."""
        restore(state.memento)
        if state.own:
            state.memento.part.Document.abortTransaction()
        self.swallow_release = True
        self.state = Idle()
        self.refresh()
        if self.panel is not None and self._panel_open():
            self.panel.refresh()
