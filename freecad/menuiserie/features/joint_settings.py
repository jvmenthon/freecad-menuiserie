# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier appliqués aux assemblages neufs (ADR 0031, 0069).

Table (type d'assemblage → paramètre de ``core`` → réglage), lue à la création : un réglage
modifié donne sa valeur au paramètre que l'appelant n'a pas fourni ; un réglage à sa valeur par
défaut ne change rien (le paramètre garde son défaut de ``core``, « automatique » compris). Un
assemblage existant ou une copie gardent leurs valeurs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.features import settings as config
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import property_name

__all__ = ["apply_joint_settings", "record_joint_used"]

_PARAMETERS: Final[Mapping[JointKind, Mapping[str, str]]] = {
    JointKind.MORTISE_TENON: {
        "mortise_clearance": config.MORTISE_CLEARANCE,
        "through": config.MORTISE_THROUGH,
    },
    JointKind.TONGUE_GROOVE: {
        "groove_clearance": config.GROOVE_CLEARANCE,
        "tongue_length": config.TONGUE_LENGTH,
        "through_groove": config.GROOVE_THROUGH,
    },
    JointKind.RABBET: {"through": config.RABBET_THROUGH},
    JointKind.DOWELS: {"hole_clearance": config.DOWEL_CLEARANCE},
    JointKind.DOVETAIL: {"angle": config.DOVETAIL_ANGLE},
    JointKind.LOOSE_TENON: {"custom_size": config.SLOT_FREE_SIZE},
}


def apply_joint_settings(kind: JointKind, params: Mapping[str, object]) -> dict[str, object]:
    """Paramètres de la création : ceux de l'appelant, complétés par les réglages modifiés de
    l'atelier pour les paramètres qu'il n'a pas donnés."""
    values = config.settings()
    wanted = {
        name: values.value(key)
        for name, key in _PARAMETERS.get(kind, {}).items()
        if name not in params and values.is_modified(key)
    }
    return {**wanted, **params}


def record_joint_used(joint: DocumentObject) -> None:
    """« Dernier utilisé » : valeurs de l'assemblage créé, retenues pour les réglages dont la
    case est cochée."""
    values = config.settings()
    for name, key in _PARAMETERS.get(joint.Proxy.KIND, {}).items():
        value = getattr(joint, property_name(name))
        values.record_used(key, getattr(value, "Value", value))
