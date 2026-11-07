# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits du document : proxies ``LooseTenonJoint`` et ``BiscuitJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, noms des classes et des propriétés
figés. Les deux types partagent les mêmes propriétés ; la forme de l'assemblage est l'ensemble
des pièces rapportées, et les deux pièces sont mortaisées (:mod:`core.joints.slots`).
La taille se choisit dans la liste du commerce (Festool Domino, Lamello) ; seul le faux tenon
accepte des cotes personnalisées (case « Taille personnalisée »), 0 valant « automatique »
(taille du commerce qui tient). Le nombre vaut 0 pour « automatique » aussi.
"""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT
from freecad.menuiserie.core.joints.slots import SlotParams
from freecad.menuiserie.features.freecad_types import HIDDEN
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import DISTANCE, LENGTH, PropertySpec

__all__ = ["BiscuitJoint", "LooseTenonJoint"]

_GROUP: Final = "Mortaises"
_DEFAULTS: Final = SlotParams()

_SIZE_TIP: Final = QT_TRANSLATE_NOOP(
    "App::Property",
    "Taille de la pièce rapportée, dans la liste du commerce. Automatique : la plus grande "
    "taille qui tient dans les pièces.",
)

_DOMINO_SIZE = PropertySpec(
    "Size",
    "App::PropertyEnumeration",
    _GROUP,
    _SIZE_TIP,
    default=_DEFAULTS.size,
    label=QT_TRANSLATE_NOOP("Menuiserie", "Taille Festool"),
    choices=(
        ("auto", QT_TRANSLATE_NOOP("Menuiserie", "Automatique")),
        ("4x20", QT_TRANSLATE_NOOP("Menuiserie", "Domino 4 x 20 mm")),
        ("5x30", QT_TRANSLATE_NOOP("Menuiserie", "Domino 5 x 30 mm")),
        ("6x40", QT_TRANSLATE_NOOP("Menuiserie", "Domino 6 x 40 mm")),
        ("8x40", QT_TRANSLATE_NOOP("Menuiserie", "Domino 8 x 40 mm")),
        ("8x50", QT_TRANSLATE_NOOP("Menuiserie", "Domino 8 x 50 mm")),
        ("10x50", QT_TRANSLATE_NOOP("Menuiserie", "Domino 10 x 50 mm")),
    ),
)
_BISCUIT_SIZE = PropertySpec(
    "Size",
    "App::PropertyEnumeration",
    _GROUP,
    _SIZE_TIP,
    default=_DEFAULTS.size,
    label=QT_TRANSLATE_NOOP("Menuiserie", "Taille Lamello"),
    choices=(
        ("auto", QT_TRANSLATE_NOOP("Menuiserie", "Automatique")),
        ("0", QT_TRANSLATE_NOOP("Menuiserie", "Lamelle n° 0 (47 x 15 mm)")),
        ("10", QT_TRANSLATE_NOOP("Menuiserie", "Lamelle n° 10 (53 x 19 mm)")),
        ("20", QT_TRANSLATE_NOOP("Menuiserie", "Lamelle n° 20 (56 x 23 mm)")),
    ),
)

_COMMON_PROPERTIES: Final[tuple[PropertySpec, ...]] = (
    PropertySpec(
        "CustomSize",
        "App::PropertyBool",
        _GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Saisir les cotes de la pièce rapportée au lieu de choisir une taille du commerce "
            "(faux tenons seulement).",
        ),
        default=_DEFAULTS.custom_size,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Taille personnalisée"),
        visible_if="custom_allowed",
    ),
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
        visible_if="custom_size",
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
        visible_if="custom_size",
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
        visible_if="custom_size",
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


_CUSTOM_SIZE_PROPERTIES: Final = ("CustomSize", "Thickness", "Along", "TotalDepth")
_LOOSE_TENON_PROPERTIES: Final = (_DOMINO_SIZE, *_COMMON_PROPERTIES)
# Biscuit : taille de la liste seulement, les propriétés de taille personnalisée sont masquées.
_BISCUIT_PROPERTIES: Final = (
    _BISCUIT_SIZE,
    *(
        replace(spec, mode=HIDDEN) if spec.name in _CUSTOM_SIZE_PROPERTIES else spec
        for spec in _COMMON_PROPERTIES
    ),
)


class LooseTenonJoint(JointFeature):
    """Faux tenons (type Domino) logés dans une mortaise de chaque pièce."""

    KIND: ClassVar[JointKind] = JointKind.LOOSE_TENON
    TYPE: ClassVar[str] = "Menuiserie::LooseTenon"
    OBJECT_NAME: ClassVar[str] = "LooseTenon"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Faux tenons")
    PARAMS: ClassVar[type[SlotParams]] = SlotParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = _LOOSE_TENON_PROPERTIES


class BiscuitJoint(JointFeature):
    """Biscuits (lamelles) logés dans une fente de chaque pièce."""

    KIND: ClassVar[JointKind] = JointKind.BISCUIT
    TYPE: ClassVar[str] = "Menuiserie::Biscuit"
    OBJECT_NAME: ClassVar[str] = "Biscuit"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Biscuits")
    PARAMS: ClassVar[type[SlotParams]] = SlotParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = _BISCUIT_PROPERTIES
