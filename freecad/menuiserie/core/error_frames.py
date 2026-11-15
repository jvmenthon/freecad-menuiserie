# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cadres d'exécution gardés par la dernière erreur affichée de l'interpréteur."""

from __future__ import annotations

import sys
from contextlib import suppress

__all__ = ["release_last_error_frames"]


def release_last_error_frames() -> None:
    """Vide les cadres d'exécution gardés par la dernière erreur affichée (``sys.last_traceback``).

    Une erreur de recalcul pendant l'aperçu d'un panneau (valeur en cours de saisie refusée par
    un assemblage) est affichée par FreeCAD, et Python en garde la trace : ses cadres remontent
    jusqu'au signal du panneau et gardent en vie ce panneau, donc les enveloppes PySide de ses
    widgets, après sa fermeture. Qt réutilise ensuite leurs adresses pour les widgets du panneau
    suivant, vus sous l'ancienne enveloppe (``kindCombo`` pris pour un ``QGridLayout`` : le
    panneau ne s'ouvre pas). Seules les variables locales des cadres terminés sont lâchées."""
    trace = getattr(sys, "last_traceback", None)
    while trace is not None:
        frame = trace.tb_frame
        while frame is not None:
            with suppress(RuntimeError):  # cadre encore en cours d'exécution
                frame.clear()
            frame = frame.f_back
        trace = trace.tb_next
