# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de la commande « Pièce de bois » et de son panneau (lot J1c, testeur).

Critères C2 à C7 de ``docs/specs/J1-piece-de-bois.md`` : saisies avec unités et refusées,
recalcul après chaque champ, titres, annuler / rétablir après « OK » et « Annuler »,
enregistrement puis réouverture, double-clic sur une pièce déjà en édition, document fermé ou
pièce supprimée pendant l'édition, matériau absent de la bibliothèque, bibliothèque vide,
changement de Type, expressions. Module importé par ``verifier_atelier.py``.

Un défaut constaté est une vérification décorée par :func:`defaut_connu`, équivalent de
``pytest.mark.xfail(strict=True)`` pour ce script lancé par FreeCAD : ses écarts sont rapportés
comme défauts connus sans faire échouer le script ; s'il n'en a plus, le script échoue pour que
le marqueur soit retiré.

Aucune vérification ne garde de référence à un formulaire au-delà de la vie de son panneau :
une enveloppe PySide survivant à son widget serait réutilisée à tort par le panneau suivant.
"""

from __future__ import annotations

import functools
import json
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.features import library
from tests.gui.verifications_panneau import (
    COMMAND,
    CREATE,
    EDIT,
    annuler,
    avec_document,
    choisir,
    creer_par_la_commande,
    ecarts,
    formulaire,
    modifier_tout,
    nouveau_document,
    piece_validee,
    saisir,
    valeur,
    valeurs,
    valider,
)

Verification = Callable[[], list[str]]
# Défauts connus constatés pendant l'exécution, ajoutés au rapport après la ligne « OK ».
DEFAUTS_CONSTATES: list[str] = []
NOUVELLE = "Nouvelle pièce de bois"
VOLUME_INITIAL = 800 * 200 * 22
ERABLE = {
    "id": "erable",
    "kind": "solid",
    "name": {"fr": "Érable", "en": "Maple"},
    "density": 650,
    "thicknesses": [22],
    "color": "#E8D2A8",
}


def defaut_connu(numero: str, raison: str) -> Callable[[Verification], Verification]:
    """Marque une vérification qui échoue à cause d'un défaut du code de production.

    Comme ``xfail(strict=True)`` : écarts ou exception → défaut connu, rapporté sans échec ;
    aucun écart → échec « XPASS » (défaut corrigé : retirer le marqueur)."""

    def decorer(verification: Verification) -> Verification:
        @functools.wraps(verification)
        def attendue_en_echec() -> list[str]:
            try:
                problemes = verification()
            except Exception as erreur:  # comme xfail : une exception est un échec
                problemes = [f"{type(erreur).__name__} : {erreur}"]
            if not problemes:
                return [f"XPASS strict, {numero} corrigé ? retirer defaut_connu : {raison}"]
            DEFAUTS_CONSTATES.append(f"XFAIL {numero} : {raison} [constaté : {problemes[0]}]")
            return []

        return attendue_en_echec

    return decorer


# --- Aides --------------------------------------------------------------------------------


def taper(champ: Any, texte: str) -> None:
    """Saisie au clavier dans un champ de cote (texte analysé par le champ, unités comprises)."""
    champ.findChild(QtGui.QLineEdit).setText(texte)


def double_cliquer(obj: Any) -> bool:
    vobj = obj.ViewObject
    return bool(vobj.Proxy.doubleClicked(vobj))


def editer(obj: Any) -> None:
    """Ouvre le panneau d'édition sans garder de référence au formulaire."""
    double_cliquer(obj)


def transaction_ouverte() -> object:
    return App.getActiveTransaction()


class Ecritures:
    """Observateur de document : noms des propriétés écrites sur un objet."""

    def __init__(self, obj: Any) -> None:
        self.cible = (obj.Document.Name, obj.Name)
        self.proprietes: list[str] = []

    def slotChangedObject(self, obj: Any, prop: str) -> None:
        if (obj.Document.Name, obj.Name) == self.cible:
            self.proprietes.append(prop)


@contextmanager
def ecritures(obj: Any) -> Iterator[list[str]]:
    """Propriétés de ``obj`` écrites pendant le bloc."""
    observateur = Ecritures(obj)
    App.addDocumentObserver(observateur)
    try:
        yield observateur.proprietes
    finally:
        App.removeDocumentObserver(observateur)


@contextmanager
def bibliotheque(fichier_integre: Path | None, *materiaux: dict[str, object]) -> Iterator[Path]:
    """Bibliothèque de la session remplacée le temps du bloc : fichier utilisateur temporaire
    (``materiaux``) et, si ``fichier_integre`` est donné, bibliothèque intégrée déplacée."""
    parametres = App.ParamGet(library.PARAM_PATH)
    precedent = parametres.GetString(library.USER_LIBRARY_PARAM, "")
    integree = library.builtin_library_path
    utilisateur = Path(tempfile.mkdtemp()) / "materiaux.json"
    contenu = {"format": 1, "materials": list(materiaux)}
    utilisateur.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    parametres.SetString(library.USER_LIBRARY_PARAM, str(utilisateur))
    if fichier_integre is not None:
        library.builtin_library_path = lambda: fichier_integre
    try:
        library.reload_library()
        yield utilisateur
    finally:
        library.builtin_library_path = integree
        if precedent:
            parametres.SetString(library.USER_LIBRARY_PARAM, precedent)
        else:
            parametres.RemString(library.USER_LIBRARY_PARAM)
        library.reload_library()


def libelle_affiche_par_type(obj: Any) -> list[str]:
    """Pour chaque type du filtre : écart entre le libellé affiché et ``obj.Material``."""
    problemes: list[str] = []
    for index in range(formulaire().kindCombo.count()):
        formulaire().kindCombo.setCurrentIndex(index)
        texte = formulaire().materialCombo.currentText()
        problemes += ecarts(f"libellé affiché, type {index}", texte, obj.Material)
    formulaire().kindCombo.setCurrentIndex(0)
    return problemes


# --- C7 : unités, valeurs refusées, valeurs extrêmes --------------------------------------

SAISIES = (
    # (champ, texte tapé, valeur attendue de la propriété en mm)
    ("lengthEdit", "80 cm", 800.0),
    ("widthEdit", "2'", 609.6),
    ("thicknessEdit", "0", 22.0),
    ("thicknessEdit", "-5", 22.0),
    ("thicknessEdit", "0.05 mm", 22.0),
    ("thicknessEdit", "abc", 22.0),
    ("thicknessEdit", "0.1 mm", 0.1),
    ("lengthEdit", "20001 mm", 800.0),
    ("lengthEdit", "1e9", 800.0),
    ("lengthEdit", "20000 mm", 20000.0),
    ("lengthAllowanceEdit", "-1 mm", 20.0),
    ("lengthAllowanceEdit", "0 mm", 0.0),
)
PROPRIETES = {
    "lengthEdit": "Length",
    "widthEdit": "Width",
    "thicknessEdit": "Thickness",
    "lengthAllowanceEdit": "LengthAllowance",
    "widthAllowanceEdit": "WidthAllowance",
    "thicknessAllowanceEdit": "ThicknessAllowance",
}


def verifier_saisies_et_refus() -> list[str]:
    """C7 : unités acceptées ; ≤ 0, sous 0,1 mm, au-delà de 20 000 mm ou illisible : la pièce
    garde sa dernière valeur valide ; « Annuler » rétablit tout."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        problemes: list[str] = []
        for champ, texte, attendu in SAISIES:
            taper(getattr(formulaire(), champ), texte)
            prop = PROPRIETES[champ]
            obtenu = round(getattr(obj, prop).Value, 6)
            problemes += ecarts(f"{prop} après « {texte} »", obtenu, attendu)
            problemes += ecarts(f"pièce valide après « {texte} »", obj.isValid(), True)
        annuler()
        return problemes + ecarts("valeurs rétablies", valeurs(obj), avant)

    return avec_document("VerifSaisies", verification)


# --- C4 : recalcul après chaque champ -----------------------------------------------------

NOUVELLES_COTES = (
    ("lengthEdit", 1000.0, 1000 * 200 * 22),
    ("widthEdit", 250.0, 1000 * 250 * 22),
    ("thicknessEdit", 27.0, 1000 * 250 * 27),
    ("lengthAllowanceEdit", 35.0, 1000 * 250 * 27),
    ("widthAllowanceEdit", 7.0, 1000 * 250 * 27),
    ("thicknessAllowanceEdit", 2.0, 1000 * 250 * 27),
)


def verifier_recalcul_de_chaque_cote() -> list[str]:
    """C4 : chaque cote saisie est écrite et la forme recalculée aussitôt (aperçu). L'objet
    reste « Touched » jusqu'à « OK » : ``obj.recompute()`` ne le remet pas à jour."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        problemes: list[str] = []
        for champ, cote, volume in NOUVELLES_COTES:
            saisir(getattr(formulaire(), champ), cote)
            prop = PROPRIETES[champ]
            problemes += [
                *ecarts(prop, getattr(obj, prop).Value, cote),
                *ecarts(f"volume après {prop}", round(obj.Shape.Volume), volume),
                *ecarts(f"pièce valide après {prop}", obj.isValid(), True),
            ]
        valider()
        return problemes + ecarts("entrées d'annulation", doc.UndoNames, [CREATE])

    return avec_document("VerifRecalcul", verification)


# --- C2, C4 : titres ----------------------------------------------------------------------


def verifier_titre_avec_un_libelle_particulier() -> list[str]:
    """C4 : titre « Modifier « <Label> » », accolades et guillemets du libellé compris."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.Label = "Montant {gauche} « bis »"
        editer(obj)
        titre = formulaire().windowTitle()
        return ecarts("titre", titre, "Modifier « Montant {gauche} « bis » »")

    return avec_document("VerifTitre", verification)


# --- C3, C4 : annuler / rétablir ----------------------------------------------------------


def verifier_ok_et_annuler_sans_modification() -> list[str]:
    """« OK » ou « Annuler » sans rien changer : aucune entrée d'annulation, pièce à jour et
    pile « Rétablir » intacte."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        piece_validee(doc)
        doc.undo()
        problemes: list[str] = []
        for bouton in (valider, annuler):
            editer(obj)
            bouton()
            nom = bouton.__name__
            problemes += [
                *ecarts(f"{nom} : annulations", doc.UndoNames, [CREATE]),
                *ecarts(f"{nom} : rétablissements", doc.RedoNames, [CREATE]),
                *ecarts(f"{nom} : pièce à jour", "Touched" in obj.State, False),
            ]
        return problemes

    return avec_document("VerifSansModification", verification)


def verifier_annuler_retablir_la_creation() -> list[str]:
    """C2 : la création validée s'annule puis se rétablit avec les valeurs du panneau."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        modifier_tout(formulaire())
        valider()
        nom, apres = obj.Name, valeurs(obj)
        doc.undo()
        problemes = ecarts("création annulée", doc.getObject(nom), None)
        doc.redo()
        doc.recompute()
        obj = doc.getObject(nom)
        return [
            *problemes,
            *ecarts("création rétablie", valeurs(obj), apres),
            *ecarts("volume rétabli", round(obj.Shape.Volume), 1000 * 250 * 27),
        ]

    return avec_document("VerifAnnulerCreation", verification)


def verifier_annuler_retablir_la_modification() -> list[str]:
    """C4 : l'entrée « Modifier » validée s'annule et se rétablit, forme et couleur comprises."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        modifier_tout(formulaire())
        valider()
        apres = valeurs(obj)
        doc.undo()
        problemes = [
            *ecarts("valeurs annulées", valeurs(obj), avant),
            *ecarts("volume annulé", round(obj.Shape.Volume), VOLUME_INITIAL),
        ]
        doc.redo()
        return [
            *problemes,
            *ecarts("valeurs rétablies", valeurs(obj), apres),
            *ecarts("volume rétabli", round(obj.Shape.Volume), 1000 * 250 * 27),
            *ecarts("rétablissements", doc.RedoNames, []),
        ]

    return avec_document("VerifAnnulerModification", verification)


def verifier_annuler_apres_une_annulation() -> list[str]:
    """C4 : « Annuler » n'ajoute aucune entrée, même juste après Édition > Annuler."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        editer(obj)
        saisir(formulaire().lengthEdit, 1000.0)
        valider()
        doc.undo()
        editer(obj)
        annuler()
        return [
            *ecarts("annulations", doc.UndoNames, [CREATE]),
            *ecarts("rétablissements", doc.RedoNames, [EDIT]),
        ]

    return avec_document("VerifAnnulerApresUndo", verification)


def verifier_std_undo_pendant_l_edition() -> list[str]:
    """C4 : « Annuler » rétablit les valeurs d'origine, même après Std_Undo dans le panneau."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        saisir(formulaire().lengthEdit, 1000.0)
        Gui.Command.get("Std_Undo").run()
        if Gui.Control.activeDialog():
            saisir(formulaire().widthEdit, 300.0)
            annuler()
        Gui.updateGui()  # suites différées de la fermeture du panneau
        return [
            *ecarts("valeurs d'origine", valeurs(obj), avant),
            *ecarts("transaction close", transaction_ouverte(), None),
            *ecarts("mode édition quitté", Gui.ActiveDocument.getInEdit(), None),
        ]

    return avec_document("VerifUndoPendantEdition", verification)


# --- Double-clic --------------------------------------------------------------------------


def verifier_double_clic_pendant_la_creation() -> list[str]:
    """Double-clic sur la pièce en cours de création : refusé, le panneau de création reste."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        saisir(formulaire().lengthEdit, 1000.0)
        problemes = [
            *ecarts("double-clic accepté", double_cliquer(obj), False),
            *ecarts("panneau de création", formulaire().windowTitle(), NOUVELLE),
            *ecarts("pièce en édition", Gui.ActiveDocument.getInEdit(), None),
        ]
        annuler()
        return [
            *problemes,
            *ecarts("pièces", len(doc.Objects), 0),
            *ecarts("entrées d'annulation", doc.UndoCount, 0),
        ]

    return avec_document("VerifDoubleClicCreation", verification)


def verifier_double_clic_sur_la_piece_en_edition() -> list[str]:
    """C4 : un second double-clic ne fait rien ; « Annuler » rétablit tout."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        saisir(formulaire().lengthEdit, 1000.0)
        double_cliquer(obj)
        annuler()
        return [
            *ecarts("valeurs d'origine", valeurs(obj), avant),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
        ]

    return avec_document("VerifDoubleClicEdition", verification)


def verifier_double_clic_sur_une_autre_piece() -> list[str]:
    """C4 : le double-clic sur une autre pièce est refusé ; « Annuler » rétablit la première."""

    def verification(doc: Any) -> list[str]:
        premiere, seconde = piece_validee(doc), piece_validee(doc)
        avant = valeurs(premiere)
        editer(premiere)
        saisir(formulaire().lengthEdit, 1000.0)
        accepte = double_cliquer(seconde)
        annuler()
        return [
            *ecarts("double-clic accepté", accepte, False),
            *ecarts("valeurs d'origine", valeurs(premiere), avant),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE, CREATE]),
        ]

    return avec_document("VerifDoubleClicAutre", verification)


def verifier_ouvertures_successives() -> list[str]:
    """Stabilité (enveloppes PySide réutilisées en 1.0) : 30 ouvertures, « OK » et « Annuler »
    en alternance ; chaque panneau s'ouvre et porte les bons widgets."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        problemes: list[str] = []
        for tour in range(30):
            if not double_cliquer(obj) or not Gui.Control.activeDialog():
                problemes.append(f"tour {tour} : panneau non ouvert")
                continue
            saisir(formulaire().lengthEdit, 900.0 + tour)
            (valider if tour % 2 else annuler)()
        return problemes + ecarts("longueur finale", obj.Length.Value, 929.0)

    return avec_document("VerifOuvertures", verification)


# --- Document fermé, pièce supprimée ------------------------------------------------------


def verifier_document_ferme_pendant_l_edition() -> list[str]:
    """Fermer le document pendant l'édition ferme le panneau sans transaction pendante."""
    doc = nouveau_document("VerifFermetureEdition")
    obj = piece_validee(doc)
    editer(obj)
    saisir(formulaire().lengthEdit, 1000.0)
    App.closeDocument(doc.Name)
    problemes = [
        *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
        *ecarts("transaction close", transaction_ouverte(), None),
    ]
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    return problemes + avec_document(
        "VerifApresFermeture",
        lambda _doc: ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
    )


def verifier_document_ferme_pendant_la_creation() -> list[str]:
    """Fermer le document pendant la création ferme le panneau (FreeCAD 1.0 plantait en
    détruisant les liaisons d'expression) ; la commande redevient active."""
    doc = nouveau_document("VerifFermetureCreation")
    creer_par_la_commande(doc)
    saisir(formulaire().lengthEdit, 1000.0)
    App.closeDocument(doc.Name)
    Gui.updateGui()  # suites différées de la fermeture
    problemes = [
        *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
        *ecarts("transaction close", transaction_ouverte(), None),
    ]
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    return problemes + avec_document(
        "VerifApresFermetureCreation",
        lambda _doc: ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
    )


def verifier_piece_supprimee_pendant_la_creation() -> list[str]:
    """Supprimer la pièce en création : suppression refusée ou panneau fermé."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        nom = obj.Name
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        Gui.runCommand("Std_Delete")
        supprimee = doc.getObject(nom) is None
        Gui.updateGui()  # suites différées de la fermeture du panneau
        return [
            *ecarts(
                "panneau ouvert sur une pièce supprimée",
                (supprimee and bool(Gui.Control.activeDialog())),
                False,
            ),
            *ecarts("transaction close", transaction_ouverte(), None),
            *ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
        ]

    return avec_document("VerifSuppressionCreation", verification)


# --- Matériau absent, bibliothèque vide, changement de Type -------------------------------


def verifier_materiau_absent_de_la_bibliotheque() -> list[str]:
    """C5 : matériau inconnu localement, libellé enregistré affiché, menu des épaisseurs
    inactif, aucun avertissement ; « Annuler » le rétablit, « OK » le garde."""
    from freecad.menuiserie.api import make_wood_part

    def verification(doc: Any) -> list[str]:
        with bibliotheque(None, ERABLE) as fichier:
            obj = make_wood_part(material_id="erable", doc=doc)
            fichier.unlink()
            library.reload_library()
        doc.recompute()
        avant = valeurs(obj)
        editer(obj)
        problemes = [
            *ecarts("matériau affiché", formulaire().materialCombo.currentData(), "erable"),
            *ecarts("menu actif", formulaire().standardThicknessButton.isEnabled(), False),
            *ecarts("avertissement masqué", formulaire().thicknessWarning.isHidden(), True),
            *libelle_affiche_par_type(obj),
        ]
        annuler()
        problemes += ecarts("valeurs rétablies", valeurs(obj), avant)
        editer(obj)
        saisir(formulaire().lengthEdit, 900.0)
        valider()
        return [
            *problemes,
            *ecarts("matériau gardé", (obj.MaterialId, obj.Material), ("erable", "Érable")),
            *ecarts("pièce valide", obj.isValid(), True),
        ]

    return avec_document("VerifMateriauAbsent", verification)


def verifier_bibliotheque_vide() -> list[str]:
    """Bibliothèque vide : la commande ne crée rien et ne laisse ni panneau ni transaction ;
    le panneau d'une pièce existante s'ouvre, un type vide ne la modifie pas, « OK » marche."""
    from freecad.menuiserie.api import make_wood_part

    def verification(doc: Any) -> list[str]:
        obj = make_wood_part(doc=doc)
        doc.recompute()
        with bibliotheque(Path(tempfile.mkdtemp()) / "absente.json"):
            Gui.Command.get(COMMAND).run()
            problemes = [
                *ecarts("pièces après la commande", len(doc.Objects), 1),
                *ecarts("panneau après la commande", Gui.Control.activeDialog(), False),
                *ecarts("transaction après la commande", transaction_ouverte(), None),
            ]
            avant = valeurs(obj)
            editer(obj)
            problemes += ecarts(
                "libellé affiché", formulaire().materialCombo.currentText(), "Chêne"
            )
            formulaire().kindCombo.setCurrentIndex(1)
            problemes += ecarts("pièce inchangée par un type vide", valeurs(obj), avant)
            formulaire().kindCombo.setCurrentIndex(0)
            saisir(formulaire().lengthEdit, 900.0)
            valider()
        return [
            *problemes,
            *ecarts("longueur validée", obj.Length.Value, 900.0),
            *ecarts("matériau gardé", obj.MaterialId, "chene"),
            *ecarts("entrées d'annulation", doc.UndoNames, [EDIT]),
        ]

    return avec_document("VerifBibliothequeVide", verification)


def verifier_changements_de_type() -> list[str]:
    """C5 : chaque type affiche le libellé de ``obj.Material`` ; « Annuler » rétablit tout ;
    le même parcours validé par « OK » donne une seule entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        problemes = libelle_affiche_par_type(obj)
        annuler()
        problemes += ecarts("valeurs rétablies", valeurs(obj), avant)
        editer(obj)
        libelle_affiche_par_type(obj)
        valider()
        return problemes + ecarts("entrées d'annulation", doc.UndoNames, [EDIT, CREATE])

    return avec_document("VerifTypes", verification)


# --- Enregistrement et réouverture --------------------------------------------------------


def verifier_reouverture_apres_le_panneau() -> list[str]:
    """Pièce réglée dans le panneau, enregistrée, rouverte : valeurs intactes, document non
    modifié, panneau rouvert avec ses valeurs, nouvelle modification annulable."""
    doc = nouveau_document("VerifReouverturePanneau")
    obj = creer_par_la_commande(doc)
    modifier_tout(formulaire())
    valider()
    nom, attendu = obj.Name, valeurs(obj)
    chemin = Path(tempfile.mkdtemp()) / f"{doc.Name}.FCStd"
    doc.saveAs(str(chemin))
    App.closeDocument(doc.Name)
    doc = App.openDocument(str(chemin))
    doc.UndoMode = 1
    try:
        obj = doc.getObject(nom)
        problemes = [
            *ecarts("valeurs rouvertes", valeurs(obj), attendu),
            *ecarts("document modifié", Gui.getDocument(doc.Name).Modified, False),
        ]
        editer(obj)
        problemes += [
            *ecarts("longueur affichée", valeur(formulaire().lengthEdit), 1000.0),
            *ecarts("matériau affiché", formulaire().materialCombo.currentData(), "hetre"),
        ]
        saisir(formulaire().widthEdit, 300.0)
        valider()
        problemes += ecarts("entrées d'annulation", doc.UndoNames, [EDIT])
        doc.undo()
        return problemes + ecarts("largeur annulée", obj.Width.Value, 250.0)
    finally:
        App.closeDocument(doc.Name)


# --- C6 : expressions ---------------------------------------------------------------------


def verifier_expression_sur_une_surcote() -> list[str]:
    """C6 : surcote pilotée par une expression, affichée par le champ et conservée ; la valeur
    suit une cote modifiée dans le panneau et un changement de matériau ne l'écrit pas."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("LengthAllowance", "Length / 40")
        doc.recompute()
        editer(obj)
        champ = formulaire().lengthAllowanceEdit.property("expression")
        problemes = ecarts("expression affichée", champ, "Length / 40")
        choisir(formulaire().materialCombo, "mdf")
        saisir(formulaire().lengthEdit, 1000.0)
        valider()
        doc.recompute()
        return [
            *problemes,
            *ecarts(
                "expression conservée",
                dict(obj.ExpressionEngine),
                {"LengthAllowance": "Length / 40"},
            ),
            *ecarts("surcote recalculée", obj.LengthAllowance.Value, 25.0),
            *ecarts("matériau", obj.MaterialId, "mdf"),
        ]

    return avec_document("VerifExpressionSurcote", verification)


def verifier_cotes_pilotees_jamais_ecrites() -> list[str]:
    """C6 : saisie dans un champ piloté et épaisseur standard du menu : rien n'est écrit."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("Length", "Width * 4")
        obj.setExpression("Thickness", "Width / 10")
        doc.recompute()
        editer(obj)
        with ecritures(obj) as ecrites:
            saisir(formulaire().lengthEdit, 1234.0)
            saisir(formulaire().thicknessEdit, 18.0)
            for action in formulaire().standardThicknessButton.menu().actions():
                action.trigger()
        valider()
        return [
            *ecarts("cotes écrites", sorted({"Length", "Thickness"} & set(ecrites)), []),
            *ecarts("expressions", sorted(dict(obj.ExpressionEngine)), ["Length", "Thickness"]),
            *ecarts("cotes", (obj.Length.Value, obj.Thickness.Value), (800.0, 20.0)),
        ]

    return avec_document("VerifCotesPilotees", verification)


def champ_pilote_inactif_et_jamais_ecrit(
    prop: str, expression: str, action: Callable[[Any], None], widget: str
) -> Verification:
    """C6 : ``prop`` pilotée par ``expression`` ; widget inactif, ``action`` n'écrit rien."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.GrainDirection = "Width"
        obj.setExpression(prop, expression)
        doc.recompute()
        editer(obj)
        actif = getattr(formulaire(), widget).isEnabled()
        with ecritures(obj) as ecrites:
            action(formulaire())
        valider()
        return [
            *ecarts(f"{widget} actif", actif, False),
            *ecarts(f"propriétés écrites par le panneau ({prop})", ecrites, []),
            *ecarts("expression conservée", prop in dict(obj.ExpressionEngine), True),
        ]

    return lambda: avec_document(f"VerifPilote{prop}", verification)


def _taper_un_repere(form: Any) -> None:
    form.markEdit.selectAll()
    form.markEdit.insert("X")  # émet textEdited, comme une frappe


def verifier_repere_pilote() -> list[str]:
    return champ_pilote_inactif_et_jamais_ecrit("Mark", "Label", _taper_un_repere, "markEdit")()


def verifier_fil_pilote() -> list[str]:
    return champ_pilote_inactif_et_jamais_ecrit(
        "GrainDirection",
        "<<Width>>",
        lambda form: choisir(form.grainCombo, "Length"),
        "grainCombo",
    )()


def verifier_materiau_pilote() -> list[str]:
    return champ_pilote_inactif_et_jamais_ecrit(
        "Material",
        "<<Hêtre>>",
        lambda form: choisir(form.materialCombo, "mdf"),
        "materialCombo",
    )()


VERIFICATIONS_LIMITES: tuple[Verification, ...] = (
    verifier_saisies_et_refus,
    verifier_recalcul_de_chaque_cote,
    verifier_titre_avec_un_libelle_particulier,
    verifier_ok_et_annuler_sans_modification,
    verifier_annuler_retablir_la_creation,
    verifier_annuler_retablir_la_modification,
    verifier_annuler_apres_une_annulation,
    verifier_std_undo_pendant_l_edition,
    verifier_double_clic_pendant_la_creation,
    verifier_double_clic_sur_la_piece_en_edition,
    verifier_double_clic_sur_une_autre_piece,
    verifier_ouvertures_successives,
    verifier_document_ferme_pendant_l_edition,
    verifier_document_ferme_pendant_la_creation,
    verifier_piece_supprimee_pendant_la_creation,
    verifier_materiau_absent_de_la_bibliotheque,
    verifier_bibliotheque_vide,
    verifier_changements_de_type,
    verifier_reouverture_apres_le_panneau,
    verifier_expression_sur_une_surcote,
    verifier_cotes_pilotees_jamais_ecrites,
    verifier_repere_pilote,
    verifier_fil_pilote,
    verifier_materiau_pilote,
)
