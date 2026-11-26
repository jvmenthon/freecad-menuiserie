# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier appliqués à une pièce neuve : cotes, matériau, surcotes, arête cassée
(ADR 0031, 0069).

Un réglage ne sert que de valeur par défaut à la création : une pièce existante, une copie ou une
répétition gardent leurs valeurs. Sans réglage modifié, les valeurs sont celles de ``core``.
"""

from __future__ import annotations

from freecad.menuiserie.core.edges import EdgeId, all_edges
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.core.part_model import Allowances, Dimensions
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import settings as config
from freecad.menuiserie.features.edge_profile_native import native_shape
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.wood_material import part_kind

__all__ = [
    "apply_new_allowances",
    "broken_edge_designation",
    "broken_edge_size",
    "new_allowances",
    "new_dimensions",
    "new_material_id",
    "warn_broken_edge_refused",
]

_BROKEN_EDGE_REFUSED = QT_TRANSLATE_NOOP(
    "Menuiserie", "Arête cassée non ajoutée à « {label} » : {error}"
)

_ALLOWANCE_KEYS = (*config.SOLID_ALLOWANCES, *config.PANEL_ALLOWANCES)
_ALLOWANCE_PROPERTIES = ("LengthAllowance", "WidthAllowance", "ThicknessAllowance")


def _number(key: str) -> float:
    return float(config.settings().value(key))


def new_dimensions() -> Dimensions:
    """Cotes finies d'une pièce neuve (mm) : celles de l'atelier, 800 x 200 x 22 par défaut."""
    return Dimensions(_number(config.LENGTH), _number(config.WIDTH), _number(config.THICKNESS))


def new_material_id() -> str | None:
    """Matériau d'une pièce neuve : celui de l'atelier s'il est dans la bibliothèque, sinon
    ``None`` (premier matériau de la bibliothèque)."""
    chosen = str(config.settings().value(config.MATERIAL))
    return chosen if chosen and chosen in get_library() else None


def new_allowances(kind: MaterialKind) -> Allowances:
    """Surcotes de débit d'une pièce neuve de la famille ``kind`` (panneau ou massif)."""
    keys = config.SOLID_ALLOWANCES if kind is MaterialKind.SOLID else config.PANEL_ALLOWANCES
    return Allowances(*(_number(key) for key in keys))


def apply_new_allowances(part: DocumentObject) -> None:
    """Écrit dans la pièce neuve ``part`` les surcotes de l'atelier pour sa famille ; sans réglage
    de surcote modifié, la pièce garde celles de son matériau (aucune lecture, aucune écriture)."""
    settings = config.settings()
    if not any(settings.is_modified(key) for key in _ALLOWANCE_KEYS):
        return
    values = new_allowances(part_kind(part, None))
    for name, value in zip(
        _ALLOWANCE_PROPERTIES, (values.length, values.width, values.thickness), strict=True
    ):
        if getattr(part, name).Value != value:
            setattr(part, name, value)


def broken_edge_size() -> float | None:
    """Rayon (mm) de l'arête cassée à donner aux pièces neuves, ``None`` si le réglage est
    décoché."""
    if not config.settings().value(config.BROKEN_EDGE):
        return None
    return _number(config.BROKEN_EDGE_SIZE)


def broken_edge_designation(part: DocumentObject) -> list[EdgeId] | list[str]:
    """Toutes les arêtes de ``part`` : les douze d'une boîte, ou les arêtes natives d'une pièce
    en bois (``ValueError`` traduite si sa forme ne permet pas de les suivre)."""
    if not is_shaped_part(part):
        return list(all_edges())
    count = len(native_shape(part).Edges)
    return [f"Edge{index}" for index in range(1, count + 1)]


def warn_broken_edge_refused(part: DocumentObject, error: Exception) -> None:
    """Avertissement dans la vue rapport : l'arête cassée de l'atelier est refusée pour ``part``,
    qui est créée quand même."""
    report_warning(
        translated(_BROKEN_EDGE_REFUSED, {"label": quoted_value(part.Label), "error": str(error)})
    )
