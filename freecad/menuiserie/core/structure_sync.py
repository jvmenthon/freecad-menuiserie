# SPDX-License-Identifier: LGPL-2.1-or-later
"""Synchronisation du panneau « Structure » (ADR 0046, lot 2), sans FreeCAD ni Qt.

Logique pure que ``gui/structure_sync.py`` branche sur les observateurs et les minuteries :
regroupement des notifications (:class:`Coalescer`), garde contre les boucles de rétroaction
entre le panneau et la sélection de FreeCAD (:class:`ReentrancyGuard`), identité des lignes pour
garder l'état déplié d'un rafraîchissement à l'autre, et correspondance entre objets
sélectionnés et lignes.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from contextlib import contextmanager
from typing import Final

from freecad.menuiserie.core.structure_tree import StructureNode

__all__ = [
    "IGNORED_PROPERTIES",
    "Coalescer",
    "ReentrancyGuard",
    "expanded_after_refresh",
    "is_relevant_change",
    "keys_to_select_in_freecad",
    "node_id",
    "rows_for_selection",
]

# Propriétés dont la modification ne change jamais l'arbre (géométrie, affichage) : un
# recalcul ou un déplacement ne relance pas le panneau.
IGNORED_PROPERTIES: Final = frozenset({"Shape", "Placement", "Visibility", "Proxy", "Touched"})


def is_relevant_change(property_name: str) -> bool:
    """Vrai si la modification de ``property_name`` peut changer l'arbre du panneau."""
    return property_name not in IGNORED_PROPERTIES


class Coalescer:
    """Fond une rafale de demandes en une seule exécution différée de ``action``.

    ``schedule(callback)`` fournit le différé (``QTimer.singleShot`` dans l'interface, un
    simple rangement dans les tests). Une demande faite pendant l'attente est absorbée ; une
    demande faite pendant ``action`` en programme une nouvelle."""

    def __init__(
        self, schedule: Callable[[Callable[[], None]], None], action: Callable[[], None]
    ) -> None:
        self._schedule = schedule
        self._action = action
        self._pending = False

    @property
    def pending(self) -> bool:
        """Vrai si une exécution est attendue."""
        return self._pending

    def request(self) -> None:
        """Demande l'exécution (sans effet si elle est déjà attendue)."""
        if not self._pending:
            self._pending = True
            self._schedule(self._run)

    def cancel(self) -> None:
        """Annule l'exécution attendue (le rappel déjà programmé ne fera plus rien)."""
        self._pending = False

    def _run(self) -> None:
        if not self._pending:
            return
        self._pending = False
        self._action()


class ReentrancyGuard:
    """Garde contre la rétroaction : pendant qu'un côté (panneau ou sélection de FreeCAD)
    écrit dans l'autre, les notifications qui en reviennent sont ignorées."""

    def __init__(self) -> None:
        self._depth = 0

    @property
    def active(self) -> bool:
        """Vrai pendant un :meth:`applying`."""
        return self._depth > 0

    @contextmanager
    def applying(self) -> Iterator[None]:
        """Marque une écriture en cours, même si elle échoue."""
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1


def node_id(parent_id: str, node: StructureNode) -> str:
    """Identité stable d'une ligne : chemin des clés depuis la racine (le nœud « Assemblages »,
    sans clé, prend son genre), pour retrouver l'état déplié après un rafraîchissement."""
    return f"{parent_id}/{node.key or node.kind.value}"


def expanded_after_refresh(default: bool, ident: str, previous: Mapping[str, bool]) -> bool:
    """État déplié d'une ligne reconstruite : celui que l'utilisateur lui avait laissé, sinon
    celui du modèle (``default``)."""
    return previous.get(ident, default)


def rows_for_selection(selected: Iterable[str], row_keys: Collection[str]) -> list[str]:
    """Clés des lignes à surligner pour les objets sélectionnés (``selected``, déjà ramenés à
    la clé de ligne) : celles que le panneau montre, sans doublon, dans l'ordre reçu."""
    seen: dict[str, None] = {}
    for key in selected:
        if key in row_keys:
            seen[key] = None
    return list(seen)


def keys_to_select_in_freecad(row_keys: Iterable[str]) -> list[str]:
    """Objets à sélectionner dans FreeCAD pour les lignes choisies (``row_keys`` : clé de
    chaque ligne choisie) : sans clé vide (nœud « Assemblages ») ni doublon."""
    return list(dict.fromkeys(key for key in row_keys if key))
