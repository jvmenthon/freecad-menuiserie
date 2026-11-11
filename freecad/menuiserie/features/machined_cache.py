# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cache borné des formes usinées (répétition d'un ensemble : les copies ont la même brute et
les mêmes enlèvements, exprimés dans le repère de la brute, que leur source).

La clé est exacte (aucun arrondi) : cotes de la brute et solides de l'usinage, comparés
valeur par valeur. Une forme dessinée n'est pas mise en cache (pas de signature sûre). Le cache
garde et rend des **copies** : l'objet OCC n'est jamais partagé entre deux pièces. Cache explicite,
borné et réinitialisable par :func:`reset_machined_cache`.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable, Sequence
from typing import Any, Final

from freecad.menuiserie.core._polyhedron import PlanSolid
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.solids import machined_shape
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = [
    "cached_machined_shape",
    "machined_cache_size",
    "machining_key",
    "reset_machined_cache",
]

MAX_ENTRIES: Final = 256

_Key = tuple[Hashable, ...]
_CACHE: OrderedDict[_Key, Any] = OrderedDict()


def reset_machined_cache() -> None:
    """Vide le cache (tests, rechargement)."""
    _CACHE.clear()


def machined_cache_size() -> int:
    """Nombre de formes mémorisées."""
    return len(_CACHE)


def machining_key(
    blank: DocumentObject,
    additions: Sequence[PlanSolid],
    cuts: Sequence[PlanSolid],
    trims: Sequence[PlanSolid],
) -> _Key | None:
    """Clé exacte de l'usinage de la brute ``blank`` (cotes et solides), ``None`` pour une forme
    dessinée ou si un solide n'est pas hachable : pas de cache."""
    if is_shaped_part(blank):
        return None
    key = (dimensions_of(blank), tuple(additions), tuple(cuts), tuple(trims))
    try:
        hash(key)
    except TypeError:
        return None
    return key


def cached_machined_shape(
    base: Any,
    key: _Key | None,
    additions: Sequence[PlanSolid],
    cuts: Sequence[PlanSolid],
    trims: Sequence[PlanSolid] = (),
) -> Any:
    """Comme :func:`machined_shape`, mémorisée sur ``key`` (:func:`machining_key`, ``None`` :
    calcul direct). Les échecs (``ValueError``) ne sont jamais mémorisés."""
    if key is None:
        return machined_shape(base, additions, cuts, trims)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key].copy()
    shape = machined_shape(base, additions, cuts, trims)
    _CACHE[key] = shape.copy()
    if len(_CACHE) > MAX_ENTRIES:
        _CACHE.popitem(last=False)
    return shape
