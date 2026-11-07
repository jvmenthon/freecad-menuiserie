# SPDX-License-Identifier: LGPL-2.1-or-later
"""Paramètres et valeurs pour le perçage LR32 et taquets de tablette.

Ce module contient les dataclasses de paramètres et de valeurs, ainsi que les constantes
utilisées pour le perçage LR32.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    choice_param,
    count_param,
    derived_param,
    flag_param,
    length_param,
    validate_params,
)

# Constantes de sécurité et valeurs par défaut (mm)
MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond d'un trou
MIN_WALL_MM: Final = 2.0  # matière entre deux trous : pas ≥ diamètre + 2 mm
AUTO_EDGE_MM: Final = 37.0  # distance des colonnes aux bouts horizontaux, par défaut
AUTO_MARGIN_MM: Final = 64.0  # distance du premier/dernier trou aux bouts verticaux
AUTO_DIAMETER_MM: Final = 5.0
AUTO_DEPTH_MM: Final = 12.0
FACES: Final = ("auto", "plus", "minus")  # face percée : intérieure, +Z ou -Z du côté

# Messages d'erreur internationalisés
BAD_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le pas et la saillie des taquets doivent être strictement positifs."
)
HOLE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Trou de {depth} mm trop profond pour un côté de {thickness} mm : "
    "il faut laisser {bottom} mm de matière.",
)
TOO_SHORT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le côté est trop petit pour {rows} rangs de trous au pas de {pitch} mm, "
    "à {margin} mm des bouts et {edge} mm des bords.",
)
PITCH_TOO_SMALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pas de {pitch} mm trop petit pour des trous de {diameter} mm : "
    "il faut au moins {minimum} mm.",
)
NO_SUCH_ROW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le taquet est prévu au rang {row} mais il n'y a que {rows} rangs de trous."
)


@dataclass(frozen=True)
class ShelfPinsParams:
    """Paramètres du perçage et des taquets (mm) ; 0 = automatique.

    ``neighbors`` et ``guest_neighbors`` ne sont pas des réglages : les pièces du document
    autour du côté (et du montant opposé), qui bornent la zone percée et reçoivent des taquets.

    Attributes:
        hole_diameter: Diamètre des trous (0 = automatique = 5 mm)
        hole_depth: Profondeur des trous (0 = automatique = 12 mm)
        pitch: Pas entre les trous (32 mm par défaut)
        edge_distance: Distance des colonnes aux bouts horizontaux (0 = auto = 37 mm)
        end_margin: Marge aux extrémités verticales (0 = auto = 64 mm)
        rows: Nombre de rangs de trous (0 = automatique)
        with_pins: Si vrai, génère des taquets
        pin_row: Rang pour les taquets (0 = un rang sous chaque tablette)
        pin_projection: Saillie des taquets (7 mm par défaut)
        face: Face à percer ('auto', 'plus', 'minus')
        zone_height: Hauteur de la zone à percer depuis le bas
        both_sides: Si vrai, perce aussi le montant opposé en miroir
        neighbors: Pièces voisines du côté (calculé automatiquement)
        guest_neighbors: Pièces voisines du montant opposé (calculé automatiquement)
    """

    hole_diameter: float = length_param(0.0)  # 5
    hole_depth: float = length_param(0.0)  # 12
    pitch: float = length_param(32.0)
    edge_distance: float = length_param(0.0)  # colonnes aux bouts horizontaux : 37 mm
    end_margin: float = length_param(0.0)  # trou le plus proche d'une pièce : 64 mm
    rows: int = count_param(0)  # 0 = autant de rangs que la zone libre en reçoit
    with_pins: bool = flag_param(True)
    pin_row: int = count_param(0)  # 0 = un rang sous chaque tablette ; sinon rang depuis le bas
    pin_projection: float = length_param(7.0)  # saillie du taquet hors de la face
    face: str = choice_param("auto", FACES)
    zone_height: float = length_param(0.0)  # hauteur (depuis le bas) dans la zone à percer
    both_sides: bool = flag_param(True)  # percer aussi le montant opposé (guest) en miroir
    neighbors: tuple = derived_param(())
    guest_neighbors: tuple = derived_param(())  # autour du montant opposé

    def __post_init__(self) -> None:
        """Validation des paramètres après initialisation."""
        validate_params(self)
        if min(self.pitch, self.pin_projection) <= 0:
            raise JointError(BAD_VALUE, {})


@dataclass(frozen=True)
class ShelfPinsValues:
    """Valeurs effectives du perçage (mm), affichées par le panneau.

    Attributes:
        hole_diameter: Diamètre effectif des trous
        hole_depth: Profondeur effective des trous
        pitch: Pas effectif entre les trous
        edge_distance: Distance effective des colonnes aux bords
        end_margin: Marge effective aux extrémités
        rows: Nombre effectif de rangs de trous
        pin_row: Premier rang de taquets depuis le bas (1-indexé)
        pin_projection: Saillie effective des taquets
        with_pins: Si des taquets sont générés
        pin_rows: Rangs (0-indexés) qui portent des taquets
        heights: Hauteur de chaque rang depuis le bas du côté
        face: Face percée ('plus' ou 'minus')
        zone_height: Milieu de la zone percée depuis le bas
        zone: Zone libre (min, max) depuis le bas
        opposite_pins: Nombre de taquets du montant opposé
        opposite_holes: Nombre de trous du montant opposé
    """

    hole_diameter: float
    hole_depth: float
    pitch: float
    edge_distance: float
    end_margin: float
    rows: int
    pin_row: int  # premier rang de taquets depuis le bas (1 : le plus bas), 0 : aucun
    pin_projection: float
    with_pins: bool
    pin_rows: tuple[int, ...] = ()  # rangs (depuis 0) qui portent des taquets
    heights: tuple[float, ...] = ()  # hauteur de chaque rang depuis le bas du côté
    face: str = "plus"  # face percée : « plus » (+Z du côté) ou « minus » (-Z)
    zone_height: float = 0.0  # milieu de la zone percée, depuis le bas du côté
    zone: tuple[float, float] = (0.0, 0.0)  # zone libre (entre pièces assemblées), depuis le bas
    opposite_pins: int = 0  # taquets du montant opposé
    opposite_holes: int = 0  # trous du montant opposé

    @property
    def count(self) -> int:
        """Nombre de taquets (un par colonne dans chaque rang choisi, montant opposé compris)."""
        return 2 * len(self.pin_rows) + self.opposite_pins

    @property
    def hole_count(self) -> int:
        """Nombre de trous percés (montant opposé compris)."""
        return 2 * self.rows + self.opposite_holes

    def pin_top(self, row: int) -> float:
        """Hauteur du dessus du taquet du rang ``row`` (où repose le dessous de la tablette)."""
        return self.heights[row] + self.hole_diameter / 2
