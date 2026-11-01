# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit de la façade publique (J2).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import FreeCAD as App

from freecad.menuiserie.core.cutlist import INTERNATIONAL_CSV, CsvDialect, CutList
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import (
    cutlist_collect,
    cutlist_export,
    cutlist_marks,
    cutlist_object,
    cutlist_thumbnail,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture_bindings import notice_messages, report
from freecad.menuiserie.features.i18n import translated

# --- Liste de débit (J2) ------------------------------------------------------------------


def cut_list_of(doc: Document, objects: Sequence[DocumentObject] | None = None) -> CutList:
    """Liste de débit (:class:`~freecad.menuiserie.core.cutlist.CutList`) du document ``doc`` ou,
    si ``objects`` est donné et non vide, de ces objets : pièces de bois ou usinées, ensembles,
    Std Part, groupes et liens (une pièce vue par un lien compte une fois de plus, fois
    ``ElementCount``). Longueurs de débit tenons compris, tourillons en fournitures. Lecture
    seule : le document n'est pas modifié. ``ValueError`` traduite pour un objet d'un autre
    document."""
    return cutlist_collect.cut_list_of(doc, objects)


def make_cut_list(doc: Document, objects: Sequence[DocumentObject] | None = None) -> DocumentObject:
    """Crée ou met à jour la liste de débit **vivante** de ``doc`` et renvoie sa feuille de
    calcul « Liste de débit » (nom interne ``MenuiserieCutList``, retrouvée par sa marque même
    renommée). Deux objets : la feuille, ``Spreadsheet::Sheet`` ordinaire, et l'objet
    ``Menuiserie::CutList`` qui la réécrit à chaque recalcul du document (cote modifiée, pièce
    ajoutée ou supprimée) ; relancer cette fonction les retrouve, change la portée (``objects``,
    sinon tout le document) et réécrit tout de suite. Colonnes A à O réécrites, celles de P et
    au-delà conservées ; avertissements en bas de la feuille et dans la vue rapport. Une seule
    transaction « Liste de débit » (Annuler restaure la feuille). Supprimer l'objet ou la feuille
    arrête la mise à jour ; un nouvel appel la rétablit."""
    sheet, messages = cutlist_object.ensure_cut_list(doc, objects)
    _shown_cut_list(doc)
    report(messages)
    return sheet


def _shown_cut_list(doc: Document) -> None:
    """Pose le ViewProvider de la liste vivante (si l'interface est chargée et qu'il manque)."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.cutlist import ViewProviderCutList

        cut_list = cutlist_object.find_cut_list(doc)
        if cut_list is not None and not isinstance(cut_list.ViewObject.Proxy, ViewProviderCutList):
            ViewProviderCutList(cut_list.ViewObject)


def number_marks(
    doc: Document,
    objects: Sequence[DocumentObject] | None = None,
    prefix: str = "M",
) -> dict[str, str]:
    """Numérote les pièces sans repère de ``doc`` (ou de ``objects``) : un repère ``<prefix><n>``
    par groupe de pièces identiques (mêmes cotes, matériau, fil, surcotes et ajouts), au premier
    numéro libre, ensemble puis cotes décroissantes. Les pièces qui ont déjà un repère ne
    changent pas ; le libellé suit le repère. Renvoie le repère écrit pour chaque pièce (nom
    interne → repère). Une seule transaction « Numéroter les repères », document recalculé (la
    liste de débit vivante suit). ``ValueError`` traduite pour un préfixe vide ou un objet d'un
    autre document."""
    return cutlist_marks.number_marks(doc, objects, prefix)


def export_cut_list_csv(
    doc: Document,
    path: str | os.PathLike[str],
    objects: Sequence[DocumentObject] | None = None,
    dialect: CsvDialect = INTERNATIONAL_CSV,
) -> Path:
    """Exporte la liste de débit de ``doc`` (ou de ``objects``) en CSV dans ``path`` et renvoie le
    chemin. Dialecte par défaut ``INTERNATIONAL_CSV`` (``,``, point décimal, UTF-8 avec BOM, CRLF) ;
    ``FRENCH_CSV`` (``;``, virgule décimale) est disponible. ``ValueError`` traduite, avant
    toute écriture, si le chemin n'a pas l'extension ``.csv``, désigne un dossier, est dans un
    dossier absent ou non accessible en écriture. Écriture atomique ; le document n'est pas
    modifié."""
    target = cutlist_export.validated_path(path)
    cut_list = cut_list_of(doc, objects)
    written = cutlist_export.export_csv(cut_list, target, dialect)
    report(notice_messages(cut_list.warnings))
    return written


_PDF_NEEDS_GUI = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export PDF impossible : il demande l'interface de FreeCAD."
)


def export_cut_list_pdf(
    doc: Document,
    path: str | os.PathLike[str],
    objects: Sequence[DocumentObject] | None = None,
) -> Path:
    """Exporte la liste de débit de ``doc`` (ou de ``objects``) en PDF (A4 paysage, marges 10 mm)
    dans ``path`` et renvoie le chemin. **Demande l'interface de FreeCAD** (Qt dessine les
    polices) : sans elle, ``ValueError`` traduite. Mêmes refus que le CSV avec l'extension
    ``.pdf`` imposée, avant toute écriture ; écriture atomique ; le document n'est pas
    modifié."""
    target = cutlist_export.validated_path(path, cutlist_export.PDF_SUFFIX)
    if App.GuiUp:
        from freecad.menuiserie.gui import cutlist_pdf

        cut_list, html = _cut_list_and_html(doc, objects)
        written = cutlist_pdf.write_pdf(html, target)
        report(notice_messages(cut_list.warnings))
        return written
    raise ValueError(translated(_PDF_NEEDS_GUI))


def _cut_list_and_html(
    doc: Document, objects: Sequence[DocumentObject] | None
) -> tuple[CutList, str]:
    """Liste de débit et son HTML avec miniatures (celui du PDF et de l'aperçu)."""
    cut_list = cut_list_of(doc, objects)
    html = cutlist_export.pdf_html(
        cut_list,
        doc.Label,
        len(objects) if objects else None,
        thumbnails=cutlist_thumbnail.thumbnails_of(doc, cut_list),
    )
    return cut_list, html


def cut_list_html(doc: Document, objects: Sequence[DocumentObject] | None = None) -> str:
    """Document HTML autonome de la liste de débit de ``doc`` (ou de ``objects``), tel que
    l'aperçu l'affiche et que le PDF l'imprime : tableau, totaux, fournitures, avertissements
    et, en tête de chaque ligne, la miniature isométrique de la forme **usinée** de la première
    pièce du groupe (boîte de débit si elle n'est pas utilisable). Images incluses en ``data:``
    (SVG), aucune ressource externe. Lecture seule, sans interface ; ``ValueError`` traduite
    pour un objet d'un autre document."""
    return _cut_list_and_html(doc, objects)[1]
