# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 du document : proxy ``ShelfPinsJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et des propriétés
figés. ``HostPart`` est le côté debout percé ; ``GuestPart`` est le montant opposé percé en
miroir (un seul objet pour les deux côtés), ou la même pièce s'il n'y a pas de montant en face
(documents antérieurs compris). Les taquets sont les pièces rapportées de la forme.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, ClassVar, Final, cast

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointError, JointKind, strategy_for
from freecad.menuiserie.core.joints.shelf_pins import (
    Neighbor,
    ShelfPinsParams,
    ShelfPinsValues,
    facing_side,
    opposite_values,
)
from freecad.menuiserie.core.part_model import InvalidDimensionsError
from freecad.menuiserie.features.freecad_types import HIDDEN, DocumentObject
from freecad.menuiserie.features.joints.base import (
    JointFeature,
    is_joint,
    params_from,
    placed_blank,
    resolved_for,
)
from freecad.menuiserie.features.machined_part import machined_part_of, timber_blanks_around
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

__all__ = ["ShelfPinsJoint", "opposite_upright"]

_GROUP: Final = "Perçage LR32"
_DEFAULTS: Final = ShelfPinsParams()
_MAX_ROWS: Final = 50


def _assembled_with(part: DocumentObject, other: DocumentObject) -> bool:
    """Vrai si un assemblage (autre que des perçages LR32) relie ``other`` à ``part``."""
    machined = machined_part_of(part)
    for joint in getattr(machined, "Joints", ()):
        other_kind = is_joint(joint) and joint.Proxy.KIND is not JointKind.SHELF_PINS
        if other_kind and other in (joint.HostPart, joint.GuestPart):
            return True
    return False


def opposite_upright(part: DocumentObject, params: ShelfPinsParams) -> DocumentObject | None:
    """Montant opposé de ``part`` : le côté debout parallèle le plus proche en face de sa face
    percée avec ``params`` ; ``None`` s'il n'y en a pas, si le perçage y est impossible ou s'il
    y retomberait sur des trous déjà percés (même face, même hauteur : autre zone acceptée)."""
    container = part.getParentGeoFeatureGroup()
    candidates, blocks = [], []
    for other in timber_blanks_around(part):
        if other.getParentGeoFeatureGroup() != container:
            continue
        try:
            blocks.append(placed_blank(other))
        except (ValueError, InvalidDimensionsError):
            continue
        candidates.append(other)
    strategy = strategy_for(JointKind.SHELF_PINS)
    try:
        host = placed_blank(part)
        with_neighbors = replace(params, neighbors=_neighbors_of(part))
        face = strategy.resolve(host, host, with_neighbors).face
        found = facing_side(host, face, tuple(blocks))
        if found is None:
            return None
        other = candidates[found[0]]
        mirrored = replace(with_neighbors, guest_neighbors=_neighbors_of(other))
        strategy.plan(host, blocks[found[0]], mirrored)  # montant opposé perçable
        planned = opposite_values(host, blocks[found[0]], mirrored)
    except (JointError, ValueError, InvalidDimensionsError):
        return None
    if planned is None or _levels(planned) & _drilled_levels(other):
        return None
    return other


def _levels(values: ShelfPinsValues) -> set[tuple[str, float]]:
    """(face, hauteur au dixième de mm) de chaque rang de trous."""
    return {(values.face, round(height, 1)) for height in values.heights}


def _drilled_levels(part: DocumentObject) -> set[tuple[str, float]]:
    """Rangs déjà percés dans ``part`` par ses perçages LR32 (comme côté ou montant opposé)."""
    levels: set[tuple[str, float]] = set()
    machined = machined_part_of(part)
    for joint in getattr(machined, "Joints", ()):
        if not is_joint(joint) or joint.Proxy.KIND is not JointKind.SHELF_PINS:
            continue
        try:
            if joint.HostPart == part:
                levels |= _levels(cast(ShelfPinsValues, resolved_for(joint)))
            elif joint.GuestPart == part:
                host = placed_blank(joint.HostPart)
                params = joint.Proxy.params(joint)
                values = opposite_values(host, placed_blank(part), params)
                levels |= _levels(values) if values is not None else set()
        except (JointError, ValueError, InvalidDimensionsError):
            continue
    return levels


def _neighbors_of(part: DocumentObject) -> tuple[Neighbor, ...]:
    """Pièces voisines de ``part`` : assemblées (bornent la zone percée) ou libres (tablettes)."""
    neighbors = []
    for other in timber_blanks_around(part):
        try:
            block = placed_blank(other)
        except (ValueError, InvalidDimensionsError):
            continue
        neighbors.append(Neighbor(block, _assembled_with(part, other)))
    return tuple(neighbors)


class ShelfPinsJoint(JointFeature):
    """Perçage au pas de 32 mm dans un côté debout, taquets de tablette rapportés."""

    KIND: ClassVar[JointKind] = JointKind.SHELF_PINS
    TYPE: ClassVar[str] = "Menuiserie::ShelfPins"
    OBJECT_NAME: ClassVar[str] = "ShelfPins"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Perçage LR32")
    PARAMS: ClassVar[type[ShelfPinsParams]] = ShelfPinsParams
    INVERT_TIP: ClassVar[str] = QT_TRANSLATE_NOOP(
        "Menuiserie", "Perce l'autre face du côté (les trous et les taquets changent de face)."
    )

    def invert_error(self, obj: DocumentObject) -> str | None:
        """Toujours possible : « Inverser » change de face, pas de rôles."""
        return None

    def invert(self, obj: DocumentObject) -> None:
        """« Inverser » : l'autre face du côté est percée (le montant opposé reste percé sur sa
        face tournée vers le côté)."""
        try:
            current = cast(ShelfPinsValues, resolved_for(obj)).face
        except ValueError:
            current = "minus" if obj.Face == "plus" else "plus"
        obj.Face = "minus" if current == "plus" else "plus"

    def part_joints_changed(self, obj: DocumentObject) -> None:
        """Assemblage ajouté au côté ou au montant opposé (ou retiré) : la zone percée change ;
        voisines relues (une pièce ajoutée depuis le perçage est suivie) et recalcul demandé."""
        host = obj.HostPart
        if host is None:
            return
        around = timber_blanks_around(host)
        if list(obj.Neighbors) != around:
            obj.Neighbors = around
        obj.touch()

    def params(self, obj: DocumentObject) -> Any:
        """Réglages des propriétés, plus les pièces voisines du côté et du montant opposé dans
        le document : celles qui leur sont assemblées bornent la zone percée, les autres
        (tablettes) reçoivent un taquet sous elles."""
        guest = obj.GuestPart
        opposite = _neighbors_of(guest) if guest is not None and guest != obj.HostPart else ()
        return replace(
            params_from(obj, ShelfPinsParams),
            neighbors=_neighbors_of(obj.HostPart),
            guest_neighbors=opposite,
        )

    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Neighbors",
            "App::PropertyLinkList",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Pièces du document qui bornent le perçage ou reposent sur ses taquets : leur "
                "déplacement recalcule le perçage.",
            ),
            mode=HIDDEN,
        ),
        PropertySpec(
            "HoleDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Diamètre des trous (taquets à tige). 0 : automatique (5 mm)."
            ),
            default=_DEFAULTS.hole_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des trous"),
            resolved="hole_diameter",
        ),
        PropertySpec(
            "HoleDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Profondeur des trous dans le côté. 0 : automatique (12 mm)."
            ),
            default=_DEFAULTS.hole_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des trous"),
            resolved="hole_depth",
        ),
        PropertySpec(
            "Pitch",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Pas entre deux trous d'une colonne (32 mm)."),
            default=_DEFAULTS.pitch,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Pas"),
        ),
        PropertySpec(
            "EdgeDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance des deux colonnes aux bords avant et arrière du côté. 0 : automatique "
                "(37 mm).",
            ),
            default=_DEFAULTS.edge_distance,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance au bord"),
            resolved="edge_distance",
        ),
        PropertySpec(
            "EndMargin",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance du premier et du dernier trou aux pièces assemblées au côté (fond, "
                "dessus) ou à ses bouts. 0 : automatique (64 mm).",
            ),
            default=_DEFAULTS.end_margin,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Marge aux pièces assemblées"),
            resolved="end_margin",
        ),
        PropertySpec(
            "Rows",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de trous par colonne. 0 : automatique, autant que la zone libre entre les "
                "pièces assemblées au côté en reçoit.",
            ),
            default=(_DEFAULTS.rows, 0, _MAX_ROWS, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Trous par colonne"),
            resolved="rows",
        ),
        PropertySpec(
            "WithPins",
            "App::PropertyBool",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Poser les taquets : sous chaque tablette posée contre le côté, ou dans le rang "
                "choisi.",
            ),
            default=_DEFAULTS.with_pins,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Poser les taquets"),
        ),
        PropertySpec(
            "PinRow",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Rang des taquets, compté depuis le bas de la zone percée (1 : le plus bas). 0 : "
                "automatique, un rang sous chaque tablette posée contre le côté.",
            ),
            default=(_DEFAULTS.pin_row, 0, _MAX_ROWS, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Rang des taquets"),
            resolved="pin_row",
        ),
        PropertySpec(
            "PinProjection",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Saillie du taquet hors de la face du côté."),
            default=_DEFAULTS.pin_projection,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Saillie des taquets"),
        ),
        PropertySpec(
            "ZoneHeight",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Hauteur, depuis le bas du côté, d'un point de la zone à percer (entre deux pièces "
                "assemblées au côté) : celle du clic à la création. 0 : automatique, la plus "
                "grande zone libre.",
            ),
            default=_DEFAULTS.zone_height,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Hauteur de la zone percée"),
            resolved="zone_height",
        ),
        PropertySpec(
            "BothSides",
            "App::PropertyBool",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Percer aussi le montant opposé (le côté en face), en miroir et avec les mêmes "
                "réglages.",
            ),
            default=_DEFAULTS.both_sides,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Montant opposé aussi"),
        ),
        PropertySpec(
            "Face",
            "App::PropertyEnumeration",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Face percée du côté. Automatique : la face intérieure, celle contre laquelle sont "
                "posées des pièces et qui regarde l'autre côté.",
            ),
            default=_DEFAULTS.face,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Face percée"),
            choices=(
                ("auto", QT_TRANSLATE_NOOP("Menuiserie", "Automatique (face intérieure)")),
                ("plus", QT_TRANSLATE_NOOP("Menuiserie", "Face +Z de la pièce")),
                ("minus", QT_TRANSLATE_NOOP("Menuiserie", "Face -Z de la pièce")),
            ),
        ),
    )
