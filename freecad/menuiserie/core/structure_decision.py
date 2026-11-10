# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réponse commune des décisions du panneau « Structure » (ADR 0046), sans FreeCAD ni Qt."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

__all__ = ["Decision", "refuse"]


@dataclass(frozen=True)
class Decision:
    """Réponse à « cette action est-elle permise ? ». Refusée, ``template`` est le gabarit
    français (à traduire puis remplir avec ``params``) ; un refus au gabarit vide ne dit rien
    (rien à faire, par exemple un nom inchangé). Autorisée, ``keys`` sont les lignes que
    l'action touche (déjà ramenées aux plus hautes, sans celles qui sont en place)."""

    allowed: bool
    template: str = ""
    params: Mapping[str, str] = field(default_factory=dict)
    keys: tuple[str, ...] = ()

    @property
    def silent(self) -> bool:
        """Vrai pour un refus sans message : l'interface ne fait rien et ne dit rien."""
        return not self.allowed and not self.template

    @property
    def message(self) -> str:
        """Gabarit rempli (non traduit), pour les journaux et les tests."""
        return self.template.format_map(self.params)


def refuse(template: str, **params: str) -> Decision:
    return Decision(False, template, params)
