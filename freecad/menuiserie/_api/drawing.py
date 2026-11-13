# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés de la façade publique (issue #153, ADR 0053).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.features import drawing, drawing_parts
from freecad.menuiserie.features.drawing import DrawingOptions
from freecad.menuiserie.features.freecad_types import Document, DocumentObject

__all__ = ["DrawingOptions", "make_overall_drawing", "make_part_drawings"]


def make_overall_drawing(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> DocumentObject:
    """Crée ou refait le **plan de l'ouvrage** de ``objects`` (ensembles, pièces, Std Part) et
    renvoie sa page, une ``TechDraw::DrawPage`` ordinaire : face, coupe verticale (A-A) et
    coupe horizontale (B-B) au milieu de l'ouvrage, perspective, à la même échelle normalisée,
    cotes hors tout (largeur, profondeur, hauteur) qui suivent le modèle, gabarit de l'atelier
    (cartouche en français) et cartouche rempli (ouvrage, matériau,
    échelle, date, auteur ; client et numéro de devis facultatifs).

    ``options`` (:class:`DrawingOptions`) fixe le format (« A4 » à « A0 »), le sens, le titre, le
    client et le numéro de devis ; ce qui n'est pas donné vient de la configuration de l'atelier
    (A3 paysage par défaut) ou de la page déjà faite. Relancer la fonction sur les mêmes objets
    refait l'échelle, la mise en page et le cartouche ; une page modifiée à la main (vue ajoutée
    ou retirée) est laissée telle quelle et une nouvelle page est créée. Une seule transaction
    « Plan de l'ouvrage ». ``ValueError`` traduite si TechDraw n'est pas disponible, s'il n'y a
    rien à dessiner ou pour un format inconnu."""
    return drawing.make_overall_drawing(doc, objects, options)


def make_part_drawings(
    doc: Document, objects: Sequence[DocumentObject], options: DrawingOptions | None = None
) -> list[DocumentObject]:
    """Crée ou refait un **plan de pièce** par pièce de bois distincte de ``objects`` (pièces,
    pièces usinées, ensembles ; tout le document si la liste est vide) et renvoie les pages.

    Chaque page dessine la pièce dans son repère (face, chant, bout, perspective), cote sa
    longueur, sa largeur et son épaisseur, et liste ses usinages (perçages, enlèvements, ajouts)
    avec leur position depuis le coin bas gauche de la face. Des pièces de même matériau, mêmes
    cotes et mêmes usinages partagent une page ; leur nombre est au cartouche. ``options`` fixe le
    format, le sens, le client et le numéro de devis (le titre est le nom de la pièce). Une page
    modifiée à la main est laissée telle quelle. Une seule transaction « Plan de pièce ».
    ``ValueError`` traduite si TechDraw n'est pas disponible ou s'il n'y a aucune pièce."""
    return drawing_parts.make_part_drawings(doc, objects, options)
