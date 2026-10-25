# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de « Définir une distance » (DI-b, critères E1, E2, E4, E5).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque
vérification renvoie la liste de ses problèmes. Les éléments sont sélectionnés par script
(``Gui.Selection.addSelection``), aucun clic de souris.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import api, icon_path
from tests.elements_choisis import Point, element_name
from tests.gui.verifications_ensemble import boite_de_refus
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    emplacements,
    formulaire_nomme,
    nouveau_document,
    saisir,
    valider,
)

COMMANDE = "Menuiserie_SetDistance"
FORM = "DistanceTaskPanel"
TRANSACTION = "Définir une distance"
PLATEAU_BAS: Point = (400, 100, 700)
ETAGERE_HAUT: Point = (300, 100, 122)


def piece(doc: Any, taille: Point, base: Point, nom: str) -> Any:
    obj = api.make_wood_part(*taille, "chene", doc=doc)
    obj.Label = nom
    obj.Placement = App.Placement(App.Vector(*base), App.Rotation())
    doc.recompute()
    return obj


def plateau_et_etagere(doc: Any) -> tuple[Any, Any]:
    return (
        piece(doc, (800, 200, 22), (0, 0, 700), "Plateau"),
        piece(doc, (600, 200, 22), (0, 0, 100), "Étagère"),
    )


def selectionner(*elements: tuple[Any, str, Point]) -> None:
    """Sélectionne des éléments (objet, type, point proche), dans cet ordre."""
    Gui.Selection.clearSelection()
    for obj, genre, proche in elements:
        Gui.Selection.addSelection(obj, element_name(obj, genre, proche))


def hauteur(obj: Any) -> float:
    return round(float(obj.Placement.Base.z), 6)


def etiquette(form: Any, nom: str) -> Any:
    return form.findChild(QtGui.QLabel, nom)


def avec_document(nom: str, verification: Callable[[Any], list[str]]) -> list[str]:
    """``verification`` sur un document neuf, toujours refermé (panneau compris)."""
    doc = nouveau_document(nom)
    nom_du_document = doc.Name
    try:
        return verification(doc)
    finally:
        if Gui.Control.activeDialog():
            annuler()
        Gui.Selection.clearSelection()
        if nom_du_document in App.listDocuments():
            App.closeDocument(nom_du_document)


def ouvrir(doc: Any) -> tuple[Any, Any, Any]:
    """Plateau et étagère, face-face sélectionnées, commande lancée ; renvoie les deux pièces et
    le formulaire."""
    plateau, etagere = plateau_et_etagere(doc)
    selectionner((plateau, "Face", PLATEAU_BAS), (etagere, "Face", ETAGERE_HAUT))
    doc.clearUndos()
    Gui.Command.get(COMMANDE).run()
    return plateau, etagere, formulaire_nomme(FORM)


# --- E1 : commande, activation, menu contextuel ----------------------------------------------


def verifier_commande_de_distance_presente() -> list[str]:
    """E1 : libellé, infobulle, icône générée, barre d'outils et menu Menuiserie."""
    commande = Gui.Command.get(COMMANDE)
    if commande is None:
        return [f"{COMMANDE} non enregistrée"]
    infos = commande.getInfo()
    constats = {
        "libellé": (infos["menuText"], TRANSACTION),
        "infobulle": (bool(infos["toolTip"].strip()), True),
        "icône": (infos["pixmap"], icon_path(f"{COMMANDE}.svg")),
        "icône affichée": (commande.getAction()[0].icon().isNull(), False),
        "emplacements": (
            sorted(set(emplacements(COMMANDE))),
            [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")],
        ),
    }
    return [
        p for quoi, (obtenu, attendu) in constats.items() for p in ecarts(quoi, obtenu, attendu)
    ]


def verifier_activation_de_la_distance() -> list[str]:
    """E1 : active seulement avec deux éléments de deux objets différents."""

    def verification(doc: Any) -> list[str]:
        plateau, etagere = plateau_et_etagere(doc)
        elements = {
            "aucune sélection": [],
            "un seul élément": [(plateau, "Face", PLATEAU_BAS)],
            "deux éléments du même objet": [
                (plateau, "Face", PLATEAU_BAS),
                (plateau, "Face", (400, 100, 722)),
            ],
            "deux éléments de deux objets": [
                (plateau, "Face", PLATEAU_BAS),
                (etagere, "Face", ETAGERE_HAUT),
            ],
        }
        attendu = {"deux éléments de deux objets": True}
        problemes = []
        for cas, choisis in elements.items():
            selectionner(*choisis)
            problemes += ecarts(
                cas, bool(Gui.Command.get(COMMANDE).isActive()), attendu.get(cas, False)
            )
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(plateau)
        Gui.Selection.addSelection(etagere)
        problemes += ecarts(
            "deux objets entiers", bool(Gui.Command.get(COMMANDE).isActive()), False
        )
        return problemes

    return avec_document("DistanceActivation", verification)


def verifier_menu_contextuel_de_la_distance() -> list[str]:
    """E1 : ``ContextMenu`` (vue 3D et arborescence) s'exécute avec ou sans sélection adaptée."""

    def verification(doc: Any) -> list[str]:
        plateau, etagere = plateau_et_etagere(doc)
        Gui.activateWorkbench("MenuiserieWorkbench")
        atelier = Gui.activeWorkbench()
        problemes = []
        for choisis in ([], [(plateau, "Face", PLATEAU_BAS), (etagere, "Face", ETAGERE_HAUT)]):
            selectionner(*choisis)
            for destinataire in ("View", "Tree"):
                try:
                    atelier.ContextMenu(destinataire)
                except Exception as erreur:
                    problemes.append(f"ContextMenu({destinataire}) : {erreur!r}")
        return problemes

    return avec_document("DistanceMenu", verification)


# --- E2 : panneau et aperçu en direct --------------------------------------------------------


def verifier_panneau_de_distance() -> list[str]:
    """E2 : « Entre … et … », distance actuelle, champ initialisé, pièce déplacée, Inverser."""

    def verification(doc: Any) -> list[str]:
        _plateau, _etagere, form = ouvrir(doc)
        if form is None:
            return ["panneau absent"]
        champ = form.findChild(QtGui.QWidget, "distanceEdit")
        entre = etiquette(form, "betweenLabel").text()
        deplacee = etiquette(form, "movedLabel").text()
        constats = {
            "champ (mm)": (round(float(champ.property("rawValue")), 3), 578.0),
            "entre": ("Entre : " in entre and "Plateau" in entre and "Étagère" in entre, True),
            "pièce déplacée (la seconde)": ("Étagère" in deplacee, True),
            "distance actuelle": ("578" in etiquette(form, "currentLabel").text(), True),
            "direction cachée (face-face)": (
                form.findChild(QtGui.QComboBox, "directionCombo").isVisibleTo(form),
                False,
            ),
            "Inverser actif": (form.findChild(QtGui.QPushButton, "swapButton").isEnabled(), True),
        }
        return [
            p for quoi, (obtenu, attendu) in constats.items() for p in ecarts(quoi, obtenu, attendu)
        ]

    return avec_document("DistancePanneau", verification)


def verifier_apercu_en_direct() -> list[str]:
    """E2 : la pièce suit la saisie, sans recalcul du document ; Inverser déplace l'autre."""

    def verification(doc: Any) -> list[str]:
        plateau, etagere, form = ouvrir(doc)
        saisir(form.findChild(QtGui.QWidget, "distanceEdit"), 320)
        problemes = ecarts("étagère déplacée en direct", hauteur(etagere), 358.0)
        form.findChild(QtGui.QPushButton, "swapButton").click()
        problemes += ecarts("étagère revenue", hauteur(etagere), 100.0)
        problemes += ecarts("plateau déplacé", hauteur(plateau), 442.0)
        problemes += ecarts(
            "pièce déplacée", "Plateau" in etiquette(form, "movedLabel").text(), True
        )
        return problemes

    return avec_document("DistanceApercu", verification)


def verifier_direction_de_deux_sommets() -> list[str]:
    """E2 : la liste Direction (Directe, X, Y, Z) n'apparaît que pour deux sommets."""

    def verification(doc: Any) -> list[str]:
        fixe = piece(doc, (100, 100, 20), (0, 0, 0), "Fixe")
        mobile = piece(doc, (100, 100, 20), (300, 40, 0), "Mobile")
        selectionner((fixe, "Vertex", (0, 0, 0)), (mobile, "Vertex", (300, 40, 0)))
        Gui.Command.get(COMMANDE).run()
        form = formulaire_nomme(FORM)
        if form is None:
            return ["panneau absent"]
        liste = form.findChild(QtGui.QComboBox, "directionCombo")
        problemes = ecarts("liste visible", liste.isVisibleTo(form), True)
        problemes += ecarts(
            "entrées", [liste.itemData(i) for i in range(liste.count())], ["", "X", "Y", "Z"]
        )
        liste.setCurrentIndex(liste.findData("X"))
        problemes += ecarts(
            "distance sur X",
            round(float(form.findChild(QtGui.QWidget, "distanceEdit").property("rawValue")), 3),
            300.0,
        )
        saisir(form.findChild(QtGui.QWidget, "distanceEdit"), 50)
        base = mobile.Placement.Base
        problemes += ecarts(
            "déplacement sur X seul", (round(base.x, 3), round(base.y, 3)), (50.0, 40.0)
        )
        return problemes

    return avec_document("DistanceSommets", verification)


# --- E5 : OK et Annuler ----------------------------------------------------------------------


def verifier_distance_validee() -> list[str]:
    """E5 : « OK » = une seule entrée d'annulation « Définir une distance » ; Annuler/Rétablir."""

    def verification(doc: Any) -> list[str]:
        _plateau, etagere, form = ouvrir(doc)
        saisir(form.findChild(QtGui.QWidget, "distanceEdit"), 320)
        valider()
        problemes = ecarts("panneau fermé", Gui.Control.activeDialog(), False)
        problemes += ecarts("position gardée", hauteur(etagere), 358.0)
        problemes += ecarts("entrées d'annulation", doc.UndoNames, [TRANSACTION])
        doc.undo()
        problemes += ecarts("après annulation", hauteur(etagere), 100.0)
        doc.redo()
        problemes += ecarts("après rétablissement", hauteur(etagere), 358.0)
        return problemes

    return avec_document("DistanceOk", verification)


def verifier_distance_annulee() -> list[str]:
    """E5 : « Annuler » : rien n'a changé, aucune entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        _plateau, etagere, form = ouvrir(doc)
        saisir(form.findChild(QtGui.QWidget, "distanceEdit"), 320)
        annuler()
        problemes = ecarts("panneau fermé", Gui.Control.activeDialog(), False)
        problemes += ecarts("position", hauteur(etagere), 100.0)
        problemes += ecarts("entrées d'annulation", doc.UndoNames, [])
        return problemes

    return avec_document("DistanceAnnule", verification)


# --- Refus (E3, E4) --------------------------------------------------------------------------


def verifier_refus_de_la_distance() -> list[str]:
    """Éléments non parallèles ou objets étrangers : refus expliqué, aucun panneau."""

    def verification(doc: Any) -> list[str]:
        plateau, etagere = plateau_et_etagere(doc)
        selectionner((plateau, "Face", PLATEAU_BAS), (etagere, "Face", (0, 100, 111)))
        Gui.Command.get(COMMANDE).run()
        problemes = ecarts("panneau ouvert", Gui.Control.activeDialog(), False)
        boite = boite_de_refus()
        texte = boite.text() if boite is not None else ""
        problemes += ecarts("refus expliqué", "parallèles" in texte, True)
        problemes += ecarts("entrées d'annulation", doc.UndoNames, [])
        cube_a = doc.addObject("Part::Box", "CubeA")
        cube_b = doc.addObject("Part::Box", "CubeB")
        cube_b.Placement = App.Placement(App.Vector(200, 0, 0), App.Rotation())
        doc.recompute()
        selectionner((cube_a, "Face", (0, 5, 5)), (cube_b, "Face", (200, 5, 5)))
        Gui.Command.get(COMMANDE).run()
        texte = boite_de_refus().text()
        problemes += ecarts("aucune pièce de l'atelier", "pièce de l'atelier" in texte, True)
        problemes += ecarts("panneau ouvert (cubes)", Gui.Control.activeDialog(), False)
        return problemes

    return avec_document("DistanceRefus", verification)


def verifier_axe_pilote_par_une_formule() -> list[str]:
    """E4 : une formule de l'utilisateur sur l'axe : message rouge, « OK » ne ferme pas."""

    def verification(doc: Any) -> list[str]:
        plateau, etagere = plateau_et_etagere(doc)
        etagere.setExpression("Placement.Base.z", "100 mm")
        doc.recompute()
        selectionner((plateau, "Face", PLATEAU_BAS), (etagere, "Face", ETAGERE_HAUT))
        Gui.Command.get(COMMANDE).run()
        form = formulaire_nomme(FORM)
        saisir(form.findChild(QtGui.QWidget, "distanceEdit"), 320)
        erreur = etiquette(form, "errorLabel")
        problemes = ecarts("message", "piloté par une formule" in erreur.text(), True)
        problemes += ecarts("message visible", erreur.isVisibleTo(form), True)
        valider()
        problemes += ecarts("panneau toujours ouvert", bool(Gui.Control.activeDialog()), True)
        annuler()
        problemes += ecarts("position", hauteur(etagere), 100.0)
        return problemes

    return avec_document("DistanceFormule", verification)


VERIFICATIONS_DISTANCE: tuple[Callable[[], list[str]], ...] = (
    verifier_commande_de_distance_presente,
    verifier_activation_de_la_distance,
    verifier_menu_contextuel_de_la_distance,
    verifier_panneau_de_distance,
    verifier_apercu_en_direct,
    verifier_direction_de_deux_sommets,
    verifier_distance_validee,
    verifier_distance_annulee,
    verifier_refus_de_la_distance,
    verifier_axe_pilote_par_une_formule,
)
