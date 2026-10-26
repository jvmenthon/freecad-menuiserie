# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaisons sans cycle entre objets (ADR 0019, limite connue).

Le graphe de dépendances de FreeCAD est par objet : une pièce dont une expression cite
l'épaisseur d'une autre en dépend, et deux pièces ne peuvent pas se citer l'une l'autre
(``RuntimeError: cyclic reference``). Les liaisons voulues de tous les membres sont donc
parcourues dans un ordre déterministe (clés triées, cote avant position, axes X, Y, Z) ; le terme
d'épaisseur qui fermerait un cycle est figé en constante (coefficient x épaisseur actuelle). Une
pièce peut citer sa propre épaisseur.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from freecad.menuiserie.core.furniture._linear import Linear
from freecad.menuiserie.core.furniture._model import FurnitureAxis

__all__ = ["Wanted", "break_cycles"]


@dataclass(frozen=True)
class Wanted:
    """Liaison voulue : propriété, axe, valeur affine, écrite depuis l'``Origin`` (position),
    et vrai si elle est écrite même constante (positions d'un sous-ensemble)."""

    prop: str
    axis: FurnitureAxis
    linear: Linear
    from_origin: bool
    always: bool = False


def _reaches(edges: Mapping[str, set[str]], start: str, target: str) -> bool:
    seen: set[str] = set()
    todo = [start]
    while todo:
        found = todo.pop()
        if found == target:
            return True
        if found not in seen:
            seen.add(found)
            todo.extend(edges.get(found, ()))
    return False


def _acyclic(
    key: str, linear: Linear, edges: dict[str, set[str]], thicknesses: Mapping[str, float]
) -> Linear:
    """``linear`` de la liaison de ``key``, ses termes qui fermeraient un cycle figés."""
    frozen: dict[str, float] = {}
    for cited in sorted(linear.keys - {key}):
        if _reaches(edges, cited, key):
            frozen[cited] = thicknesses[cited]
        else:
            edges.setdefault(key, set()).add(cited)
    return linear.frozen(frozen) if frozen else linear


def break_cycles(
    wanted: Mapping[str, list[Wanted]], thicknesses: Mapping[str, float]
) -> dict[str, list[Wanted]]:
    """Liaisons voulues (par clé de membre) sans cycle entre membres. ``thicknesses`` : épaisseur
    actuelle de chaque pièce. Une liaison devenue constante est retirée (sauf ``always``)."""
    edges: dict[str, set[str]] = {}
    result: dict[str, list[Wanted]] = {}
    for key in sorted(wanted):
        kept: list[Wanted] = []
        for item in wanted[key]:
            linear = _acyclic(key, item.linear, edges, thicknesses)
            if item.always or not linear.constant:
                kept.append(replace(item, linear=linear))
        result[key] = kept
    return result
