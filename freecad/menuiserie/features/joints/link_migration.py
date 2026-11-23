# SPDX-License-Identifier: LGPL-2.1-or-later
"""Migration des liens d'un assemblage vers des liens globaux (ADR 0054)."""

from __future__ import annotations

from collections.abc import Iterable

from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["migrate_links"]


def migrate_links(obj: DocumentObject, specs: Iterable[PropertySpec]) -> None:
    """Liens ``specs`` (``HostPart``, ``GuestPart``) d'un document d'avant l'ADR 0054
    (``App::PropertyLink``) recréés en ``App::PropertyLinkGlobal`` (liens entre Std Part), sans
    perdre leurs pièces ; lien ``Frames`` des essais de la PR #249 retiré (cycle avec le Std
    Part)."""
    for spec in specs:
        if obj.getTypeIdOfProperty(spec.name) != "App::PropertyLink":
            continue
        part = getattr(obj, spec.name)
        obj.setPropertyStatus(spec.name, "-ReadOnly")
        obj.removeProperty(spec.name)
        schema.add_missing_properties(obj, [spec])
        setattr(obj, spec.name, part)
        schema.apply_editor_modes(obj, [spec])
    if "Frames" in obj.PropertiesList:
        obj.removeProperty("Frames")
