# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des plans cotés (issue #153, ADR 0053, lot P-b) : commandes,
panneau (format de la configuration, cartouche), page ouverte, export PDF de plusieurs
plans dans un seul fichier (maquette B du 24/11). Module importé par ``verifier_atelier.py``."""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.commandes_plan import COMMANDES_PLAN
from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_debit import noms_selectionnes
from tests.gui.verifications_ensemble import pieces_du_bureau, regrouper
from tests.gui.verifications_panneau import ecarts

PLAN = "Menuiserie_Drawing"
PDF = "Menuiserie_DrawingPdf"


def _pages(doc: Any) -> list[Any]:
    return [obj for obj in doc.Objects if obj.TypeId == "TechDraw::DrawPage"]


def _panneau(doc: Any) -> Any:
    """Lance la commande, vérifie qu'un panneau s'ouvre, le referme, puis ouvre un panneau du même
    contenu construit ici (l'objet Python du panneau de la commande n'est pas accessible)."""
    from freecad.menuiserie.features.drawing import document_scope
    from freecad.menuiserie.gui.task_panels.drawing import DrawingTaskPanel

    Gui.Command.get(PLAN).run()
    if not Gui.Control.activeDialog():
        return None
    Gui.Control.closeDialog()
    objets = [o for o in Gui.Selection.getSelection() if o.TypeId != "TechDraw::DrawPage"]
    panneau = DrawingTaskPanel(doc, objets or document_scope(doc))
    Gui.Control.showDialog(panneau)
    return panneau


def verifier_commandes_du_plan() -> list[str]:
    """Commandes enregistrées, libellés, état sans panneau."""
    problemes: list[str] = []
    for nom, libelle in COMMANDES_PLAN.items():
        commande = Gui.Command.get(nom)
        if commande is None:
            problemes.append(f"commande absente : {nom}")
            continue
        problemes += ecarts(f"libellé de {nom}", commande.getInfo()["menuText"], libelle)
    return problemes


def verifier_panneau_et_page() -> list[str]:
    """Le panneau prend la sélection, reprend le format de la configuration, et « OK » crée la
    page marquée avec le client saisi au cartouche ; la sélection n'est pas touchée."""
    parametres = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Menuiserie")
    parametres.SetString("DrawingPageFormat", "A2")
    try:
        with pieces_du_bureau("VerifPlanPanneau", assemble=True) as bureau:
            ensemble = regrouper(bureau)
            selectionner(ensemble)
            avant = noms_selectionnes()
            panneau = _panneau(bureau.doc)
            if panneau is None:
                return ["panneau « Plan de l'ouvrage » non ouvert"]
            problemes = ecarts("format prérempli", panneau.page_format.currentText(), "A2")
            problemes += ecarts("objets", [o.Name for o in panneau.objects], [ensemble.Name])
            panneau.client.setText("Mme Dupont")
            panneau.accept()
            pages = _pages(bureau.doc)
            problemes += ecarts("une page", len(pages), 1)
            problemes += ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False)
            if pages:
                textes = set(dict(pages[0].Template.EditableTexts).values())
                client = any("Mme Dupont" in texte for texte in textes)
                problemes += ecarts("client au cartouche", client, True)
                problemes += ecarts("feuille A2", "A2" in pages[0].Template.Template, True)
            problemes += ecarts("sélection intacte", noms_selectionnes(), avant)
            return problemes
    finally:
        parametres.RemString("DrawingPageFormat")


def verifier_annuler_ne_cree_rien() -> list[str]:
    with pieces_du_bureau("VerifPlanAnnuler") as bureau:
        Gui.Selection.clearSelection()
        avant = [obj.Name for obj in bureau.doc.Objects]
        panneau = _panneau(bureau.doc)
        if panneau is None:
            return ["panneau non ouvert sans sélection"]
        problemes = ecarts("tout le document", len(panneau.objects), 4)
        panneau.reject()
        return problemes + ecarts("rien créé", [obj.Name for obj in bureau.doc.Objects], avant)


def _pages_du_pdf(octets: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", octets))


def _export(bureau: Any) -> list[str]:
    """La page sélectionnée et « Ouvrir le PDF » sont précochées ; une pièce sans plan cochée
    reçoit son plan ; un fichier déjà là fait demander (annuler, puis « plans 2 ») ; les deux
    pages partent dans un seul PDF, ouvert ensuite."""
    from freecad.menuiserie import api
    from freecad.menuiserie.features.cutlist_export import NUMBERED
    from freecad.menuiserie.gui.task_panels import drawing_export
    from freecad.menuiserie.gui.task_panels.drawing_export import ExportPdfTaskPanel

    page = api.make_overall_drawing(bureau.doc, [regrouper(bureau)])
    selectionner(page)
    Gui.Command.get(PDF).run()
    ouvert = bool(Gui.Control.activeDialog())
    Gui.Control.closeDialog()
    panneau = ExportPdfTaskPanel(bureau.doc, [page])
    Gui.Control.showDialog(panneau)
    coches = [obj.Name for obj in panneau.chosen()]
    ouvrir_precoche = panneau.open_pdf.isChecked()
    ouverts: list[str] = []
    vrai_open_url = drawing_export.open_url

    def ouvrir(url: Any) -> bool:  # pas de lecteur de PDF en CI
        ouverts.append(url.toLocalFile())
        return True

    reponses = [None, NUMBERED]  # annuler, puis écrire « plans 2.pdf »
    drawing_export.open_url = ouvrir
    panneau.choose_existing = lambda _path, _other: reponses.pop(0)
    piece = next(iter(bureau.parts.values()))
    with tempfile.TemporaryDirectory() as dossier:
        deja_la = Path(dossier) / "plans.pdf"
        deja_la.write_bytes(b"ancien")
        cible = Path(dossier) / "plans 2.pdf"
        panneau.path.setText(str(deja_la))
        panneau.check(piece.Name)
        avant = len(_pages(bureau.doc))
        panneau.path.setText(str(Path(dossier) / "absent" / "plans.pdf"))
        refuse = not panneau.accept()
        sans_creation = len(_pages(bureau.doc)) == avant
        panneau.path.setText(str(deja_la))
        try:
            annule = not panneau.accept()
            sans_creation &= len(_pages(bureau.doc)) == avant
            accepte = panneau.accept()
        finally:
            drawing_export.open_url = vrai_open_url
        garde = deja_la.read_bytes() == b"ancien"
        octets = cible.read_bytes() if cible.exists() else b""
        restes = [p.name for p in Path(dossier).iterdir() if p.suffix == ".tmp"]
    message = Gui.getMainWindow().statusBar().currentMessage()
    return [
        *ecarts("panneau ouvert", ouvert, True),
        *ecarts("page précochée", page.Name in coches, True),
        *ecarts("« Ouvrir le PDF » précochée", ouvrir_precoche, True),
        *ecarts("chemin invalide refusé", refuse, True),
        *ecarts("fichier existant : annuler garde le panneau", annule, True),
        *ecarts("refus et annulation : aucun plan créé", sans_creation, True),
        *ecarts("fichier existant non écrasé", garde, True),
        *ecarts("export accepté", accepte, True),
        *ecarts("plan de pièce créé", len(_pages(bureau.doc)), avant + 1),
        *ecarts("le PDF commence par %PDF", octets[:4], b"%PDF"),
        *ecarts("PDF ouvert une fois", [Path(p).name for p in ouverts], ["plans 2.pdf"]),
        *ecarts("deux pages dans un seul PDF", _pages_du_pdf(octets), 2),
        *ecarts("aucun temporaire", restes, []),
        *ecarts("confirmation", "plans 2.pdf" in message, True),
    ]


def verifier_export_pdf() -> list[str]:
    with pieces_du_bureau("VerifPlanPdf", assemble=True) as bureau:
        Gui.Selection.clearSelection()
        actif = Gui.Command.get(PDF).isActive()
        return [*ecarts("export actif sans sélection", actif, True), *_export(bureau)]


VERIFICATIONS_PLAN: tuple[Callable[[], list[str]], ...] = (
    verifier_commandes_du_plan,
    verifier_panneau_et_page,
    verifier_annuler_ne_cree_rien,
    verifier_export_pdf,
)
