# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cache borné des plans d'usinage (répétition : les copies d'un assemblage ont les mêmes
cotes, le même placement relatif et les mêmes paramètres que leur source).

Un plan est exprimé dans le repère de chaque pièce ; il ne dépend donc que des cotes des deux
pièces, de leur placement relatif, de la rotation de l'hôte (le bas, pour les pieds et les
étagères) et des paramètres. La clé est exacte (aucun arrondi) ; sans clé hachable, ou en cas
d'échec (``JointError``, jamais mémorisé), le plan est recalculé. Un :class:`JointPlan` est
immuable : il peut être partagé. Cache explicite, borné et réinitialisable.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from typing import Any, Final

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.joints import JointPlan

__all__ = ["cached_plan", "plan_cache_size", "reset_plan_cache"]

MAX_ENTRIES: Final = 512

_CACHE: OrderedDict[Hashable, JointPlan] = OrderedDict()


def reset_plan_cache() -> None:
    """Vide le cache (tests, rechargement)."""
    _CACHE.clear()


def plan_cache_size() -> int:
    """Nombre de plans mémorisés."""
    return len(_CACHE)


def _key_of(strategy: Any, host: PlacedBlock, guest: PlacedBlock, params: Any) -> Hashable | None:
    """Clé exacte du plan, ``None`` si ``params`` n'est pas hachable."""
    relative = host.placement.inverse().compose(guest.placement)
    key = (
        strategy.kind,
        host.dimensions,
        guest.dimensions,
        host.placement.rotation,
        relative,
        params,
    )
    try:
        hash(key)
    except TypeError:
        return None
    return key


def cached_plan(strategy: Any, host: PlacedBlock, guest: PlacedBlock, params: Any) -> JointPlan:
    """``strategy.plan(host, guest, params)``, mémorisé sur ses entrées exprimées dans le repère
    local des deux pièces."""
    key = _key_of(strategy, host, guest, params)
    if key is None:
        plan: JointPlan = strategy.plan(host, guest, params)
        return plan
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    plan = strategy.plan(host, guest, params)
    _CACHE[key] = plan
    if len(_CACHE) > MAX_ENTRIES:
        _CACHE.popitem(last=False)
    return plan
