# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arbre du choix des pièces des plans de pièce (issue #153, retour de jv du 23/11, maquette A).

Quand rien n'est sélectionné, le panneau « Plans de pièce » montre les ensembles de plus haut
niveau avec leurs sous-ensembles et leurs pièces, les copies par lien, puis les pièces hors
ensemble. Ce module construit cet arbre (sans Qt) ; le panneau le coche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from freecad.menuiserie.features.drawing_scope import document_scope, link_target, links_in
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["MAX_DEPTH", "Choice", "part_choices", "part_label"]

MAX_DEPTH: Final = 16  # sous-ensembles imbriqués montrés au plus, contre les boucles


@dataclass(frozen=True)
class Choice:
    """Ligne de l'arbre : un ensemble (avec ses lignes), une pièce ou une copie par lien."""

    obj: DocumentObject
    children: tuple[Choice, ...] = field(default=())

    @property
    def parts(self) -> int:
        """Pièces sous la ligne (elle-même si c'est une pièce ou un lien)."""
        if not self.children:
            return 0 if is_furniture(self.obj) else 1
        return sum(child.parts for child in self.children)


def part_label(obj: DocumentObject) -> str:
    """Repère puis libellé de la pièce (le libellé seul s'il contient déjà le repère)."""
    mark = str(getattr(obj, "Mark", "")).strip()
    label = str(obj.Label)
    return f"{mark} {label}" if mark and mark not in label else label


def _choice(obj: DocumentObject, depth: int) -> Choice | None:
    if is_timber(obj) or link_target(obj) is not None:
        return Choice(obj)
    if not is_furniture(obj) or depth >= MAX_DEPTH:
        return None
    rows = [_choice(member, depth + 1) for member in [*members_of(obj), *links_in(obj)]]
    found = tuple(row for row in rows if row is not None)
    return Choice(obj, found) if found else None


def part_choices(doc: Document) -> tuple[list[Choice], list[Choice]]:
    """(Ensembles et copies par lien de plus haut niveau, pièces hors ensemble), chacun dans
    l'ordre du document par nom ; un ensemble sans pièce n'est pas montré."""
    groups: list[Choice] = []
    loose: list[Choice] = []
    for obj in document_scope(doc):
        row = _choice(obj, 0)
        if row is not None:
            (loose if is_timber(obj) else groups).append(row)
    return groups, loose
