# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des assemblages (J3d) : commandes, pièce usinée, assemblage.

Critères C1 à C7 de ``docs/specs/J3-assemblages.md`` (et B4, D6, A5 de ``J4-ensembles.md``
pour les commandes du mi-bois, de la queue d'aronde et de l'onglet). Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification renvoie la liste de
ses problèmes. Le cadre de référence (§ 3) est construit par l'api ; les commandes sont lancées
sur la sélection.
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
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.commands.base import would_run
from tests.commandes_assemblages import COMMANDES_ASSEMBLAGE
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    emplacements,
    emplacements_attendus,
    formulaire,
    nouveau_document,
    saisir,
    valider,
)

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
    for nom, (libelle, _fabrique) in COMMANDES_ASSEMBLAGE.items():
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
                emplacements_attendus(nom),
            ),
        ]
    return problemes


def actives() -> dict[str, bool]:
    return {nom: would_run(nom) for nom in COMMANDES_ASSEMBLAGE}


PIEDS = ("Menuiserie_Foot", "Menuiserie_ShelfPins")  # commandes sur une seule pièce


def attendues(actives_si_fabrique: bool, une_piece: bool = False) -> dict[str, bool]:
    """Activation attendue : seulement si la fabrique existe dans l'api (J3c pour trois) ;
    ``une_piece`` : la sélection est une seule pièce, que seuls les pieds acceptent."""
    return {
        nom: (une_piece if nom in PIEDS else actives_si_fabrique) and hasattr(api, fabrique)
        for nom, (_libelle, fabrique) in COMMANDES_ASSEMBLAGE.items()
    }


def verifier_selection_expliquee(doc: Any) -> list[str]:
    """Issue #221 : sans sélection, chaque commande reste active ; lancée, elle dit quoi
    sélectionner dans la boîte de l'atelier, sans objet créé ni entrée d'annulation."""
    from PySide import QtGui

    from freecad.menuiserie.gui.commands.base import REFUSAL_BOX_NAME

    Gui.Selection.clearSelection()
    doc.UndoMode = 1
    avant, entrees = [o.Name for o in doc.Objects], list(doc.UndoNames)
    restees_actives = {nom: bool(Gui.Command.get(nom).isActive()) for nom in COMMANDES_ASSEMBLAGE}
    problemes = ecarts(
        "actives sans sélection", restees_actives, dict.fromkeys(restees_actives, True)
    )
    for nom, attendu in (
        ("Menuiserie_MortiseTenon", "deux pièces"),
        ("Menuiserie_Foot", "une seule"),
    ):
        Gui.Command.get(nom).run()
        boite = Gui.getMainWindow().findChild(QtGui.QMessageBox, REFUSAL_BOX_NAME)
        message = boite.text() if boite is not None and boite.isVisible() else ""
        if boite is not None:
            boite.hide()
        problemes += ecarts(f"{nom} : sélection expliquée", attendu in message, True)
    return [
        *problemes,
        *ecarts("objets", [o.Name for o in doc.Objects], avant),
        *ecarts("panneau ouvert", bool(Gui.Control.activeDialog()), False),
        *ecarts("entrées d'annulation", list(doc.UndoNames), entrees),
    ]


def verifier_activation_des_commandes_d_assemblage() -> list[str]:
    """C1 : n'agissent que pour deux pièces distinctes (les pieds : une pièce) et sans panneau
    ouvert ; sans la bonne sélection elles restent actives et disent quoi sélectionner (issue
    #221)."""
    with cadre("VerifActivationAssemblage") as (doc, pieces):
        problemes = ecarts("aucune sélection", actives(), attendues(False))
        problemes += verifier_selection_expliquee(doc)
        selectionner(pieces["M1"])
        problemes += ecarts("une pièce", actives(), attendues(False, une_piece=True))
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


def verifier_assemblage_impossible_refuse() -> list[str]:
    """Demande de jv : mi-bois entre deux pièces qui ne se touchent pas : message explicatif,
    ni objet créé, ni panneau, ni entrée d'annulation."""
    from PySide import QtGui

    from freecad.menuiserie.gui.commands.base import REFUSAL_BOX_NAME

    with cadre("VerifAssemblageImpossible") as (doc, pieces):
        doc.UndoMode = 1
        avant, entrees = [o.Name for o in doc.Objects], list(doc.UndoNames)
        assembler(doc, pieces["M1"], pieces["M2"], commande="Menuiserie_HalfLap", ok=False)
        boite = Gui.getMainWindow().findChild(QtGui.QMessageBox, REFUSAL_BOX_NAME)
        message = boite.text() if boite is not None and boite.isVisible() else ""
        if boite is not None:
            boite.hide()
        return [
            *ecarts("objets", [o.Name for o in doc.Objects], avant),
            *ecarts("panneau ouvert", bool(Gui.Control.activeDialog()), False),
            *ecarts("entrées d'annulation", list(doc.UndoNames), entrees),
            *ecarts("message explicatif", "se chevaucher" in message, True),
        ]


def verifier_ok_refuse_si_assemblage_en_erreur() -> list[str]:
    """Demande de jv : « OK » du panneau d'assemblage refusé (et grisé) tant que l'assemblage
    est en erreur ; « Annuler » reste possible."""
    from PySide import QtGui

    from freecad.menuiserie.gui.commands.base import REFUSAL_BOX_NAME

    with cadre("VerifOkRefuse") as (doc, pieces):
        joint = assembler(doc, pieces["T1"], pieces["M1"], ok=False)
        if joint is None or not Gui.Control.activeDialog():
            return ["aucun panneau d'assemblage ouvert"]
        loin = App.Placement(App.Vector(5000, 5000, 5000), App.Rotation())
        pieces["T1"].Placement = loin  # les pièces ne se touchent plus : impossible
        doc.recompute()
        valider()
        boite = Gui.getMainWindow().findChild(QtGui.QMessageBox, REFUSAL_BOX_NAME)
        message = boite.text() if boite is not None and boite.isVisible() else ""
        if boite is not None:
            boite.hide()
        problemes = [
            *ecarts("panneau toujours ouvert", bool(Gui.Control.activeDialog()), True),
            *ecarts("message de refus", "non validé" in message, True),
        ]
        if Gui.Control.activeDialog():
            annuler()
        problemes += ecarts("annulé", bool(Gui.Control.activeDialog()), False)
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
            joint = doc.getObjectsByLabel("Tenon-mortaise : M1 T1")[0]
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


@contextmanager
def choix_de_suppression(reponse: bool) -> Iterator[list[tuple[str, list[str]]]]:
    """Fonction de choix de la fenêtre « assemblage lié » remplacée (hors écran, une boîte modale
    ne se clique pas) ; donne les questions posées (pièce, libellés des assemblages)."""
    questions: list[tuple[str, list[str]]] = []

    def choisir(piece: str, libelles: Any) -> bool:
        questions.append((piece, list(libelles)))
        return reponse

    original, joint_choice.part_chooser = joint_choice.part_chooser, choisir
    try:
        yield questions
    finally:
        joint_choice.part_chooser = original


def supprimer_depuis_l_arbre(doc: Any, objet: Any) -> None:
    """Vraie suppression : « Supprimer » (``Std_Delete``) sur l'objet sélectionné."""
    selectionner(objet)
    Gui.runCommand("Std_Delete")
    Gui.Selection.clearSelection()
    doc.recompute()


def verifier_suppression_de_la_piece_usinee() -> list[str]:
    """Supprimer une pièce usinée qui porte un assemblage ouvre la fenêtre « assemblage lié » :
    « Annuler » ne change rien ; « Supprimer la pièce et l'assemblage » retire l'assemblage, la
    pièce usinée et sa brute (la brute de l'autre pièce réapparaît), en une seule entrée
    d'annulation (Ctrl+Z rétablit tout). Sans assemblage, suppression normale et aucune fenêtre."""
    with cadre("VerifSuppressionPieceUsinee") as (doc, pieces):
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        doc.UndoMode = 1
        doc.clearUndos()
        usinee = usinee_de(pieces["M1"])
        noms = [joint.Name, usinee.Name, pieces["M1"].Name]
        autre = pieces["T1"].Name
        with choix_de_suppression(False) as questions:
            supprimer_depuis_l_arbre(doc, usinee)
        problemes = [
            *ecarts("annulée : une question", len(questions), 1),
            *ecarts("annulée : objets", [doc.getObject(n) is not None for n in noms], [True] * 3),
            *ecarts("annulée : aucune entrée", doc.UndoNames, []),
        ]
        with choix_de_suppression(True) as questions:
            supprimer_depuis_l_arbre(doc, usinee_de(pieces["M1"]))
        problemes += [
            *ecarts("supprimée : une question", len(questions), 1),
            *ecarts("supprimée : objets", [doc.getObject(n) is None for n in noms], [True] * 3),
            *ecarts("autre brute visible", doc.getObject(autre).Visibility, True),
            *ecarts("autre pièce usinée retirée", api.machined_part_of(doc.getObject(autre)), None),
            *ecarts("une entrée", len(doc.UndoNames), 1),
        ]
        doc.undo()
        doc.recompute()
        problemes += [
            *ecarts("Ctrl+Z : objets", [doc.getObject(n) is not None for n in noms], [True] * 3),
            *ecarts(
                "Ctrl+Z : pièce usinée", api.machined_part_of(doc.getObject(noms[2])) is None, False
            ),
        ]
        brute = doc.getObject(noms[2])
        doc.removeObject(noms[0])
        doc.recompute()
        with choix_de_suppression(True) as questions:
            supprimer_depuis_l_arbre(doc, usinee_de(brute))
        return [
            *problemes,
            *ecarts("sans assemblage : aucune fenêtre", questions, []),
            *ecarts("sans assemblage : supprimée", api.machined_part_of(brute), None),
            *ecarts("sans assemblage : brute réaffichée", brute.Visibility, True),
        ]


def verifier_suppression_groupee_sans_question() -> list[str]:
    """Supprimer ensemble les deux pièces usinées et leur assemblage (cas d'un Std Part supprimé
    avec son contenu) : aucun lien ne sort de la suppression, la fenêtre « assemblage lié » n'est
    pas ouverte. Une pièce usinée supprimée seule garde sa question."""
    with cadre("VerifSuppressionGroupee") as (doc, pieces):
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        usinees = [usinee_de(pieces[repere]) for repere in ("M1", "T1")]
        noms = [joint.Name, *(u.Name for u in usinees)]
        with choix_de_suppression(False) as questions:
            selectionner(joint, *usinees)
            Gui.runCommand("Std_Delete")
            Gui.Selection.clearSelection()
            doc.recompute()
        return [
            *ecarts("aucune question", questions, []),
            *ecarts("supprimés", [doc.getObject(n) is None for n in noms], [True] * 3),
        ]


def verifier_suppression_du_contenu_d_un_groupe() -> list[str]:
    """« Supprimer le contenu du groupe » (Std Part supprimé avec son contenu) : FreeCAD appelle
    ``onDelete`` avec ``group_recursive_deletion`` ; la pièce usinée accepte sans question et ne
    supprime rien elle-même (sinon pointeurs morts dans la boucle de FreeCAD)."""
    with cadre("VerifSuppressionContenuGroupe") as (doc, pieces):
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        usinee = usinee_de(pieces["M1"])
        groupe = doc.addObject("App::DocumentObjectGroup", "GroupeComplet")
        for objet in (joint, usinee, usinee_de(pieces["T1"]), pieces["M1"], pieces["T1"]):
            groupe.addObject(objet)
        nom = joint.Name
        with choix_de_suppression(False) as questions:
            accepte = usinee.ViewObject.Proxy.onDelete(
                usinee.ViewObject, ["group_recursive_deletion"]
            )
        return [
            *ecarts("aucune question", questions, []),
            *ecarts("acceptée", accepte, True),
            *ecarts("rien supprimé par l'atelier", doc.getObject(nom) is not None, True),
        ]


def verifier_groupe_supprime_avec_une_seule_piece() -> list[str]:
    """Groupe de l'utilisateur supprimé avec son contenu, qui ne contient qu'une des deux pièces :
    l'assemblage resté dehors est supprimé (pas d'« Assemblage incomplet »), la pièce usinée de
    l'autre pièce aussi, sa brute réaffichée."""
    with cadre("VerifGroupeUnePiece") as (doc, pieces):
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        usinee = usinee_de(pieces["M1"])
        autre = usinee_de(pieces["T1"])
        noms = [joint.Name, autre.Name]
        groupe = doc.addObject("App::DocumentObjectGroup", "GroupeUtilisateur")
        groupe.addObject(usinee)
        groupe.addObject(pieces["M1"])
        accepte = usinee.ViewObject.Proxy.onDelete(usinee.ViewObject, ["group_recursive_deletion"])
        return [
            *ecarts("acceptée", accepte, True),
            *ecarts(
                "assemblage et autre usinée supprimés", [doc.getObject(n) for n in noms], [None] * 2
            ),
            *ecarts("pièce usinée gardée pour FreeCAD", usinee.isValid(), True),
            *ecarts("autre brute visible", pieces["T1"].Visibility, True),
        ]


def verifier_suppression_d_un_assemblage() -> list[str]:
    """Supprimer un assemblage : pas d'avertissement « objets référencés » pour ses pièces
    usinées (``canDelete``), qui sont recalculées sans sa coupe."""
    with cadre("VerifSuppressionAssemblage") as (doc, pieces):
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        usinees = [usinee_de(pieces[repere]) for repere in ("M1", "T1")]
        problemes: list[str] = []
        for usinee in usinees:
            proxy = usinee.ViewObject.Proxy
            problemes += ecarts(f"{usinee.Label} : assemblage", proxy.canDelete(joint), True)
            problemes += ecarts(
                f"{usinee.Label} : autre objet", proxy.canDelete(pieces["M2"]), False
            )
        doc.removeObject(joint.Name)
        doc.recompute()
        for usinee in usinees:
            problemes += ecarts(f"{usinee.Label} recalculée", usinee.isValid(), True)
            problemes += ecarts(f"{usinee.Label} sans coupe", list(usinee.Joints), [])
        return problemes


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
    verifier_assemblage_impossible_refuse,
    verifier_ok_refuse_si_assemblage_en_erreur,
    verifier_affichage_de_la_piece_usinee,
    verifier_affichage_de_l_assemblage,
    verifier_reouverture_des_assemblages,
    verifier_double_clic_sur_la_piece_usinee,
    verifier_deplacement_de_la_piece_usinee,
    verifier_suppression_de_la_piece_usinee,
    verifier_suppression_groupee_sans_question,
    verifier_suppression_du_contenu_d_un_groupe,
    verifier_groupe_supprime_avec_une_seule_piece,
    verifier_suppression_d_un_assemblage,
    verifier_aucun_observateur_laisse,
)
