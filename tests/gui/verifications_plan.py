# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des plans cotés (issue #153, ADR 0053, lot P-b) : commandes,
panneau (format de la configuration, cartouche), page ouverte, export PDF par TechDraw (boîte
d'enregistrement remplacée par un double). Module importé par ``verifier_atelier.py``."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.commandes_plan import COMMANDES_PLAN
from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_debit import boite_d_enregistrement, noms_selectionnes
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
                problemes += ecarts("client au cartouche", "Mme Dupont" in textes, True)
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


def _export(bureau: Any) -> list[str]:
    from freecad.menuiserie import api

    page = api.make_overall_drawing(bureau.doc, [regrouper(bureau)])
    with tempfile.TemporaryDirectory() as dossier:
        cible = Path(dossier) / "plan.pdf"
        selectionner(page)
        actif = Gui.Command.get(PDF).isActive()
        with boite_d_enregistrement(str(cible)) as appels:
            Gui.Command.get(PDF).run()
        octets = cible.read_bytes() if cible.exists() else b""
        restes = [p.name for p in Path(dossier).iterdir() if p.suffix == ".tmp"]
        message = Gui.getMainWindow().statusBar().currentMessage()
        return [
            *ecarts("export actif sur une page", actif, True),
            *ecarts("une boîte d'enregistrement", len(appels), 1),
            *ecarts("filtre", "*.pdf" in appels[0][2] if appels else None, True),
            *ecarts("le PDF commence par %PDF", octets[:4], b"%PDF"),
            *ecarts("aucun temporaire", restes, []),
            *ecarts("confirmation", str(cible) in message, True),
        ]


def verifier_export_pdf() -> list[str]:
    with pieces_du_bureau("VerifPlanPdf", assemble=True) as bureau:
        Gui.Selection.clearSelection()
        inactif = Gui.Command.get(PDF).isActive()
        return [*ecarts("export grisé sans page", inactif, False), *_export(bureau)]


VERIFICATIONS_PLAN: tuple[Callable[[], list[str]], ...] = (
    verifier_commandes_du_plan,
    verifier_panneau_et_page,
    verifier_annuler_ne_cree_rien,
    verifier_export_pdf,
)
