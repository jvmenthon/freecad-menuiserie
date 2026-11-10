# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture du document pour le panneau « Structure » (ADR 0046, lot 1).

:class:`DocumentStructure` adapte un document FreeCAD à la :class:`StructureSource` de
``core/structure_tree.py`` avec les aides existantes (membres d'un ensemble, assemblages,
pièce usinée de sa brute). Lecture seule : aucun objet, propriété ni dossier n'est créé ni
modifié, et aucun import de l'interface.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.structure_tree import (
    JOINTS_TITLE,
    StructureNode,
    build_structure,
)
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture, is_member
from freecad.menuiserie.features.furniture_view import furniture_children, shown_object
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["DocumentStructure", "structure_of"]


def structure_of(doc: Document) -> tuple[StructureNode, ...]:
    """Arbre simplifié de ``doc`` (libellés traduits)."""
    return build_structure(
        DocumentStructure(doc), lambda count: translated(JOINTS_TITLE, {"count": str(count)})
    )


class DocumentStructure:
    """Un document vu comme la source de l'arbre simplifié. Les enfants de chaque ensemble sont
    lus une fois (``furniture_children``) puis classés : sous-ensemble, pièce ou assemblage."""

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._by_name = {obj.Name: obj for obj in doc.Objects}
        self._children: dict[str, list[DocumentObject]] = {}

    def root_furnitures(self) -> Sequence[str]:
        """Ensembles qui ne sont membres d'aucun autre, dans l'ordre du document."""
        return [obj.Name for obj in self._doc.Objects if is_furniture(obj) and not is_member(obj)]

    def loose_pieces(self) -> Sequence[str]:
        """Pièces de bois hors ensemble, la pièce usinée à la place de sa brute."""
        return [
            shown_object(obj).Name
            for obj in self._doc.Objects
            if is_timber(obj) and not is_member(obj)
        ]

    def sub_furnitures(self, furniture: str) -> Sequence[str]:
        """Sous-ensembles directs de ``furniture``."""
        return [obj.Name for obj in self._children_of(furniture) if is_furniture(obj)]

    def pieces(self, furniture: str) -> Sequence[str]:
        """Pièces directes de ``furniture`` (ni sous-ensemble, ni assemblage, ni Distance)."""
        return [obj.Name for obj in self._children_of(furniture) if _is_piece(obj)]

    def joints(self, furniture: str) -> Sequence[str]:
        """Assemblages, quincaillerie et Distances de ``furniture``."""
        return [
            obj.Name for obj in self._children_of(furniture) if is_joint(obj) or is_distance(obj)
        ]

    def label(self, key: str) -> str:
        """Libellé de l'objet ``key`` ; une pièce usinée porte celui de sa brute (sans
        « (usinée) »)."""
        obj = self._by_name[key]
        shown = blank_of(obj) if is_machined_part(obj) else obj
        return str(shown.Label)

    def _children_of(self, furniture: str) -> list[DocumentObject]:
        if furniture not in self._children:
            self._children[furniture] = furniture_children(self._by_name[furniture])
        return self._children[furniture]


def _is_piece(obj: DocumentObject) -> bool:
    return not (is_furniture(obj) or is_joint(obj) or is_distance(obj))
