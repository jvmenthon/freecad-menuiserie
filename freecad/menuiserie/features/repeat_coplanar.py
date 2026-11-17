# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faces des copies d'une répétition coplanaires à une face voisine (jv, 2026-11-14, ADR 0058).

Pendant le réglage d'une répétition, jv veut voir quand l'espacement met une copie au ras d'une
pièce voisine. :class:`RepeatPlanes` lit **une fois** les faces planes des objets voisins (ni
les pièces répétées, ni leurs copies, ni leurs assemblages), dans le repère du conteneur des
sources (celui des axes X, Y, Z de la répétition) ; :meth:`RepeatPlanes.coplanar` donne, pour
les copies du moment, les faces normales aux axes répétés qui sont coplanaires à une voisine, et
ces voisines. Aucun import de ``FreeCADGui`` ; rien n'est écrit dans le document.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import FreeCAD as App

from freecad.menuiserie.core.magnet import Guide, PlaneIndex
from freecad.menuiserie.core.repeat import RepeatAxis, axis_index
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_container import guide_container, std_part_of
from freecad.menuiserie.features.magnet_guides import neighbor_planes, own_names, plane_guides
from freecad.menuiserie.features.snap_geometry import ERRORS

__all__ = ["RepeatPlanes", "axis_indices"]


def axis_indices(axes: Iterable[RepeatAxis]) -> tuple[int, ...]:
    """Indices 0, 1, 2 des axes X, Y, Z répétés, sans doublon."""
    return tuple(dict.fromkeys(axis_index(axis) for axis in axes))


def _anchor(source: DocumentObject) -> DocumentObject:
    """Objet dont le ``Placement`` reçoit le pas : le Std Part d'un ensemble, sinon la source."""
    if is_furniture(source):
        part = std_part_of(source)
        if part is not None:
            return part
    return source


def _skipped(objects: Iterable[DocumentObject]) -> set[str]:
    """Noms des objets ``objects`` (et Std Parts de leurs ensembles), de leurs pièces usinées et
    de leurs assemblages : ils ne comptent pas comme voisins."""
    names: set[str] = set()
    for obj in objects:
        names |= own_names(obj)
        if is_furniture(obj):
            part = std_part_of(obj)
            if part is not None:
                names.add(part.Name)
    return names


class RepeatPlanes:
    """Faces voisines de la répétition des ``sources``, lues à la construction ; ``excluded`` :
    les objets qui ne sont pas des voisins (sources, copies, leurs pièces affichées).

    ``ValueError`` si ``sources`` est vide."""

    def __init__(self, sources: Sequence[DocumentObject], excluded: Iterable[DocumentObject]):
        if not sources:
            raise ValueError("RepeatPlanes : au moins une source attendue")
        anchor = _anchor(sources[0])
        holder = anchor.getParentGeoFeatureGroup()
        self.origin = holder.getGlobalPlacement() if holder is not None else App.Placement()
        skip = _skipped([*sources, *excluded])
        planes = neighbor_planes(anchor.Document, guide_container(anchor), self.origin, skip)
        self._index = PlaneIndex(planes)

    def coplanar(self, copies: Iterable[DocumentObject], axes: Iterable[int]) -> tuple[Guide, ...]:
        """Faces des ``copies`` (objets affichés) normales à un axe de ``axes`` et coplanaires à
        une face voisine, puis ces voisines (repère :attr:`origin`) ; aucune si une copie est
        illisible."""
        try:
            faces = plane_guides(copies, self.origin)
        except ERRORS:
            return ()
        return self._index.coplanar(faces, axes)

    @property
    def planes(self) -> PlaneIndex:
        """Faces planes des voisines, dans le repère :attr:`origin`."""
        return self._index

    def faces(self, objects: Iterable[DocumentObject], axis: int) -> list[float]:
        """Positions sur ``axis`` (0, 1, 2) des faces des ``objects`` (affichés) normales à
        ``axis``, dans le repère :attr:`origin` ; aucune si un objet est illisible."""
        try:
            found = plane_guides(objects, self.origin)
        except ERRORS:
            return []
        return sorted({g.position(axis) for g in found if g.axis == axis})
