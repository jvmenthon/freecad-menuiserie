# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaison d'une copie à sa source par expressions natives (ADR 0043, comme l'ADR 0009).

Pour la copie de rang ``k`` de la source ``S`` d'une répétition ``R`` sur l'axe ``a`` :

- ``Length``, ``Width``, ``Thickness`` = celles de ``S`` ;
- ``Placement.Base.c`` = ``S.Placement.Base.c`` (+ ``k * (R.Reverse ? -1 : 1) * R.Step`` pour la
  seule composante ``c`` de l'axe) ; ``Placement.Rotation`` = celle de ``S`` ;
- matériau, sens du fil et surcotes : **expressions aussi** (FreeCAD accepte une expression sur une
  énumération). Choix vérifié dans FreeCAD 1.1 : à l'évaluation, ``Material`` appelle le proxy de
  la copie (``select_material``), qui recopie identifiant, catégorie et masse volumique ; le sens
  du fil et les surcotes, liés eux aussi, gardent la valeur de la source. Un changement de
  matériau de la source (éditeur de propriétés ou ``set_material``) suit donc sans autre code.
  Limite connue : le libellé de ``Material`` doit figurer dans la liste de la copie, qui est la
  bibliothèque locale, comme celle de la source.

Les expressions citent les objets par leur ``Name`` (stable), jamais par leur libellé. Elles sont
écrites par l'API dans la transaction en cours, jamais pendant un recalcul ni dans un autre objet
que la copie. Retrait (:func:`unlink_copy`) : seules les expressions qui citent la source ou la
répétition sont retirées, une formule de l'utilisateur sur la même propriété est laissée.
"""

from __future__ import annotations

import re
from typing import Final

from freecad.menuiserie.core.repeat import RepeatAxis
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.repeat import (
    COPY_PROPERTY_NAMES,
    copies_of,
    is_copy,
    is_repeat,
    sources_of,
)

__all__ = [
    "BOUND_PATHS",
    "copy_expressions",
    "link_copy",
    "repeat_removed",
    "source_removed",
    "unlink_copy",
]

DIMENSIONS: Final = ("Length", "Width", "Thickness")
MATERIAL: Final = (
    "Material",
    "GrainDirection",
    "LengthAllowance",
    "WidthAllowance",
    "ThicknessAllowance",
)
COMPONENTS: Final = {RepeatAxis.X: "x", RepeatAxis.Y: "y", RepeatAxis.Z: "z"}
ROTATION: Final = "Placement.Rotation"
BOUND_PATHS: Final = (
    *DIMENSIONS,
    *(f"Placement.Base.{c}" for c in COMPONENTS.values()),
    ROTATION,
    *MATERIAL,
)


def copy_expressions(source: str, repeat: str, index: int, axis: RepeatAxis) -> dict[str, str]:
    """Expressions de la copie de rang ``index`` : propriété → texte. ``source`` et ``repeat``
    sont les noms (``Name``) des objets."""
    expressions = {name: f"{source}.{name}" for name in (*DIMENSIONS, *MATERIAL)}
    for component in COMPONENTS.values():
        expressions[f"Placement.Base.{component}"] = f"{source}.Placement.Base.{component}"
    expressions[ROTATION] = f"{source}.{ROTATION}"
    moved = f"Placement.Base.{COMPONENTS[axis]}"
    expressions[moved] += f" + {index} * ({repeat}.Reverse ? -1 : 1) * {repeat}.Step"
    return expressions


def link_copy(
    copy: DocumentObject, source: DocumentObject, repeat: DocumentObject, axis: RepeatAxis
) -> None:
    """Écrit (ou réécrit) les expressions de ``copy`` d'après son rang ``RepeatIndex``."""
    expressions = copy_expressions(source.Name, repeat.Name, copy.RepeatIndex, axis)
    for path, text in expressions.items():
        copy.setExpression(path, text)


def _cites(text: str, names: set[str]) -> bool:
    """Vrai si l'expression ``text`` cite l'un des objets ``names`` (``Nom.propriété``)."""
    return any(re.search(rf"(?<![\w.]){re.escape(name)}\.", text) for name in names)


def unlink_copy(copy: DocumentObject) -> None:
    """Dissocie ``copy`` : retire ses expressions de liaison et ses propriétés ``Repeat``,
    ``RepeatSource`` et ``RepeatIndex``. Elle garde ses valeurs actuelles et devient une pièce
    libre. Sans effet sur ce qui n'est pas une copie liée."""
    if not is_copy(copy):
        return
    names = {obj.Name for obj in (copy.Repeat, copy.RepeatSource) if obj is not None}
    for path, text in expressions_of(copy).items():
        if path in BOUND_PATHS and _cites(text, names):
            copy.setExpression(path, None)
    for name in COPY_PROPERTY_NAMES:
        copy.removeProperty(name)


def _during_deletion(obj: DocumentObject) -> bool:
    """Faux pendant une annulation, un rétablissement ou une restauration : seule une
    suppression par l'utilisateur ou par un script dissocie les copies."""
    return "Restore" in obj.State or bool(obj.Document.Transacting)


def repeat_removed(repeat: DocumentObject) -> None:
    """Répétition supprimée (``unsetupObject``) : ses copies sont dissociées."""
    if _during_deletion(repeat):
        return
    for copy in copies_of(repeat):
        unlink_copy(copy)


def source_removed(source: DocumentObject) -> None:
    """Pièce source supprimée (``unsetupObject`` de la pièce) : ses copies restantes sont
    dissociées, puis la pièce sort de ``Source`` de ses répétitions."""
    if _during_deletion(source):
        return
    for parent in list(source.InList):
        if is_copy(parent) and parent.RepeatSource == source:
            unlink_copy(parent)
        elif is_repeat(parent) and source in sources_of(parent):
            parent.Source = [obj for obj in sources_of(parent) if obj != source]
