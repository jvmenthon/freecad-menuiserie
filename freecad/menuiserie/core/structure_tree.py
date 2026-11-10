# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arbre simplifié du panneau « Structure » (ADR 0046, lot 1), calculé sans FreeCAD.

L'arbre est une valeur immuable bâtie par :func:`build_structure` d'après une
:class:`StructureSource` (lecture du document, fournie par ``features/``). Un nœud par ensemble
(les sous-ensembles sont ses enfants), ses pièces (brute et pièce usinée : une seule ligne), puis
un nœud « Assemblages (N) » qui regroupe assemblages, quincaillerie et Distances. Les pièces hors
ensemble sont à la racine. Les clés des nœuds sont les noms des objets du document.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final, Protocol

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

# Gabarit du nœud replié des assemblages ; ``{count}`` est le nombre d'éléments qu'il contient.
JOINTS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblages ({count})")


class NodeKind(Enum):
    """Nature d'un nœud du panneau."""

    FURNITURE = "furniture"
    PIECE = "piece"
    JOINTS = "joints"  # nœud replié « Assemblages (N) »
    JOINT = "joint"  # assemblage, quincaillerie ou Distance


@dataclass(frozen=True)
class StructureNode:
    """Un nœud de l'arbre. ``key`` est le nom de l'objet du document que la ligne sélectionne
    (pièce usinée à la place de sa brute) ; vide pour le nœud « Assemblages (N) »."""

    kind: NodeKind
    label: str
    key: str = ""
    children: tuple[StructureNode, ...] = ()
    expanded: bool = True

    def walk(self) -> list[StructureNode]:
        """Le nœud puis tous ses descendants, en profondeur d'abord."""
        found = [self]
        for child in self.children:
            found.extend(child.walk())
        return found


class StructureSource(Protocol):
    """Lecture du document par le modèle : des noms d'objets et des libellés, rien d'autre."""

    def root_furnitures(self) -> Sequence[str]:
        """Ensembles qui ne sont membres d'aucun autre."""

    def loose_pieces(self) -> Sequence[str]:
        """Pièces qui ne sont membres d'aucun ensemble."""

    def sub_furnitures(self, furniture: str) -> Sequence[str]:
        """Sous-ensembles directs de ``furniture``."""

    def pieces(self, furniture: str) -> Sequence[str]:
        """Pièces directes de ``furniture`` (la pièce usinée à la place de sa brute)."""

    def joints(self, furniture: str) -> Sequence[str]:
        """Assemblages, quincaillerie et Distances de ``furniture``."""

    def label(self, key: str) -> str:
        """Libellé affiché pour l'objet ``key`` (vocabulaire du débutant)."""


def build_structure(
    source: StructureSource, joints_title: Callable[[int], str]
) -> tuple[StructureNode, ...]:
    """Racines de l'arbre : les ensembles de plus haut niveau, puis les pièces hors ensemble.
    ``joints_title(n)`` donne le texte traduit du nœud « Assemblages (n) »."""
    seen: set[str] = set()
    roots = [_furniture_node(source, key, joints_title, seen) for key in source.root_furnitures()]
    roots.extend(_piece_node(source, key) for key in source.loose_pieces())
    return tuple(roots)


def _piece_node(source: StructureSource, key: str) -> StructureNode:
    return StructureNode(NodeKind.PIECE, source.label(key), key)


def _furniture_node(
    source: StructureSource, key: str, joints_title: Callable[[int], str], seen: set[str]
) -> StructureNode:
    """Nœud de l'ensemble ``key`` : sous-ensembles, pièces, puis les assemblages repliés.
    ``seen`` coupe un cycle éventuel de sous-ensembles."""
    seen.add(key)
    children = [
        _furniture_node(source, sub, joints_title, seen)
        for sub in source.sub_furnitures(key)
        if sub not in seen
    ]
    children.extend(_piece_node(source, piece) for piece in source.pieces(key))
    joints = source.joints(key)
    if joints:
        leaves = tuple(StructureNode(NodeKind.JOINT, source.label(j), j) for j in joints)
        title = joints_title(len(leaves))
        children.append(StructureNode(NodeKind.JOINTS, title, "", leaves, expanded=False))
    return StructureNode(NodeKind.FURNITURE, source.label(key), key, tuple(children))
