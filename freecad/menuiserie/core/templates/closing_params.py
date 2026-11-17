# SPDX-License-Identifier: LGPL-2.1-or-later
"""Paramètres du gabarit « Fermer le caisson » (ADR 0064) : valeurs validées à la construction.

Les entrées sont bornées (CONTRIBUTING, « Entrées utilisateur ») : hauteur, épaisseurs, quarts de
tour et choix sont refusés par une :class:`ClosingError` qui cite le champ, jamais acceptés « au
mieux ». La géométrie est dans :mod:`.closing`, les assemblages dans :mod:`.closing_joints`.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum
from typing import Final, TypeVar

from freecad.menuiserie.core._validation import decimal_text, to_finite_float
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, Dimensions

__all__ = [
    "BACK_RABBET_MM",
    "DEFAULT_ELEMENTS",
    "DEFAULT_HEIGHT_MM",
    "GROOVE_SETBACK_MM",
    "MAX_FRONT_TURNS",
    "MIN_DOWELLED_THICKNESS_MM",
    "MIN_INNER_MM",
    "THIN_BACK_MM",
    "BackJoinery",
    "ClosingError",
    "ClosingJoinery",
    "ClosingParams",
    "ClosingRole",
    "Element",
    "check_materials",
]

DEFAULT_HEIGHT_MM: Final = 720.0
MAX_FRONT_TURNS: Final = 3  # avant tourné de 0 à 3 quarts de tour
THIN_BACK_MM: Final = 8.0  # épaisseur par défaut du fond mince (au plus celle de l'ancre)
BACK_RABBET_MM: Final = 10.0  # profondeur de la feuillure du fond (réduite aux pièces minces)
GROOVE_SETBACK_MM: Final = 10.0  # recul du fond dans une rainure, depuis l'arrière
MIN_INNER_MM: Final = 1.0  # hauteur intérieure minimale entre l'ancre et la pièce opposée
MIN_DOWELLED_THICKNESS_MM: Final = 12.0  # tourillons de 6 mm au moins, 3 mm de fond de perçage


class Element(str, Enum):
    """Éléments que le menuisier peut activer ou désactiver (valeurs stables)."""

    LEFT = "left"
    RIGHT = "right"
    BACK = "back"
    FRONT = "front"
    OPPOSITE = "opposite"


DEFAULT_ELEMENTS: Final = frozenset({Element.LEFT, Element.RIGHT, Element.BACK, Element.OPPOSITE})


class ClosingRole(str, Enum):
    """Rôle de la pièce sélectionnée : le caisson monte (dessous) ou descend (dessus)."""

    BOTTOM = "bottom"
    TOP = "top"


class ClosingJoinery(str, Enum):
    """Assemblage commun à tous les angles des côtés (valeurs stables)."""

    NONE = "None"  # pièces aboutées, à visser ou à coller
    DOWELS = "Dowels"
    DOVETAIL = "Dovetail"
    MITER = "Miter"
    RABBET = "Rabbet"


class BackJoinery(str, Enum):
    """Assemblage du fond mince avec son pourtour (valeurs stables)."""

    RABBET = "Rabbet"  # feuillure arrière (comme le gabarit Caisson)
    GROOVE = "Groove"  # rainure dans le pourtour, fond reculé
    NONE = "None"  # fond posé entre les pièces, vissé derrière


FIELDS: Final = {
    "anchor": QT_TRANSLATE_NOOP("Menuiserie", "pièce sélectionnée"),
    "anchor_thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur de la pièce sélectionnée"),
    "height": QT_TRANSLATE_NOOP("Menuiserie", "hauteur hors tout"),
    "front_turns": QT_TRANSLATE_NOOP("Menuiserie", "avant du caisson"),
    "role": QT_TRANSLATE_NOOP("Menuiserie", "rôle de la pièce sélectionnée"),
    "elements": QT_TRANSLATE_NOOP("Menuiserie", "éléments du caisson"),
    "thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur des côtés"),
    "opposite_thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur de la pièce opposée"),
    "back_thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur du fond"),
    "material_id": QT_TRANSLATE_NOOP("Menuiserie", "matériau des côtés"),
    "opposite_material_id": QT_TRANSLATE_NOOP("Menuiserie", "matériau de la pièce opposée"),
    "back_material_id": QT_TRANSLATE_NOOP("Menuiserie", "matériau du fond"),
    "anchor_material_id": QT_TRANSLATE_NOOP("Menuiserie", "matériau de la pièce sélectionnée"),
    "joinery": QT_TRANSLATE_NOOP("Menuiserie", "assemblage des côtés"),
    "back_joinery": QT_TRANSLATE_NOOP("Menuiserie", "assemblage du fond"),
}
NOT_A_BLOCK: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Fermer le caisson : {field} invalide ; des cotes de pièce rectangulaire sont attendues.",
)
HEIGHT_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Fermer le caisson : {field} = {value} mm ; il faut au moins {min} mm (ancre, pièce opposée "
    "et {inner} mm d'intérieur) et au plus {max} mm.",
)
THICKNESS_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Fermer le caisson : {field} = {value} mm ; il faut plus de 0 mm et moins de la moitié de "
    "la plus petite cote du caisson ({max} mm).",
)
OTHER_THICKNESS_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Fermer le caisson : {field} = {value} mm ; il faut plus de 0 mm et au plus {max} mm.",
)
TURNS_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Fermer le caisson : {field} = {value} ; il faut un entier de 0 à {max}."
)
UNKNOWN_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Fermer le caisson : {field} inconnu : « {value} »."
)
TOO_THIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Fermer le caisson : {field} = {value} mm ; il faut au moins {min} mm pour des tourillons.",
)


class ClosingError(TemplatedError):
    """Paramètres de fermeture refusés ; ``params["field"]`` cite le champ (traduisible)."""


def _error(template: str, name: str, value: object, **params: str) -> ClosingError:
    number = to_finite_float(value)
    shown = decimal_text(number) if number is not None else str(value)
    return ClosingError(template, {"field": FIELDS[name], "value": shown, **params})


_C = TypeVar("_C", bound=Enum)


def _choice(kind: type[_C], name: str, value: object) -> _C:
    """``value`` converti en ``kind`` ; refus citant le champ ``name`` sinon."""
    try:
        return kind(value)
    except ValueError:
        raise _error(UNKNOWN_VALUE, name, value) from None


@dataclass(frozen=True)
class ClosingParams:
    """Paramètres de la fermeture d'un caisson autour d'une ancre (mm), validés à la
    construction (:class:`ClosingError` citant le champ).

    ``anchor`` : cotes de l'ancre (``Length`` selon X, ``Width`` selon Y, ``Thickness`` selon Z) ;
    ``role`` : dessous (le caisson monte) ou dessus (il descend) ; ``height`` : hauteur hors tout,
    ancre comprise ; ``front_turns`` : quarts de tour de l'avant (0 : bord Y = 0 de l'ancre) ;
    ``elements`` : éléments créés. Épaisseurs et matériaux valent ceux de l'ancre par défaut
    (``None``), sauf le fond mince (``THIN_BACK_MM`` au plus) ; une seule épaisseur pour les côtés,
    l'avant et le fond épais (``thick_back``). ``joinery`` : assemblage commun des angles des
    côtés ; ``back_joinery`` : assemblage du fond mince.
    """

    anchor: Dimensions
    anchor_material_id: str
    role: ClosingRole = ClosingRole.BOTTOM
    height: float = DEFAULT_HEIGHT_MM
    front_turns: int = 0
    elements: frozenset[Element] = DEFAULT_ELEMENTS
    thickness: float | None = None
    opposite_thickness: float | None = None
    back_thickness: float | None = None
    material_id: str | None = None
    opposite_material_id: str | None = None
    back_material_id: str | None = None
    thick_back: bool = False
    joinery: ClosingJoinery = ClosingJoinery.DOWELS
    back_joinery: BackJoinery = BackJoinery.RABBET

    def __post_init__(self) -> None:
        if not isinstance(self.anchor, Dimensions):
            raise _error(NOT_A_BLOCK, "anchor", self.anchor)
        self._check_choices()
        self._check_dimensions()
        self._check_materials()
        self._check_dowels()

    # --- Cotes du caisson ---------------------------------------------------------------

    @property
    def width(self) -> float:
        """Largeur du caisson (selon X) : celle de l'ancre, ou sa largeur d'un quart de tour."""
        return self.anchor.length if self.front_turns % 2 == 0 else self.anchor.width

    @property
    def depth(self) -> float:
        """Profondeur du caisson (selon Y, avant en 0)."""
        return self.anchor.width if self.front_turns % 2 == 0 else self.anchor.length

    def has(self, element: Element) -> bool:
        """Vrai si l'élément est créé."""
        return element in self.elements

    @property
    def side_t(self) -> float:
        """Épaisseur des côtés, de l'avant et du fond épais (résolue)."""
        return float(self.thickness or 0.0)

    @property
    def opposite_t(self) -> float:
        """Épaisseur de la pièce opposée (résolue)."""
        return float(self.opposite_thickness or 0.0)

    @property
    def back_t(self) -> float:
        """Épaisseur du fond : celle des côtés pour un fond épais, la sienne sinon."""
        return self.side_t if self.thick_back else float(self.back_thickness or 0.0)

    @property
    def rabbet_depth(self) -> float:
        """Profondeur de la feuillure du fond : ``BACK_RABBET_MM``, réduite à l'épaisseur de la
        plus mince des pièces qui la reçoivent."""
        hosts = [self.anchor.thickness]
        hosts += [self.side_t] * (self.has(Element.LEFT) or self.has(Element.RIGHT))
        hosts += [self.opposite_t] * self.has(Element.OPPOSITE)
        return min(BACK_RABBET_MM, *hosts)

    # --- Validation ---------------------------------------------------------------------

    def _check_choices(self) -> None:
        object.__setattr__(self, "role", _choice(ClosingRole, "role", self.role))
        object.__setattr__(self, "joinery", _choice(ClosingJoinery, "joinery", self.joinery))
        object.__setattr__(
            self, "back_joinery", _choice(BackJoinery, "back_joinery", self.back_joinery)
        )
        turns = self.front_turns
        if (
            isinstance(turns, bool)
            or not isinstance(turns, int)
            or not 0 <= turns <= MAX_FRONT_TURNS
        ):
            raise _error(TURNS_RANGE, "front_turns", turns, max=str(MAX_FRONT_TURNS))
        try:
            elements = frozenset(Element(item) for item in self.elements)
        except (TypeError, ValueError):
            raise _error(UNKNOWN_VALUE, "elements", self.elements) from None
        object.__setattr__(self, "elements", elements)
        object.__setattr__(self, "thick_back", bool(self.thick_back))

    def _check_dimensions(self) -> None:
        anchor = self.anchor.thickness
        limit = min(self.width, self.depth) / 2
        self._set("thickness", anchor, limit, THICKNESS_RANGE, strict=True)
        opposite = self._set("opposite_thickness", anchor, MAX_DIMENSION_MM, OTHER_THICKNESS_RANGE)
        self._set("back_thickness", min(anchor, THIN_BACK_MM), limit, THICKNESS_RANGE, strict=True)
        below = anchor + (opposite if self.has(Element.OPPOSITE) else 0.0)
        height = to_finite_float(self.height)
        if height is None or not below + MIN_INNER_MM <= height <= MAX_DIMENSION_MM:
            values = {
                "min": decimal_text(below + MIN_INNER_MM),
                "inner": decimal_text(MIN_INNER_MM),
                "max": decimal_text(MAX_DIMENSION_MM),
            }
            raise _error(HEIGHT_RANGE, "height", self.height, **values)
        object.__setattr__(self, "height", height)

    def _set(
        self, name: str, default: float, limit: float, template: str, *, strict: bool = False
    ) -> float:
        """Champ ``name`` résolu (``default`` si ``None``), entre 0 (exclu) et ``limit`` (exclu si
        ``strict``) ; refus citant le champ."""
        raw = getattr(self, name)
        value = to_finite_float(default if raw is None else raw)
        if value is None or value <= 0 or (value >= limit if strict else value > limit):
            raise _error(template, name, default if raw is None else raw, max=decimal_text(limit))
        object.__setattr__(self, name, value)
        return value

    def _check_materials(self) -> None:
        for name in (
            "anchor_material_id",
            "material_id",
            "opposite_material_id",
            "back_material_id",
        ):
            value = getattr(self, name)
            fallback = value is None and name != "anchor_material_id"
            if not fallback and (not isinstance(value, str) or not value):
                raise _error(UNKNOWN_VALUE, name, value)
            if fallback:
                object.__setattr__(self, name, self.anchor_material_id)

    def _check_dowels(self) -> None:
        """Tourillons : toutes les pièces qu'ils joignent ont au moins 12 mm d'épaisseur."""
        if self.joinery is not ClosingJoinery.DOWELS:
            return
        if not (self.has(Element.LEFT) or self.has(Element.RIGHT)):
            return  # aucun côté : aucun assemblage
        needed = {"thickness": self.side_t, "anchor_thickness": self.anchor.thickness}
        if self.has(Element.OPPOSITE):
            needed["opposite_thickness"] = self.opposite_t
        for name, value in needed.items():
            if value < MIN_DOWELLED_THICKNESS_MM:
                limit = decimal_text(MIN_DOWELLED_THICKNESS_MM)
                raise _error(TOO_THIN, name, value, min=limit)


def check_materials(params: ClosingParams, known: Collection[str]) -> None:
    """Refuse (``ClosingError`` citant le champ) un identifiant de matériau de pièce **créée**
    absent de ``known`` (identifiants de la bibliothèque). L'ancre est déjà dans le document."""
    for name in ("material_id", "opposite_material_id", "back_material_id"):
        if getattr(params, name) not in known:
            raise _error(UNKNOWN_VALUE, name, getattr(params, name))
