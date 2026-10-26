# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la pièce en bois (PD-d, critères D1 à D6).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification
renvoie la liste de ses problèmes. Hors écran, aucun clic ni mouvement de souris n'est envoyé à la
vue ; l'atelier et la vue 3D sont réactivés avant ``Gui.activeView()`` ; le formulaire n'est jamais
gardé au-delà de son panneau.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from PySide import QtGui

from freecad.menuiserie.gui.task_panels.shaped_part_axes import NODE_NAME
from tests.gui.verifications_double_clic import ATELIER, vue_3d_active
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    ecarts,
    formulaire_nomme,
    saisir,
    valider,
)

COMMANDE = "Menuiserie_ShapedPart"
FORM = "ShapedPartTaskPanel"
TRANSACTION = "Convertir en pièce en bois"


def pied(doc: Any, longueur: float = 720.0) -> Any:
    """Corps PartDesign : esquisse 45 x 95, protrusion de ``longueur``."""
    corps = doc.addObject("PartDesign::Body", "Pied")
    esquisse = corps.newObject("Sketcher::SketchObject", "Esquisse")
    coins = [App.Vector(0, 0, 0), App.Vector(45, 0, 0), App.Vector(45, 95, 0), App.Vector(0, 95, 0)]
    for i, debut in enumerate(coins):
        esquisse.addGeometry(Part.LineSegment(debut, coins[(i + 1) % 4]), False)
    protrusion = corps.newObject("PartDesign::Pad", "Protrusion")
    protrusion.Profile = esquisse
    protrusion.Length = longueur
    doc.recompute()
    return corps


def convertir(doc: Any, *objets: Any) -> list[Any]:
    """Lance la commande sur ``objets`` ; renvoie les pièces en bois créées (panneau ouvert)."""
    Gui.activateWorkbench(ATELIER)
    avant = set(doc.Objects)
    Gui.Selection.clearSelection()
    for obj in objets:
        Gui.Selection.addSelection(obj)
    Gui.Command.get(COMMANDE).run()
    return [o for o in doc.Objects if o not in avant and o.TypeId == "Part::FeaturePython"]


def enfant(form: Any, nom: str) -> Any:
    """Widget ``nom`` construit par le panneau (absent du fichier ``.ui``, donc sans attribut)."""
    return form.findChild(QtGui.QWidget, nom)


def noeuds_nommes(nom: str) -> int:
    """Nombre de nœuds Coin nommés ``nom`` dans la vue 3D active (0 sans vue)."""
    vue = Gui.activeView()
    if vue is None or not hasattr(vue, "getSceneGraph"):
        return 0
    action = coin.SoSearchAction()
    action.setName(coin.SbName(nom))
    action.setInterest(coin.SoSearchAction.ALL)
    action.setSearchingAll(True)
    action.apply(vue.getSceneGraph())
    return int(action.getPaths().getLength())


def _conversion(doc: Any) -> list[str]:
    corps = pied(doc)
    doc.clearUndos()
    Gui.activateWorkbench(ATELIER)
    vue_3d_active(doc)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(corps)
    actif = Gui.Command.get(COMMANDE).isActive()
    pieces = convertir(doc, corps)
    problemes = [*ecarts("commande active", actif, True), *ecarts("une pièce", len(pieces), 1)]
    if len(pieces) != 1:
        return problemes
    piece = pieces[0]
    form = formulaire_nomme(FORM)
    problemes += [
        *ecarts("panneau ouvert", form is not None, True),
        *ecarts("source masquée", corps.Visibility, False),
        *ecarts("source liée", piece.Source.Name, corps.Name),
        *ecarts(
            "enfants de l'arbre", [o.Name for o in piece.ViewObject.Proxy.claimChildren()], ["Pied"]
        ),
        *ecarts("trièdre dans la vue", noeuds_nommes(NODE_NAME) >= 1, True),
    ]
    if form is not None:
        problemes += [
            *ecarts("L", round(float(form.lengthEdit.property("rawValue")), 2), 720.0),
            *ecarts(
                "encombrement en lecture seule", bool(form.lengthEdit.property("readOnly")), True
            ),
        ]
    del form
    nom = piece.Name
    annuler()
    return [
        *problemes,
        *ecarts("annulation : pièce retirée", doc.getObject(nom) is None, True),
        *ecarts("annulation : source réaffichée", corps.Visibility, True),
        *ecarts("trièdre retiré", noeuds_nommes(NODE_NAME), 0),
    ]


def verifier_conversion_et_annulation() -> list[str]:
    """D1, D2, D3 : conversion d'un corps, panneau, trièdre ; « Annuler » revient à l'avant."""
    return avec_document("VerifPieceEnBois", _conversion)


def _saisies_en_direct(doc: Any) -> list[str]:
    corps = pied(doc)
    piece = convertir(doc, corps)[0]
    form = formulaire_nomme(FORM)
    if form is None:
        return ["panneau non ouvert"]
    enfant(form, "turnWidthButton").click()  # quart de tour du repère : la pièce ne bouge pas
    centre = piece.Shape.BoundBox.Center
    problemes = ecarts(
        "encombrement relu",
        round(float(form.lengthEdit.property("rawValue")), 2),
        piece.Length.Value,
    )
    saisir(form.lengthAllowanceEdit, 12.0)
    problemes += ecarts("surcote en direct", piece.LengthAllowance.Value, 12.0)
    form.rotateZButton.click()
    problemes += ecarts(
        "rotation sur place", piece.Shape.BoundBox.Center.distanceToPoint(centre) < 1e-3, True
    )
    enfant(form, "automaticAxesButton").click()
    problemes += ecarts(
        "repère automatique : pièce en place",
        piece.Shape.BoundBox.Center.distanceToPoint(centre) < 1e-3,
        True,
    )
    del form
    annuler()
    return problemes


def verifier_saisies_en_direct() -> list[str]:
    """D2 : repère, surcotes et rotation s'affichent en direct dans la pièce."""
    return avec_document("VerifPieceEnBoisDirect", _saisies_en_direct)


def _double_clic(doc: Any) -> list[str]:
    corps = pied(doc)
    piece = convertir(doc, corps)[0]
    valider()
    vobj = piece.ViewObject
    ouvert = bool(vobj.Proxy.doubleClicked(vobj))
    problemes = ecarts("double-clic : panneau", ouvert and formulaire_nomme(FORM) is not None, True)
    if Gui.Control.activeDialog():
        annuler()
    return problemes


def verifier_double_clic_pieces_en_bois() -> list[str]:
    """D2 : double-clic sur la pièce en bois (arbre) ouvre son panneau."""
    return avec_document("VerifPieceEnBoisDoubleClic", _double_clic)


def _suppression(doc: Any) -> list[str]:
    corps = pied(doc)
    piece = convertir(doc, corps)[0]
    valider()
    piece.ViewObject.Proxy.onDelete(piece.ViewObject, None)
    problemes = ecarts("onDelete réaffiche la source", corps.Visibility, True)
    problemes += ecarts("canDelete(source)", piece.ViewObject.Proxy.canDelete(corps), True)
    problemes += ecarts("canDelete(autre)", piece.ViewObject.Proxy.canDelete(piece), False)
    return problemes


def verifier_suppression_reaffiche_la_source() -> list[str]:
    """D5, B8 : supprimer la pièce réaffiche la source."""
    return avec_document("VerifPieceEnBoisSuppression", _suppression)


def _refus(doc: Any) -> list[str]:
    ouverte = doc.addObject("Sketcher::SketchObject", "Ouverte")
    ouverte.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)), False)
    doc.recompute()
    boite = doc.addObject("Part::Box", "Boite")
    doc.recompute()
    avant = len(doc.Objects)
    pieces = convertir(doc, ouverte, boite)
    problemes = ecarts("une seule pièce (la boîte)", len(pieces), 1)
    boite_de_refus = [
        w for w in QtGui.QApplication.allWidgets() if w.objectName() == "MenuiserieRefusal"
    ]
    problemes += ecarts("boîte de refus affichée", bool(boite_de_refus), True)
    problemes += ecarts("seule la boîte est convertie", len(doc.Objects), avant + 1)
    if Gui.Control.activeDialog():
        annuler()
    return problemes


def verifier_refus_listes() -> list[str]:
    """D1 : une source refusée est listée, l'autre est convertie (une transaction)."""
    return avec_document("VerifPieceEnBoisRefus", _refus)


VERIFICATIONS_PIECE_EN_BOIS: tuple[Callable[[], list[str]], ...] = (
    verifier_conversion_et_annulation,
    verifier_saisies_en_direct,
    verifier_double_clic_pieces_en_bois,
    verifier_suppression_reaffiche_la_source,
    verifier_refus_listes,
)
