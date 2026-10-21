# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarit « Caisson » (J4d, critères K1 et K2 ; spécification J4, § 4.7).

Repère de l'ensemble : X = largeur, Y = profondeur (avant en 0), Z = hauteur. Côtés pleine
hauteur et pleine profondeur ; dessus et dessous entre les côtés, reliés aux côtés par des
tourillons (ou sans assemblage) ; fond logé dans une feuillure des côtés, du dessus et du
dessous ; étagères posées, avec un jeu aux côtés et devant le fond, réparties à intervalles
égaux. Le gabarit fixe lui-même ses jeux et ses retraits (options « fixe » explicites).
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core._validation import decimal_text, to_finite_float
from freecad.menuiserie.core.furniture import Edge, FurnitureBox
from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.joints import JointKind, mm_round
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.templates import JointSpec, Layout, PieceSpec

__all__ = [
    "CARCASS_TEMPLATE",
    "MAX_SHELVES",
    "CarcassError",
    "CarcassJoinery",
    "CarcassParams",
    "carcass_layout",
    "check_materials",
]

CARCASS_TEMPLATE: Final = "Carcass"  # valeur de ``Template`` (enregistrée, figée)
MAX_SHELVES: Final = 10
SHELF_GAP_MM: Final = 1.0  # jeu de l'étagère aux côtés et devant le fond
MIN_JOINED_THICKNESS_MM: Final = 12.0  # tourillons de 6 mm au moins, 3 mm de fond de perçage
_STANDARD_DIAMETERS: Final = (6.0, 8.0, 10.0, 12.0)

CARCASS_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Caisson")
LABELS: Final = {
    "left": QT_TRANSLATE_NOOP("Menuiserie", "Côté gauche"),
    "right": QT_TRANSLATE_NOOP("Menuiserie", "Côté droit"),
    "bottom": QT_TRANSLATE_NOOP("Menuiserie", "Dessous"),
    "top": QT_TRANSLATE_NOOP("Menuiserie", "Dessus"),
    "back": QT_TRANSLATE_NOOP("Menuiserie", "Fond"),
    "shelf": QT_TRANSLATE_NOOP("Menuiserie", "Étagère"),
}
FIELDS: Final = {
    "thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur des panneaux"),
    "back_thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur du fond"),
    "rabbet_depth": QT_TRANSLATE_NOOP("Menuiserie", "profondeur de la feuillure"),
    "shelf_count": QT_TRANSLATE_NOOP("Menuiserie", "nombre d'étagères"),
    "material_id": QT_TRANSLATE_NOOP("Menuiserie", "matériau des panneaux"),
    "back_material_id": QT_TRANSLATE_NOOP("Menuiserie", "matériau du fond"),
    "joinery": QT_TRANSLATE_NOOP("Menuiserie", "type d'assemblage"),
    "origin": QT_TRANSLATE_NOOP("Menuiserie", "position du caisson"),
}
THICKNESS_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Caisson : {field} = {value} mm ; il faut plus de 0 mm et moins de la moitié de la plus "
    "petite cote ({max} mm).",
)
BACK_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Caisson : {field} = {value} mm ; il faut plus de 0 mm et moins que l'épaisseur des "
    "panneaux ({max} mm).",
)
RABBET_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Caisson : {field} = {value} mm ; il faut plus de 0 mm et au plus l'épaisseur des "
    "panneaux ({max} mm).",
)
SHELF_COUNT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Caisson : {field} = {value} ; il faut un nombre entier de 0 à {max}."
)
NO_ROOM: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Caisson : {field} = {value} ; les étagères ne tiennent pas dans le caisson."
)
TOO_THIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Caisson : {field} = {value} mm ; il faut au moins {min} mm pour des tourillons.",
)
UNKNOWN_VALUE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Caisson : {field} inconnu : « {value} ».")
INVALID_ORIGIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Caisson : {field} invalide ; trois coordonnées finies attendues."
)

# Rotations (lignes de la matrice) : axes locaux L, l, e de la pièce dans le repère du caisson.
_FLAT: Final = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))  # L selon X, l selon Y
_UPRIGHT: Final = ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))  # L selon Z, e selon -X
_STANDING: Final = ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))  # L selon Z, l X, e Y

_ALL_EDGES: Final = frozenset(Edge)
ZERO: Final = Vec3(0.0, 0.0, 0.0)


class CarcassError(TemplatedError):
    """Paramètres de caisson refusés ; ``params["field"]`` cite le champ (traduisible)."""


class CarcassJoinery(str, Enum):
    """Assemblage des côtés avec le dessus et le dessous (valeurs stables)."""

    DOWELS = "Dowels"  # tourillons (côté hôte)
    NONE = "None"  # pièces aboutées, à visser ou à coller


def _error(template: str, name: str, value: object, **params: str) -> CarcassError:
    number = to_finite_float(value)
    shown = decimal_text(number) if number is not None else str(value)
    return CarcassError(template, {"field": FIELDS[name], "value": shown, **params})


@dataclass(frozen=True)
class CarcassParams:
    """Paramètres du caisson (mm), validés à la construction (``ValueError`` citant le champ).

    Cotes hors tout de ``FurnitureBox`` ; épaisseur des panneaux de plus de 0 et de moins de la
    moitié de la plus petite cote ; fond plus mince que les panneaux ; feuillure d'au plus
    l'épaisseur des panneaux ; 0 à 10 étagères ; ``origin`` : coin avant gauche bas.
    Les matériaux sont contrôlés par :func:`check_materials` (bibliothèque de ``features``).
    """

    width: float = 600.0
    depth: float = 400.0
    height: float = 720.0
    thickness: float = 18.0
    back_thickness: float = 8.0
    rabbet_depth: float = 10.0
    shelf_count: int = 1
    material_id: str = "cp-bouleau"
    back_material_id: str = "cp-bouleau"
    joinery: CarcassJoinery = CarcassJoinery.DOWELS
    origin: Vec3 = ZERO

    def __post_init__(self) -> None:
        box = FurnitureBox(self.width, self.depth, self.height)  # FurnitureError : cote citée
        for name in ("width", "depth", "height"):
            object.__setattr__(self, name, getattr(box, name))
        self._check_thicknesses(min(self.width, self.depth, self.height))
        self._check_shelves()
        self._check_choices()

    def _check_thicknesses(self, smallest: float) -> None:
        thickness = _positive_below(self, "thickness", smallest / 2, THICKNESS_RANGE)
        _positive_below(self, "back_thickness", thickness, BACK_RANGE)
        rabbet = to_finite_float(self.rabbet_depth)
        if rabbet is None or not 0 < rabbet <= thickness:
            limit = decimal_text(thickness)
            raise _error(RABBET_RANGE, "rabbet_depth", self.rabbet_depth, max=limit)
        object.__setattr__(self, "rabbet_depth", rabbet)

    def _check_shelves(self) -> None:
        count = self.shelf_count
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= MAX_SHELVES:
            raise _error(SHELF_COUNT, "shelf_count", count, max=str(MAX_SHELVES))
        room = (
            _shelf_gap(self) > 0
            and self.width - 2 * self.thickness - 2 * SHELF_GAP_MM >= 1.0
            and self.depth - self.back_thickness - SHELF_GAP_MM >= 1.0
        )
        if count and not room:
            raise _error(NO_ROOM, "shelf_count", count)

    def _check_choices(self) -> None:
        for name in ("material_id", "back_material_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise _error(UNKNOWN_VALUE, name, value)
        try:
            object.__setattr__(self, "joinery", CarcassJoinery(self.joinery))
        except ValueError:
            raise _error(UNKNOWN_VALUE, "joinery", self.joinery) from None
        if self.joinery is CarcassJoinery.DOWELS and self.thickness < MIN_JOINED_THICKNESS_MM:
            limit = decimal_text(MIN_JOINED_THICKNESS_MM)
            raise _error(TOO_THIN, "thickness", self.thickness, min=limit)
        origin = self.origin
        values = [getattr(origin, axis, None) for axis in "xyz"]
        coordinates = [to_finite_float(value) for value in values]
        if not isinstance(origin, Vec3) or any(value is None for value in coordinates):
            raise CarcassError(INVALID_ORIGIN, {"field": FIELDS["origin"]})


def _positive_below(params: CarcassParams, name: str, limit: float, template: str) -> float:
    """Valeur du champ ``name``, strictement entre 0 et ``limit`` ; refus sinon."""
    value = to_finite_float(getattr(params, name))
    if value is None or not 0 < value < limit:
        raise _error(template, name, getattr(params, name), max=decimal_text(limit))
    object.__setattr__(params, name, value)
    return value


def _shelf_gap(params: CarcassParams) -> float:
    """Intervalle égal entre le dessous, les étagères et le dessus."""
    inside = params.height - 2 * params.thickness
    return (inside - params.shelf_count * params.thickness) / (params.shelf_count + 1)


def check_materials(params: CarcassParams, known: Collection[str]) -> None:
    """Refuse (``CarcassError`` citant le champ) un identifiant de matériau absent de
    ``known`` (identifiants de la bibliothèque)."""
    for name in ("material_id", "back_material_id"):
        value = getattr(params, name)
        if value not in known:
            raise _error(UNKNOWN_VALUE, name, value)


# --- Pièces ---------------------------------------------------------------------------------


Row = tuple[float, float, float]


def _block(size: Row, base: Row, rotation: tuple[Row, Row, Row]) -> PlacedBlock:
    """Pièce de cotes ``size`` (L, l, e), origine locale en ``base``, axes tournés."""
    rows = [[*row, base[index]] for index, row in enumerate(rotation)]
    return PlacedBlock(Dimensions(*size), RigidTransform.from_matrix([*rows, [0, 0, 0, 1]]))


def _without(*edges: Edge) -> frozenset[Edge]:
    return _ALL_EDGES - frozenset(edges)


def _panels(params: CarcassParams) -> list[PieceSpec]:
    """Côtés, dessous et dessus : fixes sur les bords qu'ils touchent et du côté des pièces
    qu'ils touchent (toutes les distances, sauf la face intérieure de l'épaisseur)."""
    w, d, h, t = params.width, params.depth, params.height, params.thickness
    side, across = (h, d, t), (w - 2 * t, d, t)
    layout = {  # clé : (cotes, origine locale, rotation, face intérieure non fixe)
        "left": (side, (t, 0.0, 0.0), _UPRIGHT, Edge.RIGHT),
        "right": (side, (w, 0.0, 0.0), _UPRIGHT, Edge.LEFT),
        "bottom": (across, (t, 0.0, 0.0), _FLAT, Edge.TOP),
        "top": (across, (t, 0.0, h - t), _FLAT, Edge.BOTTOM),
    }
    return [
        PieceSpec(key, LABELS[key], _block(size, base, turn), params.material_id, _without(inner))
        for key, (size, base, turn, inner) in layout.items()
    ]


def _back(params: CarcassParams) -> PieceSpec:
    """Fond logé de ``rabbet_depth`` dans les feuillures : retraits fixes sur ses quatre
    chants ; sur son épaisseur, seule la face arrière est fixe (une seule règle, F7)."""
    w, d, h, t = params.width, params.depth, params.height, params.thickness
    inset = t - params.rabbet_depth
    size = (h - 2 * inset, w - 2 * inset, params.back_thickness)
    block = _block(size, (inset, d - params.back_thickness, inset), _STANDING)
    return PieceSpec("back", LABELS["back"], block, params.back_material_id, _without(Edge.FRONT))


def _shelves(params: CarcassParams) -> list[PieceSpec]:
    """Étagères posées, jeux fixes aux côtés, devant et au fond ; non fixes en hauteur."""
    t, gap = params.thickness, _shelf_gap(params)
    size = (
        params.width - 2 * t - 2 * SHELF_GAP_MM,
        params.depth - params.back_thickness - SHELF_GAP_MM,
        t,
    )
    fixed = _without(Edge.BOTTOM, Edge.TOP)
    return [
        PieceSpec(
            f"shelf{index}",
            LABELS["shelf"],
            _block(size, (t + SHELF_GAP_MM, 0.0, t + index * gap + (index - 1) * t), _FLAT),
            params.material_id,
            fixed,
        )
        for index in range(1, params.shelf_count + 1)
    ]


# --- Assemblages ----------------------------------------------------------------------------


def dowel_params(thickness: float) -> DowelParams:
    """Tourillons des côtés : diamètre du commerce d'au plus la moitié de l'épaisseur,
    enfoncés des deux tiers de l'épaisseur dans le côté, aussi profond que l'épaisseur dans le
    dessus ou le dessous (18 mm : Ø 8 x 30, 12 dans le côté). Nombre automatique."""
    diameter = max(d for d in _STANDARD_DIAMETERS if d <= thickness / 2)
    host_depth = mm_round(2 * thickness / 3)
    return DowelParams(
        diameter=diameter, dowel_length=host_depth + thickness, host_depth=host_depth
    )


def _joints(params: CarcassParams) -> list[JointSpec]:
    joints: list[JointSpec] = []
    if params.joinery is CarcassJoinery.DOWELS:
        dowels = dowel_params(params.thickness)
        joints += [
            JointSpec(JointKind.DOWELS, side, panel, dowels)
            for side in ("left", "right")
            for panel in ("bottom", "top")
        ]
    rabbet = RabbetParams(through=True)
    joints += [
        JointSpec(JointKind.RABBET, host, "back", rabbet)
        for host in ("left", "right", "bottom", "top")
    ]
    return joints


def carcass_layout(params: CarcassParams) -> Layout:
    """Pièces et assemblages du caisson (fonction pure, ADR 0010)."""
    box = FurnitureBox(params.width, params.depth, params.height)
    pieces = (*_panels(params), _back(params), *_shelves(params))
    return Layout(
        CARCASS_TEMPLATE, CARCASS_LABEL, box, params.origin, pieces, tuple(_joints(params))
    )
