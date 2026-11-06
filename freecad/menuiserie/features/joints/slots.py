# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits du document : proxies ``LooseTenonJoint`` et ``BiscuitJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, noms des classes et des propriétés
figés. Les deux types partagent les mêmes propriétés ; la forme de l'assemblage est l'ensemble
des pièces rapportées, et les deux pièces sont mortaisées (:mod:`core.joints.slots`).
Les cotes et le nombre valent 0 pour « automatique » (taille du commerce qui tient).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT
from freecad.menuiserie.core.joints.slots import SlotParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import DISTANCE, LENGTH, PropertySpec

__all__ = ["BiscuitJoint", "LooseTenonJoint"]

_GROUP: Final = "Mortaises"
_DEFAULTS: Final = SlotParams()

_SLOT_PROPERTIES: Final[tuple[PropertySpec, ...]] = (
    PropertySpec(
        "Thickness",
        LENGTH,
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Épaisseur de la pièce rapportée. 0 : automatique, la plus grande taille du commerce "
            "qui tient dans les pièces.",
        ),
        default=_DEFAULTS.thickness,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur"),
        resolved="thickness",
    ),
    PropertySpec(
        "Along",
        LENGTH,
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Longueur de la mortaise le long du joint. 0 : automatique, la plus grande taille du "
            "commerce qui tient dans les pièces.",
        ),
        default=_DEFAULTS.along,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Longueur le long du joint"),
        resolved="along",
    ),
    PropertySpec(
        "TotalDepth",
        LENGTH,
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Pénétration totale de la pièce rapportée à travers le joint (moitié dans chaque "
            "pièce). 0 : automatique, la plus grande taille du commerce qui tient dans les pièces.",
        ),
        default=_DEFAULTS.total_depth,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Pénétration totale"),
        resolved="total_depth",
    ),
    PropertySpec(
        "Count",
        "App::PropertyIntegerConstraint",
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Nombre de mortaises. 0 : automatique, selon la longueur du contact."
        ),
        label=QT_TRANSLATE_NOOP("Menuiserie", "Nombre"),
        resolved="count",
        default=(_DEFAULTS.count, 0, MAX_DOWEL_COUNT, 1),
    ),
    PropertySpec(
        "EdgeDistance",
        LENGTH,
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Distance du bord du contact au bord de la première et de la dernière mortaise. "
            "0 : automatique.",
        ),
        label=QT_TRANSLATE_NOOP("Menuiserie", "Distance au bord"),
        resolved="edge_distance",
        default=_DEFAULTS.edge_distance,
    ),
    PropertySpec(
        "ThicknessOffset",
        DISTANCE,
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Décalage des mortaises dans l'épaisseur de la pièce, depuis le milieu. 0 : centrées.",
        ),
        label=QT_TRANSLATE_NOOP("Menuiserie", "Décalage en épaisseur"),
        default=_DEFAULTS.thickness_offset,
    ),
    PropertySpec(
        "HoleClearance",
        LENGTH,
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Jeu de fond : profondeur de chaque mortaise au-delà du bout de la pièce rapportée.",
        ),
        label=QT_TRANSLATE_NOOP("Menuiserie", "Jeu de fond des mortaises"),
        default=_DEFAULTS.hole_clearance,
    ),
)


class LooseTenonJoint(JointFeature):
    """Faux tenons (type Domino) logés dans une mortaise de chaque pièce."""

    KIND: ClassVar[JointKind] = JointKind.LOOSE_TENON
    TYPE: ClassVar[str] = "Menuiserie::LooseTenon"
    OBJECT_NAME: ClassVar[str] = "LooseTenon"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Faux tenons")
    PARAMS: ClassVar[type[SlotParams]] = SlotParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = _SLOT_PROPERTIES


class BiscuitJoint(JointFeature):
    """Biscuits (lamelles) logés dans une fente de chaque pièce."""

    KIND: ClassVar[JointKind] = JointKind.BISCUIT
    TYPE: ClassVar[str] = "Menuiserie::Biscuit"
    OBJECT_NAME: ClassVar[str] = "Biscuit"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Biscuits")
    PARAMS: ClassVar[type[SlotParams]] = SlotParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = _SLOT_PROPERTIES
