# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alias de type et constantes partagés pour manipuler les objets de FreeCAD.

FreeCAD ne fournit pas d'annotations de type : ``DocumentObject`` et ``Document`` (``Any``)
documentent les signatures. ``EDITABLE``, ``READ_ONLY`` et ``HIDDEN`` sont les modes de
``setEditorMode`` (éditeur de propriétés). Module public, utilisé aussi par ``gui/`` et
``api.py``.
"""

from __future__ import annotations

from typing import Any, Final

__all__ = ["EDITABLE", "HIDDEN", "READ_ONLY", "Document", "DocumentObject", "proxy_is"]

DocumentObject = Any  # objets FreeCAD, sans annotations de type
Document = Any

EDITABLE: Final = 0
READ_ONLY: Final = 1
HIDDEN: Final = 2


def proxy_is(obj: object, proxy_class: type) -> bool:
    """Vrai si le proxy de ``obj`` est une instance de ``proxy_class`` (faux pour un objet
    supprimé du document ou sans proxy)."""
    try:
        proxy = getattr(obj, "Proxy", None)
    except ReferenceError:  # objet FreeCAD supprimé du document
        return False
    return isinstance(proxy, proxy_class)
