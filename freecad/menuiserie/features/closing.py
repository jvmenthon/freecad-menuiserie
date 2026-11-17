# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fermer le caisson (ADR 0064) : pièce choisie (ancre), paramètres par défaut et construction.

L'ancre est la brute d'une pièce de bois rectangulaire ; elle n'est ni recréée ni déplacée. Les
choix par défaut viennent d'elle : cotes, matériau, sens du caisson (dessous qui monte ou dessus
qui descend, d'après la face choisie ou l'orientation de son épaisseur) et avant (grand chant le
plus proche de l'observateur). Ni transaction ni recalcul : c'est à l'appelant (``api.py``,
commande, panneau) de les faire.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.templates.closing import (
    ANCHOR_KEY,
    check_feasible,
    closing_layout,
    nearest_front,
)
from freecad.menuiserie.core.templates.closing_params import (
    ClosingParams,
    ClosingRole,
    check_materials,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.templates import Built, build_layout
from freecad.menuiserie.features.wood_part import dimensions_of, is_wood_part

__all__ = [
    "anchor_blank",
    "build_closing",
    "closing_params",
    "default_front_turns",
    "default_role",
]

_VERTICAL: Final = 0.9  # composante verticale à partir de laquelle l'épaisseur est « verticale »
_ONE_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Sélectionnez une seule pièce de bois (le dessous ou le dessus du caisson) pour fermer le "
    "caisson.",
)
_NOT_A_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois de l'atelier."
)
_SHAPED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est une pièce dessinée : fermer le caisson demande, pour l'instant, une base "
    "rectangulaire.",
)


def anchor_blank(objects: Sequence[DocumentObject]) -> DocumentObject:
    """Brute de l'unique pièce de bois rectangulaire de ``objects`` (une pièce usinée donne sa
    brute) ; ``ValueError`` traduite pour zéro ou plusieurs objets, un autre objet ou une pièce
    dessinée."""
    if len(objects) != 1:
        raise ValueError(translated(_ONE_PART))
    obj = objects[0]
    label = {"label": quoted_value(getattr(obj, "Label", obj))}
    try:
        blank = blank_of(obj)
    except TypeError:
        raise ValueError(translated(_NOT_A_PART, label)) from None
    if is_shaped_part(blank):
        raise ValueError(translated(_SHAPED, label))
    if not is_wood_part(blank):
        raise ValueError(translated(_NOT_A_PART, label))
    return blank


def _local_up(blank: DocumentObject) -> float:
    """Composante verticale (Z du document) de l'axe de l'épaisseur de ``blank``."""
    placement = App.Placement(blank.getGlobalPlacement())
    return float(placement.Rotation.multVec(App.Vector(0, 0, 1)).z)


def _face_side(blank: DocumentObject, picked: DocumentObject, face: str) -> float | None:
    """Sens, sur l'épaisseur de ``blank``, de la normale de la face ``face`` (``Face3``) de l'objet
    ``picked`` (la brute ou sa pièce usinée) : positif sur la face +épaisseur, négatif sur la face
    opposée, ``None`` pour un chant ou une face illisible."""
    try:
        normal = picked.Shape.getElement(face).normalAt(0.0, 0.0)
        container = App.Placement(picked.getGlobalPlacement()).multiply(
            App.Placement(picked.Placement).inverse()
        )  # la forme porte le Placement local : il reste le repère du conteneur
        normal = container.Rotation.multVec(normal)
    except (AttributeError, RuntimeError, ValueError, TypeError):
        return None
    placement = App.Placement(blank.getGlobalPlacement())
    local_z = float(placement.Rotation.inverted().multVec(normal).z)
    return local_z if abs(local_z) > _VERTICAL else None


def default_role(
    blank: DocumentObject, face: str | None = None, picked: DocumentObject | None = None
) -> ClosingRole:
    """Sens du caisson : avec une face ``face`` de ``picked`` (``blank`` par défaut) choisie, il
    part de cette face (dessous si sa normale est celle de l'épaisseur, dessus sinon) ; sans face,
    une épaisseur verticale donne un dessous qui monte (+Z du document), sinon le caisson part du
    côté +épaisseur."""
    side = _face_side(blank, blank if picked is None else picked, face) if face else None
    if side is None:
        up = _local_up(blank)
        side = up if abs(up) > _VERTICAL else 1.0
    return ClosingRole.BOTTOM if side > 0 else ClosingRole.TOP


def default_front_turns(blank: DocumentObject, viewer: tuple[float, float, float]) -> int:
    """Avant du caisson : grand chant de ``blank`` le plus proche de ``viewer`` (position de la
    caméra dans le document)."""
    placement = App.Placement(blank.getGlobalPlacement())
    local = placement.inverse().multVec(App.Vector(*viewer))
    return nearest_front(dimensions_of(blank), Vec3(local.x, local.y, local.z))


def closing_params(anchor: DocumentObject, **values: Any) -> ClosingParams:
    """Paramètres de la fermeture autour de ``anchor`` : cotes et matériau de l'ancre, puis
    ``values`` (champs de :class:`ClosingParams`) ; ``ValueError`` traduite si refusés."""
    blank = anchor_blank([anchor])
    with translated_errors():
        return ClosingParams(dimensions_of(blank), str(blank.MaterialId), **values)


def build_closing(doc: Document, anchor: DocumentObject, params: ClosingParams) -> Built:
    """Crée les pièces, les assemblages et l'ensemble « Caisson » (``Template`` =
    ``ClosedCarcass``) autour de ``anchor`` ; si elle est membre d'un ensemble, elle en sort et
    l'ensemble créé devient son sous-ensemble. Tout est contrôlé avant la première création
    (matériaux, cotes de chaque assemblage) : ``TypeError`` ou ``ValueError`` traduites."""
    blank = anchor_blank([anchor])
    with translated_errors():
        check_materials(params, {material.id for material in get_library()})
        layout = closing_layout(params)
        check_feasible(layout)
    return build_layout(doc, layout, existing={ANCHOR_KEY: blank})
