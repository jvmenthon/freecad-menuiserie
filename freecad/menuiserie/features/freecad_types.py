# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alias de type et constantes partagés pour manipuler les objets de FreeCAD.

FreeCAD ne fournit pas d'annotations de type : ``DocumentObject`` et ``Document`` (``Any``)
documentent les signatures. ``EDITABLE``, ``READ_ONLY`` et ``HIDDEN`` sont les modes de
``setEditorMode`` (éditeur de propriétés). :class:`StatelessProxy` est la base des proxys sans
état (objets et ViewProviders). :func:`expressions_of` et ses variantes lisent
l'``ExpressionEngine`` d'un objet. Module public, utilisé aussi par ``gui/`` et ``api.py``.
"""

from __future__ import annotations

from typing import Any, Final

__all__ = [
    "EDITABLE",
    "HIDDEN",
    "READ_ONLY",
    "Document",
    "DocumentObject",
    "StatelessProxy",
    "expression_of",
    "expressions_of",
    "has_expression",
    "placement_expression",
    "proxy_is",
    "restoring_or_undoing",
]

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


def restoring_or_undoing(obj: DocumentObject) -> bool:
    """Vrai pendant la restauration de ``obj`` ou une annulation / un rétablissement du
    document : ``onChanged`` ne doit alors réagir à rien (aucune saisie de l'utilisateur)."""
    return "Restore" in obj.State or bool(obj.Document.Transacting)


def expressions_of(obj: DocumentObject) -> dict[str, str]:
    """Expressions de ``obj`` par chemin de propriété (``Placement.Base.y``, sans le point
    initial que FreeCAD ajoute aux sous-chemins)."""
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


def expression_of(obj: DocumentObject, prop: str) -> str | None:
    """Expression qui pilote la propriété ``prop`` de ``obj``, ``None`` s'il n'y en a pas."""
    return expressions_of(obj).get(prop)


def has_expression(obj: DocumentObject, prop: str) -> bool:
    """Vrai si la propriété ``prop`` de ``obj`` est pilotée par une expression."""
    return prop in expressions_of(obj)


def placement_expression(obj: DocumentObject) -> str | None:
    """Chemin de la première expression qui pilote le ``Placement`` de ``obj`` (liaison d'un
    ensemble, formule de l'utilisateur), ``None`` s'il n'y en a pas."""
    paths = sorted(expressions_of(obj))
    return next((path for path in paths if path.split(".")[0] == "Placement"), None)


class StatelessProxy:
    """Base des proxys sans état (ADR 0003) : tout est dans les propriétés de l'objet, rien
    n'est enregistré pour le proxy lui-même."""

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state
