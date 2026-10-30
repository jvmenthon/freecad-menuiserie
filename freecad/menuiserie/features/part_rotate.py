# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture d'une rotation libre : angle absolu et geste à la souris (RO-b, ADR 0025).

Seul le ``Placement`` de la **brute** est écrit (et celui de sa pièce usinée, pour l'affichage),
sans recalcul du document, autour du centre de la brute (L/2, l/2, e/2). Dans un conteneur
(``App::Part``, Body), le ``Placement`` est celui du repère local : les angles sont les siens.
Une pièce en bois (``ShapedPart``) tourne par son propre ``Placement`` ; sa source n'est jamais
écrite. Aucun import de ``FreeCADGui``.

- :func:`rotate_to` : les trois angles du ``Placement`` (champs du panneau) ;
- :func:`rotate_by` : le geste à la souris, par rapport à un :class:`DragMemento` (écritures
  absolues depuis le début, rien ne s'accumule) ; Échap : :func:`~part_drag.restore` (placement et
  Distances) ; relâchement : :func:`end_rotation`, le chemin de
  :func:`~part_drag.end_drag` (Distances, assemblages défaits par l'ADR 0026, un recalcul).

Une expression sur le ``Placement`` (liaison d'ensemble, formule) interdit la rotation : les
fonctions renvoient faux sans rien écrire. Pendant un geste, les liaisons de l'atelier sont déjà
mises de côté par ``begin_drag`` ; le mémento les retient (``aside``) et elles comptent aussi.
"""

from __future__ import annotations

import math
from typing import Final

from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.rotation import Angles, matrix_of, turned_about
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_drag import (
    DragMemento,
    end_drag,
    raw_part,
    write_placement,
)
from freecad.menuiserie.features.placement import to_placement
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["MAX_ANGLE_DEGREES", "end_rotation", "rotate_by", "rotate_to"]

MAX_ANGLE_DEGREES: Final = 360.0  # borne des angles écrits (spécification § 4.6)
_OUT_OF_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les angles doivent être compris entre -360 et 360 degrés"
)


def _driven(raw: DocumentObject, aside: dict[str, str] | None = None) -> bool:
    """Vrai si une expression pilote le ``Placement`` de ``raw`` (ou l'a piloté avant qu'un
    geste ne la mette de côté : ``aside``)."""
    if placement_expression(raw) is not None:
        return True
    return any(path.split(".")[0] == "Placement" for path in aside or ())


def _center(raw: DocumentObject) -> Vec3:
    size = dimensions_of(raw)
    return Vec3(size.length / 2, size.width / 2, size.thickness / 2)


def rotate_to(obj: DocumentObject, angles: Angles, aside: dict[str, str] | None = None) -> bool:
    """Donne à la brute de ``obj`` les angles absolus ``angles`` (X, Y, Z du ``Placement``,
    degrés), le centre de la brute restant fixe (B1, B2, B5). Sans recalcul du document. Faux,
    sans rien écrire, si une expression pilote le ``Placement`` ou le pilotait avant qu'un geste
    ne la mette de côté (``aside``, comme :func:`rotate_by`). ``ValueError`` si un angle n'est
    pas fini ou sort de [-360, 360] (spécification § 4.6)."""
    raw = raw_part(obj)
    rotation = matrix_of(angles)  # refuse les angles non finis avant toute écriture
    if any(abs(angle) > MAX_ANGLE_DEGREES for angle in angles):
        raise ValueError(translated(_OUT_OF_RANGE))
    if _driven(raw, aside):
        return False
    start = rigid_transform(raw.Placement)
    center = _center(raw)
    held = start.apply(center)
    carried = RigidTransform(rotation, Vec3(0.0, 0.0, 0.0)).rotate(center)
    translation = Vec3(held.x - carried.x, held.y - carried.y, held.z - carried.z)
    write_placement(raw, to_placement(RigidTransform(rotation, translation)))
    return True


def rotate_by(memento: DragMemento, axis: int, angle: float) -> bool:
    """Tourne la brute de ``angle`` degrés autour de l'axe fixe ``axis`` (0 = X, 1 = Y, 2 = Z) du
    repère de son ``Placement``, **à partir de son orientation du début** du geste (B3) : deux
    appels successifs ne s'ajoutent pas. Centre fixe, sans recalcul du document. Faux, sans rien
    écrire, si une expression pilote le ``Placement``. ``ValueError`` si ``axis`` ou ``angle`` est
    invalide."""
    raw = memento.part
    if not math.isfinite(angle):
        raise ValueError("rotate_by.angle : angle fini attendu")
    if _driven(raw, memento.aside):
        return False
    turned = turned_about(rigid_transform(memento.placement), dimensions_of(raw), axis, angle)
    write_placement(raw, to_placement(turned))
    return True


def end_rotation(memento: DragMemento, choose: JointChoice | None = None) -> list[str]:
    """Fin d'une rotation (B4) : exactement :func:`~part_drag.end_drag` (Distances gardées mises
    à jour, assemblages défaits proposés à ``choose`` avant tout recalcul, un recalcul du
    document). ``DragCancelledError`` si ``choose`` annule : la brute est revenue. Renvoie les
    avertissements pour la vue rapport."""
    return end_drag(memento, choose)
