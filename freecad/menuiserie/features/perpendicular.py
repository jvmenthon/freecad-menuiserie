# SPDX-License-Identifier: LGPL-2.1-or-later
"""Départ d'une pièce créée contre une face de pièce de bois (issue #136).

Si une seule face est sélectionnée et qu'elle appartient à une pièce de bois, à une pièce en bois
(corps converti) ou à leur pièce usinée, d'équerre avec elle, la nouvelle pièce part
perpendiculaire à la face, avec la largeur et l'épaisseur de la face sélectionnée (celles de la
pièce qui la porte quand la cote est normale à la face). Tout reste modifiable dans le panneau.
Dans tous les autres cas (plusieurs éléments, arête, sommet, face courbe ou oblique, objet d'un
autre atelier, lien), rien ne change : :func:`perpendicular_start` renvoie ``None``. Aucune
modification du document ni de la sélection ; aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Final

import Part

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Matrix3, Vec3
from freecad.menuiserie.core.snap import (
    FaceTarget,
    Orientation,
    along_edge,
    face_section,
    footprint,
    perpendicular_orientation,
    support_rotation,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.picked import crosses_link
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.snap_geometry import (
    ERRORS,
    face_normal,
    global_shape,
    owner_shape,
    to_vector,
)
from freecad.menuiserie.features.snap_local_face import (
    NoRoomError,
    fit_to_footprint,
    local_face_target,
    oblique_edge_target,
)
from freecad.menuiserie.features.snap_targets import TargetReading
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["PerpendicularStart", "perpendicular_start"]

_FIT_PASSES: Final = 3  # un resserrement par axe, puis un de contrôle : le calcul converge en deux
# en dessous, une pièce resserrée au clic près d'une pointe aiguë n'est qu'une lamelle inutile
# (moins que le plus fin chanfrein d'un usage réel) : autre essai ou accrochage habituel. Plus
# exigeant que MIN_DIMENSION_MM (cote minimale d'une pièce saisie), qui reste la borne absolue
_SLIVER_MM: Final = 5.0
_PARALLEL: Final = 1e-6  # norme du produit vectoriel de deux normales unitaires parallèles


@dataclass(frozen=True)
class PerpendicularStart:
    """Orientation de départ, section (largeur, épaisseur, mm) de la nouvelle pièce et lecture à
    utiliser pour l'accrochage (face limitée à la tranche cliquée)."""

    orientation: Orientation
    width: float
    thickness: float
    reading: TargetReading


def _wood_part_of(reading: TargetReading) -> DocumentObject | None:
    """Pièce de bois ou pièce en bois (corps converti) qui porte l'unique face lue, ``None`` si ce
    n'en est pas une (ou si le chemin traverse un lien : le Placement global d'un lien n'est pas
    celui de l'original)."""
    element = reading.elements[0]
    if crosses_link(element):
        return None
    try:
        blank = blank_of(element.owner())
    except TypeError:
        return None
    return blank if is_timber(blank) else None


def _blank_face(reading: TargetReading, blank: DocumentObject) -> Any:
    """Face extérieure de la pièce brute ``blank`` au droit du point cliqué : parmi ses faces planes
    tournées comme la face lue, celle qui porte le point (ramené dans son plan) et qui est la plus
    en dehors dans le sens de la normale. ``None`` s'il n'y en a pas (forme absente, point hors de
    la brute). Les assemblages (mortaises, rainures, feuillures) découpent ou décalent la face de
    la pièce usinée : la largeur mesurée au clic doit l'être sur la face extérieure de la brute."""
    target, point = reading.targets[0], reading.elements[0].point
    if not isinstance(target, FaceTarget) or point is None:
        return None
    normal, click = to_vector(target.frame.z), to_vector(point)
    best: tuple[float, Any] | None = None
    try:
        for face in global_shape(blank).Faces:
            if not isinstance(face.Surface, Part.Plane):
                continue
            facing = face_normal(face)
            if facing.cross(normal).Length >= _PARALLEL or facing.dot(normal) <= 0.0:
                continue
            height = face.CenterOfMass.dot(normal)  # position le long de la normale
            above = click + normal * (height - click.dot(normal))  # clic ramené dans le plan
            if face.distToShape(Part.Vertex(above))[0] >= CONTACT_TOLERANCE_MM:
                continue
            if best is None or height > best[0]:
                best = (height, face)
    except ERRORS:
        return None
    return best[1] if best is not None else None


@dataclass(frozen=True)
class _Frames:
    """Repère d'appui, rotation de la pièce porteuse, orientation de la nouvelle pièce et axe
    d'appui (0 ou 1) de l'arête la plus proche du clic (``None`` : inconnu)."""

    support: Matrix3
    owner: Matrix3
    orientation: Orientation
    edge_row: int | None

    def section(
        self, extent: tuple[float, float], section: tuple[float, float]
    ) -> tuple[float, float]:
        """Section (largeur, épaisseur) de la pièce contre une face d'étendue ``extent``."""
        return face_section(
            self.support, self.owner, self.orientation, extent, section, self.edge_row
        )


def _nearest_edge_row(target: FaceTarget, click: Vec3 | None) -> int | None:
    """Axe d'appui (0 ou 1) que suit l'arête de ``target`` la plus proche de ``click`` : le coin du
    repère est au plus près du clic, l'arête la plus proche est donc l'un des deux côtés qui en
    partent. À égale distance, le côté qui suit l'axe 1. ``None`` sans clic ou sans distance
    calculable (point non fini)."""
    if click is None:
        return None
    offset = to_vector(click) - to_vector(target.frame.origin)
    to_x_side = abs(offset.dot(to_vector(target.frame.x)))  # distance au côté qui suit y
    to_y_side = abs(offset.dot(to_vector(target.frame.y)))  # distance au côté qui suit x
    if not (math.isfinite(to_x_side) and math.isfinite(to_y_side)):
        return None
    return 1 if to_x_side <= to_y_side else 0


def _oblique(local: FaceTarget, blank_face: Any | None, click: Vec3 | None) -> FaceTarget | None:
    """Cible le long de l'arête oblique la plus proche du clic, ``None`` si l'arête la plus
    proche est un côté droit (ou sans face brute, sans clic)."""
    if blank_face is None or click is None:
        return None
    return oblique_edge_target(local, blank_face, click)


def _fit_in_face(
    reading: TargetReading,
    blank_face: Any | None,
    frames: _Frames,
    section: tuple[float, float],
) -> tuple[TargetReading, float, float] | None:
    """Lecture resserrée et section (largeur, épaisseur) pour que la pièce tienne dans la face
    brute ``blank_face`` (une arête oblique la coupe parfois avant la fin de la tranche cliquée) ;
    ``None`` s'il ne reste pas la place d'une pièce (ou que celle d'une lamelle)."""
    target = reading.targets[0]
    if not isinstance(target, FaceTarget):
        return None
    width, thickness = frames.section(target.extent, section)
    if blank_face is None:
        return reading, width, thickness
    for _ in range(_FIT_PASSES):
        try:
            fitted = fit_to_footprint(
                target, blank_face, footprint(frames.orientation, (width, thickness))
            )
        except NoRoomError:
            return None
        if fitted is None:
            break
        reading, target = replace(reading, targets=(fitted,)), fitted
        width, thickness = frames.section(target.extent, section)
    if width < min(section[0], _SLIVER_MM) or thickness < min(section[1], _SLIVER_MM):
        return None
    return reading, width, thickness


@dataclass(frozen=True)
class _Plan:
    """Données communes aux essais de départ perpendiculaire : lecture, repère d'appui, rotation
    de la pièce porteuse et section (largeur, épaisseur) de la pièce."""

    reading: TargetReading
    support: Matrix3
    owner: Matrix3
    section: tuple[float, float]

    def start(
        self,
        orientation: Orientation,
        edge: int | FaceTarget | None,
        blank_face: Any | None,
    ) -> PerpendicularStart | None:
        """Départ le long de ``edge`` : axe d'appui (0 ou 1) de la cible lue, repère d'une arête
        (son axe 0) ou ``None`` (inconnu) ; resserré dans ``blank_face``. ``None`` s'il ne reste
        pas la place d'une pièce."""
        reading, support, edge_row = self.reading, self.support, edge
        if isinstance(edge, FaceTarget):  # repère d'appui tourné le long de l'arête
            reading, edge_row = replace(reading, targets=(edge,)), 0
            support = support_rotation(reading.targets) or support
        if edge_row is not None:
            orientation = along_edge(orientation, edge_row)
        frames = _Frames(support, self.owner, orientation, edge_row)
        fitted = _fit_in_face(reading, blank_face, frames, self.section)
        if fitted is None:  # pointe aiguë : pas de départ perpendiculaire, accrochage habituel
            return None
        reading, width, thickness = fitted
        return PerpendicularStart(orientation, width, thickness, reading)

    def along_nearest_edge(
        self,
        orientation: Orientation,
        local: FaceTarget,
        blank_face: Any | None,
        click: Vec3 | None,
    ) -> PerpendicularStart | None:
        """Départ le long de l'arête la plus proche de ``click`` : arête oblique (repère tourné),
        sinon côté droit de ``local`` ; si ce côté, mesuré au clic près d'une pointe aiguë, ne
        laisse qu'une lamelle, repère de l'arête (profondeur au milieu de l'arête)."""
        oblique = _oblique(local, blank_face, click)
        if oblique is not None:
            return self.start(orientation, oblique, blank_face)
        start = self.start(orientation, _nearest_edge_row(local, click), blank_face)
        if start is not None or blank_face is None or click is None:
            return start
        edge = oblique_edge_target(local, blank_face, click, any_edge=True)
        return None if edge is None else self.start(orientation, edge, blank_face)


def perpendicular_start(reading: TargetReading) -> PerpendicularStart | None:
    """Départ perpendiculaire à la face lue, ``None`` s'il ne s'applique pas."""
    if len(reading.targets) != 1 or not reading.elements:
        return None
    target = reading.targets[0]
    if not isinstance(target, FaceTarget) or not target.planar:
        return None
    blank = _wood_part_of(reading)
    if blank is None:
        return None
    # La face à l'endroit du clic, pas toute la face :
    blank_face = _blank_face(reading, blank)
    local = local_face_target(reading, blank_face, owner_shape(reading.elements[0]))
    if local is not None:
        reading, target = replace(reading, targets=(local,)), local
    support = support_rotation(reading.targets)
    owner = rigid_transform(blank.getGlobalPlacement()).rotation
    orientation = None if support is None else perpendicular_orientation(support, owner)
    if support is None or orientation is None:
        return None
    dimensions = dimensions_of(blank)
    plan = _Plan(reading, support, owner, (dimensions.width, dimensions.thickness))
    if local is None:
        return plan.start(orientation, None, None)
    return plan.along_nearest_edge(orientation, local, blank_face, reading.elements[0].point)
