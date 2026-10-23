# SPDX-License-Identifier: LGPL-2.1-or-later
"""Placement d'une pièce : conversion ``RigidTransform`` ↔ ``App.Placement`` et pose dans un
conteneur (J6c, ADR 0011).

Le placement est calculé une fois par ``core/snap`` (repère global) puis écrit ici ; aucun lien
vers un autre objet n'est créé. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import FreeCAD as App

from freecad.menuiserie.core.geometry import Matrix3, RigidTransform, squared_rotation
from freecad.menuiserie.core.snap import (
    FreeTest,
    Orientation,
    SnapNotice,
    Target,
    Turn,
    snap,
    support_rotation,
    turned_in_place,
)
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    has_expression,
    placement_expression,
)
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = [
    "SnapSession",
    "add_to_container",
    "local_placement",
    "rotate_part",
    "snap_part",
    "to_placement",
]


def to_placement(transform: RigidTransform) -> App.Placement:
    """``Placement`` de ``transform`` ; la rotation d'équerre est ramenée à la permutation exacte
    (pas de 1e-16 dans les fichiers)."""
    rotation = squared_rotation(transform.rotation)
    translation = transform.translation
    rows = [(*row, translation.component(i)) for i, row in enumerate(rotation)]
    values = [value for row in rows for value in row] + [0.0, 0.0, 0.0, 1.0]
    return App.Placement(App.Matrix(*values))


def local_placement(
    global_placement: App.Placement, container_global: App.Placement
) -> App.Placement:
    """Placement exprimé dans le repère d'un conteneur (Std Part) de placement global
    ``container_global`` : ``container_global⁻¹ · global_placement``."""
    return container_global.inverse().multiply(global_placement)


def add_to_container(obj: DocumentObject, container: DocumentObject | None) -> None:
    """Range ``obj`` dans le Std Part ``container`` (``App::Part``) ; sans effet pour ``None``.

    Le ``Placement`` de ``obj`` est alors lu dans le repère du conteneur : le fixer après."""
    if container is not None:
        container.addObject(obj)


@dataclass
class SnapSession:
    """État de l'accrochage d'une pièce en création : cibles (coordonnées globales), orientation
    courante et étirement. L'étirement (Q2) ne donne que la valeur initiale des cotes : une fois
    appliqué, la saisie du menuisier l'emporte et il n'est plus recalculé.

    ``container`` : Std Part qui reçoit la pièce (son ``Placement`` est alors exprimé dans le
    repère du conteneur) ; ``furniture`` : ensemble candidat de la case « Ajouter à l'ensemble » ;
    ``free`` : test de chevauchement d'un sommet ; ``shapes`` : formes des éléments retenus ;
    ``ignored`` : messages des éléments ignorés. ``used`` et ``notices`` sont ceux du dernier
    calcul de :func:`snap_part`."""

    targets: tuple[Target, ...] = ()
    orientation: Orientation = field(default_factory=Orientation)
    stretch: bool = True
    container: DocumentObject | None = None
    furniture: DocumentObject | None = None
    free: FreeTest | None = None
    shapes: tuple[Any, ...] = ()
    ignored: tuple[str, ...] = ()
    used: tuple[str, ...] = ()
    notices: tuple[SnapNotice, ...] = ()

    @property
    def support(self) -> Matrix3 | None:
        """Rotation repère d'appui → document de la première cible (``None`` sans cible)."""
        return support_rotation(self.targets)


def snap_part(obj: DocumentObject, session: SnapSession) -> bool:
    """Pose ``obj`` d'après ``session`` : ``Placement`` recalculé (la pièce reste accrochée),
    cote étirée écrite la première fois seulement. Une cote ou un ``Placement`` piloté par une
    expression n'est pas écrit. Vrai si une cote a été écrite."""
    result = snap(
        dimensions_of(obj),
        session.orientation,
        session.targets,
        stretch=session.stretch,
        is_free=session.free,
    )
    session.used, session.notices = result.used, result.notices
    stretched = result.dimensions if session.stretch and session.targets else None
    session.stretch = False
    written = False
    if stretched is not None:
        written = _write_dimension(obj, "Length", stretched.length)
        written = _write_dimension(obj, "Width", stretched.width) or written
    if placement_expression(obj) is None:
        placement = to_placement(result.placement)
        if session.container is not None:
            placement = local_placement(placement, session.container.getGlobalPlacement())
        if obj.Placement != placement:
            obj.Placement = placement
    return written


def _write_dimension(obj: DocumentObject, prop: str, value: float) -> bool:
    if has_expression(obj, prop) or getattr(obj, prop).Value == value:
        return False
    setattr(obj, prop, value)
    return True


def rotate_part(obj: DocumentObject, turn: Turn, session: SnapSession | None = None) -> bool:
    """Quart de tour de ``obj`` autour de l'axe X, Y ou Z du document (ou de son conteneur).
    En création contre une face inclinée, l'axe est celui du repère d'appui (limite documentée).

    Avec ``session`` (création) : l'orientation change et la pièce est reposée, donc reste
    accrochée. Sans (modification) : elle tourne sur place, centre fixe. Faux, sans rien
    changer, si une expression pilote son ``Placement``."""
    if placement_expression(obj) is not None:
        return False
    if session is not None:
        session.orientation = session.orientation.turned(turn, session.support)
        snap_part(obj, session)
        return True
    turned = turned_in_place(rigid_transform(obj.Placement), dimensions_of(obj), turn)
    obj.Placement = to_placement(turned)
    return True
