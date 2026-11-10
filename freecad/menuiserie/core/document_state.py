# SPDX-License-Identifier: LGPL-2.1-or-later
"""État saisi d'un document, comparé pour savoir si une tâche l'a modifié (ADR 0046), sans FreeCAD.

FreeCAD ne dit pas si la transaction ouverte d'un panneau est vide. Le panneau garde donc une
photo des propriétés que l'utilisateur peut changer (``features/document_snapshot``) à son
ouverture et la compare à la demande : lecture seule, la transaction et Ctrl+Z ne sont pas touchés.
Les propriétés calculées (``Output``, ``Transient``, forme, proxy) et la visibilité ne comptent
pas : un recalcul ne rend pas une tâche « modifiée ».
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Final

__all__ = ["Snapshot", "changed_objects", "differs", "is_tracked"]

Snapshot = Mapping[str, Mapping[str, str]]  # nom d'objet -> propriété -> valeur écrite

UNTRACKED_NAMES: Final = frozenset({"Shape", "Proxy", "Visibility", "Touched"})
UNTRACKED_TYPES: Final = frozenset(
    {"Part::PropertyPartShape", "App::PropertyPythonObject", "Part::PropertyGeometryList"}
)
# « ReadOnly » n'en fait pas partie : c'est un mode d'éditeur, et des panneaux écrivent des
# propriétés ainsi déclarées (« Inverser » écrit HostPart et GuestPart).
UNTRACKED_STATUS: Final = frozenset({"Output", "Transient"})


def is_tracked(name: str, type_id: str, status: Collection[str]) -> bool:
    """Vrai si la propriété ``name`` (type ``type_id``, états ``status``) est une saisie."""
    return (
        name not in UNTRACKED_NAMES
        and type_id not in UNTRACKED_TYPES
        and UNTRACKED_STATUS.isdisjoint(status)
    )


def changed_objects(before: Snapshot, after: Snapshot) -> list[str]:
    """Noms des objets créés, supprimés ou dont une propriété suivie a changé."""
    names = sorted(set(before) | set(after))
    return [name for name in names if before.get(name) != after.get(name)]


def differs(before: Snapshot, after: Snapshot) -> bool:
    """Vrai si le document a changé entre les deux photos."""
    return bool(changed_objects(before, after))
