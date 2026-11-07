# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fonctions utilitaires pour les faux tenons et biscuits.

Ce module contient les fonctions de validation et de calcul utilisées par
les stratégies d'assemblage par mortaises plates.
"""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, JointError
from freecad.menuiserie.core.i18n import mm_text
from freecad.menuiserie.core.joints._profile import ContactFrame
from freecad.menuiserie.core.joints._slot_shapes import half_stadium, rounded_rectangle
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT, positions

from ._params import (
    MIN_WALL_MM,
    MIN_BOTTOM_MM,
    AUTO_EDGE_MM,
    AUTO_SPACING_MM,
    TOO_THIN,
    TOO_DEEP,
    DOES_NOT_FIT,
    SlotValues,
)


def _extent(frame: ContactFrame, values: SlotValues, role: str) -> tuple[float, float, float]:
    """Calcule l'origine, le sens et la longueur du logement.

    Pour chaque rôle :
    - host : s'enfoncent de la moitié de la pièce rapportée plus le jeu de fond
    - guest : même chose que host
    - insert : la pièce rapportée traverse de part et d'autre du plan de contact

    Args:
        frame: Le cadre de contact
        values: Les valeurs calculées
        role: Rôle ('host', 'guest' ou 'insert')

    Returns:
        tuple[float, float, float]: (origine, direction, longueur)
    """
    reach = values.half_depth
    plane = frame.guest_plane
    sign = frame.sign

    if role == "host":
        return frame.host_near, sign, reach + values.hole_clearance

    if role == "guest":
        return plane, -sign, reach + values.hole_clearance

    # role == "insert"
    return plane - sign * reach, sign, 2 * reach


def _point(frame: ContactFrame, across: float, level: float, normal: float) -> "Vec3":
    """Crée un point dans le repère de l'invitée.

    Args:
        frame: Le cadre de contact
        across: Position selon la largeur du contact
        level: Position selon l'épaisseur
        normal: Position selon la normale du contact

    Returns:
        Vec3: Le point créé
    """
    from freecad.menuiserie.core.geometry import Vec3

    point = Vec3(0.0, 0.0, 0.0).with_component(frame.width_axis, across)
    return point.with_component(frame.thickness_axis, level).with_component(frame.normal, normal)


def _fits(frame: ContactFrame, size: "SlotSize", shortest: float, clearance: float) -> bool:
    """Vérifie si une taille tient dans l'épaisseur et dans la plus mince des deux pièces.

    Args:
        frame: Le cadre de contact
        size: La taille à vérifier
        shortest: Épaisseur de la plus fine des deux pièces
        clearance: Jeu de fond

    Returns:
        bool: True si la taille tient, False sinon
    """
    wall = size.thickness / 2 + MIN_WALL_MM
    return (
        frame.contact_thickness >= 2 * wall
        and shortest - (size.total_depth / 2 + clearance) >= MIN_BOTTOM_MM
        and frame.contact_width >= size.along + 2 * MIN_WALL_MM
    )


def _auto_count(width: float, edge: float, along: float) -> int:
    """Calcule le nombre automatique de mortaises.

    Une mortaise sur un contact étroit, sinon assez pour qu'elles soient espacées
    de 150 mm au plus entre centres (le premier et le dernier à ``edge`` des bords).

    Args:
        width: Largeur du contact
        edge: Distance au bord
        along: Longueur d'une mortaise

    Returns:
        int: Nombre de mortaises (1 à MAX_DOWEL_COUNT)
    """
    span = width - 2 * edge
    if span <= along:
        return 1
    return min(MAX_DOWEL_COUNT, max(2, math.ceil(span / AUTO_SPACING_MM) + 1))


def _check_section(frame: ContactFrame, values: SlotValues) -> None:
    """Vérifie que la section de la mortaise tient dans l'épaisseur du contact.

    Args:
        frame: Le cadre de contact
        values: Les valeurs calculées

    Raises:
        JointError: Si les pièces sont trop minces
    """
    room = frame.contact_thickness / 2 - values.thickness / 2 - abs(values.thickness_offset)
    if room < MIN_WALL_MM - CONTACT_TOLERANCE_MM:
        text = {
            "thickness": mm_text(values.thickness),
            "contact_thickness": mm_text(frame.contact_thickness),
            "wall": mm_text(MIN_WALL_MM),
        }
        raise JointError(TOO_THIN, text)


def _check_depths(frame: ContactFrame, guest: "PlacedBlock", values: SlotValues) -> None:
    """Vérifie que les mortaises ne sont pas trop profondes.

    Args:
        frame: Le cadre de contact
        guest: La pièce invitée
        values: Les valeurs calculées

    Raises:
        JointError: Si les mortaises sont trop profondes
    """
    hole = values.half_depth + values.hole_clearance
    extents = (frame.contact.host_depth, guest.local_box().size(frame.normal))

    for extent in extents:
        if extent - hole < MIN_BOTTOM_MM - CONTACT_TOLERANCE_MM:
            text = {
                "depth": mm_text(hole),
                "extent": mm_text(extent),
                "bottom": mm_text(MIN_BOTTOM_MM),
            }
            raise JointError(TOO_DEEP, text)


def _check_spacing(frame: ContactFrame, values: SlotValues) -> None:
    """Vérifie que les mortaises sont correctement espacées.

    Vérifie que :
    1. Les mortaises ne dépassent pas des bords du contact
    2. Les mortaises sont suffisamment espacées entre elles

    Args:
        frame: Le cadre de contact
        values: Les valeurs calculées

    Raises:
        JointError: Si l'espacement est incorrect
    """
    half = values.along / 2
    width = frame.contact_width
    first, last = values.positions[0], values.positions[-1]

    # Vérifier que les mortaises sont à l'intérieur du contact
    inside = first - half > -CONTACT_TOLERANCE_MM and width - last - half > -CONTACT_TOLERANCE_MM

    # Vérifier l'espacement entre les mortaises
    gaps = [b - a for a, b in zip(values.positions, values.positions[1:], strict=False)]
    apart = all(gap > values.along + CONTACT_TOLERANCE_MM for gap in gaps)

    if not (inside and apart):
        text = {
            "count": str(values.count),
            "along": mm_text(values.along),
            "width": mm_text(width),
            "edge": mm_text(values.edge_distance),
        }
        raise JointError(DOES_NOT_FIT, text)
