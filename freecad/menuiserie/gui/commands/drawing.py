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
from freecad.menuiserie.features.drawing import document_scope, is_page, techdraw_available
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui import drawing_pdf
from freecad.menuiserie.gui.commands.base import TransactionCommand, report_refusal
from freecad.menuiserie.gui.commands.cutlist import selected_objects, show_status
from freecad.menuiserie.gui.drawing_hlr import HlrWait

DRAWING: Final = "Menuiserie_Drawing"
DRAWING_PDF: Final = "Menuiserie_DrawingPdf"
PART_DRAWINGS: Final = "Menuiserie_PartDrawings"
EXPLODED: Final = "Menuiserie_ExplodedDrawing"
COMMANDS: Final = (DRAWING, PART_DRAWINGS, EXPLODED, DRAWING_PDF)

_PARTS_DONE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} plan(s) de pièce faits ; chaque page s'exporte en PDF."
)


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
        return [obj for obj in selected_objects() or [] if not is_page(obj)]


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
        "ou celles des ensembles sélectionnés ; sans sélection, ouvre la liste des pièces "
        "par ensemble pour cocher celles à dessiner.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Plan de pièce")

    def Activated(self) -> None:
        """Pages faites, la première montrée ; refus affiché."""
        doc = App.ActiveDocument
        objects = self.selection()
        if not objects:  # rien de sélectionné : choix des pièces dans un panneau (maquette A)
            from freecad.menuiserie.gui.task_panels.part_drawings import PartDrawingsTaskPanel

            Gui.Control.showDialog(PartDrawingsTaskPanel(doc))
            return
        try:
            pages = api.make_part_drawings(doc, objects, api.DrawingOptions(settle=HlrWait()))
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


class DrawingPdfCommand(_PlanCommand):
    """Exporte des plans en un seul PDF : panneau du choix des plans (maquette B)."""

    NAME = DRAWING_PDF
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_DrawingPdf", "Exporter les plans (PDF)…")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_DrawingPdf",
        "Choisit les plans à mettre dans un seul PDF prêt à imprimer, une page par plan : plans "
        "existants, ou pièces dont le plan est alors créé. La sélection est déjà cochée.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Exporter les plans")

    def Activated(self) -> None:
        """Panneau ouvert, la sélection (pages comprises) précochée."""
        from freecad.menuiserie.gui.task_panels.drawing_export import ExportPdfTaskPanel

        doc = App.ActiveDocument
        try:
            panel = ExportPdfTaskPanel(doc, selected_objects() or [])
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        Gui.Control.showDialog(panel)


def register() -> None:
    """Enregistre les commandes des plans auprès de FreeCAD."""
    Gui.addCommand(DRAWING, DrawingCommand())
    Gui.addCommand(PART_DRAWINGS, PartDrawingsCommand())
    Gui.addCommand(EXPLODED, ExplodedDrawingCommand())
    Gui.addCommand(DRAWING_PDF, DrawingPdfCommand())
