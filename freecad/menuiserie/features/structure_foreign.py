# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets d'autres ateliers montrés sous « Autres objets » (ADR 0046, lot 4).

Lecture seule, par prudence : on ne montre que ce qui est **sans équivoque** hors de l'atelier,
et jamais ce que l'atelier range ou consomme lui-même. Un objet est montré si :

- ce n'est pas un objet de l'atelier (proxy de ``freecad.menuiserie``) ni le tableur de la liste
  de débit ;
- rien ne dépend de lui (``InList`` vide) : sinon c'est une source ou un élément d'un autre objet
  (Body et esquisse d'une pièce en forme, Origine d'un Std Part, opérande d'un ``Part::Cut``…),
  que l'arbre natif range déjà sous son parent ;
- il ne contient ni ne lit aucun objet de l'atelier (``OutList``) : c'est le Std Part d'un
  ensemble ;
- ce n'est pas une Origine.

Le panneau n'ouvre, ne renomme, ne range ni ne supprime ces objets (``core/structure_actions``).
"""

from __future__ import annotations

from freecad.menuiserie.features.cutlist_sheet import is_workshop_sheet
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.shaped_sources import is_workshop_object

__all__ = ["foreign_objects", "is_foreign"]

_ORIGIN_PREFIX = "App::Origin"


def is_foreign(obj: DocumentObject, doc: Document) -> bool:
    """Vrai si ``obj`` est un objet de premier niveau d'un autre atelier (voir le module)."""
    if is_workshop_object(obj) or is_workshop_sheet(obj, doc):
        return False
    if str(getattr(obj, "TypeId", "")).startswith(_ORIGIN_PREFIX):
        return False
    if getattr(obj, "InList", ()):
        return False
    return not any(is_workshop_object(other) for other in getattr(obj, "OutList", ()))


def foreign_objects(doc: Document) -> list[DocumentObject]:
    """Objets d'autres ateliers de ``doc``, dans l'ordre du document."""
    return [obj for obj in doc.Objects if is_foreign(obj, doc)]
