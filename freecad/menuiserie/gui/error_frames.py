# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cadres d'exécution gardés par la dernière erreur affichée de l'interpréteur.

Sans import de FreeCAD ni de Qt : testable hors FreeCAD.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Iterator
from contextlib import suppress
from types import FrameType, TracebackType

__all__ = ["release_last_error_frames"]

_SUSPENDABLE = inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR


def release_last_error_frames() -> None:
    """Lâche les variables locales des cadres gardés par la dernière erreur affichée
    (``sys.last_exc``, ``sys.last_value``, ``sys.last_traceback``).

    Une erreur de recalcul pendant l'aperçu d'un panneau (valeur en cours de saisie refusée par
    un assemblage) est affichée par FreeCAD, et Python en garde la trace : ses cadres remontent
    (``f_back``) jusqu'au signal du panneau et gardent en vie ce panneau, donc les enveloppes
    PySide de ses widgets, après sa fermeture. Qt réutilise ensuite leurs adresses pour les
    widgets du panneau suivant, vus sous l'ancienne enveloppe (``kindCombo`` pris pour un
    ``QGridLayout`` : le panneau ne s'ouvre pas).

    Les exceptions chaînées (``__cause__``, ``__context__``) sont suivies. Un cadre en cours
    d'exécution est laissé tel quel, comme celui d'un générateur ou d'une coroutine (le vider le
    fermerait). L'erreur et sa pile restent lisibles (``traceback.print_last``) ; seules les
    variables locales des cadres terminés ne sont plus visibles d'un débogage après coup
    (``pdb.pm()``), y compris pour une erreur venue d'un autre atelier."""
    for frame in _frames():
        if frame.f_code.co_flags & _SUSPENDABLE:
            continue
        with suppress(RuntimeError):  # cadre encore en cours d'exécution
            frame.clear()


def _frames() -> Iterator[FrameType]:
    """Chaque cadre atteint depuis la dernière erreur affichée, une seule fois."""
    seen: set[int] = set()
    for trace in _traces():
        while trace is not None:
            frame: FrameType | None = trace.tb_frame
            while frame is not None and id(frame) not in seen:
                seen.add(id(frame))
                yield frame
                frame = frame.f_back
            trace = trace.tb_next


def _traces() -> Iterator[TracebackType | None]:
    """Trace de la dernière erreur affichée et de chaque exception qu'elle chaîne."""
    trace = getattr(sys, "last_traceback", None)
    yield trace if isinstance(trace, TracebackType) else None
    pending = [getattr(sys, "last_exc", None), getattr(sys, "last_value", None)]
    seen: set[int] = set()
    while pending:
        error = pending.pop()
        if not isinstance(error, BaseException) or id(error) in seen:
            continue
        seen.add(id(error))
        yield error.__traceback__
        pending += [error.__cause__, error.__context__]
