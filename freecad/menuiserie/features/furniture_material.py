# SPDX-License-Identifier: LGPL-2.1-or-later
"""Matériau commun à toutes les pièces d'un ensemble, sous-ensembles compris (issue #77).

Chaque pièce est traitée comme par ``set_material`` (recopie du matériau, du fil, des surcotes).
Une pièce dont le matériau est piloté par une expression, ou qui vient d'un document plus récent,
est laissée telle quelle avec un avertissement. Aucun avertissement pour une pièce qui a déjà le
matériau. Le matériau est contrôlé avant toute écriture : un identifiant inconnu ne change rien.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.furniture_members import checked_furniture
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.wood_material import is_newer_version

__all__ = ["set_furniture_material", "timber_parts"]

MAX_DEPTH: Final = 32  # sous-ensembles imbriqués, contre les boucles

_DRIVEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : le matériau suit une expression, la pièce est laissée telle quelle.",
)
_NEWER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » vient d'une version plus récente de l'atelier, la pièce est laissée telle quelle.",
)


def timber_parts(furniture: DocumentObject) -> list[DocumentObject]:
    """Pièces de bois et pièces en bois de ``furniture`` et de ses sous-ensembles, sans doublon,
    ordre des noms (les distances et autres membres sont ignorés)."""
    found: dict[str, DocumentObject] = {}
    pending = [(furniture, 0)]
    seen = {furniture.Name}
    while pending:
        current, depth = pending.pop()
        for member in members_of(current):
            if is_timber(member):
                found[member.Name] = member
            elif is_furniture(member) and member.Name not in seen and depth < MAX_DEPTH:
                seen.add(member.Name)
                pending.append((member, depth + 1))
    return [found[name] for name in sorted(found)]


def set_furniture_material(furniture: DocumentObject, material_id: str) -> tuple[str, ...]:
    """Donne le matériau ``material_id`` à toutes les pièces de ``furniture`` et de ses
    sous-ensembles ; renvoie les avertissements traduits (pièces laissées telles quelles).
    ``TypeError`` traduite si ``furniture`` n'est pas un ensemble, ``UnknownMaterialError`` si le
    matériau est inconnu : rien n'est écrit. Aucune transaction ni recalcul : à l'appelant."""
    checked_furniture(furniture)
    material = get_library().get(material_id)
    notices: list[str] = []
    for part in timber_parts(furniture):
        params = {"label": quoted_value(part.Label)}
        if has_expression(part, "Material") or has_expression(part, "MaterialId"):
            notices.append(translated(_DRIVEN, params))
        elif is_newer_version(part, part.Proxy.VERSION):
            notices.append(translated(_NEWER, params))
        elif part.MaterialId != material.id:
            part.Proxy.select_material(part, material)
    return tuple(notices)
