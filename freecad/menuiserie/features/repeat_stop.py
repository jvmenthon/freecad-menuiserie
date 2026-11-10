# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition jusqu'à une butée (ADR 0047, spécification § 10 « Jusqu'à une butée »).

Dans les modes « sur une longueur » (nombre ou pas), la longueur d'un axe peut être **calculée** :
c'est la distance, sur l'axe et dans le sens de la répétition, entre l'original et une butée (face,
arête, sommet ou pièce entière, d'un objet du document, éventuellement hors du conteneur). Le calcul
pur est dans :mod:`freecad.menuiserie.core.repeat`; ce module lit la géométrie, garde la butée dans
la répétition (``Stop``, ``Stop2``, ``Stop3`` : liens globaux avec sous-élément) et la suit.

Suivi (Q3) : la longueur **suit** la butée. ``Repeat.execute`` relit la butée à chaque recalcul,
réécrit ``Span`` et, en « nombre sur une longueur », ``Step`` : les copies, liées à ``Step`` par
expression, suivent. Limite (comme « Suivre le redimensionnement ») : un recalcul n'écrit pas la
structure du document ; en « pas sur une longueur », le nombre de copies ne change donc qu'à
l'édition de la répétition (un avertissement l'indique). Butée supprimée : le lien se vide, la
répétition garde la dernière longueur et repasse en saisie, avec un avertissement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final, NamedTuple

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import (
    RepeatAxis,
    RepeatParams,
    SpacingMode,
    farthest_axis,
    resolve_line,
    stop_kind,
    stop_reverse,
    stop_span,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    has_expression,
    restoring_or_undoing,
)
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import report_warning, translated, translated_errors
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.repeat import is_copy, sources_of, stored_params
from freecad.menuiserie.features.repeat_members import descendants_of
from freecad.menuiserie.features.repeat_props import LINE_COUNT, NO_AXIS, line_name
from freecad.menuiserie.features.repeat_sources import (
    common_container,
    source_bounds,
    source_extent,
)
from freecad.menuiserie.features.repeat_stop_props import HOLDERS_PROPERTY

__all__ = [
    "Stop",
    "Stops",
    "bounded_params",
    "follow_stops",
    "kept_stops",
    "start_axis",
    "stop_axis",
    "stop_bounds",
    "stop_text",
    "stored_stops",
    "write_stops",
]

_NEEDS_SPAN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : une butée remplace la longueur ; elle demande le mode « Nombre sur une "
    "longueur » ou « Pas sur une longueur ».",
)
_FOLLOW_EXCLUSIVE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : une butée et « Suivre le redimensionnement » se contredisent (deux longueurs "
    "calculées) ; gardez l'un des deux.",
)
_NO_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : la butée « {label} » n'a pas de forme ; choisissez une pièce."
)
_NO_ELEMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : la butée « {sub} » n'existe pas dans « {label} »."
)
_IS_SOURCE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » est la pièce répétée ou l'une de ses copies ; elle ne peut pas "
    "servir de butée.",
)
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : la butée « {label} » est dans un autre document."
)
_LOST: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition « {label} » : la butée « {stop} » n'existe plus ; la longueur reste à {span} mm "
    "(dernière valeur) et se saisit de nouveau.",
)
_COUNT_CHANGED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition « {label} » : la butée a bougé ; le nombre de copies sur l'axe {axis} ne change "
    "qu'en modifiant la répétition ({count} copies tiendraient).",
)
_TOLERANCE: Final = 1e-9


class Stop(NamedTuple):
    """Butée choisie : l'objet et son sous-élément (``FaceN``, ``EdgeN``, ``VertexN`` ; vide :
    pièce)."""

    obj: DocumentObject
    sub: str = ""


Stops = Mapping[RepeatAxis, Stop]


def stop_text(stop: Stop) -> str:
    """Nom de la butée pour l'interface : libellé de l'objet, puis son sous-élément."""
    return f"{stop.obj.Label} : {stop.sub}" if stop.sub else str(stop.obj.Label)


def _label(stop: Stop) -> str:
    return quoted_value(stop.obj.Label)


def _is_source(obj: DocumentObject, sources: Sequence[DocumentObject], repeat: object) -> bool:
    """Vrai si ``obj`` (ou sa pièce brute) est une source, un membre d'une source ensemble, ou une
    copie de ``repeat``."""
    base = obj.Base if is_machined_part(obj) else obj
    originals = {source.Name for source in sources}
    for source in sources:
        if is_furniture(source):
            originals.update(member.Name for member in descendants_of(source))
    return base.Name in originals or (
        repeat is not None and is_copy(base) and base.Repeat == repeat
    )


def checked_stop(stop: Stop, sources: Sequence[DocumentObject], repeat: object = None) -> None:
    """Refus traduits (``ValueError``) d'une butée : autre document, sous-élément ni face ni
    sommet, pièce répétée ou copie, objet sans forme, sous-élément absent."""
    with translated_errors():
        stop_kind(stop.sub)
    label = _label(stop)
    if stop.obj.Document != sources[0].Document:
        raise ValueError(translated(_OTHER_DOCUMENT, {"label": label}))
    if _is_source(stop.obj, sources, repeat):
        raise ValueError(translated(_IS_SOURCE, {"label": label}))
    shape = getattr(stop.obj, "Shape", None)
    if shape is None or shape.isNull():
        raise ValueError(translated(_NO_SHAPE, {"label": label}))
    _element(stop)


def _element(stop: Stop) -> App.Shape:
    """Forme de la butée : l'objet entier, ou sa face, son arête ou son sommet."""
    shape = stop.obj.Shape
    if not stop.sub:
        return shape
    try:
        return shape.getElement(stop.sub)
    except (IndexError, ValueError):
        raise ValueError(
            translated(_NO_ELEMENT, {"sub": stop.sub, "label": _label(stop)})
        ) from None


def _global_of(container: DocumentObject | None) -> App.Placement:
    return App.Placement() if container is None else container.getGlobalPlacement()


def stop_bounds(
    stop: Stop, container: DocumentObject | None, axis: RepeatAxis
) -> tuple[float, float]:
    """Étendue (bas, haut, en mm) de la butée sur ``axis``, dans le repère de ``container``
    (celui des sources). Une face oblique ou une pièce entière donne son encombrement."""
    shape = _element(stop).copy()
    holder = stop.obj.getParentGeoFeatureGroup()
    if holder != container:
        shape.transformShape(
            _global_of(container).inverse().multiply(_global_of(holder)).toMatrix()
        )
    box = shape.BoundBox
    low, high = (float(getattr(box, f"{axis.value}{end}")) for end in ("Min", "Max"))
    return round(low, 6), round(high, 6)


def start_axis(stop: Stop, sources: Sequence[DocumentObject]) -> RepeatAxis | None:
    """Face plane d'une pièce répétée choisie comme butée : c'est le point de départ (retour de
    jv), son axe est renvoyé ; ``None`` pour tout autre choix."""
    if not stop.sub.startswith("Face") or not _is_source(stop.obj, sources, None):
        return None
    container = common_container(sources)
    spans = {axis: stop_bounds(stop, container, axis) for axis in RepeatAxis}
    flat = [axis for axis, (low, high) in spans.items() if high - low < _TOLERANCE]
    return flat[0] if len(flat) == 1 else None


def stop_axis(stop: Stop, sources: Sequence[DocumentObject]) -> RepeatAxis:
    """Axe vers la butée (le plus grand écart aux sources), pour un choix sans axe donné ;
    ``ValueError`` traduite si la butée est refusée."""
    checked_stop(stop, sources, None)
    container = common_container(sources)
    return farthest_axis(
        {axis: source_bounds(sources, axis) for axis in RepeatAxis},
        {axis: stop_bounds(stop, container, axis) for axis in RepeatAxis},
    )


def bounded_params(
    sources: Sequence[DocumentObject],
    params: RepeatParams,
    stops: Stops,
    repeat: DocumentObject | None = None,
) -> RepeatParams:
    """``params`` dont la longueur de chaque axe qui a une butée est la distance à cette butée
    (les butées d'axes inactifs sont ignorées). ``repeat`` : répétition modifiée, dont les copies
    ne peuvent pas servir de butée. ``ValueError`` traduite si le mode n'est pas « sur une
    longueur », avec « Suivre le redimensionnement », ou si une butée est refusée (derrière
    l'original, trop proche, pièce répétée, sous-élément invalide)."""
    active = {line.axis for line in params.lines}
    used = {axis: stop for axis, stop in stops.items() if axis in active}
    if not used:
        return params
    if params.spacing is SpacingMode.COUNT_AND_STEP:
        raise ValueError(translated(_NEEDS_SPAN))
    if params.follow_resize:
        raise ValueError(translated(_FOLLOW_EXCLUSIVE))
    container = common_container(sources)
    lines = []
    for line in params.lines:
        stop = used.get(line.axis)
        if stop is not None:
            checked_stop(stop, sources, repeat)
            bounds = source_bounds(sources, line.axis)
            low, high = stop_bounds(stop, container, line.axis)
            reverse = stop_reverse(bounds, (low, high))  # le sens va vers la butée
            with translated_errors():
                span = stop_span(
                    bounds,
                    high if reverse else low,
                    line.axis,
                    reverse=reverse,
                    deduct=params.deduct_thickness and not params.end_gap,
                )
            line = replace(line, span=span, reverse=reverse)
        lines.append(line)
    return replace(params, grid=tuple(lines))


def _line_axes(repeat: DocumentObject) -> list[RepeatAxis | None]:
    """Axe de chacune des trois lignes (``None`` : ligne inutilisée)."""
    axes: list[RepeatAxis | None] = []
    for index in range(LINE_COUNT):
        name = str(getattr(repeat, line_name("Axis", index), NO_AXIS))
        axes.append(None if name == NO_AXIS else RepeatAxis(name))
    return axes


def _link_of(repeat: DocumentObject, index: int) -> Stop | None:
    value = getattr(repeat, line_name("Stop", index), None)
    if not value or value[0] is None:
        return None
    return Stop(value[0], next((name for name in value[1] if name), ""))


def stored_stops(repeat: DocumentObject) -> dict[RepeatAxis, Stop]:
    """Butées que garde la répétition, par axe (celles dont l'objet existe encore)."""
    found: dict[RepeatAxis, Stop] = {}
    for index, axis in enumerate(_line_axes(repeat)):
        stop = _link_of(repeat, index)
        if axis is not None and stop is not None:
            found[axis] = stop
    return found


def _write(repeat: DocumentObject, name: str, value: object) -> None:
    """Écrit la propriété ``name`` si sa valeur change."""
    if name not in repeat.PropertiesList:
        return
    current = getattr(repeat, name)
    if getattr(current, "Value", current) != value:
        setattr(repeat, name, value)


def _ancestors(obj: DocumentObject) -> list[DocumentObject]:
    """Conteneurs (``App::Part``…) de ``obj``, du plus proche au plus lointain."""
    found: list[DocumentObject] = []
    while (holder := obj.getParentGeoFeatureGroup()) is not None and holder not in found:
        found.append(holder)
        obj = holder
    return found


def _holders(repeat: DocumentObject, stops: Stops) -> list[DocumentObject]:
    """Conteneurs des butées qui ne contiennent pas la répétition (elle en dépendrait en cycle) :
    la répétition en dépend, donc déplacer l'un d'eux recalcule la longueur."""
    own = _ancestors(repeat)
    found: list[DocumentObject] = []
    for stop in stops.values():
        found.extend(h for h in _ancestors(stop.obj) if h not in own and h not in found)
    return found


def kept_stops(repeat: DocumentObject, params: RepeatParams, stops: Stops | None) -> Stops:
    """Butées d'une modification de ``repeat`` : celles données, ou (``None``) celles qu'elle
    garde, sauf si ``params`` n'a pas de longueur à remplacer (nombre et pas, ou suivi du
    redimensionnement : les butées sont alors retirées)."""
    if stops is not None:
        return stops
    if params.spacing is SpacingMode.COUNT_AND_STEP or params.follow_resize:
        return {}
    return stored_stops(repeat)


def write_stops(repeat: DocumentObject, axes: Sequence[RepeatAxis], stops: Stops) -> None:
    """Écrit la butée de chaque ligne (``axes`` : axes des lignes, dans l'ordre) ; une ligne sans
    butée est vidée. Ne touche pas aux propriétés qui ne changent pas."""
    holders = _holders(repeat, stops)
    if (
        HOLDERS_PROPERTY in repeat.PropertiesList
        and list(getattr(repeat, HOLDERS_PROPERTY)) != holders
    ):
        setattr(repeat, HOLDERS_PROPERTY, holders)
    for index in range(LINE_COUNT):
        stop = stops.get(axes[index]) if index < len(axes) else None
        if (_link_of(repeat, index) or None) != stop:
            value = None if stop is None else (stop.obj, [stop.sub] if stop.sub else [])
            setattr(repeat, line_name("Stop", index), value)
        _write(repeat, line_name("StopLabel", index), "" if stop is None else stop_text(stop))


def _lost_stops(repeat: DocumentObject) -> list[tuple[int, str]]:
    """Lignes dont la butée a disparu du document : (ligne, libellé gardé)."""
    return [
        (index, str(getattr(repeat, line_name("StopLabel", index))))
        for index in range(LINE_COUNT)
        if getattr(repeat, line_name("StopLabel", index), "") and _link_of(repeat, index) is None
    ]


def _report_lost(repeat: DocumentObject) -> None:
    """Butée supprimée : la ligne repasse en saisie avec sa dernière longueur, un avertissement
    le dit (une seule fois : le libellé gardé est vidé)."""
    for index, label in _lost_stops(repeat):
        span = float(getattr(repeat, line_name("Span", index)).Value)
        params = {"label": quoted_value(repeat.Label), "stop": quoted_value(label)}
        report_warning(translated(_LOST, {**params, "span": f"{span:g}"}))
        setattr(repeat, line_name("StopLabel", index), "")


def follow_stops(repeat: DocumentObject) -> None:
    """``Repeat.execute`` : butée supprimée signalée, puis longueur de chaque ligne à butée
    recalculée d'après la butée (``Span``, et ``Step`` en « nombre sur une longueur »).
    Rien pendant une annulation ou une restauration. Un refus (butée devenue trop proche ou
    derrière l'original) est un avertissement : les valeurs gardées restent."""
    if restoring_or_undoing(repeat):
        return
    stops = stored_stops(repeat)
    if not stops and not _lost_stops(repeat):
        return
    _report_lost(repeat)
    sources = sources_of(repeat)
    if not stops or not sources:
        return
    try:
        with translated_errors():
            params = stored_params(repeat)
        _apply_spans(repeat, params, bounded_params(sources, params, stops, repeat))
    except ValueError as refusal:
        report_warning(str(refusal))


def _apply_spans(repeat: DocumentObject, before: RepeatParams, after: RepeatParams) -> None:
    """Écrit la nouvelle longueur de chaque ligne de ``after`` et, en « nombre sur une longueur »,
    son pas (sauf s'il est piloté par une expression de l'utilisateur)."""
    sources = sources_of(repeat)
    axes = [axis for axis in _line_axes(repeat) if axis is not None]
    for index, (old, line) in enumerate(zip(before.lines, after.lines, strict=True)):
        if line.reverse != old.reverse:  # butée passée de l'autre côté de l'original
            _write(repeat, line_name("Reverse", index), line.reverse)
        if abs(line.span - old.span) < _TOLERANCE and line.reverse == old.reverse:
            continue
        _write(repeat, line_name("Span", index), line.span)
        with translated_errors():
            resolved = resolve_line(
                after.spacing,
                line,
                source_extent(sources, axes[index]),
                deduct=after.deduct_thickness,
                gap=after.end_gap,
            )
        if after.spacing is SpacingMode.COUNT_ON_SPAN:
            if not has_expression(repeat, line_name("Step", index)):
                _write(repeat, line_name("Step", index), resolved.step)
        elif resolved.count != line.count - 1:
            params = {"label": quoted_value(repeat.Label), "axis": axes[index].value}
            report_warning(translated(_COUNT_CHANGED, {**params, "count": str(resolved.count)}))
