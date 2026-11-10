# SPDX-License-Identifier: LGPL-2.1-or-later
"""Photo des propriétés saisies d'un document (ADR 0046), pour savoir si une tâche l'a modifié.

Lecture seule : rien n'est écrit, aucune transaction n'est touchée. Les valeurs sont écrites en
texte stable (un objet lié par son nom, jamais par son adresse). Le choix des propriétés suivies
est dans ``core/document_state``.
"""

from __future__ import annotations

from freecad.menuiserie.core.document_state import Snapshot, is_tracked
from freecad.menuiserie.features.freecad_types import Document, DocumentObject

__all__ = ["snapshot_of"]


def _stable(value: object) -> str:
    """Texte de ``value`` sans adresse mémoire : un objet de FreeCAD est cité par son nom."""
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_stable(item) for item in value) + "]"
    if hasattr(value, "TypeId") and hasattr(value, "Name"):
        return f"<{value.Name}>"
    return str(value)


def _properties(obj: DocumentObject) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in obj.PropertiesList:
        if not is_tracked(name, obj.getTypeIdOfProperty(name), obj.getPropertyStatus(name)):
            continue
        try:
            found[name] = _stable(getattr(obj, name))
        except (ReferenceError, RuntimeError, AttributeError, TypeError):
            found[name] = ""  # propriété illisible : stable d'une photo à l'autre
    return found


def snapshot_of(doc: Document) -> Snapshot:
    """Propriétés suivies de chaque objet de ``doc``, par nom d'objet."""
    return {obj.Name: _properties(obj) for obj in doc.Objects}
