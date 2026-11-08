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

from collections.abc import Sequence
from dataclasses import replace
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import (
    Guide,
    Ray,
    axis_param,
    handle_at,
)
from freecad.menuiserie.core.rotation import plane_point
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.magnet_guides import collect_guides
from freecad.menuiserie.features.part_drag import (
    begin_drag,
    drag_limits,
    raw_part,
)
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.drag.copying import (
    Copying,
    check_copyable,
    copy_axis,
    passive_memento,
)
from freecad.menuiserie.gui.drag.geometry import (
    ARROW_PX,
    MAGNET_PX,
    Layout,
    build_drawing,
    build_layout,
    parse_key,
    pixel_targets,
    target_line,
)
from freecad.menuiserie.gui.drag.overlay import Overlay
from freecad.menuiserie.gui.drag.parts import (
    Grab,
    PanelContext,
    Turn,
    box_of,
    frame_of,
    give_up,
    open_transaction,
    rings_of,
)
from freecad.menuiserie.gui.drag.rings import (
    ring_axis,
    ring_ray,
    ring_under,
)
from freecad.menuiserie.gui.drag.states import (
    Idle,
    Moving,
    Resizing,
    Rotating,
    State,
)
from freecad.menuiserie.gui.drag.view import Point, ViewPort

__all__ = ["DragSession", "PanelContext"]

MOVE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déplacer la pièce")
ROTATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tourner la pièce")
_RESIZE_ERRORS: Final = (RuntimeError, ValueError, TypeError, AttributeError, ReferenceError)


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
            frame, box = frame_of(part.getGlobalPlacement()), box_of(part)
            center = frame.to_transform().apply(Vec3(*(box.center(i) for i in range(3))))
            self._size_mm = port.mm(center, ARROW_PX)
            resizable = limits.resizable_axes if self._panel_shown else frozenset()
            layout = build_layout(frame, box, self._size_mm, limits.fixed_axes, resizable)
            layout = replace(layout, rings=rings_of(part, box))
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
                self.layout,
                self.state.key,
                guides,
                guides_frame,
                self.state.sweep,
                self.state.ghost,
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

    def press(self, point: Point, shift: bool = False, copy: bool = False) -> bool:
        """Clic gauche enfoncé au pixel ``point`` (``copy`` : Ctrl enfoncé) ; vrai s'il saisit une
        flèche ou une poignée."""
        return self.state.press(self, point, shift, copy)

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
        if self.dragging:
            self.state.escape(self)

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
        own = open_transaction(part, MOVE_TRANSACTION)
        try:
            memento = begin_drag(part)
            guides = collect_guides(part, part.getParentGeoFeatureGroup())
            tolerance = port.mm(frame_of(part.getGlobalPlacement()).origin, MAGNET_PX)
        except (*_RESIZE_ERRORS, App.Base.FreeCADError):
            give_up(part, own)
            return False
        kind = Moving if isinstance(parse_key(key), int) else Resizing
        state = kind(Grab(key, point, line, origin, memento, guides, tolerance, own))
        state.shift = shift
        self.enter(state)
        return True

    def begin_copy(self, key: str, point: Point, shift: bool) -> bool:
        """Ctrl + clic sur la cible ``key`` : copie par glissement si c'est une flèche (voir
        ``copying.py``). Une poignée ou un anneau n'est pas pris (le clic reste à FreeCAD, Ctrl+clic
        de sélection). Un refus (copie liée, pièce tournée, panneau ouvert) est affiché ; le clic
        et son relâchement sont alors consommés, sans quoi le Ctrl+clic désélectionnerait la
        pièce."""
        local = parse_key(key)
        if not isinstance(local, int):
            return False
        part, port = self.part, self.port
        if part is None or port is None:
            return False
        line = self.line(key)
        origin = axis_param(port.ray(point), line)
        if origin is None:
            return False
        try:
            check_copyable(part)
            # Repère du conteneur (celui de ``Placement``) : c'est l'axe X, Y ou Z de la répétition.
            axis, sign = copy_axis(frame_of(part.Placement), local)
            memento = passive_memento(part)
            guides = collect_guides(part, part.getParentGeoFeatureGroup())
            tolerance = port.mm(frame_of(part.getGlobalPlacement()).origin, MAGNET_PX)
        except ValueError as refusal:
            report_refusal(str(refusal))
            self.swallow_release = True
            return True
        except (*_RESIZE_ERRORS, App.Base.FreeCADError):
            return False
        state = Copying(
            Grab(key, point, line, origin, memento, guides, tolerance, False), axis, sign
        )
        state.shift = shift
        self.enter(state)
        return True

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
        from_center = hit - ring.center
        if from_center == Vec3(0.0, 0.0, 0.0):
            return False
        own = open_transaction(part, ROTATE_TRANSACTION)
        try:
            memento = begin_drag(part)
        except (*_RESIZE_ERRORS, App.Base.FreeCADError):
            give_up(part, own)
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

    def leave(self) -> None:
        """Fin du geste : retour à l'état :class:`Idle`, flèches redessinées, champs du panneau
        relus."""
        self.state = Idle()
        self.refresh()
        if self.panel is not None and self._panel_open():
            self.panel.refresh()
