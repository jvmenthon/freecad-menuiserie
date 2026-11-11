# SPDX-License-Identifier: LGPL-2.1-or-later
"""Butée prise sur la pièce brute plutôt que sur la pièce usinée (retour de jv, 2026-11-10).

Une pièce usinée dépend de ses assemblages ; les assemblages recopiés dépendent des copies, qui
dépendent de la répétition. Une répétition qui viserait la pièce usinée assemblée à l'original
formerait un cycle (« The graph must be a DAG »). La butée vise donc la brute : même élément s'il
existe tel quel, sinon l'élément de la brute qui le contient (face entamée par un usinage), sinon
la pièce entière. Un document où la butée vise une pièce usinée est corrigé à l'ouverture.
"""

from __future__ import annotations

import re
from typing import Final

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.repeat_props import LINE_COUNT, line_name
from freecad.menuiserie.features.repeat_stop import Stop, Stops

__all__ = ["raw_stop", "raw_stops", "restore_raw_stops"]

_TOLERANCE: Final = 1e-6
_KIND: Final = re.compile(r"(Face|Edge|Vertex)\d+")
_ELEMENTS: Final = {"Face": "Faces", "Edge": "Edges", "Vertex": "Vertexes"}


def _raw_element(machined: DocumentObject, raw: DocumentObject, sub: str) -> str:
    """Nom de l'élément de ``raw`` qui correspond à l'élément ``sub`` de ``machined`` : même
    encombrement, sinon le plus petit qui le contient ; vide (pièce entière) à défaut."""
    match = _KIND.fullmatch(sub)
    if match is None:
        return ""
    try:
        box = machined.Shape.getElement(sub).BoundBox
    except (IndexError, ValueError):
        return ""
    kind = match.group(1)
    found: list[tuple[float, str]] = []
    for index, element in enumerate(getattr(raw.Shape, _ELEMENTS[kind]), start=1):
        candidate = element.BoundBox
        candidate.enlarge(_TOLERANCE)
        if candidate.isInside(box):
            found.append((candidate.DiagonalLength, f"{kind}{index}"))
    return min(found)[1] if found else ""


def raw_stop(stop: Stop) -> Stop:
    """``stop`` ramenée à la pièce brute si elle vise une pièce usinée (sinon inchangée)."""
    obj = stop.obj
    raw = getattr(obj, "Base", None)
    if not is_machined_part(obj) or raw is None:
        return stop
    return Stop(raw, _raw_element(obj, raw, stop.sub) if stop.sub else "")


def raw_stops(stops: Stops | None) -> Stops | None:
    """Chaque butée de ``stops`` ramenée à la brute (``None`` reste ``None``)."""
    return None if stops is None else {axis: raw_stop(stop) for axis, stop in stops.items()}


def restore_raw_stops(repeat: DocumentObject) -> None:
    """Ouverture d'un document : une butée qui vise une pièce usinée vise désormais sa brute."""
    for index in range(LINE_COUNT):
        name = line_name("Stop", index)
        value = getattr(repeat, name, None)
        if not value or value[0] is None or not is_machined_part(value[0]):
            continue
        sub = next((element for element in value[1] if element), "")
        stop = raw_stop(Stop(value[0], sub))
        setattr(repeat, name, (stop.obj, [stop.sub] if stop.sub else []))
