# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture du document pour le panneau « Structure » (ADR 0046, lot 1).

:class:`DocumentStructure` adapte un document FreeCAD à la :class:`StructureSource` de
``core/structure_tree.py`` avec les aides existantes (membres d'un ensemble, assemblages,
pièce usinée de sa brute). Lecture seule : aucun objet, propriété ni dossier n'est créé ni
modifié, et aucun import de l'interface.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.structure_hardware import is_hardware_kind
from freecad.menuiserie.core.structure_icons import DISTANCE_SUBTYPE, SHAPED_SUBTYPE
from freecad.menuiserie.core.structure_tree import (
    HARDWARE_TITLE,
    JOINTS_TITLE,
    LEFTOVERS_TITLE,
    OTHERS_TITLE,
    REPEAT_LABEL,
    StructureNode,
    Titles,
    build_structure,
)
from freecad.menuiserie.features.cutlist_object import is_cut_list
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture, is_member
from freecad.menuiserie.features.furniture_view import furniture_children, shown_object
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.shaped_part import is_shaped_part, is_timber
from freecad.menuiserie.features.shaped_sources import is_workshop_object
from freecad.menuiserie.features.structure_foreign import foreign_objects
from freecad.menuiserie.features.structure_repetitions import RepetitionReader, repetition_reader

__all__ = ["DocumentStructure", "renamed_object", "row_key_of", "structure_of"]


def structure_of(doc: Document) -> tuple[StructureNode, ...]:
    """Arbre simplifié de ``doc`` (libellés traduits)."""
    source = DocumentStructure(doc)
    return build_structure(source, _joints_title, source, _TITLES)


def _joints_title(count: int) -> str:
    return translated(JOINTS_TITLE, {"count": str(count)})


def _others_title(count: int) -> str:
    return translated(OTHERS_TITLE, {"count": str(count)})


def _hardware_title(count: int) -> str:
    return translated(HARDWARE_TITLE, {"count": str(count)})


def _leftovers_title(count: int) -> str:
    return translated(LEFTOVERS_TITLE, {"count": str(count)})


def _repeat_label(name: str, count: int) -> str:
    return translated(REPEAT_LABEL, {"name": name, "count": str(count)})


_TITLES = Titles(
    joints=_joints_title,
    others=_others_title,
    repeat=_repeat_label,
    leftovers=_leftovers_title,
    hardware=_hardware_title,
)


class DocumentStructure:
    """Un document vu comme la source de l'arbre simplifié. Les enfants de chaque ensemble sont
    lus une fois (``furniture_children``) puis classés : sous-ensemble, pièce ou assemblage.
    Fournit aussi les lectures du lot 4 (``StructureExtras``) : répétitions (par un
    ``RepetitionReader``, vide tant que le type n'existe pas), listes de débit, autres objets."""

    def __init__(self, doc: Document, repetitions: RepetitionReader | None = None) -> None:
        self._doc = doc
        self._repetitions = repetitions if repetitions is not None else repetition_reader(doc)
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
        """Assemblages (hors quincaillerie) et Distances de ``furniture``."""
        return [obj.Name for obj in self._children_of(furniture) if _is_plain_joint(obj)]

    def hardware(self, furniture: str) -> Sequence[str]:
        """Objets de quincaillerie de ``furniture`` (voir ``core/structure_hardware``)."""
        return [obj.Name for obj in self._children_of(furniture) if _is_hardware(obj)]

    def loose_joints(self) -> Sequence[str]:
        """Assemblages et Distances qu'aucun ensemble ne range (pièces hors ensemble ou d'ensembles
        sans ensemble commun, pièce supprimée…)."""
        ranged = {name for furniture in self.all_furnitures() for name in self.joints(furniture)}
        return [
            obj.Name for obj in self._doc.Objects if _is_plain_joint(obj) and obj.Name not in ranged
        ]

    def loose_hardware(self) -> Sequence[str]:
        """Quincaillerie qu'aucun ensemble ne range : pieds ou coulisses d'une pièce hors
        ensemble…"""
        ranged = {name for furniture in self.all_furnitures() for name in self.hardware(furniture)}
        return [
            obj.Name for obj in self._doc.Objects if _is_hardware(obj) and obj.Name not in ranged
        ]

    def subtype(self, key: str) -> str:
        """Type précis de ``key`` pour l'icône : type d'assemblage, « distance » ou « shaped »."""
        obj = self._by_name[key]
        if (kind := _joint_kind(obj)) is not None:
            return str(kind.value)
        if is_distance(obj):
            return DISTANCE_SUBTYPE
        return SHAPED_SUBTYPE if is_shaped_part(renamed_object(obj)) else ""

    def all_furnitures(self) -> Sequence[str]:
        """Tous les ensembles du document, dans l'ordre du document."""
        return [obj.Name for obj in self._doc.Objects if is_furniture(obj)]

    def repetitions(self, container: str | None) -> Sequence[str]:
        """Répétitions rangées dans l'ensemble ``container`` (``None`` : hors ensemble)."""
        return [
            key
            for key in self._repetitions.all_repetitions()
            if key in self._by_name and self._repetitions.container_of(key) == container
        ]

    def copies(self, repetition: str) -> Sequence[str]:
        """Copies de ``repetition`` (clés de ligne) qui existent dans le document."""
        return [key for key in self._repetitions.copies_of(repetition) if key in self._by_name]

    def all_copies(self) -> Collection[str]:
        """Copies de toutes les répétitions."""
        return {key for rep in self._repetitions.all_repetitions() for key in self.copies(rep)}

    def cut_lists(self) -> Sequence[str]:
        """Listes de débit (le tableur n'est pas montré)."""
        return [obj.Name for obj in self._doc.Objects if is_cut_list(obj)]

    def other_objects(self) -> Sequence[str]:
        """Objets d'autres ateliers (voir ``structure_foreign``)."""
        return [obj.Name for obj in foreign_objects(self._doc)]

    def workshop_objects(self) -> Sequence[str]:
        """Clés de ligne de tous les objets de l'atelier (``is_workshop_object``)."""
        return [row_key_of(obj) for obj in self._doc.Objects if is_workshop_object(obj)]

    def label(self, key: str) -> str:
        """Libellé de l'objet ``key`` ; une pièce usinée porte celui de sa brute (sans
        « (usinée) »)."""
        return str(renamed_object(self._by_name[key]).Label)

    def _children_of(self, furniture: str) -> list[DocumentObject]:
        if furniture not in self._children:
            self._children[furniture] = furniture_children(self._by_name[furniture])
        return self._children[furniture]


def _is_hardware(obj: DocumentObject) -> bool:
    """Vrai pour un assemblage dont le type est de la quincaillerie (ADR 0033)."""
    kind = _joint_kind(obj)
    return kind is not None and is_hardware_kind(kind)


def _joint_kind(obj: DocumentObject) -> JointKind | None:
    """Type d'assemblage de ``obj``, ``None`` si ce n'est pas un assemblage typé."""
    kind = getattr(getattr(obj, "Proxy", None), "KIND", None)
    return kind if isinstance(kind, JointKind) else None


def _is_plain_joint(obj: DocumentObject) -> bool:
    """Vrai pour un assemblage hors quincaillerie ou une Distance."""
    return (is_joint(obj) and not _is_hardware(obj)) or is_distance(obj)


def _is_piece(obj: DocumentObject) -> bool:
    return not (is_furniture(obj) or is_joint(obj) or is_distance(obj))


def row_key_of(obj: DocumentObject) -> str:
    """Clé de la ligne du panneau qui représente ``obj`` : la pièce usinée pour sa brute (une
    seule ligne pour les deux), sinon l'objet lui-même."""
    return str(shown_object(obj).Name)


def renamed_object(obj: DocumentObject) -> DocumentObject:
    """Objet dont le libellé est celui de la ligne : la brute pour une pièce usinée (la ligne
    porte le libellé de sa brute, sans « (usinée) », ADR 0046), sinon l'objet lui-même."""
    return blank_of(obj) if is_machined_part(obj) else obj
