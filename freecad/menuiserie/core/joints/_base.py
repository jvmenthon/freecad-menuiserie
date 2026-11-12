# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle des assemblages : types, plan d'usinage, protocole, arrondi et règles communes.

Module privé : la façade ``core.joints`` ré-exporte l'API publique.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Protocol, TypeVar, runtime_checkable

from freecad.menuiserie.core._polyhedron import PlanSolid
from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, bounded_float, decimal_text
from freecad.menuiserie.core.contact import Contact, Overlap, Relation, classify
from freecad.menuiserie.core.geometry import Axis, JointError, PlacedBlock, Vec3, is_square
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value

MAX_COUNT: Final = 50
MIN_WALL_MM: Final = 2.0  # matière laissée entre deux usinages voisins ou de chaque côté de l'un
MAX_ANGLE_DEG: Final = 30.0  # angle d'un flanc de queue d'aronde, au plus
# Garde-fou : au-delà, les opérations booléennes d'OCC peuvent figer FreeCAD (saisie aberrante).
MAX_PLAN_SOLIDS: Final = 1000
TOO_MANY_SOLIDS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'assemblage demanderait {count} formes d'usinage (au plus {max}) : vérifier les cotes "
    "saisies (pas, nombre, longueurs).",
)

SEPARATED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Les pièces ne se touchent pas.")
OVERLAPPING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les pièces se chevauchent sans que la pièce logée entre dans l'autre par un seul côté : "
    "elle ne peut pas être ramenée au contact.",
)
SQUARE_ONLY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cet assemblage demande des pièces d'équerre ; entre pièces en biais : tenon-mortaise ou "
    "rainure-languette.",
)
NOT_OVERLAPPING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les pièces ne se chevauchent pas : la pièce logée doit occuper la place de la feuillure ou "
    "toucher l'autre par une face.",
)

_PARAM_KIND: Final = "joint_param"
_CHOICES_KEY: Final = "joint_choices"
_DERIVED: Final = "joint_derived"  # champ fourni par le document, pas par une propriété
_INVALID: Final = object()


class ObliqueReference(str, Enum):
    """Pièce qui sert de référence au tenon entre pièces en biais (ADR 0024) : le tenon suit le
    fil de la pièce à tenon (défaut), est d'équerre à la face de la pièce mortaisée, ou partage
    l'écart par moitié. Sans effet entre pièces d'équerre."""

    TENON_PIECE = "TenonPiece"
    MORTISED_PIECE = "MortisedPiece"
    HALF_ANGLE = "HalfAngle"


OBLIQUE_REFERENCES: Final = tuple(reference.value for reference in ObliqueReference)


class JointKind(str, Enum):
    """Type d'assemblage ; non enregistré dans les documents (le chemin du proxy l'est)."""

    MORTISE_TENON = "MortiseTenon"
    TONGUE_GROOVE = "TongueGroove"
    RABBET = "Rabbet"
    DOWELS = "Dowels"
    HALF_LAP = "HalfLap"
    DOVETAIL = "Dovetail"
    MITER = "Miter"
    LOOSE_TENON = "LooseTenon"
    BISCUIT = "Biscuit"
    FOOT = "Foot"
    SHELF_PINS = "ShelfPins"
    DRAWER_SLIDE = "DrawerSlide"
    HINGE = "Hinge"


@dataclass(frozen=True)
class Bevel:
    """Bout d'une invitée coupé en biais : face coupée, normale du plan d'épaulement (repère de
    l'invitée) et coordonnée du long point sur l'axe de la face (liste de débit, AB-c)."""

    face: Axis
    normal: Vec3
    long_point: float

    def saw_angles(self) -> tuple[float, float]:
        """Réglages de la scie, en degrés au dixième : angle de coupe (dans le plan de la
        largeur) et inclinaison de lame (dans l'épaisseur). Pour un bout ±X, la normale
        (mx, my, mz) donne atan(|my| / |mx|) et atan(|mz| / √(mx² + my²))."""
        index = self.face.index
        width = 1 - index
        along, across = abs(self.normal.component(index)), abs(self.normal.component(width))
        cut = math.degrees(math.atan2(across, along))
        tilt = math.degrees(math.atan2(abs(self.normal.component(2)), math.hypot(along, across)))
        return round(cut, 1), round(tilt, 1)


@dataclass(frozen=True)
class JointPlan:
    """Plan d'usinage : ajouts et enlèvements dans le repère local de chaque pièce."""

    host_cuts: tuple[PlanSolid, ...] = ()  # repère local de l'hôte
    host_additions: tuple[PlanSolid, ...] = ()
    guest_cuts: tuple[PlanSolid, ...] = ()  # repère local de l'invitée
    guest_additions: tuple[PlanSolid, ...] = ()
    guest_trims: tuple[PlanSolid, ...] = ()  # retirés de l'invitée avant ses ajouts (ADR 0016)
    inserts: tuple[PlanSolid, ...] = ()  # pièces rapportées (tourillons), repère de l'hôte
    guest_bevels: tuple[Bevel, ...] = ()  # bouts coupés en biais (ADR 0024)

    def __post_init__(self) -> None:
        solids = (
            self.host_cuts,
            self.host_additions,
            self.guest_cuts,
            self.guest_additions,
            self.guest_trims,
            self.inserts,
        )
        count = sum(len(group) for group in solids)
        if count > MAX_PLAN_SOLIDS:
            raise JointError(TOO_MANY_SOLIDS, {"count": str(count), "max": str(MAX_PLAN_SOLIDS)})


P = TypeVar("P", contravariant=True)
R = TypeVar("R", covariant=True)


@runtime_checkable
class JointStrategy(Protocol[P, R]):
    """Calcul d'un type d'assemblage : valeurs effectives et plan d'usinage."""

    kind: ClassVar[JointKind]

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: P) -> R:
        """Valeurs effectives (automatiques résolues) utilisées par le plan."""

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: P) -> JointPlan:
        """Plan d'usinage ; lève :class:`JointError` si l'assemblage est impossible."""


def mm_round(value: float) -> float:
    """Arrondi au mm « demi vers le haut » (``floor(x + 0,5)``), au moins 1 mm."""
    return float(max(1, math.floor(value + 0.5)))


def mm_text(value: float) -> str:
    """Cote écrite à la française pour un message (« 7,5 »)."""
    return decimal_text(round(value, 6))


def square_relation(host: PlacedBlock, guest: PlacedBlock) -> Relation:
    """Position relative de deux pièces d'équerre, sinon :class:`JointError` ``SQUARE_ONLY``
    (assemblages qui ne savent pas le biais)."""
    if not is_square(host, guest):
        raise JointError(SQUARE_ONLY, {})
    return classify(host, guest)


def require_contact(host: PlacedBlock, guest: PlacedBlock) -> Contact:
    """Contact des deux pièces, sinon :class:`JointError`."""
    relation = square_relation(host, guest)
    if isinstance(relation, Contact):
        return relation
    raise JointError(OVERLAPPING if isinstance(relation, Overlap) else SEPARATED, {})


def require_overlap(host: PlacedBlock, guest: PlacedBlock) -> Overlap:
    """Chevauchement des deux pièces, sinon :class:`JointError`."""
    relation = square_relation(host, guest)
    if isinstance(relation, Overlap):
        return relation
    raise JointError(NOT_OVERLAPPING, {})


# --- Paramètres : objets valeur validés à la construction ---------------------------------


class ParamKind(Enum):
    """Nature d'un paramètre d'assemblage, qui fixe ses bornes."""

    LENGTH = "length"
    OFFSET = "offset"
    FLAG = "flag"
    COUNT = "count"
    ANGLE = "angle"
    CHOICE = "choice"


def _length(value: object) -> object:
    number = bounded_float(value, 0.0, MAX_DIMENSION_MM)
    return _INVALID if number is None else number


def _offset(value: object) -> object:
    number = bounded_float(value, -MAX_DIMENSION_MM, MAX_DIMENSION_MM)
    return _INVALID if number is None else number


def _flag(value: object) -> object:
    return value if isinstance(value, bool) else _INVALID


def _count(value: object) -> object:
    valid = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_COUNT
    return value if valid else _INVALID


def _angle(value: object) -> object:
    number = bounded_float(value, 0.0, MAX_ANGLE_DEG)
    return _INVALID if number is None else number


def _choice(value: object) -> object:
    return value  # contrôlé par validate_params, qui connaît la liste


_CHECKS: Final[Mapping[ParamKind, Callable[[object], object]]] = MappingProxyType(
    {
        ParamKind.LENGTH: _length,
        ParamKind.OFFSET: _offset,
        ParamKind.FLAG: _flag,
        ParamKind.COUNT: _count,
        ParamKind.ANGLE: _angle,
        ParamKind.CHOICE: _choice,
    }
)
_TEMPLATES: Final[Mapping[ParamKind, str]] = MappingProxyType(
    {
        ParamKind.LENGTH: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(longueur finie entre 0 et {max} mm attendue).",
        ),
        ParamKind.OFFSET: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(décalage fini entre -{max} et {max} mm attendu).",
        ),
        ParamKind.FLAG: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} (vrai ou faux attendu).",
        ),
        ParamKind.COUNT: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(nombre entier entre 0 et {max} attendu).",
        ),
        ParamKind.CHOICE: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} (choix attendu parmi {max}).",
        ),
        ParamKind.ANGLE: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(0 pour automatique, ou angle fini en degrés, supérieur à 0 et d'au plus {max}, "
            "attendu).",
        ),
    }
)
_MAXIMA: Final = MappingProxyType(
    {
        ParamKind.LENGTH: MAX_DIMENSION_MM,
        ParamKind.OFFSET: MAX_DIMENSION_MM,
        ParamKind.COUNT: MAX_COUNT,
        ParamKind.ANGLE: MAX_ANGLE_DEG,
    }
)


def length_param(default: float) -> Any:
    """Champ « longueur » : fini, non booléen, 0 ≤ x ≤ 20 000 mm (0 = automatique)."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.LENGTH})


def offset_param(default: float) -> Any:
    """Champ « décalage » : fini, non booléen, |x| ≤ 20 000 mm."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.OFFSET})


def flag_param(default: bool) -> Any:
    """Champ booléen."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.FLAG})


def count_param(default: int) -> Any:
    """Champ « nombre » : entier, non booléen, 0 à 50 (0 = automatique)."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.COUNT})


def angle_param(default: float) -> Any:
    """Champ « angle » en degrés : fini, non booléen, 0 (automatique) ou 0 < x ≤ 30°."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.ANGLE})


def choice_param(default: str, choices: tuple[str, ...]) -> Any:
    """Champ « choix » : texte parmi ``choices``."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.CHOICE, _CHOICES_KEY: choices})


def derived_param(default: Any) -> Any:
    """Champ « dérivé » : fourni par le document (pièces voisines…), sans propriété ni contrôle."""
    return field(default=default, metadata={_DERIVED: True})


def validate_params(params: object) -> None:
    """Contrôle et normalise chaque champ d'un objet de paramètres (``ValueError`` sinon)."""
    for item in fields(params):  # type: ignore[arg-type]
        if item.metadata.get(_DERIVED):
            continue
        kind: ParamKind = item.metadata[_PARAM_KIND]
        value = getattr(params, item.name)
        checked = _CHECKS[kind](value)
        if kind is ParamKind.CHOICE and value not in item.metadata[_CHOICES_KEY]:
            checked = _INVALID
        if checked is _INVALID:
            values = {"field": item.name, "value": quoted_value(value)}
            if kind in _MAXIMA:
                values["max"] = decimal_text(_MAXIMA[kind])
            if kind is ParamKind.CHOICE:
                values["max"] = ", ".join(item.metadata[_CHOICES_KEY])
            raise JointError(_TEMPLATES[kind], values)
        object.__setattr__(params, item.name, checked)
