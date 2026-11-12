# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés de la façade publique (issue #153, ADR 0053).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.drawing import DEFAULT_FORMAT, Orientation
from freecad.menuiserie.features import drawing
from freecad.menuiserie.features.freecad_types import Document, DocumentObject

__all__ = ["make_overall_drawing"]


def make_overall_drawing(
    doc: Document,
    objects: Sequence[DocumentObject],
    page_format: str = DEFAULT_FORMAT,
    orientation: Orientation = Orientation.LANDSCAPE,
) -> DocumentObject:
    """Crée ou refait le **plan de l'ouvrage** de ``objects`` (ensembles, pièces, Std Part) et
    renvoie sa page, une ``TechDraw::DrawPage`` ordinaire : face, dessus, vue de gauche et
    perspective à la même échelle normalisée, cotes hors tout (largeur, profondeur, hauteur) qui
    suivent le modèle, gabarit ISO fourni par TechDraw (``page_format`` « A4 » à « A0 »,
    ``orientation``). Relancer la fonction sur les mêmes objets refait l'échelle et la mise en
    page ; une page modifiée à la main est laissée telle quelle et une nouvelle page est créée.
    Une seule transaction « Plan de l'ouvrage ». ``ValueError`` traduite si TechDraw n'est pas
    disponible, s'il n'y a rien à dessiner ou pour un format inconnu."""
    return drawing.make_overall_drawing(
        doc, objects, drawing.DrawingOptions(page_format, orientation)
    )
