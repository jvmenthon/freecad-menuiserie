# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profils d'arête sur arêtes natives d'une pièce dessinée (ADR 0063).

Les arêtes d'une pièce qui n'est pas une boîte se désignent par leur nom FreeCAD (``"Edge7"``),
gardé dans ``EdgeProfile.EdgeRefs`` (lien suivi par le nommage topologique). Ce module valide ces
noms, lit la forme de la pièce et calcule les coupes ; une arête que FreeCAD n'a pas pu suivre
garde son « ? » (``"?Edge17"``) : elle est « perdue ».
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie.core._extrusion import Extrusion
from freecad.menuiserie.core.edges import EdgeError, EdgeFamily, edge_cut_in_frame
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.box_parts import box_part_refusal, is_box_part
from freecad.menuiserie.features.edge_frames import (
    MAX_NATIVE_EDGES,
    edge_index,
    has_element_map,
    native_edge,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.shaped_part import base_shape_of, is_shaped_part

__all__ = [
    "LOST",
    "MIXED",
    "ON_PART",
    "designated_edges",
    "is_native_designation",
    "lost_edges",
    "native_cuts",
    "native_names",
    "native_shape",
    "part_refusal",
    "refs_of",
]

_NO_EDGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Choisissez au moins une arête à profiler.")
ON_PART: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce « {label} » : {message}")
_NO_ELEMENT_MAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'a pas de noms d'éléments stables (forme importée ou calculée) : ses arêtes "
    "ne peuvent pas être suivies, choisissez une pièce dessinée dans un corps.",
)
_NOT_SHAPED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est une pièce de bois en boîte : ses arêtes se désignent par leurs faces "
    "(« dessus-avant »).",
)
_BAD_NATIVE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Arêtes natives : des noms « EdgeN » différents de la pièce (au plus {maximum}) sont attendus.",
)
LOST: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Arêtes perdues après une modification de la pièce : {edges}. Choisissez-les à nouveau.",
)
MIXED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Un profil désigne ses arêtes soit par leurs faces, soit par leur nom, pas les deux.",
)


def is_native_designation(edges: object) -> bool:
    """Vrai si ``edges`` nomme au moins une arête native (``"Edge7"``) : la liste est alors lue
    par :func:`native_names`, qui refuse un mélange avec des codes de boîte."""
    if isinstance(edges, str) or not isinstance(edges, list | tuple | set | frozenset):
        return False
    return any(edge_index(item) is not None for item in edges)


def native_names(edges: object) -> list[str]:
    """Noms ``"EdgeN"`` d'arêtes natives, triés par rang, sans doublon ; ``ValueError`` traduite
    si la liste est vide, trop longue, ou mêle d'autres textes (codes de boîte : refus clair)."""
    if isinstance(edges, str) or not isinstance(edges, list | tuple | set | frozenset):
        raise ValueError(translated(_NO_EDGE))
    items = list(edges)
    if not items:
        raise ValueError(translated(_NO_EDGE))
    if len(items) > MAX_NATIVE_EDGES:
        raise ValueError(translated(_BAD_NATIVE, {"maximum": str(MAX_NATIVE_EDGES)}))
    indexes = [edge_index(item) for item in items]
    if any(index is None for index in indexes):
        if any(index is not None for index in indexes):
            raise ValueError(translated(MIXED))
        raise ValueError(translated(_BAD_NATIVE, {"maximum": str(MAX_NATIVE_EDGES)}))
    unique = sorted({index for index in indexes if index is not None})
    if len(unique) != len(items):
        raise ValueError(translated(_BAD_NATIVE, {"maximum": str(MAX_NATIVE_EDGES)}))
    return [f"Edge{index}" for index in unique]


def refs_of(profile: DocumentObject) -> list[str]:
    """Noms enregistrés dans ``EdgeRefs`` (vide pour un profil de boîte)."""
    refs = profile.EdgeRefs if "EdgeRefs" in profile.PropertiesList else None
    if not refs:
        return []
    return [str(name) for name in refs[1]]


def designated_edges(profile: DocumentObject) -> list[str]:
    """Arêtes du profil telles qu'enregistrées : codes de boîte, ou noms natifs (un nom perdu
    garde son « ? » : ``"?Edge17"``)."""
    refs = refs_of(profile)
    return refs if refs else [str(code) for code in profile.Edges]


def lost_edges(profile: DocumentObject) -> list[str]:
    """Noms des arêtes natives du profil que FreeCAD n'a pas pu suivre (vide pour une boîte)."""
    part = profile.Part
    count = len(part.Shape.Edges) if part is not None else 0
    lost = []
    for name in refs_of(profile):
        index = edge_index(name)
        if index is None or index > count:
            lost.append(name.lstrip("?"))
    return lost


def native_shape(part: DocumentObject) -> Any:
    """Forme de la pièce dessinée ``part`` dans son repère, dont on lit les arêtes natives ;
    ``ValueError`` traduite si ce n'est pas une pièce dessinée ou si sa forme n'a pas de carte
    d'éléments (le lien désignerait un numéro, ADR 0063)."""
    label = quoted_value(part.Label)
    if not is_shaped_part(part):
        raise ValueError(translated(_NOT_SHAPED, {"label": label}))
    # La pièce se donne toujours une carte ; c'est celle de sa source qui dit si les noms des
    # arêtes sont suivis (corps PartDesign) ou tirés des numéros (primitive, forme importée).
    source = getattr(part, "Source", None)
    if not has_element_map(part.Shape if source is None else source.Shape):
        raise ValueError(translated(_NO_ELEMENT_MAP, {"label": label}))
    return base_shape_of(part)


def part_refusal(part: DocumentObject) -> str | None:
    """Raison traduite pour laquelle ``part`` ne peut pas recevoir de profil, ``None`` si elle le
    peut : une boîte toujours (codes de faces) ; une pièce dessinée si ses arêtes peuvent être
    suivies ; aucune autre pièce."""
    if is_box_part(part):
        return None
    if not is_shaped_part(part):
        return box_part_refusal(part)
    try:
        native_shape(part)
    except ValueError as error:
        return str(error)
    return None


def native_cuts(
    part: DocumentObject,
    names: list[str],
    family: EdgeFamily,
    a: float,
    b: float,
    *,
    skip_lost: bool = False,
) -> list[Extrusion]:
    """Coupes du profil ``family`` sur les arêtes natives ``names`` de la pièce dessinée
    ``part``, dans son repère. ``ValueError`` traduite, qui nomme la pièce, si une arête est
    refusée (courbe, rentrante, trop petite…) ou perdue ; avec ``skip_lost``, une arête perdue
    est seulement ignorée."""
    shape = native_shape(part)
    cuts: list[Extrusion] = []
    lost: list[str] = []
    try:
        for name in names:
            index = edge_index(name)
            if index is None or index > len(shape.Edges):
                lost.append(name.lstrip("?"))
                continue
            edge = native_edge(shape, index)
            if edge.frame is None:
                raise ValueError(edge.refusal)
            with translated_errors():
                cuts.append(edge_cut_in_frame(edge.frame, family, a, b))
        if lost and not skip_lost:
            raise ValueError(translated(LOST, {"edges": ", ".join(lost)}))
    except (ValueError, EdgeError) as error:
        raise ValueError(
            translated(ON_PART, {"label": quoted_value(part.Label), "message": str(error)})
        ) from None
    return cuts
