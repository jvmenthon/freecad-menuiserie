# SPDX-License-Identifier: LGPL-2.1-or-later
"""Avertissement traduisible commun à ``core/`` (ensembles J4, liste de débit J2).

Chaque domaine fournit son énumération de natures : un membre d'énumération expose le gabarit
français marqué pour la traduction par sa propriété ``template``. ``features/`` traduit avec
``translate(CONTEXT, notice.template).format_map(notice.params)``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from freecad.menuiserie.core._validation import FrozenMapping

__all__ = ["Notice", "TemplatedKind"]


class TemplatedKind(Protocol):
    """Nature d'avertissement : un membre d'énumération qui porte son gabarit."""

    @property
    def template(self) -> str:
        """Gabarit français marqué pour la traduction."""


@dataclass(frozen=True)
class Notice:
    """Avertissement traduisible, jamais bloquant : nature et paramètres du gabarit."""

    kind: TemplatedKind
    params: Mapping[str, str]

    def __post_init__(self) -> None:
        template = getattr(self.kind, "template", None)
        if not isinstance(self.kind, Enum) or not isinstance(template, str):
            raise ValueError("Notice.kind : membre d'énumération avec un gabarit attendu")
        object.__setattr__(self, "params", FrozenMapping(self.params))

    @property
    def template(self) -> str:
        """Gabarit français marqué pour la traduction."""
        return self.kind.template

    @property
    def message(self) -> str:
        """Gabarit rempli, en français."""
        return self.template.format_map(self.params)
