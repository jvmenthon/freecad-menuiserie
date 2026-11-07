# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits : mortaises plates dans les deux pièces, pièce rapportée entre elles.

Un faux tenon (type Domino) et un biscuit (lamelle) partagent le même plan d'usinage : logements
répartis le long de la largeur du contact, la pièce rapportée traversant de moitié chaque pièce
(ADR 0033). Leurs formes sont celles du commerce : le faux tenon a une section en stade (bouts
demi-ronds, comme les Domino de Festool) extrudée dans la profondeur ; le biscuit est un stade
dans le plan du joint (comme les lamelles de Lamello), de l'épaisseur de la fente. La taille se
choisit dans la liste du commerce (Festool, Lamello) ; seul le faux tenon accepte une taille
personnalisée. Calculs dans le repère de l'invitée (:mod:`._profile`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    choice_param,
    count_param,
    flag_param,
    length_param,
    offset_param,
    validate_params,
)

MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond de chaque logement
AUTO_EDGE_MM: Final = 50.0  # centre de la première mortaise au bord du contact (usage courant)
AUTO_SPACING_MM: Final = 150.0  # écart maximal entre deux mortaises (100 à 150 mm, usage courant)
AUTO_SIZE: Final = "auto"  # taille : la plus grande du commerce qui tient dans les pièces

TOO_THIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièces trop minces pour une mortaise de {thickness} mm : {contact_thickness} mm "
    "d'épaisseur au contact, il faut {wall} mm de matière de chaque côté.",
)
NO_SIZE_FITS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Aucune taille du commerce ne tient dans ces pièces ({contact_thickness} mm d'épaisseur, "
    "{depth} mm de profondeur au plus) : saisissez une taille plus petite.",
)
TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Logement de {depth} mm trop profond pour une pièce de {extent} mm : il faut laisser au "
    "moins {bottom} mm de fond.",
)
UNKNOWN_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Taille « {size} » inconnue pour cet assemblage (tailles : {sizes})."
)
DOES_NOT_FIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} mortaises de {along} mm ne tiennent pas sur un contact de {width} mm "
    "(distance au bord {edge} mm).",
)


@dataclass(frozen=True)
class SlotSize:
    """Taille d'une pièce rapportée du commerce (mm) : identifiant dans la liste, épaisseur,
    longueur le long du joint, pénétration totale à travers le joint."""

    id: str
    thickness: float
    along: float
    total_depth: float


LOOSE_TENON_SIZES: Final = (  # Festool Domino, du plus petit au plus grand
    SlotSize("4x20", 4.0, 16.6, 20.0),
    SlotSize("5x30", 5.0, 19.0, 30.0),
    SlotSize("6x40", 6.0, 20.0, 40.0),
    SlotSize("8x40", 8.0, 22.0, 40.0),
    SlotSize("8x50", 8.0, 22.0, 50.0),
    SlotSize("10x50", 10.0, 24.0, 50.0),
)
BISCUIT_SIZES: Final = (  # lamelles Lamello n° 0, 10 et 20 (fente de 4 mm)
    SlotSize("0", 4.0, 47.0, 15.0),
    SlotSize("10", 4.0, 53.0, 19.0),
    SlotSize("20", 4.0, 56.0, 23.0),
)
_SIZE_IDS: Final = (
    AUTO_SIZE,
    *(size.id for size in LOOSE_TENON_SIZES),
    *(size.id for size in BISCUIT_SIZES),
)


@dataclass(frozen=True)
class SlotParams:
    """Paramètres des mortaises plates (mm) ; 0 = automatique.

    ``size`` : taille de la liste du commerce (``auto`` : la plus grande qui tient). Les cotes
    ``thickness``, ``along`` et ``total_depth`` ne valent que pour le faux tenon à taille
    personnalisée (``custom_size``)."""

    size: str = choice_param(AUTO_SIZE, _SIZE_IDS)
    custom_size: bool = flag_param(False)
    thickness: float = length_param(0.0)
    along: float = length_param(0.0)
    total_depth: float = length_param(0.0)
    count: int = count_param(0)
    edge_distance: float = length_param(0.0)
    thickness_offset: float = offset_param(0.0)
    hole_clearance: float = length_param(1.0)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class SlotValues:
    """Valeurs effectives des mortaises (mm), affichées par le panneau."""

    thickness: float
    along: float
    total_depth: float
    count: int
    edge_distance: float
    thickness_offset: float
    hole_clearance: float
    positions: tuple[float, ...]  # centres le long du contact, depuis son bord
    size: str = AUTO_SIZE  # taille choisie dans la liste du commerce (vide : personnalisée)
    custom_size: bool = False  # taille personnalisée en vigueur
    custom_allowed: bool = False  # le type d'assemblage accepte une taille personnalisée

    @property
    def half_depth(self) -> float:
        """Pénétration de la pièce rapportée dans chaque pièce."""
        return self.total_depth / 2
