# SPDX-License-Identifier: LGPL-2.1-or-later
"""Textes et petites aides du panneau « Répéter » (ADR 0043, 0045 et 0047)."""

from __future__ import annotations

from typing import Final

from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import SpacingMode
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import Widget

SPACINGS: Final = {
    SpacingMode.COUNT_AND_STEP: QT_TRANSLATE_NOOP("Menuiserie", "Nombre et pas"),
    SpacingMode.COUNT_ON_SPAN: QT_TRANSLATE_NOOP("Menuiserie", "Nombre sur une longueur"),
    SpacingMode.STEP_ON_SPAN: QT_TRANSLATE_NOOP("Menuiserie", "Pas sur une longueur"),
}
SPACING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Mode de saisie")
SPACING_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Commun à tous les axes. Nombre et pas : vous donnez les deux. Nombre sur une longueur : le "
    "pas est calculé pour remplir la longueur. Pas sur une longueur : le nombre d'éléments est "
    "calculé.",
)
COPY_JOINTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Recopier les assemblages")
COPY_JOINTS_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochée : chaque copie reçoit les assemblages de la pièce d'origine, liés à ceux de "
    "l'original (modifier le premier modifie les autres). Décochée : seules les pièces sont "
    "copiées.",
)
FOLLOW: Final = QT_TRANSLATE_NOOP("Menuiserie", "Suivre le redimensionnement")
FOLLOW_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochée : quand l'ensemble est redimensionné, le pas de chaque axe est recalculé et les "
    "copies se répartissent sur la nouvelle longueur de l'ensemble sur cet axe ; leur nombre ne "
    "change pas. Décochée : les pas restent fixes.",
)
FOLLOW_DISABLED_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Grisée : la pièce répétée n'est dans aucun ensemble, il n'y a pas de redimensionnement à "
    "suivre. Placez-la d'abord dans un ensemble.",
)
UNEXPECTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La répétition n'a pas pu être construite avec ces valeurs ({reason}). Modifiez le nombre, "
    "le pas ou la longueur.",
)
DEDUCT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déduire l'épaisseur de la pièce")
DEDUCT_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Modes sur une longueur (saisie ou butée). Cochée : l'épaisseur de la pièce est déduite de la "
    "longueur, la dernière copie arrive à fleur de la fin. Décochée : elle commence à la fin de "
    "la longueur (contre une butée, elle est alors en collision avec elle).",
)
GAP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Laisser un pas libre après la dernière pièce")
GAP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Modes sur une longueur. Cochée : les éléments partagent la longueur en autant d'intervalles "
    "égaux (au lieu d'un de moins) ; la dernière pièce ne touche pas la fin ni la butée, l'écart "
    "est celui des autres pièces. « Déduire l'épaisseur » ne sert alors plus.",
)
STOP_COLLISION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Attention : l'épaisseur n'est pas déduite, la dernière copie commence à la butée de l'axe "
    "{axis} et est en collision avec elle.",
)


def checkbox(name: str, label: str, tip: str, checked: bool) -> Widget:
    """Case à cocher nommée, avec son infobulle."""
    box = QtGui.QCheckBox(translated(label))
    box.setObjectName(name)
    box.setToolTip(translated(tip))
    box.setChecked(checked)
    return box
