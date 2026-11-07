# SPDX-License-Identifier: LGPL-2.1-or-later
"""Calcul du layout pour les coulisses de tiroir.

Ce module contient les fonctions de calcul de la disposition des côtés
et des dimensions effectives des coulisses.
"""

from __future__ import annotations

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Axis,
    Box,
    JointError,
    PlacedBlock,
    RigidTransform,
    moved_box,
    relative_axes,
    relative_transform,
)
from freecad.menuiserie.core.i18n import mm_text

from ._params import SlideParams, SlideValues, NO_GAP, NO_OVERLAP, TOO_SHORT, TOO_LONG, TOO_LOW
from ._drilling import _holes


def _frame(host: PlacedBlock, guest: PlacedBlock) -> "_Frame":
    """Calcule le cadre de référence entre les deux côtés.

    Détermine l'axe qui sépare les deux côtés (axe normal) et vérifie que
    les côtés sont bien face à face (et non de chant ou de bout).

    Args:
        host: Le côté du caisson
        guest: Le côté du tiroir

    Returns:
        _Frame: Le cadre de référence avec axe normal, plans, et recouvrement

    Raises:
        JointError: Si les côtés se chevauchent trop ou ne se font pas face
    """
    from ._params import _Frame

    relative_axes(host, guest)  # JointError si les pièces ne sont pas d'équerre

    to_host = relative_transform(host, guest)
    host_box = host.local_box()
    guest_box = moved_box(guest.local_box(), to_host)

    # Calcul des écarts selon chaque axe
    gaps = [
        (max(guest_box.lo(i) - host_box.hi(i), host_box.lo(i) - guest_box.hi(i)), i)
        for i in range(3)
    ]

    # Trouver l'axe de séparation (où les côtés sont face à face)
    separated = [item for item in gaps if item[0] > CONTACT_TOLERANCE_MM]

    if separated:
        # Côtés face à face : l'axe de plus petit écart
        _gap, index = min(separated)
    else:
        # Côtés qui se touchent ou se chevauchent : l'axe de moindre pénétration
        gap, index = max(gaps)
        if -gap >= min(host_box.size(index), guest_box.size(index)) - CONTACT_TOLERANCE_MM:
            raise JointError(NO_GAP, {"gap": mm_text(gap)})

    # Déterminer si guest est au-dessus (+) ou en dessous (-) de host
    above = guest_box.center(index) > host_box.center(index)

    return _facing(index, above, host_box, guest_box, to_host)


def _facing(
    index: int,
    above: bool,
    host_box: Box,
    guest_box: Box,
    to_host: RigidTransform,
) -> "_Frame":
    """Calcule le cadre de référence pour des côtés face à face.

    Args:
        index: Axe normal (qui traverse le jeu)
        above: Si vrai, guest est du côté positif de host
        host_box: Boîte de l'hôte
        guest_box: Boîte de l'invité
        to_host: Transformation de guest vers host

    Returns:
        _Frame: Le cadre de référence complet

    Raises:
        JointError: Si les côtés ne se recouvrent pas suffisamment
    """
    from ._params import _Frame

    # Les deux autres axes (parallèles aux faces)
    others = [i for i in range(3) if i != index]
    ranges = {}

    # Calcul du recouvrement sur chaque axe parallèle
    for other in others:
        low = max(host_box.lo(other), guest_box.lo(other))
        high = min(host_box.hi(other), guest_box.hi(other))
        if high - low <= CONTACT_TOLERANCE_MM:
            raise JointError(NO_OVERLAP, {})
        ranges[other] = (low, high)

    # Déterminer l'axe de longueur (le plus long recouvrement)
    length_axis = max(others, key=lambda i: ranges[i][1] - ranges[i][0])
    height_axis = next(i for i in others if i != length_axis)

    # Boîte de recouvrement
    overlap = Box.from_ranges([ranges.get(i, (host_box.lo(i), host_box.hi(i))) for i in range(3)])

    # Déterminer les plans de l'hôte et de l'invité
    if above:
        host_plane, guest_plane, sign = host_box.hi(index), guest_box.lo(index), 1
    else:
        host_plane, guest_plane, sign = host_box.lo(index), guest_box.hi(index), -1

    return _Frame(
        normal=index,
        sign=sign,
        host_plane=host_plane,
        guest_plane=guest_plane,
        length_axis=length_axis,
        height_axis=height_axis,
        overlap=overlap,
        to_guest=to_host.inverse(),
        guest_extent=guest_box.size(index),
    )


def _values(frame: "_Frame", params: SlideParams) -> SlideValues:
    """Calcule les valeurs effectives de la coulisse.

    Args:
        frame: Le cadre de référence
        params: Les paramètres de la coulisse

    Returns:
        SlideValues: Les valeurs calculées

    Raises:
        JointError: Si les dimensions ne sont pas valides
    """
    from freecad.menuiserie.core.i18n import mm_text
    from ._params import SLIDE_LENGTHS, AUTO_HOLE_COUNT, MIN_BOTTOM_MM

    # Calcul du jeu entre les côtés
    gap = frame.sign * (frame.guest_plane - frame.host_plane)

    # Largeur du recouvrement
    span = frame.overlap.size(frame.length_axis)

    # Espace disponible pour la coulisse
    room = span - params.front_setback

    # Longueur de la coulisse
    if params.length:
        length = params.length
    else:
        # Trouver la plus grande coulisse du commerce qui tient
        fitting = [size for size in SLIDE_LENGTHS if size <= room + CONTACT_TOLERANCE_MM]
        if not fitting:
            raise JointError(TOO_SHORT, {"overlap": mm_text(span)})
        length = fitting[-1]

    # Vérifier que la coulisse n'est pas trop longue
    if length > room + CONTACT_TOLERANCE_MM:
        text = {
            "length": mm_text(length),
            "overlap": mm_text(span),
            "setback": mm_text(params.front_setback),
        }
        raise JointError(TOO_LONG, text)

    # Hauteur disponible
    height = frame.overlap.size(frame.height_axis)

    # Position verticale de la coulisse
    low = height / 2 + params.height_offset - params.slide_height / 2

    # Vérifier que la coulisse tient en hauteur
    if low < -CONTACT_TOLERANCE_MM or low + params.slide_height > height + CONTACT_TOLERANCE_MM:
        text = {"height": mm_text(params.slide_height), "overlap": mm_text(height)}
        raise JointError(TOO_LOW, text)

    # Nombre de trous
    count = params.hole_count or AUTO_HOLE_COUNT

    return SlideValues(
        length=length,
        gap=gap,
        thickness=params.thickness,
        hole_count=count,
        hole_positions=_holes(length, count),
        direction=Axis.of(frame.normal, frame.sign),
    )
