# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes d'une référence du catalogue, traduites en paramètres d'assemblage (ADR 0033).

Choisir une référence fixe les cotes du commerce de l'assemblage (diamètre et longueur d'un
tourillon, taille d'un faux tenon ou d'un biscuit) ; les autres paramètres restent automatiques.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.hardware._model import HardwareItem
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.joints import JointKind

__all__ = ["joint_kind_of", "joint_params"]

WRONG_FAMILY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La référence « {id} » ({family}) ne convient pas à cet assemblage : choisissez une "
    "référence de type {expected}.",
)
NOT_A_JOINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La référence « {id} » ({family}) ne se pose pas comme un assemblage."
)

_Params = Callable[[HardwareItem], dict[str, float]]

_KINDS: Final[Mapping[str, JointKind]] = MappingProxyType(
    {
        "dowel": JointKind.DOWELS,
        "loose-tenon": JointKind.LOOSE_TENON,
        "biscuit": JointKind.BISCUIT,
    }
)
_PARAMS: Final[Mapping[JointKind, _Params]] = MappingProxyType(
    {
        JointKind.DOWELS: lambda i: {
            "diameter": i.param("diameter"),
            "dowel_length": i.param("length"),
        },
        JointKind.LOOSE_TENON: lambda i: {
            "thickness": i.param("thickness"),
            "along": i.param("width"),
            "total_depth": i.param("length"),
        },
        JointKind.BISCUIT: lambda i: {
            "thickness": i.param("thickness"),
            "along": i.param("length"),
            "total_depth": i.param("width"),
        },
    }
)


def joint_kind_of(item: HardwareItem) -> JointKind | None:
    """Type d'assemblage qui pose cette référence, ou ``None`` (famille sans assemblage)."""
    return _KINDS.get(item.family)


def joint_params(item: HardwareItem, kind: JointKind) -> dict[str, float]:
    """Paramètres de l'assemblage ``kind`` fixés par ``item`` (mm) ; ``TemplatedError`` si la
    référence est d'une autre famille."""
    own = joint_kind_of(item)
    if own is None:
        raise TemplatedError(NOT_A_JOINT, {"id": item.id, "family": item.family})
    if own is not kind:
        expected = next(family for family, k in _KINDS.items() if k is kind)
        raise TemplatedError(
            WRONG_FAMILY, {"id": item.id, "family": item.family, "expected": expected}
        )
    return _PARAMS[kind](item)
