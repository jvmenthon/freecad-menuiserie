# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages des assemblages : clés et catalogue du groupe « Assemblages » (ADR 0031, 0069, 0070).

Ce module ne lit aucune préférence : il décrit seulement les réglages, que
:mod:`freecad.menuiserie.features.settings` réunit dans le catalogue de l'atelier.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import MAX_INPUT_SPACING_MM, MIN_INPUT_SPACING_MM
from freecad.menuiserie.core.joints.dovetail import DEFAULT_ANGLE_DEG
from freecad.menuiserie.core.joints.dowels import MAX_SPACING_MM, DowelParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.joints.slots import AUTO_SPACING_MM
from freecad.menuiserie.core.joints.tongue_groove import (
    DEFAULT_TONGUE_LENGTH_MM,
    TongueGrooveParams,
)
from freecad.menuiserie.features.settings_build import (
    DEGREES,
    flag_setting,
    length_setting,
)
from freecad.menuiserie.kit.config.catalog import Kind, Setting

__all__ = [
    "DOVETAIL_ANGLE",
    "DOWEL_CLEARANCE",
    "DOWEL_SPACING",
    "GROOVE_CLEARANCE",
    "GROOVE_THROUGH",
    "JOINTS",
    "MORTISE_CLEARANCE",
    "MORTISE_THROUGH",
    "RABBET_THROUGH",
    "SLOT_FREE_SIZE",
    "SLOT_SPACING",
    "TONGUE_LENGTH",
    "joint_settings",
]

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
MORTISE_CLEARANCE: Final = "MortiseClearance"
MORTISE_THROUGH: Final = "MortiseThrough"
GROOVE_CLEARANCE: Final = "GrooveClearance"
TONGUE_LENGTH: Final = "TongueLength"
GROOVE_THROUGH: Final = "GrooveThrough"
RABBET_THROUGH: Final = "RabbetThrough"
DOWEL_CLEARANCE: Final = "DowelHoleClearance"
DOWEL_SPACING: Final = "DowelMaxSpacing"
SLOT_SPACING: Final = "SlotMaxSpacing"
DOVETAIL_ANGLE: Final = "DovetailAngle"
SLOT_FREE_SIZE: Final = "LooseTenonFreeSize"

JOINTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblages")

_MAX_CLEARANCE_MM: Final = 20.0  # jeu d'usinage : au-delà, c'est une faute de saisie
_MAX_TONGUE_MM: Final = 1000.0
_MIN_DOVETAIL_ANGLE_DEG: Final = 1.0
_MAX_DOVETAIL_ANGLE_DEG: Final = 30.0


def _clearance(key: str, default: float, label: str, tooltip: str) -> Setting:
    return length_setting(
        key,
        default,
        label,
        tooltip,
        JOINTS,
        minimum=0.0,
        maximum=_MAX_CLEARANCE_MM,
        remember_last=True,
    )


def joint_settings() -> list[Setting]:
    return [
        _clearance(
            MORTISE_CLEARANCE,
            MortiseTenonParams().mortise_clearance,
            QT_TRANSLATE_NOOP("Menuiserie", "Jeu de mortaise"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profondeur de mortaise en plus de la longueur du tenon."
            ),
        ),
        flag_setting(
            MORTISE_THROUGH,
            MortiseTenonParams().through,
            QT_TRANSLATE_NOOP("Menuiserie", "Mortaise débouchante"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Mortaise qui traverse la pièce, pour un nouvel assemblage."
            ),
            JOINTS,
        ),
        _clearance(
            GROOVE_CLEARANCE,
            TongueGrooveParams().groove_clearance,
            QT_TRANSLATE_NOOP("Menuiserie", "Jeu de rainure"),
            QT_TRANSLATE_NOOP("Menuiserie", "Profondeur de rainure en plus de la languette."),
        ),
        length_setting(
            TONGUE_LENGTH,
            DEFAULT_TONGUE_LENGTH_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur de languette"),
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur de languette d'un nouvel assemblage."),
            JOINTS,
            maximum=_MAX_TONGUE_MM,
            remember_last=True,
        ),
        flag_setting(
            GROOVE_THROUGH,
            TongueGrooveParams().through_groove,
            QT_TRANSLATE_NOOP("Menuiserie", "Rainure débouchante"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Rainure sur toute la longueur, pour un nouvel assemblage."
            ),
            JOINTS,
        ),
        flag_setting(
            RABBET_THROUGH,
            RabbetParams().through,
            QT_TRANSLATE_NOOP("Menuiserie", "Feuillure débouchante"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Feuillure sur toute la longueur, pour un nouvel assemblage."
            ),
            JOINTS,
        ),
        _clearance(
            DOWEL_CLEARANCE,
            DowelParams().hole_clearance,
            QT_TRANSLATE_NOOP("Menuiserie", "Jeu de fond des tourillons"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profondeur de perçage en plus du tourillon, de chaque côté."
            ),
        ),
        length_setting(
            DOWEL_SPACING,
            MAX_SPACING_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Entraxe maximal des tourillons"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Écart maximal entre deux tourillons placés automatiquement."
            ),
            JOINTS,
            minimum=MIN_INPUT_SPACING_MM,
            maximum=MAX_INPUT_SPACING_MM,
            remember_last=True,
        ),
        length_setting(
            SLOT_SPACING,
            AUTO_SPACING_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Entraxe maximal des lamellos et faux tenons"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Écart maximal entre deux mortaises d'un nouvel assemblage."
            ),
            JOINTS,
            minimum=MIN_INPUT_SPACING_MM,
            maximum=MAX_INPUT_SPACING_MM,
            remember_last=True,
        ),
        Setting(
            DOVETAIL_ANGLE,
            Kind.FLOAT,
            DEFAULT_ANGLE_DEG,
            QT_TRANSLATE_NOOP("Menuiserie", "Angle de queue d'aronde"),
            QT_TRANSLATE_NOOP("Menuiserie", "Angle des flancs des queues d'un nouvel assemblage."),
            JOINTS,
            unit=DEGREES,
            minimum=_MIN_DOVETAIL_ANGLE_DEG,
            maximum=_MAX_DOVETAIL_ANGLE_DEG,
            remember_last=True,
        ),
        flag_setting(
            SLOT_FREE_SIZE,
            False,
            QT_TRANSLATE_NOOP("Menuiserie", "Faux tenons : taille libre"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Propose une taille libre plutôt que la liste des tailles."
            ),
            JOINTS,
        ),
    ]
