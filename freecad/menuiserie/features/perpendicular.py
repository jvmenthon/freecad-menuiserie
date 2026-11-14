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

from dataclasses import dataclass, replace
from typing import Any, Final

import Part

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM
from freecad.menuiserie.core.snap import (
    FaceTarget,
    Orientation,
    face_section,
    perpendicular_orientation,
    support_rotation,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.picked import crosses_link
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.snap_geometry import ERRORS, face_normal, global_shape, to_vector
from freecad.menuiserie.features.snap_local_face import local_face_target
from freecad.menuiserie.features.snap_targets import TargetReading
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["PerpendicularStart", "perpendicular_start"]

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
    local = local_face_target(reading, _blank_face(reading, blank))
    if local is not None:
        reading, target = replace(reading, targets=(local,)), local
    support = support_rotation(reading.targets)
    if support is None:
        return None
    owner = rigid_transform(blank.getGlobalPlacement()).rotation
    orientation = perpendicular_orientation(support, owner)
    if orientation is None:
        return None
    dimensions = dimensions_of(blank)
    width, thickness = face_section(
        support, owner, orientation, target.extent, (dimensions.width, dimensions.thickness)
    )
    return PerpendicularStart(orientation, width, thickness, reading)
