# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faits du document pour les actions du panneau « Structure » (ADR 0046, lot 3).

:func:`facts_of` lit un document FreeCAD et en tire le :class:`MoveFacts` de
``core/structure_actions.py`` (libellés, ensemble de chaque pièce, pièces assemblées). Lecture
seule : aucun objet, propriété ni transaction, et aucun import de l'interface. Les clés sont
celles des lignes du panneau (``row_key_of``).
"""

from __future__ import annotations

from freecad.menuiserie.core.structure_actions import MoveFacts
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.structure_source import row_key_of

__all__ = ["facts_of", "renamed_object"]


def renamed_object(obj: DocumentObject) -> DocumentObject:
    """Objet dont le libellé est celui de la ligne : la brute pour une pièce usinée (la ligne
    porte le libellé de sa brute, ADR 0046), sinon l'objet lui-même."""
    return blank_of(obj) if is_machined_part(obj) else obj


def _parent_key(member: DocumentObject) -> str | None:
    parent = furniture_of(member)
    return None if parent is None else str(parent.Name)


def _links(doc: Document) -> dict[str, set[str]]:
    """Pièces assemblées entre elles (clés de ligne), dans les deux sens."""
    links: dict[str, set[str]] = {}
    for obj in doc.Objects:
        if not is_joint(obj) or obj.HostPart is None or obj.GuestPart is None:
            continue
        host, guest = row_key_of(obj.HostPart), row_key_of(obj.GuestPart)
        links.setdefault(host, set()).add(guest)
        links.setdefault(guest, set()).add(host)
    return links


def facts_of(doc: Document) -> MoveFacts:
    """Libellés, ensembles, appartenances et assemblages des pièces de ``doc``."""
    labels: dict[str, str] = {}
    furnitures: set[str] = set()
    parent: dict[str, str] = {}
    for obj in doc.Objects:
        if not (is_furniture(obj) or is_timber(obj)):
            continue
        key = str(obj.Name) if is_furniture(obj) else row_key_of(obj)
        labels[key] = str(obj.Label)
        if is_furniture(obj):
            furnitures.add(key)
        if (owner := _parent_key(obj)) is not None:
            parent[key] = owner
    links = {
        key: frozenset(other for other in others if other in labels)
        for key, others in _links(doc).items()
        if key in labels
    }
    return MoveFacts(labels, frozenset(furnitures), parent, links)
