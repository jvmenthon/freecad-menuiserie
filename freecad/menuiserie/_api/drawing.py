# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés de la façade publique (issue #153, ADR 0053).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.features import drawing
from freecad.menuiserie.features.drawing import DrawingOptions
from freecad.menuiserie.features.freecad_types import Document, DocumentObject

__all__ = ["DrawingOptions", "make_overall_drawing"]


def make_overall_drawing(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> DocumentObject:
    """Crée ou refait le **plan de l'ouvrage** de ``objects`` (ensembles, pièces, Std Part) et
    renvoie sa page, une ``TechDraw::DrawPage`` ordinaire : face, dessus, vue de gauche et
    perspective à la même échelle normalisée, cotes hors tout (largeur, profondeur, hauteur) qui
    suivent le modèle, gabarit ISO fourni par TechDraw et cartouche rempli (ouvrage, matériau,
    échelle, date, auteur ; client et numéro de devis facultatifs).

    ``options`` (:class:`DrawingOptions`) fixe le format (« A4 » à « A0 »), le sens, le titre, le
    client et le numéro de devis ; ce qui n'est pas donné vient de la configuration de l'atelier
    (A3 paysage par défaut) ou de la page déjà faite. Relancer la fonction sur les mêmes objets
    refait l'échelle, la mise en page et le cartouche ; une page modifiée à la main (vue ajoutée
    ou retirée) est laissée telle quelle et une nouvelle page est créée. Une seule transaction
    « Plan de l'ouvrage ». ``ValueError`` traduite si TechDraw n'est pas disponible, s'il n'y a
    rien à dessiner ou pour un format inconnu."""
    return drawing.make_overall_drawing(doc, objects, options)
