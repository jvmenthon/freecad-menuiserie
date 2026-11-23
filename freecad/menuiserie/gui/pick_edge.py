# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cibles de la finition des chants désignées dans la vue 3D (issue #5, C3, ADR 0029).

Une pièce (brute ou usinée), une face, une arête ou un sommet désigne la pièce et, selon
l'élément, des arêtes : une face donne ses 4 arêtes, une arête elle-même, un sommet les 3 arêtes
du coin ; une pièce seule ne désigne aucune arête. On rapproche le centre de l'élément de la
boîte brute (:func:`~freecad.menuiserie.core.edges.edges_at`) ; seuls les codes sont transmis.
Pour une pièce dessinée qui n'est pas une boîte (ADR 0063), l'élément cliqué est rapporté aux
arêtes natives de sa brute (``"Edge7"``) : une face donne tout son contour, une arête elle-même
et ses arêtes tangentes (Alt+clic : elle seule), un sommet les arêtes qui s'y rejoignent.
Lecture de la sélection à l'ouverture du panneau, puis un observateur de sélection posé
**seulement pendant que le panneau est ouvert** (ADR 0007, § 3 : rien de permanent).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtGui

from freecad.menuiserie.core.edges import edges_at
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.box_parts import is_box_part
from freecad.menuiserie.features.edge_frames import (
    edge_index,
    edge_name,
    face_edge_names,
    tangent_chain,
    vertex_edge_names,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.shaped_part import base_shape_of, is_timber
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["EdgePicker", "Pick", "part_of", "pick_at", "selected_picks"]

_KINDS = ("Face", "Edge", "Vertex")


class Pick(NamedTuple):
    """Cibles désignées : la pièce de bois (brute) et les codes d'arêtes que les faces, arêtes
    et sommets choisis désignent."""

    part: DocumentObject
    codes: tuple[str, ...]


def part_of(target: DocumentObject) -> DocumentObject | None:
    """Pièce de bois ou pièce en bois (brute) que ``target`` désigne : elle-même, ou la brute de
    sa pièce usinée."""
    if is_machined_part(target):
        target = target.Base
    return target if is_timber(target) else None


def _pick_of(target: DocumentObject, sub: str, clicked: Any = None) -> Pick | None:
    """Cibles de l'élément ``sub`` (``"Face3"``, ``""`` pour la pièce entière) de ``target`` ;
    ``clicked`` : point cliqué, en coordonnées globales, s'il est connu."""
    part = part_of(target)
    if part is None:
        return None
    kind = sub.rstrip("0123456789")
    if kind not in _KINDS:
        return Pick(part, ()) if not sub else None
    element = target.Shape.getElement(sub)
    if not is_box_part(part):
        if clicked is not None:  # point cliqué : global, ramené au repère de la pièce
            point = part.getGlobalPlacement().inverse().multVec(clicked)
        else:  # centre de l'élément : repère du conteneur, comme ``target.Shape``
            point = part.Placement.inverse().multVec(_element_center(element, kind))
        return Pick(part, _native_names(target, part, kind, sub, point))
    center = _element_center(element, kind)
    # ``target.Shape`` est dans le repère du conteneur de la pièce (Std Part non compris) : seul
    # ``Placement`` est défait ici, pas ``getGlobalPlacement()`` (qui sert à la vue 3D).
    local = part.Placement.inverse().multVec(center)
    point, dimensions = Vec3(local.x, local.y, local.z), dimensions_of(part)
    return Pick(part, tuple(e.code for e in edges_at(dimensions, kind, point)))


def _element_center(element: Any, kind: str) -> Any:
    """Point qui représente l'élément : le sommet lui-même, le milieu d'une arête (sur la
    courbe), le centre d'une face."""
    if kind == "Vertex":
        return element.Point
    if kind == "Edge":
        return element.valueAt((element.FirstParameter + element.LastParameter) / 2)
    return element.CenterOfMass


def _alt_pressed() -> bool:
    modifiers = QtGui.QApplication.keyboardModifiers()
    return bool(modifiers & QtCore.Qt.KeyboardModifier.AltModifier)


def _nearest(candidates: list[Any], point: Any) -> int:
    """Rang (1..n) du candidat le plus proche du point ``point`` (formes ``Part``)."""
    probe = Part.Vertex(point)
    distances = [probe.distToShape(candidate)[0] for candidate in candidates]
    return distances.index(min(distances)) + 1


def _native_names(
    target: DocumentObject, part: DocumentObject, kind: str, sub: str, point: Any
) -> tuple[str, ...]:
    """Arêtes natives de la brute ``part`` désignées par l'élément ``sub`` de ``target`` (la
    brute elle-même, ou sa pièce usinée, dont les éléments sont rapportés à la brute par
    ``point``, dans le repère de la pièce : la pièce usinée est au placement de sa brute)."""
    base = base_shape_of(part)
    if kind == "Face":
        face = sub if target == part else f"Face{_nearest(base.Faces, point)}"
        return tuple(face_edge_names(base, face))
    if kind == "Vertex":
        return tuple(vertex_edge_names(base, _nearest(base.Vertexes, point)))
    named = edge_index(sub) if target == part else None
    index = named if named is not None else _nearest(base.Edges, point)
    chain = [index] if _alt_pressed() else tangent_chain(base, index)
    return tuple(edge_name(rank) for rank in chain)


def _resolve(top: DocumentObject, sub: str) -> tuple[DocumentObject, str] | None:
    """Objet et élément désignés par ``top`` et ``sub`` : un clic dans la vue 3D donne l'objet de
    plus haut niveau (l'ensemble, un Std Part) et un chemin de noms d'objets, par exemple
    ``"Tablette.Face3"`` ou ``"Caisson.Tablette.Face3"``. ``None`` si un nom du chemin est
    introuvable."""
    *chain, element = sub.split(".")
    leaf = top
    for name in chain:
        found = next((child for child in leaf.OutList if child.Name == name), None)
        if found is None:
            return None
        leaf = found
    return leaf, element


def pick_at(document: App.Document, top_name: str, sub: str, clicked: Any = None) -> Pick | None:
    """Cibles de l'élément ``sub`` de l'objet ``top_name`` du document, la pièce pouvant être
    rangée dans un ensemble (chemin de noms dans ``sub``) ; ``None`` pour tout autre élément."""
    top = document.getObject(top_name)
    resolved = None if top is None else _resolve(top, sub)
    return None if resolved is None else _pick_of(*resolved, clicked)


def selected_picks() -> list[Pick]:
    """Cibles de la sélection courante, une par pièce de bois, dans l'ordre de sélection : les
    faces, arêtes et sommets d'une même pièce sont fusionnés."""
    picks: dict[str, Pick] = {}
    for item in Gui.Selection.getSelectionEx():
        points = list(item.PickedPoints)
        for rank, sub in enumerate(item.SubElementNames or [""]):
            pick = _pick_of(item.Object, sub, points[rank] if rank < len(points) else None)
            if pick is None:
                continue
            base = picks.get(pick.part.Name, Pick(pick.part, ()))
            picks[pick.part.Name] = Pick(
                base.part, base.codes + tuple(c for c in pick.codes if c not in base.codes)
            )
    return list(picks.values())


class EdgePicker:
    """Observateur de sélection qui transmet les cibles d'un élément cliqué d'une pièce de bois
    du document ; ``on_ignored`` est appelé pour un clic qui ne désigne pas une telle pièce."""

    def __init__(
        self,
        document: App.Document,
        on_pick: Callable[[Pick], None],
        on_ignored: Callable[[], None] | None = None,
    ) -> None:
        self._document_name: str = document.Name
        self._on_pick = on_pick
        self._on_ignored = on_ignored
        self._active = False

    def start(self) -> None:
        """Pose l'observateur (idempotent)."""
        if not self._active:
            Gui.Selection.addObserver(self)
            self._active = True

    def stop(self) -> None:
        """Retire l'observateur (idempotent)."""
        if self._active:
            self._active = False
            Gui.Selection.removeObserver(self)

    def addSelection(self, doc: str, obj: str, sub: str, pos: Any) -> None:
        """Rappel de FreeCAD : un élément a été sélectionné. Seul un élément d'une pièce de bois
        compte ; la sélection est alors vidée (la pièce n'est pas laissée en surbrillance) et les
        cibles transmises hors du rappel."""
        if not self._active or doc != self._document_name:
            return
        try:
            clicked = App.Vector(*pos) if pos and len(pos) == 3 else None
            pick = pick_at(App.getDocument(self._document_name), obj, sub, clicked)
        except (RuntimeError, ValueError, Part.OCCError):  # élément périmé : clic ignoré
            pick = None
        if pick is None:
            QtCore.QTimer.singleShot(0, self._ignored)
            return
        QtCore.QTimer.singleShot(0, lambda: self._deliver(pick))

    def _ignored(self) -> None:
        """Clic sur autre chose qu'une pièce de bois, transmis seulement si l'observateur est
        encore posé (le panneau a pu se fermer entre-temps)."""
        if self._active and self._on_ignored is not None:
            self._on_ignored()

    def _deliver(self, pick: Pick) -> None:
        if not self._active:  # panneau fermé entre-temps : la sélection n'est pas touchée
            return
        Gui.Selection.clearSelection()
        self._on_pick(pick)
