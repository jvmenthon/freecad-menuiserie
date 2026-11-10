# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix d'une butée dans la vue 3D pour le panneau « Répéter » (ADR 0047).

Le bouton « Butée… » d'une ligne passe en sélection : un observateur de sélection
(``Gui.Selection``) n'est posé que le temps du choix, jamais laissé en place ensuite (ADR 0007).
Le premier clic (face, arête, sommet ou pièce) est la butée ; la suite est différée hors de la
notification de FreeCAD.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, SpacingMode
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat_stop import (
    Stop,
    Stops,
    start_axis,
    stop_axis,
    stop_text,
)
from freecad.menuiserie.features.repeat_stop_raw import raw_stop
from freecad.menuiserie.gui.task_panels.base import Widget
from freecad.menuiserie.gui.task_panels.repeat_rows import AxisRow
from freecad.menuiserie.gui.task_panels.repeat_texts import STOP_COLLISION

__all__ = ["StopControls", "StopPicker", "collision_text", "picked_stop"]


def picked_stop(document: str, name: str, sub: str) -> Stop | None:
    """Butée désignée par une sélection de FreeCAD (``sub`` : chemin depuis l'objet ``name``,
    terminé par le sous-élément : ``Face3``, ``Piece.Face3`` ou ``Piece.``). ``None`` si l'objet
    n'existe plus."""
    doc = App.getDocument(document)
    root = doc.getObject(name) if doc is not None else None
    if root is None:
        return None
    target = root.getSubObject(sub, 1) if sub else root
    if target is None:
        return None
    element = "" if not sub or sub.endswith(".") else sub.rsplit(".", 1)[-1]
    return raw_stop(Stop(target, element))  # pièce usinée cliquée : sa brute (pas de cycle)


class StopPicker:
    """Observateur de sélection posé pendant un choix de butée : ``on_pick(stop)`` est appelé
    (hors de la notification) avec le premier élément sélectionné, puis l'observateur est
    retiré. ``cancel`` retire l'observateur sans rien choisir."""

    def __init__(self, document: str, on_pick: Callable[[Stop], None]) -> None:
        self._document = document
        self._on_pick = on_pick
        self.active = False

    def start(self) -> None:
        """Vide la sélection et attend le prochain clic."""
        if self.active:
            return
        Gui.Selection.clearSelection()
        Gui.Selection.addObserver(self)
        self.active = True

    def cancel(self) -> None:
        """Retire l'observateur (sans effet s'il ne l'est plus)."""
        if self.active:
            self.active = False
            Gui.Selection.removeObserver(self)

    def addSelection(self, document: str, name: str, sub: str, _point: object = None) -> None:
        """Notification de FreeCAD : premier élément sélectionné dans le document du panneau."""
        if not self.active or document != self._document:
            return
        stop = picked_stop(document, name, sub)
        if stop is not None:
            self.cancel()
            QtCore.QTimer.singleShot(0, lambda: self._on_pick(stop))


def collision_text(params: RepeatParams, stops: Stops) -> str:
    """Avertissement : sans déduction, la dernière copie commence à la butée (collision)."""
    if params.deduct_thickness:
        return ""
    return "\n".join(translated(STOP_COLLISION, {"axis": axis.value}) for axis in stops)


def _no_trouble() -> tuple[bool, bool]:
    return False, False


class StopControls:
    """Butées du panneau « Répéter » : une par axe (``stops``), les boutons des lignes
    (``rows``), le choix dans la vue 3D. ``changed`` est appelé quand une butée change."""

    def __init__(
        self,
        document: str,
        rows: Mapping[RepeatAxis, AxisRow],
        changed: Callable[[], None],
        sources: Callable[[], Sequence[DocumentObject]],
    ) -> None:
        self.stops: dict[RepeatAxis, Stop] = {}
        self._sources = sources
        self._auto = False  # choix à l'ouverture : l'axe est déduit de la butée
        self._rows = rows
        self._changed = changed
        self._picker = StopPicker(document, self._picked)
        self._picking: RepeatAxis | None = None
        self._closed = False
        self._deduct: Widget = None
        self._trouble: Callable[[], tuple[bool, bool]] = _no_trouble

    def settle_with(self, deduct: Widget, trouble: Callable[[], tuple[bool, bool]]) -> None:
        """Case « Déduire l'épaisseur » essayée dans l'autre état après un choix de butée
        (``trouble`` : saisie refusée, copies qui se chevauchent)."""
        self._deduct, self._trouble = deduct, trouble

    def active(self, params: RepeatParams) -> dict[RepeatAxis, Stop]:
        """Butées utilisées : celles des axes actifs, si le mode de saisie a une longueur."""
        if params.spacing is SpacingMode.COUNT_AND_STEP:
            return {}
        return {axis: stop for axis, stop in self.stops.items() if self._rows[axis].checked()}

    def pick(self, axis: RepeatAxis) -> None:
        """Bouton « Butée… » : choix dans la vue 3D (un second clic sur le bouton annule)."""
        was_picking = self._picking
        self.cancel()
        if was_picking is not axis:
            self._picking = axis
            self._rows[axis].show_stop(None, picking=True)
            self._picker.start()

    def pick_auto(self) -> None:
        """Choix à l'ouverture du panneau de création, sans axe : le premier clic dans la vue 3D
        donne la butée et l'axe (celui où elle est le plus loin des pièces), seul axe actif."""
        self.pick(RepeatAxis.X)
        self._auto = True

    def cancel(self) -> None:
        """Choix abandonné : l'observateur est retiré."""
        self._auto = False
        self._picker.cancel()
        axis, self._picking = self._picking, None
        if axis is not None:
            self.show(axis)

    def close(self) -> None:
        """Panneau fermé : plus d'observateur, plus de réaction."""
        self._closed = True
        self._picker.cancel()

    def _picked(self, stop: Stop) -> None:
        axis, self._picking = self._picking, None
        auto, self._auto = self._auto, False
        if axis is None or self._closed:
            return
        start = self._start_of(stop)
        if (
            start is not None
        ):  # face de la pièce répétée : point de départ, la butée reste à choisir
            self._activate(start, axis)
            self.pick(start)
            self._changed()
            return
        if auto:
            axis = self._axis_of(stop, axis)
        self.stops[axis] = stop
        self.show(axis)
        self._changed()
        self._settle()

    def _start_of(self, stop: Stop) -> RepeatAxis | None:
        try:
            return start_axis(stop, self._sources())
        except ValueError:
            return None

    def _settle(self) -> None:
        """Chevauchement ou refus après le choix d'une butée (retour de jv) : la case « Déduire
        l'épaisseur » passe dans l'autre état ; si le problème reste, elle revient à son état
        initial (le refus ou l'avertissement restent affichés)."""
        box, trouble = self._deduct, self._trouble()
        if box is None or not any(trouble):
            return
        before = box.isChecked()
        box.setChecked(not before)
        if self._trouble() >= trouble:  # pas mieux (un refus est pire qu'un chevauchement)
            box.setChecked(before)

    def _axis_of(self, stop: Stop, default: RepeatAxis) -> RepeatAxis:
        """Axe déduit de ``stop`` (``default`` si elle est refusée : le refus sera affiché), rendu
        seul actif ; le nombre de l'axe abandonné est repris."""
        try:
            axis = stop_axis(stop, self._sources())
        except ValueError:
            return default
        self._activate(axis, default)
        return axis

    def _activate(self, axis: RepeatAxis, previous: RepeatAxis) -> None:
        """``axis`` devient le seul axe actif, avec le nombre de ``previous``."""
        count = self._rows[previous].count.value()
        self.show(previous)
        for other, row in self._rows.items():
            row.active.setChecked(other is axis)
        self._rows[axis].count.setValue(count)

    def clear(self, axis: RepeatAxis) -> None:
        """Bouton pour enlever la butée de ``axis``."""
        self.stops.pop(axis, None)
        self.show(axis)
        self._changed()

    def show(self, axis: RepeatAxis) -> None:
        """Nom de la butée de ``axis`` dans sa ligne (sauf pendant son choix)."""
        if self._picking is not axis:
            stop = self.stops.get(axis)
            self._rows[axis].show_stop(None if stop is None else stop_text(stop))
