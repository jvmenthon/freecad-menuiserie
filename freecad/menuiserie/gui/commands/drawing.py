# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes des plans cotés (issue #153, ADR 0053, lot P-b).

« Plan de l'ouvrage » ouvre le panneau du plan de la sélection (ensembles, pièces, Std Part) ou,
sans sélection, de tous les ensembles et pièces libres du document. « Exporter le plan (PDF)… »
écrit la page TechDraw sélectionnée (de l'atelier ou non) dans un fichier PDF. Les deux sont
grisées sans TechDraw ou pendant un panneau ouvert ; un refus est affiché comme les autres.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing import document_scope, techdraw_available
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui import drawing_pdf
from freecad.menuiserie.gui.commands.base import TransactionCommand, report_refusal
from freecad.menuiserie.gui.commands.cutlist import selected_objects, show_status

DRAWING: Final = "Menuiserie_Drawing"
DRAWING_PDF: Final = "Menuiserie_DrawingPdf"
PART_DRAWINGS: Final = "Menuiserie_PartDrawings"
EXPLODED: Final = "Menuiserie_ExplodedDrawing"
COMMANDS: Final = (DRAWING, PART_DRAWINGS, EXPLODED, DRAWING_PDF)
PAGE_TYPE: Final = "TechDraw::DrawPage"

_PARTS_DONE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} plan(s) de pièce faits ; chaque page s'exporte en PDF."
)


def selected_page() -> DocumentObject | None:
    """Page TechDraw sélectionnée (la seule de la sélection), ``None`` sinon."""
    pages = [obj for obj in Gui.Selection.getSelection() if obj.TypeId == PAGE_TYPE]
    return pages[0] if len(pages) == 1 else None


class _PlanCommand(TransactionCommand):
    """Base des commandes qui font des pages : active s'il y a un document, TechDraw et aucun
    panneau ouvert ; portée = sélection sans les pages."""

    def IsActive(self) -> bool:
        """Active s'il y a un document, TechDraw et aucun panneau ouvert."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and techdraw_available()
        )

    @staticmethod
    def selection() -> list[DocumentObject]:
        """Objets sélectionnés, pages TechDraw exclues."""
        return [obj for obj in selected_objects() or [] if obj.TypeId != PAGE_TYPE]


class DrawingCommand(_PlanCommand):
    """Ouvre le panneau « Plan de l'ouvrage »."""

    NAME = DRAWING
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Drawing", "Plan de l'ouvrage")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Drawing",
        "Crée ou refait une page TechDraw cotée : face, coupes verticale et horizontale au "
        "milieu du meuble et perspective à l'échelle, cotes hors tout qui suivent le modèle, "
        "cartouche rempli. Dessine les objets sélectionnés, sinon tous les ensembles et pièces "
        "du document.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Plan de l'ouvrage")

    def Activated(self) -> None:
        """Portée lue (sélection, sinon tout le document), puis panneau ouvert."""
        from freecad.menuiserie.gui.task_panels.drawing import DrawingTaskPanel

        doc = App.ActiveDocument
        objects = self.selection()
        try:
            panel = DrawingTaskPanel(doc, objects or document_scope(doc))
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        Gui.Control.showDialog(panel)


class PartDrawingsCommand(_PlanCommand):
    """Crée ou refait les plans de pièce de la sélection ou du document."""

    NAME = PART_DRAWINGS
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_PartDrawings", "Plans de pièce")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_PartDrawings",
        "Crée ou refait une page TechDraw par pièce distincte : face, chant, bout et "
        "perspective cotés, tableau des usinages (perçages, logements, tenons) et quantité au "
        "cartouche. Format de la configuration de l'atelier. Dessine les pièces sélectionnées "
        "ou celles des ensembles sélectionnés, sinon toutes celles du document.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Plan de pièce")

    def Activated(self) -> None:
        """Pages faites, la première montrée ; refus affiché."""
        doc = App.ActiveDocument
        objects = self.selection()
        try:
            pages = api.make_part_drawings(doc, objects)
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        if pages:
            drawing_pdf.show_page(pages[0])
        show_status(translated(_PARTS_DONE, {"count": str(len(pages))}))


class ExplodedDrawingCommand(_PlanCommand):
    """Crée ou refait la vue éclatée de la sélection ou du document."""

    NAME = EXPLODED
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_ExplodedDrawing", "Vue éclatée")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_ExplodedDrawing",
        "Crée ou refait une page TechDraw avec la perspective de l'ouvrage éclaté : chaque pièce "
        "s'écarte du centre. Photographie du modèle : relancer la commande après une "
        "modification. Dessine les objets sélectionnés, sinon tous les ensembles et pièces.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Vue éclatée")

    def Activated(self) -> None:
        """Page faite et montrée ; refus affiché."""
        doc = App.ActiveDocument
        objects = self.selection()
        try:
            page = api.make_exploded_drawing(doc, objects or document_scope(doc))
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        drawing_pdf.show_page(page)


class DrawingPdfCommand(TransactionCommand):
    """Exporte la page TechDraw sélectionnée en PDF."""

    NAME = DRAWING_PDF
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_DrawingPdf", "Exporter le plan (PDF)…")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_DrawingPdf",
        "Enregistre la page de plan sélectionnée dans un fichier PDF prêt à imprimer, au format "
        "de sa feuille. Le document n'est pas modifié.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Exporter le plan")
    PREREQUISITE = QT_TRANSLATE_NOOP(
        "Menuiserie", "une page de plan sélectionnée (dans l'arbre ou le panneau « Structure »)"
    )

    def IsActive(self) -> bool:
        """Active si une seule page TechDraw est sélectionnée et qu'aucun panneau n'est ouvert."""
        return not Gui.Control.activeDialog() and selected_page() is not None

    def Activated(self) -> None:
        """Fichier demandé puis PDF écrit."""
        page = selected_page()
        if page is not None:
            drawing_pdf.export_with_dialog(page)


def register() -> None:
    """Enregistre les commandes des plans auprès de FreeCAD."""
    Gui.addCommand(DRAWING, DrawingCommand())
    Gui.addCommand(PART_DRAWINGS, PartDrawingsCommand())
    Gui.addCommand(EXPLODED, ExplodedDrawingCommand())
    Gui.addCommand(DRAWING_PDF, DrawingPdfCommand())
