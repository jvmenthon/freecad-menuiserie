# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes d'une référence du catalogue, traduites en paramètres d'assemblage (ADR 0033).

Choisir une référence fixe les cotes du commerce de l'assemblage (diamètre et longueur d'un
tourillon, taille d'un faux tenon ou d'un biscuit, d'un pied, d'une coulisse ou d'une charnière) ;
les autres paramètres restent automatiques.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.hardware._model import HardwareItem
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.joints import JointKind

__all__ = ["HARDWARE_JOINT_KINDS", "joint_kind_of", "joint_params"]

WRONG_FAMILY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La référence « {id} » ({family}) ne convient pas à cet assemblage : choisissez une "
    "référence de type {expected}.",
)
NOT_A_JOINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La référence « {id} » ({family}) ne se pose pas comme un assemblage."
)

_HINGE_OPTIONAL: Final = ("edge_distance", "screw_pitch")
_Params = Callable[[HardwareItem], dict[str, float | str]]

_KINDS: Final[Mapping[str, JointKind]] = MappingProxyType(
    {
        "dowel": JointKind.DOWELS,
        "loose-tenon": JointKind.LOOSE_TENON,
        "biscuit": JointKind.BISCUIT,
        "cabinet-foot": JointKind.FOOT,
        "shelf-pin": JointKind.SHELF_PINS,
        "drawer-slide-ball": JointKind.DRAWER_SLIDE,
        "hinge-cup-35": JointKind.HINGE,
    }
)


HARDWARE_JOINT_KINDS: Final = frozenset(_KINDS.values())  # assemblages qui posent une référence


def _dowel(item: HardwareItem) -> dict[str, float | str]:
    return {"diameter": item.param("diameter"), "dowel_length": item.param("length")}


def _loose_tenon(item: HardwareItem) -> dict[str, float | str]:
    # Domino : taille de la liste Festool (identifiant du catalogue sans préfixe).
    return {"size": item.id.removeprefix("domino-")}


def _biscuit(item: HardwareItem) -> dict[str, float | str]:
    # Lamelle : taille de la liste Lamello (identifiant du catalogue sans préfixe).
    return {"size": item.id.removeprefix("biscuit-")}


def _foot(item: HardwareItem) -> dict[str, float | str]:
    return {
        "stem_diameter": item.param("stem_diameter"),
        "base_diameter": item.param("base_diameter"),
        "height": item.param("height"),
    }


def _shelf_pin(item: HardwareItem) -> dict[str, float | str]:
    # Le trou prend le diamètre de la tige du taquet.
    return {"hole_diameter": item.param("diameter")}


def _drawer_slide(item: HardwareItem) -> dict[str, float | str]:
    return {"length": item.param("length"), "thickness": item.param("thickness")}


def _hinge(item: HardwareItem) -> dict[str, float | str]:
    # Distance au chant et entraxe de platine sont facultatifs dans le catalogue.
    params: dict[str, float | str] = {
        "cup_diameter": item.param("cup_diameter"),
        "cup_depth": item.param("cup_depth"),
    }
    params.update({name: item.param(name) for name in _HINGE_OPTIONAL if name in item.params})
    return params


_PARAMS: Final[Mapping[JointKind, _Params]] = MappingProxyType(
    {
        JointKind.DOWELS: _dowel,
        JointKind.LOOSE_TENON: _loose_tenon,
        JointKind.BISCUIT: _biscuit,
        JointKind.FOOT: _foot,
        JointKind.SHELF_PINS: _shelf_pin,
        JointKind.DRAWER_SLIDE: _drawer_slide,
        JointKind.HINGE: _hinge,
    }
)


def joint_kind_of(item: HardwareItem) -> JointKind | None:
    """Type d'assemblage qui pose cette référence, ou ``None`` (famille sans assemblage)."""
    return _KINDS.get(item.family)


def joint_params(item: HardwareItem, kind: JointKind) -> dict[str, float | str]:
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
