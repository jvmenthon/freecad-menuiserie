# SPDX-License-Identifier: LGPL-2.1-or-later
"""Amener deux éléments de deux objets à une distance donnée (DI-b, ADR 0022, § 4.6).

:class:`DistanceMove` lit les deux éléments choisis (face, arête, sommet) comme cibles de
``core/snap``, choisit la pièce de l'atelier qui bouge (la brute : pièce usinée et assemblage
y reviennent, ADR 0006), mesure avec ``core/distance`` puis déplace la brute par
``features/part_drag`` (membre d'ensemble relié ensuite, axe piloté par une formule refusé).
Les objets des autres ateliers ne bougent jamais (ADR 0007). Deux usages :

- script ou ``api.set_distance`` : :meth:`DistanceMove.apply`, d'un seul geste ;
- panneau de tâche : :meth:`begin`, autant de :meth:`move_to` que de saisies (aperçu en direct,
  chaque écriture est absolue par rapport au début), puis :meth:`finish` ou :meth:`cancel`.

Aucun import de ``FreeCADGui`` ; la transaction est l'affaire de l'appelant.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.distance import Gap, measure, moved_by
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import Target, VertexTarget
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.part_drag import (
    DragMemento,
    begin_drag,
    end_drag,
    move_part,
    raw_part,
    restore,
)
from freecad.menuiserie.features.picked import PickedElement, container_of
from freecad.menuiserie.features.snap_geometry import element_shape, is_straight, to_vec3
from freecad.menuiserie.features.snap_targets import read_targets

__all__ = ["AXES", "DistanceMove"]

AXES: Final = ("X", "Y", "Z")  # axes du conteneur proposés pour deux sommets (D4)
_FROM_ABOVE: Final = Vec3(0.0, 0.0, 1.0)
_UNIT_AXES: Final = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
_NO_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Choisissez au moins une pièce de l'atelier : les autres objets ne sont pas déplacés.",
)
_SAME_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Choisissez deux éléments de deux objets différents."
)
_NOT_OF_THE_PAIR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La pièce déplacée doit porter l'un des deux éléments choisis."
)
_CURVED_EDGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » : une arête courbe n'a pas de distance définie."
)
_UNKNOWN_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'axe doit être X, Y ou Z (reçu : {axis})."
)
_NOT_STARTED: Final = "begin() doit précéder move_to() et finish()"


def piece_of(element: PickedElement) -> DocumentObject | None:
    """Brute de l'objet qui porte ``element`` si c'est une pièce de l'atelier (pièce de bois,
    pièce usinée, assemblage), ``None`` pour tout autre objet : il sert de référence seulement."""
    try:
        return raw_part(element.owner())
    except TypeError:
        return None


def _refuse_curved(element: PickedElement) -> None:
    """``ValueError`` traduite si ``element`` est une arête courbe : une droite est requise."""
    if element.element.startswith("Edge"):
        shape = element_shape(element)
        if shape is not None and not is_straight(shape):
            raise ValueError(translated(_CURVED_EDGE, {"label": element.label()}))


def _targets(
    elements: tuple[PickedElement, PickedElement], toward_observer: Vec3
) -> tuple[Target, Target]:
    """Cibles des deux éléments, dans l'ordre ; ``ValueError`` traduite si l'un n'a pas de forme
    utilisable (objet entier, arête courbe…)."""
    for element in elements:
        _refuse_curved(element)
    reading = read_targets(elements, toward_observer)
    if len(reading.targets) != len(elements):
        raise ValueError(" ".join(reading.ignored))
    return reading.targets[0], reading.targets[1]


def _moving_index(
    elements: tuple[PickedElement, PickedElement],
    pieces: tuple[DocumentObject | None, DocumentObject | None],
    moving: PickedElement | None,
) -> int:
    """Indice de l'élément de la pièce déplacée : ``moving`` s'il est donné, sinon le second
    élément s'il est à l'atelier, sinon le premier (E3)."""
    if moving is not None:
        if moving not in elements:
            raise ValueError(translated(_NOT_OF_THE_PAIR))
        index = elements.index(moving)
        if pieces[index] is None:
            raise ValueError(translated(_NO_PART))
        return index
    if pieces[1] is not None:
        return 1
    if pieces[0] is not None:
        return 0
    raise ValueError(translated(_NO_PART))


class DistanceMove:
    """Distance à définir entre deux éléments ``first`` et ``second`` de deux objets différents.

    ``moving`` : celui des deux éléments dont la pièce bouge. ``toward_observer`` : direction
    de la scène vers l'observateur (côté d'une face sans solide). ``ValueError`` traduite si la
    sélection ne convient pas (éléments de forme inutilisable, même objet, aucune pièce de
    l'atelier)."""

    def __init__(
        self,
        first: PickedElement,
        second: PickedElement,
        moving: PickedElement | None = None,
        toward_observer: Vec3 = _FROM_ABOVE,
    ) -> None:
        self.elements = (first, second)
        pieces = (piece_of(first), piece_of(second))
        owners = (first.owner(), second.owner())
        if owners[0] == owners[1] or (pieces[0] is not None and pieces[0] == pieces[1]):
            raise ValueError(translated(_SAME_OBJECT))
        self._targets = _targets(self.elements, toward_observer)
        self._pieces = pieces
        self.moving_index = _moving_index(self.elements, pieces, moving)
        self._memento: DragMemento | None = None

    # --- Lecture ------------------------------------------------------------------------

    @property
    def moving_part(self) -> DocumentObject:
        """Brute que le déplacement bouge."""
        part = self._pieces[self.moving_index]
        if part is None:  # exclu par _moving_index
            raise ValueError(translated(_NO_PART))
        return part

    @property
    def can_swap(self) -> bool:
        """Vrai si l'autre élément est aussi celui d'une pièce de l'atelier (bouton Inverser)."""
        return self._pieces[1 - self.moving_index] is not None

    @property
    def between_points(self) -> bool:
        """Vrai pour deux sommets : la direction se choisit (directe, X, Y ou Z)."""
        return all(isinstance(target, VertexTarget) for target in self._targets)

    def gap(self, axis: str | None = None) -> Gap:
        """Distance actuelle et sens dans lequel la pièce mobile s'éloigne ; ``axis`` (X, Y ou Z
        du conteneur) ne sert que pour deux sommets. ``ValueError`` traduite si les éléments ne
        sont pas parallèles ou si ``axis`` est inconnu."""
        index = self.moving_index
        with translated_errors():
            return measure(self._targets[1 - index], self._targets[index], self._axis(axis))

    def _axis(self, axis: str | None) -> Vec3 | None:
        """Vecteur global de l'axe ``axis`` du conteneur de la pièce mobile (le document sans
        Std Part)."""
        if axis is None:
            return None
        if axis not in _UNIT_AXES:
            raise ValueError(translated(_UNKNOWN_AXIS, {"axis": str(axis)}))
        container = container_of(self.elements[self.moving_index])
        rotation = container.getGlobalPlacement().Rotation if container is not None else None
        unit = App.Vector(*_UNIT_AXES[axis])
        return to_vec3(rotation.multVec(unit) if rotation is not None else unit)

    # --- Déplacement --------------------------------------------------------------------

    def swap(self) -> None:
        """Inverse la pièce déplacée (la pièce déjà déplacée revient d'abord). Sans effet si
        l'autre élément n'est pas d'une pièce de l'atelier."""
        if not self.can_swap:
            return
        self.cancel()
        self.moving_index = 1 - self.moving_index

    def begin(self) -> None:
        """Début : mémorise la brute (et met de côté les liaisons d'un membre d'ensemble)."""
        self.cancel()
        self._memento = begin_drag(self.moving_part)

    def move_to(self, value: float, axis: str | None = None) -> None:
        """Place la pièce mobile à ``value`` mm de la référence, sans recalcul du document.
        ``ValueError`` traduite si ``value`` n'est pas un nombre positif ou nul, si les éléments
        ne sont pas parallèles ou si un axe est piloté par une formule de l'utilisateur (E4)."""
        if self._memento is None:
            raise RuntimeError(_NOT_STARTED)
        gap = self.gap(axis)
        with translated_errors():
            shift = moved_by(gap, value)
        rotation = self._memento.part.getGlobalPlacement().Rotation.inverted()
        local = rotation.multVec(App.Vector(shift.x, shift.y, shift.z))
        move_part(self._memento, to_vec3(local))

    def finish(self) -> list[str]:
        """Fin : relie l'ensemble de la pièce, recalcule le document et renvoie les
        avertissements à écrire dans la vue rapport. Rangée bloquée : la pièce revient et
        l'erreur (``ValueError``) est relancée."""
        if self._memento is None:
            raise RuntimeError(_NOT_STARTED)
        memento, self._memento = self._memento, None
        return end_drag(memento)

    def cancel(self) -> None:
        """Remet la pièce où elle était au début (sans effet avant :meth:`begin`)."""
        if self._memento is not None:
            restore(self._memento)
            self._memento = None

    def apply(self, value: float, axis: str | None = None) -> list[str]:
        """:meth:`begin`, :meth:`move_to` puis :meth:`finish` ; au moindre refus la pièce revient
        à sa place avant que l'erreur soit relancée."""
        self.begin()
        try:
            self.move_to(value, axis)
            return self.finish()
        except BaseException:
            self.cancel()
            raise
