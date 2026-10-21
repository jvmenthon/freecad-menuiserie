# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des assemblages (J3d) : commandes, pièce usinée, assemblage.

Critères C1 à C7 de ``docs/specs/J3-assemblages.md``. Module importé par ``verifier_atelier.py``
(lancé par FreeCAD hors écran) : chaque vérification renvoie la liste de ses problèmes. Le cadre
de référence (§ 3) est construit par l'api ; les commandes sont lancées sur la sélection.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api, icon_path
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    emplacements,
    formulaire,
    nouveau_document,
    saisir,
    valider,
)

# Commande : (libellé, fabrique de l'api).
COMMANDES = {
    "Menuiserie_MortiseTenon": ("Tenon-mortaise", "make_mortise_tenon"),
    "Menuiserie_TongueGroove": ("Rainure-languette", "make_tongue_groove"),
    "Menuiserie_Rabbet": ("Feuillure", "make_rabbet"),
    "Menuiserie_Dowels": ("Tourillons", "make_dowels"),
}
TENON_MORTAISE = "Menuiserie_MortiseTenon"
CREATION = "Créer un assemblage tenon-mortaise"
MODULES = "freecad.menuiserie.gui.view_providers"
VP_PIECE_USINEE = f"{MODULES}.machined_part.ViewProviderMachinedPart"
VP_ASSEMBLAGE = f"{MODULES}.joint.ViewProviderJoint"
HETRE_RGB = (217, 180, 138)
BLANC_RGB = (255, 255, 255)
# Cadre de référence : repère -> (longueur, x, y, rotation autour de Z en degrés).
CADRE = {
    "M1": (600.0, 0.0, 0.0, 0.0),
    "M2": (600.0, 0.0, 340.0, 0.0),
    "T1": (280.0, 60.0, 60.0, 90.0),
    "T2": (280.0, 600.0, 60.0, 90.0),
}

Pieces = dict[str, Any]


def construire_le_cadre(doc: Any) -> Pieces:
    """Les quatre pièces brutes du cadre de référence, en chêne, recalculées."""
    pieces = {}
    for repere, (longueur, x, y, angle) in CADRE.items():
        piece = api.make_wood_part(longueur, 60.0, 22.0, "chene", mark=repere, doc=doc)
        piece.Label = repere
        rotation = App.Rotation(App.Vector(0, 0, 1), angle)
        piece.Placement = App.Placement(App.Vector(x, y, 0), rotation)
        pieces[repere] = piece
    doc.recompute()
    return pieces


@contextmanager
def cadre(nom: str) -> Iterator[tuple[Any, Pieces]]:
    """Document du cadre de référence, toujours refermé (panneau compris)."""
    doc = nouveau_document(nom)
    try:
        yield doc, construire_le_cadre(doc)
    finally:
        if Gui.Control.activeDialog():
            annuler()
        Gui.Selection.clearSelection()
        App.closeDocument(doc.Name)


def usinee_de(brute: Any) -> Any:
    """Pièce usinée de ``brute`` (exception si elle n'existe pas)."""
    usinee = api.machined_part_of(brute)
    if usinee is None:
        raise LookupError(f"pas de pièce usinée pour {brute.Label}")
    return usinee


def selectionner(*objets: Any) -> None:
    Gui.Selection.clearSelection()
    for obj in objets:
        Gui.Selection.addSelection(obj)


def assembler(doc: Any, *objets: Any, commande: str = TENON_MORTAISE, ok: bool = True) -> Any:
    """Lance ``commande`` sur ``objets`` (dans cet ordre) ; renvoie l'assemblage créé. Son
    panneau (J3e) est validé par « OK », sauf si ``ok`` est faux (panneau laissé ouvert)."""
    avant = set(doc.Objects)
    selectionner(*objets)
    Gui.Command.get(commande).run()
    if ok and Gui.Control.activeDialog():
        valider()
    crees = [obj for obj in doc.Objects if obj not in avant and hasattr(obj, "HostPart")]
    return crees[0] if crees else None


def classe_du_proxy(vobj: Any) -> str:
    proxy = vobj.Proxy
    return f"{type(proxy).__module__}.{type(proxy).__name__}"


def diffuse(vobj: Any) -> tuple[int, ...]:
    return tuple(round(c * 255) for c in vobj.ShapeAppearance[0].DiffuseColor[:3])


def apparence(vobj: Any) -> tuple[object, ...]:
    """Switch de texture (actif, directions, taille de l'image) et couleur diffuse."""
    racine = vobj.RootNode
    enfants = [racine.getChild(i) for i in range(racine.getNumChildren())]
    switchs = [e for e in enfants if e.getName().getString() == "MenuiserieTexture"]
    if len(switchs) != 1:
        return (f"{len(switchs)} switchs de texture",)
    groupe = switchs[0].getChild(0)
    plan = groupe.getChild(0)
    image = (
        groupe.getChild(1).image.get().getString().split(maxsplit=3)[:3]
        if groupe.getNumChildren() > 1
        else None
    )
    return (
        switchs[0].whichChild.getValue(),
        plan.directionS.getValue().getValue(),
        plan.directionT.getValue().getValue(),
        image,
        diffuse(vobj),
    )


# --- C1 : commandes ----------------------------------------------------------------------


def verifier_commandes_d_assemblage_presentes() -> list[str]:
    """C1 : libellés, icônes existantes, barre d'outils et menu Menuiserie."""
    problemes = []
    for nom, (libelle, _fabrique) in COMMANDES.items():
        commande = Gui.Command.get(nom)
        if commande is None:
            problemes.append(f"{nom} non enregistrée")
            continue
        infos = commande.getInfo()
        problemes += [
            *ecarts(f"{nom} libellé", infos["menuText"], libelle),
            *ecarts(f"{nom} icône", infos["pixmap"], icon_path(f"{nom}.svg")),
            *ecarts(f"{nom} icône affichée", commande.getAction()[0].icon().isNull(), False),
            *ecarts(
                f"{nom} emplacements",
                sorted(emplacements(nom)),
                [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")],
            ),
        ]
    return problemes


def actives() -> dict[str, bool]:
    return {nom: bool(Gui.Command.get(nom).isActive()) for nom in COMMANDES}


def attendues(actives_si_fabrique: bool) -> dict[str, bool]:
    """Activation attendue : seulement si la fabrique existe dans l'api (J3c pour trois)."""
    return {
        nom: actives_si_fabrique and hasattr(api, fabrique)
        for nom, (_libelle, fabrique) in COMMANDES.items()
    }


def verifier_activation_des_commandes_d_assemblage() -> list[str]:
    """C1 : actives seulement pour deux pièces distinctes et sans panneau ouvert."""
    with cadre("VerifActivationAssemblage") as (doc, pieces):
        problemes = ecarts("aucune sélection", actives(), attendues(False))
        selectionner(pieces["M1"])
        problemes += ecarts("une pièce", actives(), attendues(False))
        selectionner(pieces["M1"], pieces["T1"])
        problemes += ecarts("deux pièces", actives(), attendues(True))
        selectionner(pieces["M1"], pieces["T1"], pieces["T2"])
        problemes += ecarts("trois pièces", actives(), attendues(False))
        assembler(doc, pieces["M1"], pieces["T1"])
        usinee = usinee_de(pieces["M1"])
        selectionner(usinee, pieces["M1"])
        problemes += ecarts("pièce usinée et sa brute", actives(), attendues(False))
        selectionner(usinee, pieces["T2"])
        problemes += ecarts("pièce usinée et brute", actives(), attendues(True))
        usinee.ViewObject.Proxy.doubleClicked(usinee.ViewObject)
        selectionner(usinee, pieces["T2"])
        problemes += ecarts("panneau ouvert", actives(), attendues(False))
    return problemes


# --- C2 : création par la commande -------------------------------------------------------


def verifier_creation_d_un_assemblage() -> list[str]:
    """C2 : rôles devinés quel que soit l'ordre de sélection, une entrée d'annulation."""
    with cadre("VerifCreationAssemblage") as (doc, pieces):
        doc.UndoMode = 1
        avant = list(doc.UndoNames)
        joint = assembler(doc, pieces["T1"], pieces["M1"])
        if joint is None:
            return ["aucun assemblage créé"]
        problemes = [
            *ecarts("hôte", joint.HostPart.Label, "M1"),
            *ecarts("invitée", joint.GuestPart.Label, "T1"),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATION, *avant]),
            *ecarts("panneau ouvert", bool(Gui.Control.activeDialog()), False),
            *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
        ]
        autre = assembler(doc, pieces["M2"], pieces["T2"])
        problemes += ecarts(
            "rôles, autre ordre", (autre.HostPart.Label, autre.GuestPart.Label), ("M2", "T2")
        )
        doc.undo()
        doc.undo()
        problemes += ecarts("annulé", [o.Label for o in doc.Objects], list(CADRE))
    return problemes


# --- C3, C6 : affichage ------------------------------------------------------------------


def verifier_affichage_de_la_piece_usinee() -> list[str]:
    """C3 : icône, brute sous la pièce usinée, apparence de la brute qui suit matériau et fil."""
    with cadre("VerifAffichagePieceUsinee") as (doc, pieces):
        assembler(doc, pieces["M1"], pieces["T1"])
        brute = pieces["M1"]
        vobj = usinee_de(brute).ViewObject
        problemes = [
            *ecarts("ViewProvider", classe_du_proxy(vobj), VP_PIECE_USINEE),
            *ecarts("icône", vobj.Proxy.getIcon(), icon_path("Menuiserie_WoodPart.svg")),
            *ecarts("enfants", [o.Name for o in vobj.claimChildren()], [brute.Name]),
            *ecarts("brute masquée", brute.Visibility, False),
            *ecarts("texture affichée", apparence(vobj)[0], 0),
            *ecarts("apparence (chêne)", apparence(vobj), apparence(brute.ViewObject)),
        ]
        for propriete, valeur in (("MaterialId", "noyer"), ("GrainDirection", "Width")):
            setattr(brute, propriete, valeur)
            doc.recompute()
            problemes += ecarts(
                f"apparence ({valeur})", apparence(vobj), apparence(brute.ViewObject)
            )
    return problemes


def verifier_affichage_de_l_assemblage() -> list[str]:
    """C6 : icône du type et couleur hêtre."""
    with cadre("VerifAffichageAssemblage") as (doc, pieces):
        vobj = assembler(doc, pieces["M1"], pieces["T1"]).ViewObject
        return [
            *ecarts("ViewProvider", classe_du_proxy(vobj), VP_ASSEMBLAGE),
            *ecarts("icône", vobj.Proxy.getIcon(), icon_path("Menuiserie_MortiseTenon.svg")),
            *ecarts("couleur", diffuse(vobj), HETRE_RGB),
        ]


def verifier_reouverture_des_assemblages() -> list[str]:
    """ViewProviders et texture de la pièce usinée rétablis à la réouverture."""
    with tempfile.TemporaryDirectory() as dossier:
        chemin = str(Path(dossier) / "cadre.FCStd")
        with cadre("VerifReouvertureAssemblage") as (doc, pieces):
            assembler(doc, pieces["M1"], pieces["T1"])
            doc.saveAs(chemin)
        doc = App.openDocument(chemin)
        try:
            usinee = usinee_de(doc.getObjectsByLabel("M1")[0])
            joint = doc.getObjectsByLabel("Tenon-mortaise")[0]
            return [
                *ecarts("pièce usinée", classe_du_proxy(usinee.ViewObject), VP_PIECE_USINEE),
                *ecarts("assemblage", classe_du_proxy(joint.ViewObject), VP_ASSEMBLAGE),
                *ecarts("texture", apparence(usinee.ViewObject)[0], 0),
                *ecarts("diffuse", diffuse(usinee.ViewObject), BLANC_RGB),
                *ecarts("couleur de l'assemblage", diffuse(joint.ViewObject), HETRE_RGB),
            ]
        finally:
            App.closeDocument(doc.Name)


# --- C4, C5 : édition et déplacement -----------------------------------------------------


def verifier_double_clic_sur_la_piece_usinee() -> list[str]:
    """C4 : panneau de la brute, aperçu de la pièce usinée en direct, « Annuler » rétablit."""
    with cadre("VerifDoubleClicPieceUsinee") as (doc, pieces):
        assembler(doc, pieces["M1"], pieces["T1"])
        usinee = usinee_de(pieces["M1"])
        usinee.ViewObject.Proxy.doubleClicked(usinee.ViewObject)
        form = formulaire()
        if form is None:
            return ["panneau non ouvert"]
        problemes = ecarts("titre", form.windowTitle(), "Modifier « M1 »")
        saisir(form.lengthEdit, 700.0)
        problemes += ecarts("aperçu", round(usinee.Shape.BoundBox.XLength, 3), 700.0)
        annuler()
        return [
            *problemes,
            *ecarts("annulé", round(usinee.Shape.BoundBox.XLength, 3), 600.0),
            *ecarts("édition terminée", Gui.ActiveDocument.getInEdit(), None),
        ]


def verifier_deplacement_de_la_piece_usinee() -> list[str]:
    """C5 : déplacer la pièce usinée déplace la brute, en une entrée d'annulation."""
    with cadre("VerifDeplacementPieceUsinee") as (doc, pieces):
        assembler(doc, pieces["M1"], pieces["T1"])
        doc.UndoMode = 1
        usinee = usinee_de(pieces["M1"])
        avant = list(doc.UndoNames)
        doc.openTransaction("Déplacer")
        usinee.Placement = App.Placement(App.Vector(0, -50, 0), App.Rotation())
        doc.commitTransaction()
        doc.recompute()
        problemes = [
            *ecarts("brute déplacée", pieces["M1"].Placement.Base.y, -50.0),
            *ecarts("entrées", doc.UndoNames, ["Déplacer", *avant]),
        ]
        doc.undo()
        return problemes + ecarts("annulé", pieces["M1"].Placement.Base.y, 0.0)


# --- Suppression et C7 -------------------------------------------------------------------


def verifier_suppression_de_la_piece_usinee() -> list[str]:
    """Suppression refusée tant qu'il reste un assemblage ; ensuite la brute réapparaît."""
    with cadre("VerifSuppressionPieceUsinee") as (doc, pieces):
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        vobj = usinee_de(pieces["M1"]).ViewObject
        problemes = ecarts("refusée", vobj.Proxy.onDelete(vobj, []), False)
        doc.removeObject(joint.Name)
        problemes += ecarts("acceptée", vobj.Proxy.onDelete(vobj, []), True)
        return problemes + ecarts("brute visible", pieces["M1"].Visibility, True)


@contextmanager
def observateurs_comptes() -> Iterator[list[int]]:
    """Compte les observateurs (document, sélection) ajoutés moins ceux retirés."""
    solde = [0]
    originaux: list[tuple[Any, str, Callable[..., Any]]] = []
    for module, ajout, retrait in (
        (App, "addDocumentObserver", "removeDocumentObserver"),
        (Gui.Selection, "addObserver", "removeObserver"),
    ):
        for nom, pas in ((ajout, 1), (retrait, -1)):
            original = getattr(module, nom)
            originaux.append((module, nom, original))

            def compte(*args: Any, _original: Any = original, _pas: int = pas) -> Any:
                solde[0] += _pas
                return _original(*args)

            setattr(module, nom, compte)
    try:
        yield solde
    finally:
        for module, nom, original in originaux:
            setattr(module, nom, original)


def verifier_aucun_observateur_laisse() -> list[str]:
    """C7 : aucun observateur global après une commande ou le panneau de la brute."""
    with cadre("VerifObservateurs") as (doc, pieces), observateurs_comptes() as solde:
        assembler(doc, pieces["M1"], pieces["T1"])
        problemes = ecarts("après la commande", solde[0], 0)
        usinee = usinee_de(pieces["M1"])
        usinee.ViewObject.Proxy.doubleClicked(usinee.ViewObject)
        annuler()
        return problemes + ecarts("après le panneau", solde[0], 0)


VERIFICATIONS_ASSEMBLAGES: tuple[Callable[[], list[str]], ...] = (
    verifier_commandes_d_assemblage_presentes,
    verifier_activation_des_commandes_d_assemblage,
    verifier_creation_d_un_assemblage,
    verifier_affichage_de_la_piece_usinee,
    verifier_affichage_de_l_assemblage,
    verifier_reouverture_des_assemblages,
    verifier_double_clic_sur_la_piece_usinee,
    verifier_deplacement_de_la_piece_usinee,
    verifier_suppression_de_la_piece_usinee,
    verifier_aucun_observateur_laisse,
)
