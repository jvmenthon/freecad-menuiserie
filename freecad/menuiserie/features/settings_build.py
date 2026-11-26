# SPDX-License-Identifier: LGPL-2.1-or-later
"""Constructeurs de réglages partagés par les catalogues de l'atelier (ADR 0031, 0069)."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.kit.config.catalog import Kind, Setting

__all__ = ["DEGREES", "MM", "flag_setting", "length_setting"]

MM: Final = QT_TRANSLATE_NOOP("Menuiserie", "mm")
DEGREES: Final = QT_TRANSLATE_NOOP("Menuiserie", "°")


def length_setting(  # noqa: PLR0913 (description d'un réglage : tous ses champs sont nommés)
    key: str,
    default: float,
    label: str,
    tooltip: str,
    group: str,
    *,
    minimum: float = MIN_DIMENSION_MM,
    maximum: float = MAX_DIMENSION_MM,
    remember_last: bool = False,
) -> Setting:
    """Cote en mm."""
    return Setting(
        key,
        Kind.FLOAT,
        default,
        label,
        tooltip,
        group,
        unit=MM,
        minimum=minimum,
        maximum=maximum,
        remember_last=remember_last,
    )


def flag_setting(
    key: str, default: bool, label: str, tooltip: str, group: str, *, remember_last: bool = True
) -> Setting:
    """Case à cocher ; elle propose « Dernier utilisé » sauf si ``remember_last`` est faux
    (réglage d'interface lu à l'usage)."""
    return Setting(key, Kind.BOOL, default, label, tooltip, group, remember_last=remember_last)
