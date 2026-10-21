# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture des propriétés de membre d'un ensemble (ADR 0003, ADR 0009, critère N12).

Un document est une donnée externe : chaque propriété de membre d'un type inattendu est
supprimée avec un avertissement, puis recréée à sa valeur par défaut (``Stay`` ; option « fixe »
selon F3 ; ``Furniture`` vide si c'est le lien lui-même) ; les liaisons ne sont jamais réécrites
à la réouverture.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.furniture import Edge, FurnitureBox, with_default_options
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import (
    MEMBER_PROPERTIES,
    MODES,
    OPTIONS,
    is_furniture,
    option_name,
    origin_of,
    writing,
)
from freecad.menuiserie.features.furniture_bindings import member_of

__all__ = ["MEMBER_NOUN", "restore_member"]

MEMBER_NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Membre d'ensemble")


def _default_options(obj: DocumentObject, furniture: DocumentObject) -> dict[str, bool]:
    """Options par défaut (F3) du membre ``obj`` ; toutes fixes (Q7) s'il est illisible."""
    try:
        box = FurnitureBox(furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value)
        member = member_of(obj, origin_of(furniture), entering=True)
        [resolved] = with_default_options(box, [member])
        fixed = resolved.fixed or frozenset()
    except ValueError:
        fixed = frozenset(Edge)
    return {option_name(edge): edge in fixed for edge in Edge}


def _restore_modes(obj: DocumentObject) -> None:
    """Liste canonique de ``PositionMode`` ; une valeur inconnue (version plus récente) est
    gardée avec la liste du fichier."""
    if "PositionMode" not in obj.PropertiesList:
        return
    value = obj.PositionMode
    if value in MODES and obj.getEnumerationsOfProperty("PositionMode") != list(MODES):
        obj.PositionMode = list(MODES)
        obj.PositionMode = value


def _restore(obj: DocumentObject) -> None:
    mistyped = schema.remove_mistyped_properties(obj, MEMBER_PROPERTIES, MEMBER_NOUN)
    _restore_modes(obj)
    if not mistyped:
        return
    furniture = getattr(obj, "Furniture", None)
    defaults: dict[str, object] = {}
    if is_furniture(furniture) and any(name in mistyped for name in OPTIONS):
        defaults.update(_default_options(obj, furniture))
    schema.add_missing_properties(
        obj, MEMBER_PROPERTIES, defaults, choices={"PositionMode": list(MODES)}
    )
    schema.apply_editor_modes(obj, MEMBER_PROPERTIES)


def restore_member(obj: DocumentObject) -> None:
    """Réouverture d'un membre (appelée par son propre ``onDocumentRestored`` : FreeCAD ne
    permet pas de supprimer une propriété d'un autre objet pendant la restauration) ; ses
    liaisons ne sont pas réécrites (écriture de l'atelier : son ``onChanged`` ne réagit pas).
    Sans effet pour un objet qui n'est membre d'aucun ensemble."""
    if "Furniture" not in obj.PropertiesList:
        return
    with writing(obj):
        _restore(obj)
