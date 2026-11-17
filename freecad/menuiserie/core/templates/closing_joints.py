# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages du gabarit « Fermer le caisson » (ADR 0064, spécification § 5).

Un seul assemblage pour tous les angles des côtés (``ClosingJoinery``) et un pour le fond mince
(``BackJoinery``), chacun produit par une fonction de sa famille (Strategy : un constructeur de
paramètres par type, pas de chaîne de ``if``). Les paramètres sont ceux des stratégies de J3
(``DowelParams``, ``DovetailParams``…), déjà validés.

Rôles (l'hôte reçoit, l'invitée touche par son bout) : au contact côté ↔ ancre ou pièce
opposée, le côté est l'invitée ; l'avant et le fond épais sont les invitées des côtés. L'onglet
n'existe qu'entre un côté et l'ancre ou la pièce opposée (le côté chevauche leur bout) : l'avant
et le fond épais restent alors sans assemblage.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Final

from freecad.menuiserie.core.joints import JointKind, mm_round
from freecad.menuiserie.core.joints.dovetail import DovetailParams
from freecad.menuiserie.core.joints.dowels import MIN_BOTTOM_MM, DowelParams, auto_diameter
from freecad.menuiserie.core.joints.miter import MiterParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from freecad.menuiserie.core.templates import JointSpec
from freecad.menuiserie.core.templates.closing_params import (
    GROOVE_SETBACK_MM,
    BackJoinery,
    ClosingJoinery,
    ClosingParams,
    Element,
)

__all__ = ["back_reserve", "joint_specs"]

HOLE_CLEARANCE_MM: Final = 1.0  # jeu de fond du perçage (valeur par défaut de ``DowelParams``)
ANCHOR: Final = "anchor"
OPPOSITE: Final = Element.OPPOSITE.value
SIDES: Final = (Element.LEFT.value, Element.RIGHT.value)
_Pair = tuple[str, str]  # (clé de l'hôte, clé de l'invitée)


def back_reserve(params: ClosingParams) -> float:
    """Profondeur (selon Y, depuis l'arrière) que le fond mince occupe contre les côtés : son
    épaisseur, plus son recul dans une rainure ; 0 sans fond mince."""
    if not params.has(Element.BACK) or params.thick_back:
        return 0.0
    if params.back_joinery is BackJoinery.GROOVE:
        return params.back_t + GROOVE_SETBACK_MM
    return params.back_t


def _dowels(guest: float, host: float, reserve: float) -> DowelParams:
    """Tourillons de l'invitée (épaisseur ``guest``) dans l'hôte (épaisseur ``host``) : diamètre
    du commerce d'au plus la moitié de ``guest``, enfoncés des deux tiers de ``guest`` dans
    l'hôte (au plus ``host`` moins le fond et le jeu de perçage), aussi profond que ``guest``
    dans le bout de l'invitée. Distance au bord : 2 Ø, et au moins ``reserve`` + 1 Ø pour que le
    dernier perçage reste à ½ Ø devant le fond (18 mm : Ø 8 x 30, 12 dans l'hôte)."""
    diameter = auto_diameter(guest)
    host_depth = mm_round(min(2 * guest / 3, host - MIN_BOTTOM_MM - HOLE_CLEARANCE_MM))
    return DowelParams(
        diameter=diameter,
        dowel_length=host_depth + mm_round(guest),
        host_depth=host_depth,
        edge_distance=max(2 * diameter, reserve + diameter),
    )


def _rabbet(_guest: float, host: float, _reserve: float) -> RabbetParams:
    """Invitée logée de la moitié de l'épaisseur de l'hôte (profondeur de la feuillure)."""
    return RabbetParams(through=True, depth=mm_round(host / 2))


def _dovetail(_guest: float, _host: float, _reserve: float) -> DovetailParams:
    return DovetailParams()


def _miter(_guest: float, _host: float, _reserve: float) -> MiterParams:
    return MiterParams()


Maker = Callable[[float, float, float], object]
_CORNERS: Final[dict[ClosingJoinery, tuple[JointKind, Maker]]] = {
    ClosingJoinery.DOWELS: (JointKind.DOWELS, _dowels),
    ClosingJoinery.DOVETAIL: (JointKind.DOVETAIL, _dovetail),
    ClosingJoinery.MITER: (JointKind.MITER, _miter),
    ClosingJoinery.RABBET: (JointKind.RABBET, _rabbet),
}


def _thickness(params: ClosingParams, key: str) -> float:
    """Épaisseur de la pièce de clé ``key``."""
    if key == ANCHOR:
        return params.anchor.thickness
    return params.opposite_t if key == OPPOSITE else params.side_t


def _panels(params: ClosingParams) -> list[str]:
    """Pièces que les côtés touchent par leur bout : l'ancre, et la pièce opposée si elle existe."""
    return [ANCHOR, *([OPPOSITE] if params.has(Element.OPPOSITE) else [])]


def _corner_pairs(params: ClosingParams) -> Iterator[_Pair]:
    """(hôte, invitée) de chaque angle : côté ↔ ancre ou pièce opposée, puis, sauf en onglet,
    avant et fond épais ↔ côtés."""
    sides = [key for key in SIDES if params.has(Element(key))]
    for side in sides:
        for panel in _panels(params):
            yield panel, side
    if params.joinery is ClosingJoinery.MITER:
        return
    between = [Element.FRONT.value] * params.has(Element.FRONT)
    between += [Element.BACK.value] * (params.has(Element.BACK) and params.thick_back)
    for guest in between:
        for side in sides:
            yield side, guest


def _corner_joints(params: ClosingParams) -> list[JointSpec]:
    if params.joinery is ClosingJoinery.NONE:
        return []
    kind, maker = _CORNERS[params.joinery]
    reserve = back_reserve(params)
    return [
        JointSpec(
            kind,
            host,
            guest,
            maker(_thickness(params, guest), _thickness(params, host), reserve),
        )
        for host, guest in _corner_pairs(params)
    ]


def _back_hosts(params: ClosingParams) -> list[str]:
    sides = [key for key in SIDES if params.has(Element(key))]
    return [*sides, *_panels(params)]


def _groove(params: ClosingParams) -> TongueGrooveParams:
    """Languette du fond au tiers de son épaisseur, longue de 10 mm au plus (la moitié de la plus
    mince des pièces rainurées), rainure arrêtée : le fond est reculé de ``GROOVE_SETBACK_MM``."""
    thinnest = min(_thickness(params, host) for host in _back_hosts(params))
    return TongueGrooveParams(tongue_length=min(10.0, mm_round(thinnest / 2)), through_groove=False)


def _back_joints(params: ClosingParams) -> list[JointSpec]:
    if not params.has(Element.BACK) or params.thick_back:
        return []
    if params.back_joinery is BackJoinery.RABBET:
        rabbet = RabbetParams(through=True)
        return [JointSpec(JointKind.RABBET, host, "back", rabbet) for host in _back_hosts(params)]
    if params.back_joinery is BackJoinery.GROOVE:
        groove = _groove(params)
        return [
            JointSpec(JointKind.TONGUE_GROOVE, host, "back", groove) for host in _back_hosts(params)
        ]
    return []


def joint_specs(params: ClosingParams) -> tuple[JointSpec, ...]:
    """Assemblages des angles puis du fond, dans l'ordre du gabarit."""
    return (*_corner_joints(params), *_back_joints(params))
