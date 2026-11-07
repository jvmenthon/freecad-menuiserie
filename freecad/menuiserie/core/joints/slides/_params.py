# SPDX-License-Identifier: LGPL-2.1-or-later
"""Paramètres, valeurs et constantes pour les coulisses de tiroir.

Ce module contient les dataclasses et constantes utilisées pour les assemblages
par coulisses de tiroir à billes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    count_param,
    flag_param,
    length_param,
    mm_text,
    offset_param,
    validate_params,
)

# Constantes de dimensionnement (mm)
SLIDE_LENGTHS: Final = (250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0)
FIRST_HOLE_MM: Final = 37.0  # premier trou, depuis l'avant de la coulisse (système 32)
HOLE_STEP_MM: Final = 32.0
MIN_BOTTOM_MM: Final = 3.0
AUTO_HOLE_COUNT: Final = 3
GUEST_PILOT_MM: Final = 3.0  # avant-trou de vis dans le côté du tiroir
GUEST_PILOT_DEPTH_MM: Final = 8.0

# Messages d'erreur internationalisés
NO_GAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les côtés ne se font pas face : ils se chevauchent trop (écart de {gap} mm selon "
    "l'épaisseur). Écartez le côté du tiroir de celui du caisson.",
)
NO_OVERLAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les deux côtés ne se font pas face : leurs surfaces ne se recouvrent pas."
)
TOO_SHORT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les côtés se recouvrent sur {overlap} mm : aucune coulisse du commerce ne tient "
    "(250 mm au moins).",
)
TOO_LONG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Coulisse de {length} mm trop longue pour {overlap} mm de recouvrement (retrait de "
    "{setback} mm compris).",
)
TOO_LOW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Coulisse de {height} mm de haut : elle sort des côtés, qui se recouvrent sur {overlap} mm "
    "de hauteur.",
)
HOLE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Avant-trou de {depth} mm trop profond pour un côté de {thickness} mm : il faut "
    "{bottom} mm de matière.",
)
BAD_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Une dimension de la coulisse doit être strictement positive."
)


@dataclass(frozen=True)
class SlideParams:
    """Paramètres d'une coulisse (mm) ; 0 = automatique pour la longueur et le nombre.

    Attributes:
        length: Longueur de la coulisse (0 = automatique)
        height_offset: Décalage de la coulisse depuis le milieu du recouvrement
        front_setback: Retrait depuis l'avant des côtés
        reversed: Si vrai, avant = bout opposé
        thickness: Épaisseur de la coulisse (12.7 mm par défaut)
        slide_height: Hauteur de la coulisse (45.0 mm par défaut)
        hole_count: Nombre de trous (0 = automatique = 3)
        hole_diameter: Diamètre des trous (5.0 mm par défaut)
        hole_depth: Profondeur des trous (12.0 mm par défaut)
    """

    length: float = length_param(0.0)
    height_offset: float = offset_param(0.0)  # décalage de la coulisse depuis le milieu
    front_setback: float = length_param(0.0)  # retrait depuis l'avant des côtés
    reversed: bool = flag_param(False)  # avant = bout opposé
    thickness: float = length_param(12.7)
    slide_height: float = length_param(45.0)
    hole_count: int = count_param(0)
    hole_diameter: float = length_param(5.0)
    hole_depth: float = length_param(12.0)

    def __post_init__(self) -> None:
        """Validation des paramètres après initialisation."""
        validate_params(self)
        positive = (self.thickness, self.slide_height, self.hole_diameter, self.hole_depth)
        if min(positive) <= 0 or self.hole_count == 1:
            raise JointError(BAD_VALUE, {})


@dataclass(frozen=True)
class SlideValues:
    """Valeurs effectives de la coulisse (mm), affichées par le panneau.

    Attributes:
        length: Longueur effective de la coulisse
        gap: Jeu entre les côtés ; négatif s'ils se chevauchent
        thickness: Épaisseur effective de la coulisse
        hole_count: Nombre effectif de trous
        hole_positions: Positions des trous depuis l'avant de la coulisse
        direction: Axe de l'hôte vers l'invité, dans le repère de l'hôte
    """

    length: float
    gap: float  # jeu entre les côtés ; négatif s'ils se chevauchent
    thickness: float
    hole_count: int
    hole_positions: tuple[float, ...]  # depuis l'avant de la coulisse
    direction: "Axis"  # de l'hôte vers l'invité, dans le repère de l'hôte

    @property
    def shortfall(self) -> float:
        """Jeu qui manque pour loger la coulisse (0 si les côtés sont assez écartés)."""
        return max(0.0, self.thickness - self.gap)

    @property
    def count(self) -> int:
        """Une coulisse par assemblage (liste de débit)."""
        return 1


@dataclass(frozen=True)
class _Frame:
    """Disposition des côtés dans le repère de l'hôte.

    Attributes:
        normal: Axe qui traverse le jeu
        sign: +1 si l'invité est du côté +, -1 sinon
        host_plane: Position du plan de l'hôte sur l'axe normal
        guest_plane: Position du plan de l'invité sur l'axe normal
        length_axis: Axe de la longueur (le long du contact)
        height_axis: Axe de la hauteur (perpendiculaire au contact)
        overlap: Boîte de recouvrement dans les deux autres axes
        to_guest: Transformation de l'hôte vers l'invité
        guest_extent: Épaisseur de l'invité à travers le jeu
    """

    normal: int  # axe qui traverse le jeu
    sign: int  # +1 : l'invité est du côté +
    host_plane: float
    guest_plane: float
    length_axis: int
    height_axis: int
    overlap: "Box"  # recouvrement dans les deux autres axes
    to_guest: "RigidTransform"  # hôte → invité
    guest_extent: float  # épaisseur de l'invité à travers le jeu
