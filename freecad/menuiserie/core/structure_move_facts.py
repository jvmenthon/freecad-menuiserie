# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que les décisions du panneau « Structure » savent du document (ADR 0046), sans FreeCAD."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from freecad.menuiserie.core.text import quoted_value

__all__ = ["MoveFacts", "top_level"]


@dataclass(frozen=True)
class MoveFacts:
    """Ce que les décisions savent du document : libellés des pièces et des ensembles, ensembles,
    ensemble de chaque membre (``parent``), pièces assemblées à chaque pièce (``links``) et
    panneau de tâche ouvert (``busy``), copies de répétition (``copies``, y compris les copies
    internes d'un ensemble copie : elles ne se rangent pas à part), répétitions (``repeats``, avec
    leur libellé : elles se renomment, s'ouvrent et se suppriment, mais ne se rangent pas) et
    objets d'autres ateliers (``foreign``, qu'on ne touche pas)."""

    labels: Mapping[str, str]
    furnitures: frozenset[str]
    parent: Mapping[str, str]
    links: Mapping[str, frozenset[str]] = field(default_factory=dict)
    busy: bool = False
    copies: frozenset[str] = frozenset()
    foreign: frozenset[str] = frozenset()
    repeats: Mapping[str, str] = field(default_factory=dict)

    def plain_label(self, key: str) -> str:
        """Libellé de la pièce, de l'ensemble ou de la répétition ``key``, tel quel."""
        return self.labels.get(key) or self.repeats.get(key, key)

    def label(self, key: str) -> str:
        """Libellé cité dans un message."""
        return quoted_value(self.labels.get(key, key))

    def chain(self, key: str) -> list[str]:
        """Ensembles qui contiennent ``key``, du plus proche au plus éloigné (cycle coupé)."""
        found: list[str] = []
        current = self.parent.get(key)
        while current is not None and current not in found:
            found.append(current)
            current = self.parent.get(current)
        return found

    def pieces_under(self, key: str) -> set[str]:
        """``key`` si c'est une pièce, sinon les pièces de l'ensemble et de ses sous-ensembles."""
        if key not in self.furnitures:
            return {key}
        found: set[str] = set()
        seen = {key}
        pending = [key]
        while pending:
            current = pending.pop()
            for child, owner in self.parent.items():
                if owner != current or child in seen:
                    continue
                seen.add(child)
                if child in self.furnitures:
                    pending.append(child)
                else:
                    found.add(child)
        return found


def top_level(facts: MoveFacts, keys: Iterable[str]) -> list[str]:
    """``keys`` sans doublon ni élément dont un ensemble ancêtre est aussi choisi (il se
    déplace avec cet ensemble), dans l'ordre reçu."""
    chosen = list(dict.fromkeys(keys))
    return [key for key in chosen if not set(facts.chain(key)) & set(chosen)]
