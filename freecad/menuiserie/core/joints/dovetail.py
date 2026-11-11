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
    flag_param,
    length_param,
    mm_round,
    mm_text,
    validate_params,
)
from freecad.menuiserie.core.joints._dovetail_oblique import oblique_dovetail_plan
from freecad.menuiserie.core.joints._oblique_frame import Frame, ObliqueFrame, profile_frame
from freecad.menuiserie.core.joints._profile import THICKNESS_AXIS, ContactFrame

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
TILTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Queue d'aronde en biais : les deux pièces doivent pivoter autour de leur épaisseur.",
)
_PARALLEL: Final = 1e-6
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
    # Queues sur la pièce hôte (issue #85) : l'invitée est prolongée de ses griffes jusqu'à l'angle.
    tails_on_host: bool = flag_param(False)

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
        if isinstance(through.frame, ObliqueFrame):
            spans = _pin_spans(through, values) if params.tails_on_host else None
            return oblique_dovetail_plan(through.frame, through.outer_side, values, spans)
        if params.tails_on_host:
            return _host_tails_plan(through, values)
        tails = tuple(_tail(through, values, tail, 0.0) for tail in values.tails)
        sockets = tuple(
            moved(_tail(through, values, tail, CUT_OVERRUN_MM), through.square.to_host)
            for tail in values.tails
        )
        return through.square.bridge.plan(JointPlan(host_cuts=sockets, guest_additions=tails))


@dataclass(frozen=True)
class _Through:
    """Contact par le bout, vu de l'invitée, et côté de sa face extérieure (là où le bout de
    l'hôte arrive à fleur) : -1 = face basse (Z = 0), +1 = face haute (Z = e)."""

    frame: Frame
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

    @property
    def square(self) -> ContactFrame:
        """Cadre d'équerre (les fonctions qui ne savent pas le biais)."""
        if not isinstance(self.frame, ContactFrame):
            raise TypeError("cadre d'équerre attendu")
        return self.frame

    @property
    def axis_depth(self) -> float:
        """Profondeur de l'hôte mesurée sur l'axe de l'invitée (``L`` en équerre) : ce que les
        flancs d'une queue en biais parcourent."""
        frame = self.frame
        return self.depth / frame.cosine if isinstance(frame, ObliqueFrame) else self.depth


def _through_frame(host: PlacedBlock, guest: PlacedBlock) -> _Through:
    """Contact par le bout de l'invitée, bout de l'hôte à fleur de sa face extérieure ;
    :class:`JointError` sinon."""
    frame = profile_frame(host, guest, end_only=True)
    guest_low, guest_high = 0.0, frame.guest.dimensions.thickness
    host_low, host_high = frame.host_box.lo(THICKNESS_AXIS), frame.host_box.hi(THICKNESS_AXIS)
    if isinstance(frame, ObliqueFrame):
        host_low, host_high = _host_levels(frame)
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


def _host_levels(frame: ObliqueFrame) -> tuple[float, float]:
    """Niveaux de l'hôte selon l'épaisseur de l'invitée ; :class:`JointError` si les pièces ne
    pivotent pas autour de leur épaisseur."""
    to_guest = frame.contact.transform.inverse()
    thickness = frame.contact.transform.rotate(Vec3(0.0, 0.0, 1.0))  # épaisseur de l'invitée
    if max(abs(thickness.component(i)) for i in range(3)) < 1.0 - _PARALLEL:
        raise JointError(TILTED, {})
    box = frame.host_box
    levels = [
        to_guest.apply(Vec3(x, y, z)).z
        for x in (box.lo(0), box.hi(0))
        for y in (box.lo(1), box.hi(1))
        for z in (box.lo(2), box.hi(2))
    ]
    return min(levels), max(levels)


def _values(through: _Through, params: DovetailParams) -> DovetailValues:
    width = through.width
    # Nombre et griffes automatiques d'après la plus mince des deux pièces : inverser l'assemblage
    # (hôte et invitée échangés) ne les change pas.
    reference = min(through.thickness, through.depth)
    count = params.tail_count or max(1, math.floor(width / (3 * reference) + 0.5))
    # Les flancs se rétrécissent sur la profondeur des queues : celle de l'hôte, ou, quand les
    # queues sont sur l'hôte, l'épaisseur de l'invitée.
    depth = through.thickness if params.tails_on_host else through.axis_depth
    pin = params.pin_width or mm_round(reference / 3)
    angle = params.angle or DEFAULT_ANGLE_DEG
    tail_width = (width - (count + 1) * pin) / count
    tail_base = tail_width - 2 * depth * math.tan(math.radians(angle))
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
    frame = through.square
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


def _host_tails_plan(through: _Through, values: DovetailValues) -> JointPlan:
    """Queues sur l'hôte : l'invitée est prolongée de ses griffes jusqu'à l'angle (ajoutées à
    l'invitée) et l'hôte les perd (logements), les queues restant la matière de l'hôte.

    Griffes dans le plan (largeur, épaisseur de l'invitée), extrudées sur la profondeur de
    l'hôte : ``pin_width`` sur la face extérieure, élargies de ``e tan(angle)`` de chaque côté sur
    la face intérieure ; les griffes des bords sont droites du côté du bord."""
    pins = tuple(_pin(through, values, span, 0.0) for span in _pin_spans(through, values))
    sockets = tuple(
        moved(_pin(through, values, span, CUT_OVERRUN_MM), through.square.to_host)
        for span in _pin_spans(through, values)
    )
    return through.square.bridge.plan(JointPlan(host_cuts=sockets, guest_additions=pins))


def _pin_spans(through: _Through, values: DovetailValues) -> tuple[tuple[float, float], ...]:
    """Griffes (début, fin) côté face extérieure : entre les queues et jusqu'aux bords."""
    edges = [0.0]
    for first, last in values.tails:
        edges += [first, last]
    edges.append(through.width)
    return tuple((edges[i], edges[i + 1]) for i in range(0, len(edges), 2))


def _pin(
    through: _Through, values: DovetailValues, span: tuple[float, float], overrun: float
) -> Prism:
    """Griffe extrudée sur la profondeur de l'hôte (``overrun`` de part et d'autre pour un
    logement, et vers l'extérieur de la face extérieure), repère de l'invitée."""
    frame = through.square
    origin = frame.contact.rectangle.lo(frame.width_axis)
    flank = math.tan(math.radians(values.angle))
    thickness = through.thickness
    outward = -1.0 if through.outer_side < 0 else 1.0
    outer = 0.0 if through.outer_side < 0 else thickness
    inner = thickness if through.outer_side < 0 else 0.0
    first, last = span
    edge_first, edge_last = first == 0.0, last == through.width

    def point(across: float, level: float) -> Vec3:
        base = Vec3(0.0, 0.0, level).with_component(frame.width_axis, origin + across)
        return base.with_component(frame.normal, frame.guest_plane - frame.sign * overrun)

    reach = thickness * flank  # élargissement de la griffe entre la face extérieure et l'intérieure
    spill = overrun * flank  # prolongement du flanc au-delà de la face extérieure
    out_first = first if edge_first else first + spill
    out_last = last if edge_last else last - spill
    points = (
        point(out_first, outer + outward * overrun),
        point(out_last, outer + outward * overrun),
        point(last if edge_last else last + reach, inner),
        point(first if edge_first else first - reach, inner),
    )
    along = through.depth + 2 * overrun
    return Prism(points, Vec3(0.0, 0.0, 0.0).with_component(frame.normal, frame.sign * along))
