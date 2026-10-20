# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la commande « Pièce de bois » et de son panneau (J1c).

Critères C1 à C6 et C8 de ``docs/specs/J1-piece-de-bois.md``. Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification renvoie la liste
de ses problèmes. Les champs du panneau sont manipulés comme par l'utilisateur, par leurs
propriétés et signaux Qt ; « OK » et « Annuler » passent par le dialogue actif de FreeCAD.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.features.library import get_library

COMMAND = "Menuiserie_WoodPart"
FORM = "WoodPartTaskPanel"
CREATE = "Créer une pièce de bois"
EDIT = "Modifier une pièce de bois"
# Propriétés comparées avant et après « Annuler » (C4).
WATCHED = (
    "Length",
    "Width",
    "Thickness",
    "Material",
    "MaterialId",
    "Category",
    "GrainDirection",
    "PreferredGrainDirection",
    "Mark",
    "LengthAllowance",
    "WidthAllowance",
    "ThicknessAllowance",
)

Widget = Any


def ecarts(nom: str, obtenu: object, attendu: object) -> list[str]:
    return [] if obtenu == attendu else [f"{nom} : {obtenu!r} au lieu de {attendu!r}"]


def formulaire() -> Widget:
    """Formulaire du panneau ouvert (``None`` s'il n'y en a pas).

    Cherché parmi ``allWidgets()`` et non par ``findChild`` sur la fenêtre principale : PySide
    rattacherait l'enveloppe Python du formulaire à celle de la fenêtre, qui la garderait en
    vie après la fermeture du panneau ; ses adresses, réutilisées par les panneaux suivants,
    donneraient alors des widgets du mauvais type."""
    trouves = [w for w in QtGui.QApplication.allWidgets() if w.objectName() == FORM]
    return trouves[0] if trouves else None


def valider() -> None:
    """Bouton « OK » du panneau ouvert."""
    Gui.Control.activeTaskDialog().accept()


def annuler() -> None:
    """Bouton « Annuler » du panneau ouvert."""
    Gui.Control.activeTaskDialog().reject()


def nouveau_document(nom: str) -> Any:
    doc = App.newDocument(nom)
    doc.UndoMode = 1
    return doc


def creer_par_la_commande(doc: Any) -> Any:
    """Lance la commande et renvoie la pièce créée (panneau laissé ouvert)."""
    Gui.Command.get(COMMAND).run()
    return doc.Objects[-1] if doc.Objects else None


def ouvrir_par_double_clic(obj: Any) -> Widget:
    vobj = obj.ViewObject
    vobj.Proxy.doubleClicked(vobj)
    return formulaire()


def valeur(champ: Widget) -> float:
    return float(champ.property("rawValue"))


def saisir(champ: Widget, valeur_mm: float) -> None:
    """Saisie d'une cote (en mm) dans un champ du panneau."""
    champ.setProperty("rawValue", valeur_mm)


def choisir(liste: Widget, donnee: object) -> None:
    liste.setCurrentIndex(liste.findData(donnee))


def donnees(liste: Widget) -> list[object]:
    return [liste.itemData(i) for i in range(liste.count())]


def valeurs(obj: Any) -> dict[str, object]:
    return {nom: getattr(obj, nom) for nom in WATCHED} | {
        "MaterialColor": tuple(obj.ViewObject.MaterialColor),
    }


def avec_document(nom: str, verification: Callable[[Any], list[str]]) -> list[str]:
    """Exécute ``verification`` dans un nouveau document, toujours refermé (panneau compris)."""
    doc = nouveau_document(nom)
    try:
        return verification(doc)
    finally:
        if Gui.Control.activeDialog():
            annuler()
        App.closeDocument(doc.Name)


# --- C1 : commande, barre d'outils, menu, activation -------------------------------------


def emplacements(commande: str = COMMAND) -> list[tuple[str, str]]:
    """Barres d'outils et menus qui portent l'action de ``commande`` : (type, nom)."""
    actions = Gui.Command.get(commande).getAction()
    return [
        (type(widget).__name__, widget.objectName())
        for action in actions
        for widget in action.associatedObjects()
        if isinstance(widget, (QtGui.QToolBar, QtGui.QMenu))
    ]


def verifier_commande_presente() -> list[str]:
    """C1 : commande avec libellé, infobulle et icône, dans la barre d'outils et le menu."""
    from freecad.menuiserie import icon_path

    infos = Gui.Command.get(COMMAND).getInfo()
    actions = Gui.Command.get(COMMAND).getAction()
    places = sorted(emplacements())
    return [
        *ecarts("libellé", infos["menuText"], "Pièce de bois"),
        *ecarts("infobulle renseignée", bool(infos["toolTip"].strip()), True),
        *ecarts("icône", infos["pixmap"], icon_path("Menuiserie_WoodPart.svg")),
        *ecarts("icône affichée", [a.icon().isNull() for a in actions], [False]),
        *ecarts("emplacements", places, [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")]),
    ]


def verifier_commande_inactive() -> list[str]:
    """C1 : inactive sans document et quand un panneau de tâche est ouvert."""
    commande = Gui.Command.get(COMMAND)
    problemes = [
        *ecarts("documents restés ouverts", list(App.listDocuments()), []),
        *ecarts("active sans document", commande.isActive(), False),
    ]

    def avec_panneau(doc: Any) -> list[str]:
        resultat = ecarts("active avec un document", commande.isActive(), True)
        creer_par_la_commande(doc)
        return resultat + ecarts("active panneau ouvert", commande.isActive(), False)

    return problemes + avec_document("VerifCommandeActive", avec_panneau)


# --- C2, C3 : création -------------------------------------------------------------------


def verifier_creation_validee() -> list[str]:
    """C2 : pièce de chêne 800 x 200 x 22 et panneau ouvert ; « OK » : une pièce, une entrée."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        form = formulaire()
        problemes = [
            *ecarts("panneau ouvert", form is not None, True),
            *ecarts("matériau", obj.MaterialId, "chene"),
            *ecarts("cotes", [valeur(form.lengthEdit), valeur(form.widthEdit)], [800.0, 200.0]),
            *ecarts("épaisseur", valeur(form.thicknessEdit), 22.0),
        ]
        valider()
        return [
            *problemes,
            *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
            *ecarts("pièces", len(doc.Objects), 1),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
            *ecarts("pièce valide", doc.Objects[0].isValid(), True),
        ]

    return avec_document("VerifCreation", verification)


def verifier_creation_annulee() -> list[str]:
    """C3 : « Annuler » à la création ne laisse ni pièce ni entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        creer_par_la_commande(doc)
        saisir(formulaire().lengthEdit, 1000.0)
        annuler()
        return [
            *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
            *ecarts("pièces", len(doc.Objects), 0),
            *ecarts("entrées d'annulation", doc.UndoCount, 0),
        ]

    return avec_document("VerifCreationAnnulee", verification)


# --- C4 : modification -------------------------------------------------------------------


def piece_validee(doc: Any) -> Any:
    """Pièce créée par la commande et validée (une entrée d'annulation)."""
    obj = creer_par_la_commande(doc)
    valider()
    return obj


def modifier_tout(form: Widget) -> None:
    """Change chaque champ du panneau, comme l'utilisateur."""
    form.markEdit.selectAll()
    form.markEdit.insert("M1")  # comme une frappe : émet textEdited
    choisir(form.materialCombo, "hetre")
    choisir(form.grainCombo, "Width")
    for champ, cote in (("lengthEdit", 1000.0), ("widthEdit", 250.0), ("thicknessEdit", 27.0)):
        saisir(getattr(form, champ), cote)
    saisir(form.lengthAllowanceEdit, 30.0)


def verifier_modification_validee() -> list[str]:
    """C4 : valeurs actuelles affichées, aperçu immédiat, « OK » : une entrée « Modifier »."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.Length = 900
        doc.recompute()
        form = ouvrir_par_double_clic(obj)
        problemes = [
            *ecarts("panneau ouvert au double-clic", form is not None, True),
            *ecarts("longueur affichée", valeur(form.lengthEdit), 900.0),
            *ecarts("matériau affiché", form.materialCombo.currentData(), "chene"),
            *ecarts("fil affiché", form.grainCombo.currentData(), "Length"),
        ]
        modifier_tout(form)
        problemes += [
            *ecarts("volume en direct", round(obj.Shape.Volume), 1000 * 250 * 27),
            *ecarts("matériau en direct", obj.MaterialId, "hetre"),
            *ecarts("repère", obj.Mark, "M1"),
            *ecarts("fil", obj.GrainDirection, "Width"),
            *ecarts("surcote", obj.LengthAllowance.Value, 30.0),
        ]
        valider()
        return [
            *problemes,
            *ecarts("entrées d'annulation", doc.UndoNames, [EDIT, CREATE]),
            *ecarts("fin de l'édition", Gui.ActiveDocument.getInEdit(), None),
        ]

    return avec_document("VerifModification", verification)


def verifier_modification_annulee() -> list[str]:
    """C4 : « Annuler » rétablit toutes les valeurs d'origine, sans entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        modifier_tout(ouvrir_par_double_clic(obj))
        annuler()
        return [
            *ecarts("valeurs rétablies", valeurs(obj), avant),
            *ecarts("volume rétabli", round(obj.Shape.Volume), 800 * 200 * 22),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
            *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
            *ecarts("fin de l'édition", Gui.ActiveDocument.getInEdit(), None),
        ]

    return avec_document("VerifModificationAnnulee", verification)


# --- C5 : filtre, épaisseurs standard, avertissement -------------------------------------


def verifier_filtre_des_materiaux() -> list[str]:
    """C5 et C12 : le filtre « Type » restreint la liste et applique le premier matériau du
    type quand il exclut celui de la pièce ; « Tous » rétablit la liste sans changer la pièce."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        form = formulaire()
        bibliotheque = get_library()
        tous = [m.id for m in bibliotheque]
        types = [form.kindCombo.itemText(i) for i in range(form.kindCombo.count())]
        problemes = [
            *ecarts("types", types, ["Tous", "Massif", "Contreplaqué", "MDF", "Mélaminé"]),
            *ecarts("liste complète", donnees(form.materialCombo), tous),
        ]
        for index, kind in enumerate(MaterialKind, start=1):
            form.kindCombo.setCurrentIndex(index)
            attendus = [m.id for m in bibliotheque.by_kind(kind)]
            problemes += ecarts(f"liste {kind.value}", donnees(form.materialCombo), attendus)
            problemes += ecarts(f"matériau {kind.value}", obj.MaterialId, attendus[0])
        dernier = obj.MaterialId
        form.kindCombo.setCurrentIndex(0)
        return [
            *problemes,
            *ecarts("liste rétablie", donnees(form.materialCombo), tous),
            *ecarts("pièce inchangée par « Tous »", obj.MaterialId, dernier),
        ]

    return avec_document("VerifFiltre", verification)


def menu_des_epaisseurs(form: Widget) -> list[Any]:
    return list(form.standardThicknessButton.menu().actions())


def verifier_epaisseurs_standard() -> list[str]:
    """C5 : épaisseurs standard en un clic ; avertissement visible et non bloquant pour un
    panneau d'épaisseur hors standard, jamais pour le massif."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        form = formulaire()
        choisir(form.materialCombo, "mdf")
        actions = menu_des_epaisseurs(form)
        problemes = ecarts(
            "épaisseurs proposées", len(actions), len(get_library().get("mdf").thicknesses)
        )
        actions[-1].trigger()
        problemes += [
            *ecarts(
                "épaisseur choisie", obj.Thickness.Value, get_library().get("mdf").thicknesses[-1]
            ),
            *ecarts("champ mis à jour", valeur(form.thicknessEdit), obj.Thickness.Value),
            *ecarts("avertissement standard", form.thicknessWarning.isHidden(), True),
        ]
        saisir(form.thicknessEdit, 20.0)
        problemes += [
            *ecarts("avertissement panneau", form.thicknessWarning.isHidden(), False),
            *ecarts("pièce valide malgré l'avertissement", obj.isValid(), True),
        ]
        choisir(form.materialCombo, "chene")
        problemes += ecarts("avertissement massif", form.thicknessWarning.isHidden(), True)
        choisir(form.materialCombo, "mdf")
        valider()
        return [
            *problemes,
            *ecarts("validée hors standard", obj.Thickness.Value, 20.0),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
        ]

    return avec_document("VerifEpaisseurs", verification)


# --- C6 : expressions --------------------------------------------------------------------


def verifier_expressions() -> list[str]:
    """C6 : une cote pilotée par une expression est affichée comme telle et conservée.

    L'icône d'expression et la lecture seule du champ sont vérifiées à la main (recette) : hors
    écran, le volet des tâches peut être replié et le champ n'est pas affiché."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("Length", "Width * 4")
        obj.setExpression("Thickness", "Width / 10")
        doc.recompute()
        form = ouvrir_par_double_clic(obj)
        problemes = [
            *ecarts("valeur de l'expression", valeur(form.lengthEdit), 800.0),
            *ecarts("expression affichée", form.lengthEdit.property("expression"), "Width * 4"),
            *ecarts("champ sans expression", form.widthEdit.property("expression"), ""),
            *ecarts("menu des épaisseurs inactif", form.standardThicknessButton.isEnabled(), False),
        ]
        saisir(form.widthEdit, 250.0)
        valider()
        expressions = dict(obj.ExpressionEngine)
        return [
            *problemes,
            *ecarts(
                "expressions conservées",
                expressions,
                {"Length": "Width * 4", "Thickness": "Width / 10"},
            ),
            *ecarts("longueur recalculée", obj.Length.Value, 1000.0),
        ]

    return avec_document("VerifExpressions", verification)


# --- C8 : traductions --------------------------------------------------------------------


def verifier_libelles_traduits() -> list[str]:
    """C8 : les libellés du fil sont traduits, la valeur écrite reste la valeur stable."""

    def verification(doc: Any) -> list[str]:
        creer_par_la_commande(doc)
        form = formulaire()
        textes = [form.grainCombo.itemText(i) for i in range(form.grainCombo.count())]
        return [
            *ecarts("libellés du fil", textes, ["Longueur", "Largeur", "Sans fil"]),
            *ecarts("valeurs du fil", donnees(form.grainCombo), ["Length", "Width", "None"]),
            *ecarts("titre", form.windowTitle(), "Nouvelle pièce de bois"),
        ]

    return avec_document("VerifLibelles", verification)


VERIFICATIONS_PANNEAU: tuple[Callable[[], list[str]], ...] = (
    verifier_commande_presente,
    verifier_commande_inactive,
    verifier_creation_validee,
    verifier_creation_annulee,
    verifier_modification_validee,
    verifier_modification_annulee,
    verifier_filtre_des_materiaux,
    verifier_epaisseurs_standard,
    verifier_expressions,
    verifier_libelles_traduits,
)
