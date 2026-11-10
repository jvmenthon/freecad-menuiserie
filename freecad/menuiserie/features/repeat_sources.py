# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sources d'une répétition : contrôles, conteneur commun, cotes et grille effective (ADR 0043).

Une source est une pièce de bois (ou la pièce usinée d'une pièce de bois : la répétition porte sur
sa pièce brute, ADR 0006) ou un ensemble de pièces de bois. Les refus sont des ``ValueError`` ou
``TypeError`` traduites, levées avant toute création. La cote qui sert aux modes « sur une
longueur » est celle de l'ensemble des sources le long de chaque axe de la grille (boîte
englobante de leurs formes, ou cote d'un ensemble, lues à l'écriture).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, ResolvedGrid, resolve_grid
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_container import placement_container, std_part_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.repeat import is_copy
from freecad.menuiserie.features.repeat_follow import follow_furniture
from freecad.menuiserie.features.repeat_members import ancestors_of, descendants_of
from freecad.menuiserie.features.wood_part import is_wood_part, validated_arguments

__all__ = [
    "checked_sources",
    "common_container",
    "resolve_for",
    "source_bounds",
    "source_extent",
    "source_extents",
]

_NO_SOURCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répétition : aucune pièce à répéter.")
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'est pas une pièce de bois ; pour l'instant, seules les pièces "
    "de bois (ou leur pièce usinée) et les ensembles se répètent (pas les pièces en bois).",
)
_FOREIGN_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : l'ensemble « {furniture} » contient « {label} », qui n'est pas une pièce de "
    "bois ; pour l'instant, seuls les ensembles de pièces de bois se répètent.",
)
_IS_A_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » est déjà la copie d'une répétition ; dissociez-la d'abord pour la "
    "répéter.",
)
_WITH_ITS_FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » est membre de « {furniture} », répété en même temps ; répétez "
    "l'ensemble, ou la pièce seule.",
)
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : les pièces à répéter doivent être dans le même document."
)
_EMPTY_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'a pas de forme ; recalculez le document avant de la répéter.",
)
_OTHER_CONTAINERS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : les pièces à répéter sont dans des conteneurs différents (« {first} » et "
    "« {second} ») ; répétez-les séparément.",
)
_ROOT: Final = QT_TRANSLATE_NOOP("Menuiserie", "la racine du document")
_AXES: Final = {RepeatAxis.X: "X", RepeatAxis.Y: "Y", RepeatAxis.Z: "Z"}
_SIZES: Final = {RepeatAxis.X: "Width", RepeatAxis.Y: "Depth", RepeatAxis.Z: "Height"}


def _checked_part(obj: DocumentObject) -> None:
    """Pièce de bois de dimensions et matériau valides (``ValueError`` traduite sinon)."""
    validated_arguments(*(obj.Length.Value, obj.Width.Value, obj.Thickness.Value), obj.MaterialId)


def _checked_furniture(furniture: DocumentObject) -> None:
    """Un ensemble ne se répète que si tous ses membres, à tous les niveaux, sont des pièces de
    bois ou des ensembles (``TypeError`` traduite sinon)."""
    for member in descendants_of(furniture):
        if is_furniture(member):
            continue
        if not is_wood_part(member):
            params = {
                "furniture": quoted_value(furniture.Label),
                "label": quoted_value(member.Label),
            }
            raise TypeError(translated(_FOREIGN_MEMBER, params))
        _checked_part(member)


def _checked_source(obj: DocumentObject) -> None:
    """Une source valide : pièce de bois ou ensemble, qui n'est pas déjà une copie liée."""
    params = {"label": quoted_value(getattr(obj, "Label", obj))}
    if not (is_furniture(obj) or is_wood_part(obj)):
        raise TypeError(translated(_NOT_A_WOOD_PART, params))
    if is_copy(obj):
        raise ValueError(translated(_IS_A_COPY, params))
    if is_furniture(obj):
        _checked_furniture(obj)
    else:
        _checked_part(obj)


def _refuse_nested(sources: Sequence[DocumentObject]) -> None:
    """Une source ne peut pas être répétée en même temps que l'un de ses ensembles (``ValueError``
    traduite) : elle serait copiée deux fois."""
    names = {obj.Name for obj in sources}
    for obj in sources:
        for furniture in ancestors_of(obj):
            if furniture.Name in names:
                params = {
                    "label": quoted_value(obj.Label),
                    "furniture": quoted_value(furniture.Label),
                }
                raise ValueError(translated(_WITH_ITS_FURNITURE, params))


def common_container(sources: Sequence[DocumentObject]) -> DocumentObject | None:
    """Conteneur (``App::Part``) commun des ``sources``, ``None`` si elles sont à la racine ;
    ``ValueError`` traduite si elles sont réparties dans des conteneurs différents (les copies
    sont rangées avec la source, la répétition avec elles)."""
    containers = [placement_container(obj) for obj in sources]
    first = containers[0]
    for other in containers[1:]:
        if other != first:
            names = [getattr(c, "Label", None) or translated(_ROOT) for c in (first, other)]
            params = {"first": names[0], "second": names[1]}
            raise ValueError(translated(_OTHER_CONTAINERS, params))
    return first


def checked_sources(
    objects: Sequence[DocumentObject], *, one_container: bool = True
) -> list[DocumentObject]:
    """Pièces et ensembles à répéter, sans doublon, dans l'ordre. Refus traduits avant toute
    création : ``ValueError`` (aucune pièce, documents différents, copie déjà liée, pièce répétée
    en même temps que son propre ensemble, cote ou matériau inconnu), ``TypeError`` (autre chose
    qu'une pièce de bois ou un ensemble de pièces de bois) ; ``KeyError`` pour un matériau absent
    de la bibliothèque locale. ``one_container`` faux : le conteneur commun n'est pas contrôlé
    (l'appelant le fait après les autres réglages, avec :func:`common_container`)."""
    sources = list(
        dict.fromkeys(
            machined.Base if is_machined_part(machined) else machined for machined in objects
        )
    )
    if not sources:
        raise ValueError(translated(_NO_SOURCE))
    for obj in sources:
        _checked_source(obj)
    if len({obj.Document.Name for obj in sources}) > 1:
        raise ValueError(translated(_OTHER_DOCUMENT))
    _refuse_nested(sources)
    if one_container:
        common_container(sources)
    return sources


def source_bounds(sources: Sequence[DocumentObject], axis: RepeatAxis) -> tuple[float, float]:
    """Bas et haut des ``sources`` le long de l'axe du conteneur (mm) : boîte englobante de leurs
    formes, ou de ``Origin`` à ``Origin`` plus la cote pour un ensemble (plus la position de son
    Std Part, s'il en a un). ``ValueError`` traduite sans source (la dernière a été supprimée : la
    répétition vidée ne se modifie plus) ou sans forme."""
    if not sources:
        raise ValueError(translated(_NO_SOURCE))
    low, high = [], []
    for source in sources:
        if is_furniture(source):
            start = getattr(source.Origin, _AXES[axis].lower())
            part = std_part_of(source)
            if part is not None:
                start += getattr(part.Placement.Base, _AXES[axis].lower())
            low.append(start)
            high.append(start + getattr(source, _SIZES[axis]).Value)
            continue
        if source.Shape.isNull():
            raise ValueError(translated(_EMPTY_SHAPE, {"label": quoted_value(source.Label)}))
        box = source.Shape.BoundBox
        low.append(getattr(box, f"{_AXES[axis]}Min"))
        high.append(getattr(box, f"{_AXES[axis]}Max"))
    return float(min(low)), float(max(high))


def source_extent(sources: Sequence[DocumentObject], axis: RepeatAxis) -> float:
    """Cote des ``sources`` le long de l'axe global (mm) : haut moins bas de
    :func:`source_bounds`."""
    low, high = source_bounds(sources, axis)
    return high - low


def source_extents(
    sources: Sequence[DocumentObject], axes: Sequence[RepeatAxis]
) -> dict[RepeatAxis, float]:
    """Cote des ``sources`` le long de chacun des ``axes`` (:func:`source_extent`)."""
    return {axis: source_extent(sources, axis) for axis in axes}


def resolve_for(sources: Sequence[DocumentObject], params: RepeatParams) -> ResolvedGrid:
    """Grille effective (nombre et pas de chaque axe actif) de ``params`` pour ces ``sources`` ;
    ``ValueError`` traduite si la répétition est refusée (longueur trop courte, trop de copies,
    « suivre le redimensionnement » sans ensemble…)."""
    if params.follow_resize:
        follow_furniture(sources)
    extents = source_extents(sources, [line.axis for line in params.lines])
    with translated_errors():
        return resolve_grid(params, extents)
