# SPDX-License-Identifier: LGPL-2.1-or-later
"""Queue d'aronde traversante : queues ajoutées au bout de l'invitée (pièce à queues),
logements enlevés dans l'hôte (pièce à griffes), qu'ils traversent.

L'invitée touche l'hôte par son bout, dessinée à sa longueur visible ; le bout de l'hôte arrive
à fleur de la face extérieure de l'invitée. Calculs dans le repère de l'invitée
(:mod:`._profile`) : plan (largeur ``W``, normale), épaisseur ``e`` ; ``L`` = profondeur de
l'hôte. Chaque queue est un :class:`~.geometry.Prism` (trapèze extrudé sur ``e``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    CUT_OVERRUN_MM,
    JointError,
    PlacedBlock,
    Prism,
    Vec3,
    moved,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    MAX_COUNT,
    JointKind,
    JointPlan,
    angle_param,
    count_param,
    length_param,
    mm_round,
    mm_text,
    validate_params,
)
from freecad.menuiserie.core.joints._profile import THICKNESS_AXIS, ContactFrame, contact_frame

__all__ = [
    "DEFAULT_ANGLE_DEG",
    "MAX_TAIL_COUNT",
    "DovetailParams",
    "DovetailStrategy",
    "DovetailValues",
]

MAX_TAIL_COUNT: Final = MAX_COUNT  # nombre saisi de 0 (automatique) à 50
DEFAULT_ANGLE_DEG: Final = 10.0  # ≈ pente 1:5,7 (feuillus 1:6 à 1:8, résineux 1:5)
MIN_TAIL_BASE_MM: Final = 1.0  # largeur minimale d'une queue à l'épaulement

NOT_FLUSH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Queue d'aronde : la pièce à griffes doit arriver à fleur de la face extérieure de la "
    "pièce à queues.",
)
TOO_NARROW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Queues trop étroites : {count} queues dans {width} mm avec des griffes de {pin} mm et une "
    "angle de {angle} °.",
)


@dataclass(frozen=True)
class DovetailParams:
    """Paramètres de la queue d'aronde ; 0 = automatique pour chacun."""

    tail_count: int = count_param(0)
    pin_width: float = length_param(0.0)  # griffes au plus étroit, face extérieure de l'hôte
    angle: float = angle_param(0.0)  # angle des flancs des queues, en degrés

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class DovetailValues:
    """Valeurs effectives (mm), affichées par le panneau : nombre, griffes, angle (°), largeurs
    des queues et position de chacune côté pointe, le long du contact depuis son bord."""

    tail_count: int
    pin_width: float
    angle: float  # degrés
    tail_width: float  # t : côté pointe (face extérieure de l'hôte)
    tail_base: float  # b : côté épaulement (face intérieure de l'hôte)
    tails: tuple[tuple[float, float], ...]


class DovetailStrategy:
    """Queues de largeur égale entre des griffes de largeur ``p`` côté pointe (griffes des
    bords comprises, droites du côté du bord), flancs inclinés de l'angle choisi ; 3 queues
    environ par largeur de trois épaisseurs."""

    kind: ClassVar[JointKind] = JointKind.DOVETAIL

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: DovetailParams
    ) -> DovetailValues:
        """Valeurs effectives : nombre, griffes, angle et positions des queues."""
        return _values(_through_frame(host, guest), params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: DovetailParams) -> JointPlan:
        """Queues ajoutées à l'invitée, logements traversants enlevés à l'hôte."""
        through = _through_frame(host, guest)
        values = _values(through, params)
        tails = tuple(_tail(through, values, tail, 0.0) for tail in values.tails)
        sockets = tuple(
            moved(_tail(through, values, tail, CUT_OVERRUN_MM), through.frame.to_host)
            for tail in values.tails
        )
        return JointPlan(host_cuts=sockets, guest_additions=tails)


@dataclass(frozen=True)
class _Through:
    """Contact par le bout, vu de l'invitée, et côté de sa face extérieure (là où le bout de
    l'hôte arrive à fleur) : -1 = face basse (Z = 0), +1 = face haute (Z = e)."""

    frame: ContactFrame
    outer_side: int

    @property
    def width(self) -> float:
        """``W`` : étendue du contact selon la largeur de l'invitée."""
        return self.frame.contact_width

    @property
    def thickness(self) -> float:
        """``e`` : épaisseur de l'invitée au contact."""
        return self.frame.contact_thickness

    @property
    def depth(self) -> float:
        """``L`` : profondeur de l'hôte, longueur des queues."""
        return self.frame.contact.host_depth


def _through_frame(host: PlacedBlock, guest: PlacedBlock) -> _Through:
    """Contact par le bout de l'invitée, bout de l'hôte à fleur de sa face extérieure ;
    :class:`JointError` sinon."""
    frame = contact_frame(host, guest, end_only=True)
    guest_low, guest_high = 0.0, guest.dimensions.thickness
    host_low, host_high = frame.host_box.lo(THICKNESS_AXIS), frame.host_box.hi(THICKNESS_AXIS)
    if (
        abs(host_low - guest_low) <= CONTACT_TOLERANCE_MM
        and host_high > guest_high + CONTACT_TOLERANCE_MM
    ):
        return _Through(frame, -1)
    if (
        abs(host_high - guest_high) <= CONTACT_TOLERANCE_MM
        and host_low < guest_low - CONTACT_TOLERANCE_MM
    ):
        return _Through(frame, 1)
    raise JointError(NOT_FLUSH, {})


def _values(through: _Through, params: DovetailParams) -> DovetailValues:
    width = through.width
    count = params.tail_count or max(1, math.floor(width / (3 * through.thickness) + 0.5))
    pin = params.pin_width or mm_round(through.depth / 3)
    angle = params.angle or DEFAULT_ANGLE_DEG
    tail_width = (width - (count + 1) * pin) / count
    tail_base = tail_width - 2 * through.depth * math.tan(math.radians(angle))
    if tail_width <= 0 or tail_base < MIN_TAIL_BASE_MM:
        values = {
            "count": str(count),
            "width": mm_text(width),
            "pin": mm_text(pin),
            "angle": mm_text(angle),
        }
        raise JointError(TOO_NARROW, values)
    starts = (pin + i * (tail_width + pin) for i in range(count))
    return DovetailValues(
        tail_count=count,
        pin_width=pin,
        angle=angle,
        tail_width=tail_width,
        tail_base=tail_base,
        tails=tuple((start, start + tail_width) for start in starts),
    )


def _tail(
    through: _Through, values: DovetailValues, tail: tuple[float, float], overrun: float
) -> Prism:
    """Queue (``overrun`` = 0) ou logement prolongé de ``overrun`` hors de la matière de l'hôte
    (faces intérieure et extérieure, face extérieure de l'invitée), repère de l'invitée.

    Trapèze dans le plan (largeur, normale) : ``tail`` côté pointe (à ``L`` de l'épaulement),
    rétréci de ``L tan(angle)`` de chaque côté à l'épaulement ; flancs prolongés dans le
    dépassement. Extrudé sur l'épaisseur."""
    frame = through.frame
    depth = through.depth
    origin = frame.contact.rectangle.lo(frame.width_axis)
    low = 0.0 if through.outer_side > 0 else -overrun
    high = through.thickness + (overrun if through.outer_side > 0 else 0.0)

    def corner(across: float, along: float) -> Vec3:
        """Sommet à ``across`` du bord du contact, ``along`` de l'épaulement vers l'hôte."""
        point = Vec3(0.0, 0.0, low)
        point = point.with_component(frame.width_axis, origin + across)
        return point.with_component(frame.normal, frame.guest_plane + frame.sign * along)

    flank = math.tan(math.radians(values.angle))  # retrait par unité de profondeur

    def inset(along: float) -> float:
        return (depth - along) * flank

    first, last = tail
    near, far = -overrun, depth + overrun
    points = (
        corner(first + inset(near), near),
        corner(last - inset(near), near),
        corner(last - inset(far), far),
        corner(first + inset(far), far),
    )
    return Prism(points, Vec3(0.0, 0.0, high - low))
