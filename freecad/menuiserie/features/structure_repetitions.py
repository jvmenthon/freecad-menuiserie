# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture des répétitions pour le panneau « Structure » (ADR 0046, lot 4, ADR 0043 et 0044).

Une répétition (objet de cotes ``Repeat``) a des copies liées de ses sources : des pièces de bois
ou des ensembles complets (avec leur Std Part, jamais montré ici). Le panneau montre une ligne
« <nom> xN » par répétition, dépliable en ses copies de premier niveau ; la copie d'un membre
rangée dans un ensemble copie de la même répétition (copie « interne ») reste, elle, sous son
ensemble copie, comme tout membre. Lecture seule, aucun import de l'interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_view import shown_object
from freecad.menuiserie.features.repeat import copies_of, is_copy, is_inner_copy, is_repeat

__all__ = ["DocumentRepetitions", "RepetitionReader", "repetition_reader"]


class RepetitionReader(Protocol):
    """Lecture des répétitions d'un document, par nom d'objet (clés de ligne pour les copies :
    la pièce usinée à la place de sa brute)."""

    def all_repetitions(self) -> Sequence[str]:
        """Répétitions du document, dans l'ordre du document."""

    def container_of(self, repetition: str) -> str | None:
        """Ensemble qui range ``repetition``, ``None`` si elle est hors ensemble."""

    def copies_of(self, repetition: str) -> Sequence[str]:
        """Copies de premier niveau de ``repetition``, dans l'ordre d'affichage (par source puis
        par rang) : celles qu'une ligne « xN » regroupe."""

    def every_copy(self) -> Sequence[str]:
        """Toutes les copies du document, y compris les copies internes d'un ensemble copie."""

    def furniture_copies(self) -> Sequence[str]:
        """Copies de premier niveau qui sont des ensembles (leur contenu est sous leur ligne)."""


def _key(obj: DocumentObject) -> str:
    return str(shown_object(obj).Name)


class DocumentRepetitions:
    """Répétitions d'un document FreeCAD. Les copies sont lues une fois par répétition."""

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._repeats = {obj.Name: obj for obj in doc.Objects if is_repeat(obj)}
        self._top: dict[str, list[DocumentObject]] = {}

    def all_repetitions(self) -> Sequence[str]:
        """Répétitions du document, dans l'ordre du document."""
        return list(self._repeats)

    def container_of(self, repetition: str) -> str | None:
        """Ensemble de la première source (les copies y entrent comme elle), ``None`` hors
        ensemble ou sans source."""
        sources = list(self._repeats[repetition].Source)
        owner = furniture_of(sources[0]) if sources else None
        return None if owner is None else str(owner.Name)

    def copies_of(self, repetition: str) -> Sequence[str]:
        """Copies de premier niveau de ``repetition`` (clés de ligne)."""
        return [_key(copy) for copy in self._top_copies(repetition)]

    def every_copy(self) -> Sequence[str]:
        """Toutes les copies du document (clés de ligne), sans doublon."""
        found = (_key(obj) for obj in self._doc.Objects if is_copy(obj))
        return list(dict.fromkeys(found))

    def furniture_copies(self) -> Sequence[str]:
        """Copies de premier niveau qui sont des ensembles."""
        return [
            str(copy.Name)
            for name in self._repeats
            for copy in self._top_copies(name)
            if is_furniture(copy)
        ]

    def _top_copies(self, repetition: str) -> list[DocumentObject]:
        if repetition not in self._top:
            copies = copies_of(self._repeats[repetition])
            self._top[repetition] = [copy for copy in copies if not is_inner_copy(copy)]
        return self._top[repetition]


def repetition_reader(doc: Document) -> RepetitionReader:
    """Lecteur des répétitions de ``doc``."""
    return DocumentRepetitions(doc)
