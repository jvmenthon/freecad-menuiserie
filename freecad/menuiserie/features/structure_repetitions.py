# SPDX-License-Identifier: LGPL-2.1-or-later
"""Point d'extension « répétitions » du panneau « Structure » (ADR 0046, lot 4).

L'objet Répétition (objet de cotes ``Repeat``, ADR 0043) n'est pas encore dans cette branche :
le panneau lit les répétitions par un :class:`RepetitionReader`, et :func:`repetition_reader`
rend aujourd'hui un lecteur **vide** (:class:`NoRepetitions`) : aucune ligne « xN », aucune copie
cachée, l'arbre est celui des lots 1 à 3. Quand le type existera, seule cette fonction change :
elle rend un lecteur fondé sur ``features/repeat.py`` (``is_repeat``, ``copies_of``) ; le modèle,
les décisions du menu et le glisser-déposer sont déjà prêts. Lecture seule, aucun import de
l'interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from freecad.menuiserie.features.freecad_types import Document

__all__ = ["NoRepetitions", "RepetitionReader", "repetition_reader"]


class RepetitionReader(Protocol):
    """Lecture des répétitions d'un document, par nom d'objet (clés de ligne pour les copies :
    la pièce usinée à la place de sa brute)."""

    def all_repetitions(self) -> Sequence[str]:
        """Répétitions du document, dans l'ordre du document."""

    def container_of(self, repetition: str) -> str | None:
        """Ensemble qui range ``repetition``, ``None`` si elle est hors ensemble."""

    def copies_of(self, repetition: str) -> Sequence[str]:
        """Copies de ``repetition``, dans l'ordre d'affichage (rang croissant)."""


class NoRepetitions:
    """Lecteur vide : le type Répétition n'existe pas (encore) dans le document."""

    def all_repetitions(self) -> Sequence[str]:
        """Aucune répétition."""
        return ()

    def container_of(self, repetition: str) -> str | None:
        """Jamais appelée : il n'y a aucune répétition."""
        del repetition
        return None

    def copies_of(self, repetition: str) -> Sequence[str]:
        """Jamais appelée : il n'y a aucune répétition."""
        del repetition
        return ()


def repetition_reader(doc: Document) -> RepetitionReader:
    """Lecteur des répétitions de ``doc`` (vide tant que le type Répétition n'existe pas)."""
    del doc
    return NoRepetitions()
