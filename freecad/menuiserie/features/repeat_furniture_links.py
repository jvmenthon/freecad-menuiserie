# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaison des copies d'ensembles à leur source par expressions natives (ADR 0043, lot R-b3).

Copie d'ensemble ``E'`` de rang ``k`` de l'ensemble source ``E`` :

- ``Width``, ``Depth``, ``Height`` = celles de ``E`` ;
- ``Origin.c`` = ``E.Origin.c`` (+ ``k * (R.Reverse ? -1 : 1) * R.Step`` pour la seule composante
  de l'axe de la répétition).

Copie ``M'`` d'un membre ``M`` de ``E``, rangée dans ``E'`` : les propriétés que l'ensemble de
``M`` lui impose (ses liaisons, ``FurnitureBindings``) sont **laissées aux liaisons normales de
``E'``** (cotes étirées, positions) ; toutes les autres suivent ``M`` par expression :

- cote non liée (épaisseur, cote que ni l'ensemble ni la rangée n'étirent) = celle de ``M`` ;
- matériau, sens du fil, surcotes et rotation = ceux de ``M`` ;
- position pilotée par une formule de l'utilisateur sur ``M`` = celle de ``M`` plus le décalage
  de ``E'`` par rapport à l'ensemble de ``M`` (``E'.Origin.c - E.Origin.c``).

Comme pour une pièce, ces expressions citent les objets par leur ``Name`` et sont écrites par
l'API dans la transaction en cours. Une position sans formule, même non liée par l'ensemble de
``M``, est liée par ``E'`` : ``E'`` est une copie dont l'``Origin`` bouge, toutes les positions de
ses membres la suivent.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.repeat import RepeatAxis
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import workshop_expressions

__all__ = [
    "COMPONENTS",
    "DIMENSIONS",
    "FURNITURE_DIMENSIONS",
    "FURNITURE_PATHS",
    "MATERIAL",
    "ROTATION",
    "furniture_expressions",
    "inner_expressions",
    "shift_text",
]

DIMENSIONS: Final = ("Length", "Width", "Thickness")
FURNITURE_DIMENSIONS: Final = ("Width", "Depth", "Height")
MATERIAL: Final = (
    "Material",
    "GrainDirection",
    "LengthAllowance",
    "WidthAllowance",
    "ThicknessAllowance",
)
COMPONENTS: Final = {RepeatAxis.X: "x", RepeatAxis.Y: "y", RepeatAxis.Z: "z"}
ROTATION: Final = "Placement.Rotation"
FURNITURE_PATHS: Final = (
    *FURNITURE_DIMENSIONS,
    *(f"Origin.{c}" for c in COMPONENTS.values()),
)


def shift_text(repeat: str, index: int) -> str:
    """Décalage de la copie de rang ``index`` sur l'axe : ``k * (R.Reverse ? -1 : 1) * R.Step``."""
    return f"{index} * ({repeat}.Reverse ? -1 : 1) * {repeat}.Step"


def furniture_expressions(source: str, repeat: str, index: int, axis: RepeatAxis) -> dict[str, str]:
    """Expressions de la copie d'ensemble de rang ``index`` : propriété → texte. ``source`` et
    ``repeat`` sont les noms (``Name``) des objets."""
    expressions = {name: f"{source}.{name}" for name in FURNITURE_DIMENSIONS}
    for component in COMPONENTS.values():
        expressions[f"Origin.{component}"] = f"{source}.Origin.{component}"
    expressions[f"Origin.{COMPONENTS[axis]}"] += f" + {shift_text(repeat, index)}"
    return expressions


def inner_expressions(copy: DocumentObject, original: DocumentObject) -> dict[str, str]:
    """Expressions de ``copy``, copie du membre ``original`` rangée dans l'ensemble copie de
    l'ensemble de ``original`` : seulement ce que les liaisons de l'ensemble copie ne couvrent pas
    (voir le module)."""
    bound = workshop_expressions(original)
    name = original.Name
    furniture = is_furniture(original)
    dimensions = FURNITURE_DIMENSIONS if furniture else DIMENSIONS
    expressions = {dim: f"{name}.{dim}" for dim in dimensions if dim not in bound}
    if not furniture:
        expressions.update({prop: f"{name}.{prop}" for prop in (*MATERIAL, ROTATION)})
    parent, parent_copy = furniture_of(original), furniture_of(copy)
    if parent is None or parent_copy is None:
        return expressions
    root = "Origin" if furniture else "Placement.Base"
    formulas = expressions_of(original)
    for component in COMPONENTS.values():
        path = f"{root}.{component}"
        if path in formulas and path not in bound:  # formule de l'utilisateur : elle suit
            offset = f"{parent_copy.Name}.Origin.{component} - {parent.Name}.Origin.{component}"
            expressions[path] = f"{name}.{path} + ({offset})"
    return expressions
