# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du gabarit « Caisson » (critère K6 de ``docs/specs/J4-ensembles.md``).

Commande « Caisson » dans la barre d'outils et le menu, panneau de paramètres avec aperçu
(un seul caisson à la fois), « OK » = une entrée « Créer un caisson », « Annuler » ne laisse
aucun objet, paramètres refusés affichés sans rien créer. Module importé par
``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    choisir,
    ecarts,
    emplacements,
    saisir,
    valider,
)
from tests.gui.verifications_panneau_assemblage import widget

CAISSON = "Menuiserie_Carcass"
FORM = "CarcassTaskPanel"


def formulaire() -> Any:
    """Formulaire du panneau du caisson ouvert (``None`` s'il n'y en a pas)."""
    trouves = [w for w in QtGui.QApplication.allWidgets() if w.objectName() == FORM]
    return trouves[0] if trouves else None


def compte(doc: Any) -> dict[str, int]:
    """Nombre d'objets du document par préfixe de nom interne."""
    prefixes = ("WoodPart", "MachinedPart", "Dowels", "Rabbet", "Furniture")
    return {p: sum(o.Name.startswith(p) for o in doc.Objects) for p in prefixes}


REFERENCE = {"WoodPart": 6, "MachinedPart": 5, "Dowels": 4, "Rabbet": 4, "Furniture": 1}


def verifier_commande_du_caisson() -> list[str]:
    """K6 : commande avec libellé, infobulle et icône existante, barre d'outils et menu,
    active avec un document."""
    from freecad.menuiserie import icon_path

    commande = Gui.Command.get(CAISSON)
    if commande is None:
        return ["commande Menuiserie_Carcass absente"]
    infos = commande.getInfo()
    problemes = [
        *ecarts("libellé", infos["menuText"], "Caisson"),
        *ecarts("infobulle renseignée", bool(infos["toolTip"].strip()), True),
        *ecarts("icône", infos["pixmap"], icon_path("Menuiserie_Carcass.svg")),
        *ecarts("icône affichée", [a.icon().isNull() for a in commande.getAction()], [False]),
        *ecarts(
            "emplacements",
            sorted(emplacements(CAISSON)),
            [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")],
        ),
    ]

    def actif(doc: Any) -> list[str]:
        del doc
        return ecarts("active avec un document", commande.isActive(), True)

    return problemes + avec_document("VerifCommandeCaisson", actif)


def _apercu_puis_ok(doc: Any) -> list[str]:
    Gui.Command.get(CAISSON).run()
    form = formulaire()
    if form is None:
        return ["panneau du caisson non ouvert"]
    furniture = doc.getObject("Furniture")
    problemes = [
        *ecarts("titre", form.windowTitle(), "Nouveau caisson"),
        *ecarts("aperçu", compte(doc), REFERENCE),
        *ecarts("cotes", furniture.Width.Value if furniture else None, 600.0),
        *ecarts("erreur masquée", widget(form, "errorLabel").isHidden(), True),
    ]
    saisir(widget(form, "width"), 800.0)
    widget(form, "shelf_count").setValue(2)
    choisir(widget(form, "joinery"), "None")
    attendu = {**REFERENCE, "WoodPart": 7, "Dowels": 0}
    furniture = doc.getObject("Furniture")
    problemes += [
        *ecarts("un seul caisson", compte(doc), attendu),
        *ecarts("largeur", furniture.Width.Value if furniture else None, 800.0),
    ]
    valider()
    problemes += [
        *ecarts("panneau fermé", formulaire() is None, True),
        *ecarts("entrées", doc.UndoNames, ["Créer un caisson"]),
        *ecarts("gabarit", doc.getObject("Furniture").Template, "Carcass"),
        *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
    ]
    doc.undo()
    return problemes + ecarts("annulé", doc.Objects, [])


def verifier_apercu_et_validation() -> list[str]:
    """K6 : aperçu du caisson de référence, saisies qui le remplacent, « OK » = une entrée."""
    return avec_document("VerifCaissonValide", _apercu_puis_ok)


def _annule(doc: Any) -> list[str]:
    Gui.Command.get(CAISSON).run()
    form = formulaire()
    if form is None:
        return ["panneau du caisson non ouvert"]
    saisir(widget(form, "depth"), 500.0)
    problemes = ecarts("aperçu", compte(doc), REFERENCE)
    annuler()
    return [
        *problemes,
        *ecarts("aucun objet", doc.Objects, []),
        *ecarts("aucune entrée", doc.UndoNames, []),
        *ecarts("panneau fermé", formulaire() is None, True),
    ]


def verifier_annulation() -> list[str]:
    """K6 : « Annuler » ne laisse aucun objet ni entrée d'annulation."""
    return avec_document("VerifCaissonAnnule", _annule)


def _refus(doc: Any) -> list[str]:
    Gui.Command.get(CAISSON).run()
    form = formulaire()
    if form is None:
        return ["panneau du caisson non ouvert"]
    saisir(widget(form, "thickness"), 300.0)
    erreur = widget(form, "errorLabel")
    problemes = [
        *ecarts("refus affiché", erreur.isHidden(), False),
        *ecarts("champ cité", "épaisseur des panneaux" in erreur.text(), True),
        *ecarts("rien créé", doc.Objects, []),
    ]
    valider()  # sans effet : le panneau reste ouvert
    problemes += ecarts("panneau resté ouvert", formulaire() is not None, True)
    saisir(widget(form, "thickness"), 19.0)
    problemes += [
        *ecarts("refus effacé", erreur.isHidden(), True),
        *ecarts("caisson recréé", compte(doc), REFERENCE),
    ]
    valider()
    return problemes + ecarts("entrées", doc.UndoNames, ["Créer un caisson"])


def verifier_parametres_refuses() -> list[str]:
    """K6 : paramètres refusés affichés sous les champs, aucun objet, « OK » sans effet."""
    return avec_document("VerifCaissonRefus", _refus)


def verifier_document_ferme_panneau_ouvert() -> list[str]:
    """Document fermé, panneau ouvert : le panneau se ferme, la transaction est soldée."""
    doc = App.newDocument("VerifCaissonFerme")
    doc.UndoMode = 1
    Gui.Command.get(CAISSON).run()
    App.closeDocument(doc.Name)
    QtGui.QApplication.processEvents()
    return [
        *ecarts("panneau fermé", formulaire() is None, True),
        *ecarts("aucun panneau actif", bool(Gui.Control.activeDialog()), False),
    ]


VERIFICATIONS_CAISSON: tuple[Callable[[], list[str]], ...] = (
    verifier_commande_du_caisson,
    verifier_apercu_et_validation,
    verifier_annulation,
    verifier_parametres_refuses,
    verifier_document_ferme_panneau_ouvert,
)
