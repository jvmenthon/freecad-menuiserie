# SPDX-License-Identifier: LGPL-2.1-or-later
"""État d'un geste sur un ensemble : Memento, lecture de la boîte, début et retour (EN-b, ADR 0038).

Voir :mod:`~freecad.menuiserie.features.furniture_drag` pour le geste lui-même. Ce module garde
l'état du début (:class:`FurnitureMemento`, comme ``part_drag.DragMemento``) : toutes les écritures
sont absolues par rapport à lui. :func:`begin_furniture_drag` met de côté les liaisons de l'atelier
d'un sous-ensemble (cotes, ``Placement`` de son Std Part), :func:`restore` (Échap) les remet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    expressions_of,
    placement_expression,
)
from freecad.menuiserie.features.furniture import (
    DIMENSIONS,
    furniture_of,
    is_furniture,
    origin_of,
    writing,
)
from freecad.menuiserie.features.furniture_bindings import (
    members_of,
    workshop_expressions,
)
from freecad.menuiserie.features.furniture_checks import checked_furniture, quoted_label
from freecad.menuiserie.features.furniture_container import (
    own_std_part,
    set_member_expression,
    std_part_of,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_drag import write_placement
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.solids import rigid_transform

__all__ = [
    "DRIVEN_PLACEMENT",
    "NO_OWN_STD_PART",
    "FurnitureMemento",
    "StepResult",
    "begin_furniture_drag",
    "changed_sizes",
    "furniture_box",
    "furniture_frame",
    "furniture_placement",
    "recompute_blanks",
    "restore",
    "turn_refusal",
    "vector",
    "write_sizes",
    "write_std_placement",
]

_TOUCHED: Final = (*DIMENSIONS, "Placement")  # propriétés écrites par un geste
_NO_STD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'a pas de Std Part (ensemble d'un ancien document) : il ne peut pas être "
    "déplacé ni tourné à la souris.",
)
_SHARED_STD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le Std Part « {part} » contient autre chose que l'ensemble « {label} » : il ne peut pas "
    "être déplacé ni tourné à la souris.",
)
DRIVEN_PLACEMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : la position du Std Part suit une expression ; modifiez cette expression.",
)
NO_OWN_STD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'a pas de Std Part propre : seules ses faces arrière, droite et haute se "
    "tirent à la souris.",
)


@dataclass
class FurnitureMemento:
    """État d'un ensemble au début d'un geste : boîte (repère du Std Part, ``Origin`` à ``Origin``
    + cotes), placement du Std Part, liaisons de l'atelier mises de côté (propriété → expression,
    celles du ``Placement`` étant portées par le Std Part d'un sous-ensemble) et liaisons
    enregistrées (``FurnitureBindings``).

    ``owned`` : le Std Part est propre à l'ensemble (:func:`~furniture_container.own_std_part`) ;
    lui seul peut être déplacé, tourné, ou décalé par une face avant, gauche ou basse. Seul
    ``applied`` change : la dernière boîte écrite dans le document (valeur permise)."""

    furniture: DocumentObject
    std_part: DocumentObject | None
    box: Box
    placement: App.Placement
    aside: dict[str, str]
    recorded: dict[str, str]
    owned: bool
    applied: Box = field(init=False)

    def __post_init__(self) -> None:
        self.applied = self.box


@dataclass(frozen=True)
class StepResult:
    """Résultat d'un pas de taille : ``box`` est la boîte **écrite** dans le document (la dernière
    valeur permise), ``reached`` vrai si c'est la boîte demandée. Sinon ``message`` (traduit,
    à afficher près de la souris) dit pourquoi, ``locked`` les pièces verrouillées à proposer de
    déverrouiller (:class:`LockedPiecesError`)."""

    box: Box
    reached: bool = True
    message: str = ""
    locked: tuple[DocumentObject, ...] = ()


# --- Lecture ----------------------------------------------------------------------------------


def furniture_box(furniture: DocumentObject) -> Box:
    """Boîte de l'ensemble dans le repère de son Std Part (ou de son conteneur) : de ``Origin`` à
    ``Origin`` + ``Width``, ``Depth``, ``Height``."""
    origin = origin_of(furniture)
    size = Vec3(furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value)
    return Box(origin, origin + size)


def furniture_placement(furniture: DocumentObject) -> App.Placement:
    """Placement global (local vers global) de la boîte de ``furniture`` : celui de son Std Part,
    ou de son conteneur sans Std Part."""
    part = std_part_of(furniture)
    holder = part if part is not None else furniture.getParentGeoFeatureGroup()
    return holder.getGlobalPlacement() if holder is not None else App.Placement()


def furniture_frame(furniture: DocumentObject) -> Frame:
    """Repère (local vers global) de la boîte de ``furniture`` : le placement global de son Std
    Part, ou de son conteneur sans Std Part."""
    rows = rigid_transform(furniture_placement(furniture))
    columns = [Vec3(*(rows.rotation[r][c] for r in range(3))) for c in range(3)]
    return Frame(rows.translation, columns[0], columns[1], columns[2])


def turn_refusal(furniture: DocumentObject) -> str | None:
    """Raison (traduite) pour laquelle ``furniture`` ne peut être ni déplacé ni tourné à la souris,
    ``None`` s'il le peut : pas de Std Part (ancien document, E5), Std Part qui contient autre chose
    que l'ensemble, ou position du Std Part pilotée par une formule de l'utilisateur."""
    params = quoted_label(furniture)
    part = std_part_of(furniture)
    if part is None:
        return translated(_NO_STD_PART, params)
    if own_std_part(furniture) is None:
        return translated(_SHARED_STD_PART, {**params, "part": str(part.Label)})
    if placement_expression(part) is not None:
        return translated(DRIVEN_PLACEMENT, params)
    return None


# --- Début, retour ----------------------------------------------------------------------------


def _is_touched(prop: str) -> bool:
    return prop.split(".")[0] in _TOUCHED


def begin_furniture_drag(furniture: DocumentObject) -> FurnitureMemento:
    """Début d'un geste : mémorise ``furniture`` et, pour un sous-ensemble, met de côté les
    liaisons de l'atelier sur ses cotes et sur le ``Placement`` de son Std Part (le parent les
    repose au relâchement). Une formule de l'utilisateur n'est jamais retirée. ``TypeError``
    traduite si ``furniture`` n'est pas un ensemble."""
    checked_furniture(furniture)
    part = std_part_of(furniture)
    member = furniture_of(furniture) is not None
    recorded = (
        dict(furniture.FurnitureBindings) if "FurnitureBindings" in furniture.PropertiesList else {}
    )
    aside = {}
    if member:
        aside = {p: t for p, t in workshop_expressions(furniture).items() if _is_touched(p)}
        with writing(furniture):
            for prop in aside:
                set_member_expression(furniture, prop, None)
    placement = App.Placement(part.Placement) if part is not None else App.Placement()
    return FurnitureMemento(
        furniture,
        part,
        furniture_box(furniture),
        placement,
        aside,
        recorded,
        owned=own_std_part(furniture) is not None,
    )


def restore(memento: FurnitureMemento) -> None:
    """Échap : ramène l'ensemble à son état du début (cotes, Std Part, liaisons mises
    de côté), puis recalcule le document."""
    furniture, part = memento.furniture, memento.std_part
    if part is not None and placement_expression(part) is None:
        write_std_placement(part, memento.placement)
    with writing(furniture):
        write_sizes(furniture, memento.box)
        for prop, text in memento.aside.items():
            set_member_expression(furniture, prop, text)
        if "FurnitureBindings" in furniture.PropertiesList:
            furniture.FurnitureBindings = memento.recorded
    recompute_blanks(furniture)
    furniture.Document.recompute()


def vector(point: Vec3) -> App.Vector:
    return App.Vector(point.x, point.y, point.z)


def write_sizes(furniture: DocumentObject, box: Box) -> None:
    """Cotes de ``box`` écrites si elles diffèrent et ne suivent pas une expression."""
    driven = expressions_of(furniture)
    for index, name in enumerate(DIMENSIONS):
        if name not in driven and abs(getattr(furniture, name).Value - box.size(index)) > 0.0:
            setattr(furniture, name, box.size(index))


# --- Recalcul des brutes ----------------------------------------------------------------------


def recompute_blanks(furniture: DocumentObject) -> None:
    """Recalcule les pièces **brutes** de ``furniture`` (et celles de ses sous-ensembles, avec
    leurs cotes et leur Std Part), jamais les usinages : l'aperçu d'un geste. La pièce usinée de
    chaque brute reprend son ``Placement``."""
    for member in members_of(furniture):
        if is_furniture(member):
            member.recompute()
            part = std_part_of(member)
            if part is not None:
                part.recompute()
            recompute_blanks(member)
        elif is_timber(member):
            member.recompute()
            write_placement(member, App.Placement(member.Placement))


def write_std_placement(part: DocumentObject, placement: App.Placement) -> None:
    if part.Placement != placement:
        part.Placement = placement


def changed_sizes(furniture: DocumentObject, box: Box) -> dict[str, float | None]:
    """Cotes de ``box`` qui diffèrent de celles du document (``None`` : inchangée)."""
    found: dict[str, float | None] = {}
    for index, name in enumerate(DIMENSIONS):
        value = box.size(index)
        found[name] = value if abs(getattr(furniture, name).Value - value) > 0.0 else None
    return found
