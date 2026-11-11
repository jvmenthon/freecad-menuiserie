# SPDX-License-Identifier: LGPL-2.1-or-later
"""Membres d'un ensemble source de répétition, parcourus récursivement (ADR 0043, § 2 bis).

Une source de répétition peut être un ensemble : ses membres (pièces brutes et sous-ensembles)
sont copiés avec lui. Ce module ne fait que lire le document.
"""

from __future__ import annotations

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.repeat import sources_of

__all__ = ["ancestors_of", "descendants_of", "original_parts"]


def descendants_of(furniture: DocumentObject, seen: set[str] | None = None) -> list[DocumentObject]:
    """Membres de ``furniture`` à tous les niveaux (pièces et sous-ensembles), un ensemble avant
    ses membres, dans l'ordre des noms. ``seen`` : noms déjà parcourus, pour ne pas boucler sur
    un document forgé où des ensembles se contiennent l'un l'autre."""
    seen = {furniture.Name} if seen is None else seen
    found: list[DocumentObject] = []
    for member in members_of(furniture):
        if member.Name in seen:
            continue
        seen.add(member.Name)
        found.append(member)
        if is_furniture(member):
            found.extend(descendants_of(member, seen))
    return found


def ancestors_of(obj: DocumentObject) -> list[DocumentObject]:
    """Ensembles qui contiennent ``obj``, du plus proche au plus lointain."""
    found: list[DocumentObject] = []
    while (parent := furniture_of(obj)) is not None and parent not in found:
        found.append(parent)
        obj = parent
    return found


def original_parts(repeat: DocumentObject) -> list[DocumentObject]:
    """Pièces brutes copiées par ``repeat`` : ses sources et les membres, à tous les niveaux, de
    ses sources qui sont des ensembles."""
    found: list[DocumentObject] = []
    for source in sources_of(repeat):
        if is_furniture(source):
            found.extend(obj for obj in descendants_of(source) if not is_furniture(obj))
        else:
            found.append(source)
    return found
