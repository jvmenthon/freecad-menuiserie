# SPDX-License-Identifier: LGPL-2.1-or-later
"""Propriété ``HardwareReference`` des assemblages de quincaillerie (ADR 0033).

Elle mémorise l'identifiant de la référence du catalogue posée, pour la liste d'achat.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.hardware import HARDWARE_JOINT_KINDS
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.features.freecad_types import READ_ONLY
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["HARDWARE_REFERENCE_PROPERTY", "HARDWARE_REFERENCE_SPEC", "hardware_reference_specs"]

HARDWARE_REFERENCE_PROPERTY: Final = "HardwareReference"
HARDWARE_REFERENCE_SPEC: Final = PropertySpec(
    "HardwareReference",
    "App::PropertyString",
    "Assemblage",
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Identifiant de la référence du catalogue de quincaillerie posée (liste d'achat). Vide : "
        "cotes réglées à la main.",
    ),
    mode=READ_ONLY,
)


def hardware_reference_specs(kind: JointKind) -> tuple[PropertySpec, ...]:
    """Propriété de référence pour un assemblage de quincaillerie, rien sinon."""
    return (HARDWARE_REFERENCE_SPEC,) if kind in HARDWARE_JOINT_KINDS else ()
