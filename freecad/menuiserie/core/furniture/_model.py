# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets valeur de l'ensemble, validés à la construction (J4a, critère F1).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Repère de l'ensemble :
X = largeur, Y = profondeur, Z = hauteur, coordonnées en mm relatives à son ``Origin``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import Enum
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core._validation import (
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    bounded_float,
    decimal_text,
    to_finite_float,
)
from freecad.menuiserie.core.furniture._messages import (
    BOX_FIELDS,
    DRAWN_SIZE,
    GAP_SPLIT,
    INVALID_BOX,
    NOT_SQUARE,
    OUTSIDE_BOX,
    THICKNESS_KEPT,
    USER_FORMULA,
)
from freecad.menuiserie.core.geometry import PlacedBlock, Vec3
from freecad.menuiserie.core.i18n import TemplatedError
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.core.text import quoted_value

PIECE_AXES: Final = ("Length", "Width", "Thickness")  # axes locaux d'une pièce (X, Y, Z)
THICKNESS: Final = "Thickness"


class FurnitureError(TemplatedError):
    """Refus (cote d'ensemble, redimensionnement, cycle d'ensembles) ; gabarit traduisible."""


class BlockedRowError(FurnitureError):
    """Refus d'un changement de cote ou d'épaisseur qu'aucune pièce de la rangée ne peut
    absorber (ADR 0019, point 5).

    ``locked`` : clés des membres verrouillés de la rangée (vide si les épaisseurs la
    remplissent), ``members`` : clés de tous les membres de la rangée ; le message cite leurs
    noms. Déverrouiller ``locked`` (ou en retirer) peut débloquer la rangée.
    """

    def __init__(
        self,
        template: str,
        params: Mapping[str, str],
        *,
        locked: tuple[str, ...],
        members: tuple[str, ...],
    ) -> None:
        super().__init__(template, params)
        self.locked = locked
        self.members = members


class InteriorMode(str, Enum):
    """Mode d'un membre (propriété ``PositionMode``) : valeurs stables, ajouts en fin seulement."""

    STAY = "Stay"  # distance non fixe : la face ne bouge pas
    PROPORTIONAL = "Proportional"  # distance non fixe : la face garde sa proportion


class FurnitureAxis(Enum):
    """Axe de l'ensemble, nommé par la cote qu'il porte : X = Width, Y = Depth, Z = Height."""

    WIDTH = "Width"
    DEPTH = "Depth"
    HEIGHT = "Height"

    @property
    def index(self) -> int:
        """Indice de l'axe : 0 (X), 1 (Y) ou 2 (Z)."""
        return tuple(FurnitureAxis).index(self)

    @classmethod
    def of(cls, index: int) -> FurnitureAxis:
        """Axe d'indice 0, 1 ou 2."""
        return tuple(cls)[index]


class Edge(str, Enum):
    """Bord de l'ensemble (propriétés ``Fixed<Edge>``) : valeurs stables, ordre figé."""

    LEFT = "Left"  # début de X
    RIGHT = "Right"  # fin de X
    FRONT = "Front"  # début de Y
    BACK = "Back"  # fin de Y
    BOTTOM = "Bottom"  # début de Z
    TOP = "Top"  # fin de Z

    @property
    def axis(self) -> FurnitureAxis:
        """Axe que ce bord termine."""
        return FurnitureAxis.of(tuple(Edge).index(self) // 2)

    @property
    def at_end(self) -> bool:
        """Vrai pour le bord de fin de l'axe (droite, arrière, haut)."""
        return tuple(Edge).index(self) % 2 == 1

    @classmethod
    def of(cls, axis: FurnitureAxis, at_end: bool) -> Edge:
        """Bord de début ou de fin d'un axe."""
        return tuple(cls)[2 * axis.index + int(at_end)]

    def opposite(self) -> Edge:
        """Bord opposé sur le même axe."""
        return Edge.of(self.axis, not self.at_end)


def _box_dimension(value: object, name: str) -> float:
    number = bounded_float(value, MIN_DIMENSION_MM, MAX_DIMENSION_MM)
    if number is not None:
        return number
    finite = to_finite_float(value)
    shown = decimal_text(finite) if finite is not None else quoted_value(value)
    params = {
        "field": BOX_FIELDS[name],
        "value": shown,
        "min": decimal_text(MIN_DIMENSION_MM),
        "max": decimal_text(MAX_DIMENSION_MM),
    }
    raise FurnitureError(INVALID_BOX, params)


@dataclass(frozen=True)
class FurnitureBox:
    """Cotes d'un ensemble en mm : finies, non booléennes, de 0,1 à 20 000 mm."""

    width: float
    depth: float
    height: float

    def __post_init__(self) -> None:
        for item in fields(self):
            number = _box_dimension(getattr(self, item.name), item.name)
            object.__setattr__(self, item.name, number)

    def size(self, axis: FurnitureAxis) -> float:
        """Cote de l'ensemble sur ``axis``."""
        return (self.width, self.depth, self.height)[axis.index]


GAP_TERM: Final = "gap:"  # préfixe de la clé d'une Distance dans un terme de ``Linear``


def gap_term(key: str) -> str:
    """Clé, dans un terme de ``Linear``, de la Distance de ``Name`` ``key`` (``Name.Value``)."""
    return GAP_TERM + key


@dataclass(frozen=True)
class KeptGap:
    """Distance gardée (ADR 0022) : bloc rigide virtuel entre la face de la pièce ``a`` (sa
    fin si ``a_end``, son début sinon, sur ``axis``) et celle de la pièce ``b``. ``key`` :
    ``Name`` de l'objet Distance, cité ``Name.Value`` ; ``label`` : son nom dans les messages."""

    key: str
    a: str
    a_end: bool
    b: str
    b_end: bool
    axis: FurnitureAxis
    label: str = ""

    def __post_init__(self) -> None:
        for name in ("key", "a", "b"):
            _require(bool(getattr(self, name)), f"KeptGap.{name} : texte non vide")
        _require(self.a != self.b, "KeptGap : deux pièces différentes attendues")
        _require(isinstance(self.axis, FurnitureAxis), "KeptGap.axis : FurnitureAxis attendu")

    @property
    def name(self) -> str:
        """Nom cité dans les messages : le libellé, sinon la clé."""
        return self.label or self.key


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_text_set(value: object) -> bool:
    return isinstance(value, frozenset) and all(isinstance(item, str) for item in value)


@dataclass(frozen=True)
class Member:
    """Membre d'un ensemble : pièce brute (``block``) ou sous-ensemble (``box`` et ``origin``).

    ``block`` : cotes et placement dans le repère de l'ensemble (``Origin`` déduite) ;
    ``fixed`` : bords dont la distance est fixe, ``None`` pour un membre qui entre dans
    l'ensemble (options par défaut à calculer) ; ``driven`` : propriétés pilotées par une
    formule ou une contrainte de l'utilisateur ; ``label`` : nom cité dans les messages ;
    ``locked`` : cotes fixes, la pièce ne change jamais de cotes (ADR 0019) ; ``drawn`` : cotes
    dessinées (pièce en bois, ADR 0020 décision 8) : toujours fixes, donc verrouillées sans
    pouvoir être déverrouillées ; ``gaps`` : distances gardées dont la pièce est l'une des deux
    (:class:`KeptGap`, ADR 0022).
    """

    key: str
    block: PlacedBlock | None = None
    box: FurnitureBox | None = None
    origin: Vec3 | None = None
    mode: InteriorMode = InteriorMode.STAY
    fixed: frozenset[Edge] | None = None
    driven: frozenset[str] = frozenset()
    label: str = ""
    locked: bool = False
    gaps: tuple[KeptGap, ...] = ()
    drawn: bool = False

    def __post_init__(self) -> None:
        _require(isinstance(self.key, str) and bool(self.key), "Member.key : texte non vide")
        _require(isinstance(self.label, str), "Member.label : texte attendu")
        piece = isinstance(self.block, PlacedBlock) and self.box is None and self.origin is None
        furniture = (
            self.block is None
            and isinstance(self.box, FurnitureBox)
            and isinstance(self.origin, Vec3)
        )
        _require(piece or furniture, "Member.block ou Member.box et Member.origin attendus")
        _require(isinstance(self.mode, InteriorMode), "Member.mode : InteriorMode attendu")
        fixed_ok = self.fixed is None or (
            isinstance(self.fixed, frozenset) and all(isinstance(e, Edge) for e in self.fixed)
        )
        _require(fixed_ok, "Member.fixed : frozenset d'Edge ou None attendu")
        _require(_is_text_set(self.driven), "Member.driven : frozenset de textes attendu")
        _require(isinstance(self.locked, bool), "Member.locked : booléen attendu")
        _require(isinstance(self.drawn, bool), "Member.drawn : booléen attendu")
        if self.drawn and not self.locked:  # des cotes dessinées sont toujours fixes
            object.__setattr__(self, "locked", True)
        _require(
            isinstance(self.gaps, tuple) and all(isinstance(g, KeptGap) for g in self.gaps),
            "Member.gaps : tuple de KeptGap attendu",
        )

    @property
    def name(self) -> str:
        """Nom cité dans les messages : le libellé, sinon la clé."""
        return self.label or self.key


@dataclass(frozen=True)
class Binding:
    """Liaison : expression FreeCAD posée sur une propriété d'un membre."""

    key: str
    prop: str
    expression: str

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            _require(isinstance(value, str) and bool(value), f"Binding.{item.name} : texte")


class NoticeKind(str, Enum):
    """Nature d'un avertissement."""

    USER_FORMULA = "UserFormula"
    NOT_SQUARE = "NotSquare"
    THICKNESS_KEPT = "ThicknessKept"
    OUTSIDE_BOX = "OutsideBox"
    GAP_SPLIT = "GapSplit"
    DRAWN_SIZE = "DrawnSize"

    @property
    def template(self) -> str:
        """Gabarit français marqué pour la traduction."""
        return _NOTICE_TEMPLATES[self]


_NOTICE_TEMPLATES: Final[Mapping[NoticeKind, str]] = MappingProxyType(
    {
        NoticeKind.USER_FORMULA: USER_FORMULA,
        NoticeKind.NOT_SQUARE: NOT_SQUARE,
        NoticeKind.THICKNESS_KEPT: THICKNESS_KEPT,
        NoticeKind.OUTSIDE_BOX: OUTSIDE_BOX,
        NoticeKind.GAP_SPLIT: GAP_SPLIT,
        NoticeKind.DRAWN_SIZE: DRAWN_SIZE,
    }
)


def notice(kind: NoticeKind, member: Member, **params: str) -> Notice:
    """Avertissement qui cite ``member``."""
    return Notice(kind, {"member": member.name, **params})
