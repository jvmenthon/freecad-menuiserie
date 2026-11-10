# SPDX-License-Identifier: LGPL-2.1-or-later
"""Racines du panneau « Structure » quand un fichier abîmé contient un cycle de sous-ensembles
(A dans B et B dans A, impossible par l'api), sans FreeCAD ni Qt."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

__all__ = ["with_cycle_entries"]


def _reachable(starts: Iterable[str], subs: Callable[[str], Sequence[str]]) -> set[str]:
    seen: set[str] = set()
    todo = list(starts)
    while todo:
        key = todo.pop()
        if key not in seen:
            seen.add(key)
            todo.extend(subs(key))
    return seen


def with_cycle_entries(
    roots: Sequence[str], furnitures: Sequence[str], subs: Callable[[str], Sequence[str]]
) -> list[str]:
    """``roots`` suivies, pour chaque ensemble qu'aucune racine n'atteint (cycle sans entrée :
    chaque ensemble est membre d'un autre), de cet ensemble comme racine supplémentaire, dans
    l'ordre de ``furnitures``. Sans cycle, ``roots`` inchangées."""
    result = list(roots)
    reached = _reachable(result, subs)
    for key in furnitures:
        if key not in reached:
            result.append(key)
            reached |= _reachable([key], subs)
    return result
