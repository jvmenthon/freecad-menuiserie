# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaison des copies d'ensembles à leur source par expressions natives (ADR 0043, lot R-b3).

Copie d'ensemble ``E'`` de rang ``k`` de l'ensemble source ``E`` :

- ``Width``, ``Depth``, ``Height`` = celles de ``E`` ;
- ``Origin.c`` = ``E.Origin.c`` (+ ``i * (R.Reverse ? -1 : 1) * R.Step`` pour chaque composante dont
  la copie n'est pas à l'original ; ``Reverse2`` et ``Step2`` pour la deuxième ligne de la grille,
  ADR 0045) ;
- ensemble rangé dans un Std Part (ADR 0038, ADR 0044 « Std Part »), cas normal : la position est
  portée par le Std Part de la copie, dont ``Placement.Base.c`` = celui du Std Part de ``E`` (+ le
  décalage sur l'axe) et ``Placement.Rotation`` = la sienne ; ``Origin`` est alors celle de ``E``,
  sans décalage. Un ensemble ancien sans Std Part garde le décalage dans ``Origin``.

Copie ``M'`` d'un membre ``M`` de ``E``, rangée dans ``E'`` (dans son Std Part, à la même place que
``M`` dans celui de ``E``) : les propriétés que l'ensemble de
``M`` lui impose (ses liaisons, ``FurnitureBindings``) sont **laissées aux liaisons normales de
``E'``** (cotes étirées, positions) ; toutes les autres suivent ``M`` par expression :

- cote non liée (épaisseur, cote que ni l'ensemble ni la rangée n'étirent) = celle de ``M`` ;
- matériau, sens du fil, surcotes et rotation = ceux de ``M`` ;
- position pilotée par une formule de l'utilisateur sur ``M`` = celle de ``M`` plus le décalage
  de ``E'`` par rapport à l'ensemble de ``M`` (``E'.Origin.c - E.Origin.c``, nul si ``E'`` a son
  Std Part : le décalage est dans celui-ci).

Comme pour une pièce, ces expressions citent les objets par leur ``Name`` et sont écrites par
l'API dans la transaction en cours. Une position sans formule, même non liée par l'ensemble de
``M``, est liée par ``E'`` si ``E'`` n'a pas de Std Part : c'est alors une copie dont l'``Origin``
bouge, toutes les positions de ses membres la suivent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from freecad.menuiserie.core.repeat import Cell, RepeatAxis, axis_index
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import workshop_expressions
from freecad.menuiserie.features.furniture_container import member_expressions, std_part_of
from freecad.menuiserie.features.repeat_props import line_name
from freecad.menuiserie.features.shaped_part import is_shaped_part

__all__ = [
    "COMPONENTS",
    "DIMENSIONS",
    "FURNITURE_DIMENSIONS",
    "FURNITURE_PATHS",
    "MATERIAL",
    "ROTATION",
    "SHAPED",
    "furniture_cell_expressions",
    "furniture_expressions",
    "inner_expressions",
    "shift_terms",
    "shift_text",
    "step_text",
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
# Pièce en bois (ADR 0050) : repère et épaisseur de profil suivent la source ; les cotes
# d'encombrement (``DIMENSIONS``) viennent du dessin et ne sont jamais liées.
SHAPED: Final = ("SourceAxes", "ProfileThickness")
COMPONENTS: Final = {RepeatAxis.X: "x", RepeatAxis.Y: "y", RepeatAxis.Z: "z"}
ROTATION: Final = "Placement.Rotation"
FURNITURE_PATHS: Final = (
    *FURNITURE_DIMENSIONS,
    *(f"Origin.{c}" for c in COMPONENTS.values()),
)


def step_text(repeat: str, line: int, count: int) -> str:
    """Décalage de ``count`` pas sur l'axe de la ligne ``line`` de la répétition :
    ``count * (R.Reverse ? -1 : 1) * R.Step`` (``Reverse2`` et ``Step2`` pour la ligne 2…)."""
    reverse, step = line_name("Reverse", line), line_name("Step", line)
    return f"{count} * ({repeat}.{reverse} ? -1 : 1) * {repeat}.{step}"


def shift_text(repeat: str, index: int) -> str:
    """Décalage de la copie de rang ``index`` sur l'axe de la première ligne :
    ``k * (R.Reverse ? -1 : 1) * R.Step``."""
    return step_text(repeat, 0, index)


def shift_terms(repeat: str, cell: Cell, axes: Sequence[RepeatAxis]) -> dict[RepeatAxis, str]:
    """Décalage de la copie de cellule ``cell`` sur chaque axe où elle n'est pas à l'original :
    axe → texte d'expression. ``axes`` : axe de chaque ligne de la répétition, dans l'ordre des
    lignes (la ligne ``n`` lit ``Step`` ou ``Step{n+1}``)."""
    return {
        axis: step_text(repeat, line, cell[axis_index(axis)])
        for line, axis in enumerate(axes)
        if cell[axis_index(axis)] > 0
    }


def furniture_cell_expressions(
    source: str, shifts: Mapping[RepeatAxis, str], std_part: str | None = None
) -> dict[str, str]:
    """Expressions de la copie d'ensemble : propriété → texte. ``source`` : nom (``Name``) de
    l'ensemble ; ``shifts`` : décalage de la copie sur chaque axe (:func:`shift_terms`) ;
    ``std_part`` : nom du Std Part de la source (la copie a le sien, qui porte le décalage),
    ``None`` pour un ensemble sans Std Part (le décalage est dans ``Origin``)."""
    expressions = {name: f"{source}.{name}" for name in FURNITURE_DIMENSIONS}
    for component in COMPONENTS.values():
        expressions[f"Origin.{component}"] = f"{source}.Origin.{component}"
    if std_part is None:
        for axis, text in shifts.items():
            expressions[f"Origin.{COMPONENTS[axis]}"] += f" + {text}"
        return expressions
    for component in COMPONENTS.values():
        expressions[f"Placement.Base.{component}"] = f"{std_part}.Placement.Base.{component}"
    for axis, text in shifts.items():
        expressions[f"Placement.Base.{COMPONENTS[axis]}"] += f" + {text}"
    expressions[ROTATION] = f"{std_part}.{ROTATION}"
    return expressions


def furniture_expressions(
    source: str, repeat: str, index: int, axis: RepeatAxis, std_part: str | None = None
) -> dict[str, str]:
    """:func:`furniture_cell_expressions` pour la copie de rang ``index`` d'une répétition sur un
    seul axe (``repeat`` : nom de la répétition)."""
    return furniture_cell_expressions(source, {axis: shift_text(repeat, index)}, std_part)


def inner_expressions(copy: DocumentObject, original: DocumentObject) -> dict[str, str]:
    """Expressions de ``copy``, copie du membre ``original`` rangée dans l'ensemble copie de
    l'ensemble de ``original`` : seulement ce que les liaisons de l'ensemble copie ne couvrent pas
    (voir le module)."""
    bound = workshop_expressions(original)
    name = original.Name
    placed = std_part_of(furniture_of(copy) or copy) is not None  # le décalage est dans le Std Part
    furniture = is_furniture(original)
    shaped = is_shaped_part(original)
    dimensions = FURNITURE_DIMENSIONS if furniture else () if shaped else DIMENSIONS
    expressions = {dim: f"{name}.{dim}" for dim in dimensions if dim not in bound}
    if not furniture:
        linked = (*MATERIAL, ROTATION, *(SHAPED if shaped else ()))
        expressions.update({prop: f"{name}.{prop}" for prop in linked})
    parent, parent_copy = furniture_of(original), furniture_of(copy)
    if parent is None or parent_copy is None:
        return expressions
    carried = furniture and std_part_of(original) is not None  # position : Placement du Std Part
    root = "Origin" if furniture and not carried else "Placement.Base"
    formulas = member_expressions(original)
    for component in COMPONENTS.values():
        path = f"{root}.{component}"
        if path in formulas and path not in bound:  # formule de l'utilisateur : elle suit
            offset = f"{parent_copy.Name}.Origin.{component} - {parent.Name}.Origin.{component}"
            expressions[path] = f"{name}.{path}" + ("" if placed else f" + ({offset})")
    return expressions
