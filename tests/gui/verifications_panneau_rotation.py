# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des champs d'angle du panneau de la pièce de bois (RO-c, critères C1
à C6 de ``docs/specs/rotation-d-une-piece.md``, ADR 0025).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Leçons de l'interface
hors écran : aucun clic Qt réel (les champs sont écrits par leurs propriétés, la fin de saisie est
l'émission du signal ``editingFinished``, la fenêtre de choix des assemblages est remplacée par
``joint_choice.chooser``) ; l'atelier et la vue 3D du document sont réactivés avant usage
(:func:`preparer`) ; aucun formulaire n'est gardé après la fermeture du panneau.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any

import FreeCAD as App
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.task_panels import angle_rows, wood_part
from tests.gui.aides_panneau import ecritures
from tests.gui.verifications_apercu import cliquer
from tests.gui.verifications_assemblages import cadre
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    ouvrir_par_double_clic,
    saisir,
    valeur,
)
from tests.gui.verifications_panneau_assemblage import tenon_valide
from tests.gui.verifications_panneau_ensemble import bureau_regroupe
from tests.gui.verifications_souris import preparer

CHAMPS = ("angleXEdit", "angleYEdit", "angleZEdit")
ETIQUETTES = ("Autour de X", "Autour de Y", "Autour de Z")
PILOTE_PAR_L_ENSEMBLE = "Position pilotée par l'ensemble"
PILOTE_PAR_UNE_FORMULE = "Position pilotée par une formule"
TOLERANCE = 1e-6
Angles = tuple[float, float, float]


# --- Aides -----------------------------------------------------------------------------------


def angles_de(piece: Any) -> Angles:
    """Angles X, Y, Z (degrés) du ``Placement`` de ``piece``."""
    lacet, tangage, roulis = piece.Placement.Rotation.getYawPitchRoll()
    return (roulis, tangage, lacet)


def champs(form: Any) -> Angles:
    """Valeurs des trois champs d'angle."""
    x, y, z = (valeur(getattr(form, nom)) for nom in CHAMPS)
    return (x, y, z)


def proches(nom: str, obtenu: Iterable[float], attendu: Iterable[float]) -> list[str]:
    """Écart entre deux listes de nombres, à ``TOLERANCE`` près."""
    a, b = list(obtenu), list(attendu)
    if len(a) == len(b) and all(abs(x - y) <= TOLERANCE for x, y in zip(a, b, strict=True)):
        return []
    return [f"{nom} : {a!r} au lieu de {b!r}"]


def centre(piece: Any) -> list[float]:
    """Centre de la boîte de la brute, dans le repère du document."""
    c = piece.Placement.multVec(
        App.Vector(piece.Length.Value / 2, piece.Width.Value / 2, piece.Thickness.Value / 2)
    )
    return [c.x, c.y, c.z]


def saisir_angle(form: Any, nom: str, degres: float) -> None:
    """Saisie d'un angle : ``valueChanged`` est émis par le champ."""
    saisir(getattr(form, nom), degres)


def fin_de_saisie(form: Any, nom: str) -> None:
    """Fin de saisie du champ ``nom`` (focus perdu, Entrée) : émet ``editingFinished``."""
    QtCore.QMetaObject.invokeMethod(getattr(form, nom), "editingFinished")
    QtGui.QApplication.processEvents()


def nouvelle_piece(doc: Any, angles: Angles = (0.0, 0.0, 0.0)) -> Any:
    """Pièce de chêne 800 x 200 x 22, tournée de ``angles``, atelier et vue 3D actifs."""
    preparer(doc)
    piece = api.make_wood_part(800.0, 200.0, 22.0, "chene", doc=doc)
    x, y, z = angles
    piece.Placement = App.Placement(App.Vector(100, 50, 0), App.Rotation(z, y, x))
    doc.recompute()
    return piece


@contextmanager
def apercus_comptes() -> Iterator[list[int]]:
    """Compteur des aperçus de la brute (recalculs par ``recompute_blank``) pendant le bloc."""
    compteur = [0]
    original = angle_rows.recompute_blank

    def compter(brute: Any) -> None:
        compteur[0] += 1
        original(brute)

    angle_rows.recompute_blank = compter  # type: ignore[assignment]
    try:
        yield compteur
    finally:
        angle_rows.recompute_blank = original  # type: ignore[assignment]


def nomme(layouts: Iterable[Any]) -> list[str]:
    return [item.layout().objectName() for item in layouts if item.layout() is not None]


# --- C1, C6 : les champs -----------------------------------------------------------------------


def verifier_champs_d_angle() -> list[str]:
    """C1, C6 : trois champs en degrés de -180 à 180, étiquettes « Autour de X/Y/Z » sous les
    boutons de quart de tour, valeurs relues dans le ``Placement`` (ici 15° autour de Z)."""

    def verification(doc: Any) -> list[str]:
        piece = nouvelle_piece(doc, (0.0, 0.0, 15.0))
        form = ouvrir_par_double_clic(piece)
        if form is None:
            return ["panneau non ouvert"]
        groupe = form.rotationGroup.layout()
        sous_dispositions = nomme(groupe.itemAt(i) for i in range(groupe.count()))
        problemes = [
            *ecarts(
                "étiquettes",
                [form.findChild(QtGui.QLabel, n.replace("Edit", "Label")).text() for n in CHAMPS],
                list(ETIQUETTES),
            ),
            *ecarts(
                "boutons puis champs", sous_dispositions[:2], ["rotationLayout", "angleLayout"]
            ),
            *proches("valeurs affichées", champs(form), (0.0, 0.0, 15.0)),
        ]
        for nom in CHAMPS:
            champ = getattr(form, nom)
            problemes += proches(
                f"{nom} bornes et pas",
                [float(champ.property(p)) for p in ("minimum", "maximum", "singleStep")],
                (-180.0, 180.0, 1.0),
            )
            decimales = champ.property("decimals")
            if decimales is not None:
                problemes += ecarts(f"{nom} décimales", decimales, 1)
            problemes += ecarts(f"{nom} actif", champ.isEnabled(), True)
        return problemes

    return avec_document("VerifAnglesChamps", verification)


# --- C2 : saisie en direct ---------------------------------------------------------------------


def verifier_saisie_en_direct() -> list[str]:
    """C2 : une saisie tourne la pièce autour de son centre et montre la brute aussitôt, sans
    contrôle des assemblages ni recalcul du document ; au plus 30 aperçus par seconde, le dernier
    angle saisi toujours montré."""

    def verification(doc: Any) -> list[str]:
        piece = nouvelle_piece(doc)
        form = ouvrir_par_double_clic(piece)
        avant = centre(piece)
        questions: list[Any] = []

        def accepter(libelles: Any) -> bool:
            questions.append(list(libelles))
            return True

        original, joint_choice.chooser = joint_choice.chooser, accepter
        try:
            saisir_angle(form, "angleZEdit", 15.0)
            problemes = [
                *proches("angles écrits", angles_de(piece), (0.0, 0.0, 15.0)),
                *proches("centre fixe", centre(piece), avant),
                *proches(
                    "aperçu de la brute",
                    piece.Shape.Placement.Rotation.getYawPitchRoll(),
                    (15.0, 0.0, 0.0),
                ),
                *ecarts("aucun contrôle avant la fin de saisie", questions, []),
            ]
            with apercus_comptes() as apercus:
                debut = time.monotonic()
                for degres in range(1, 41):
                    saisir_angle(form, "angleYEdit", float(degres) / 2)
                duree = time.monotonic() - debut
                attente = time.monotonic()
                while time.monotonic() - attente < 1.0:
                    QtGui.QApplication.processEvents()
                        problemes += ecarts("dernier angle écrit", round(angles_de(piece)[1], 6), 20.0)
            problemes += proches(
                "dernier angle montré",
                piece.Shape.Placement.Rotation.getYawPitchRoll(),
                piece.Placement.Rotation.getYawPitchRoll(),
            )
            if not 1 <= apercus[0] <= duree * 30 + 2:
                problemes.append(f"cadence : {apercus[0]} aperçus en {duree:.3f} s (30/s au plus)")
        finally:
            joint_choice.chooser = original
        return problemes

    return avec_document("VerifAnglesDirect", verification)


# --- C2 : fin de saisie et assemblages ---------------------------------------------------------


def _fin_de_saisie_avec_assemblage(nom: str, supprimer: bool) -> list[str]:
    with cadre(nom) as (doc, pieces):
        preparer(doc)
        nom_assemblage = tenon_valide(doc, pieces).Name
        traverse = pieces["T1"]
        depart = angles_de(traverse)
        wood_part.start_editing(traverse)
        form = formulaire()
        questions: list[Any] = []

        def choisir(libelles: Any) -> bool:
            questions.append(list(libelles))
            return supprimer

        original, joint_choice.chooser = joint_choice.chooser, choisir
        try:
            saisir_angle(form, "angleZEdit", depart[2] + 30.0)
            problemes = ecarts("pas de fenêtre pendant la saisie", questions, [])
            fin_de_saisie(form, "angleZEdit")
        finally:
            joint_choice.chooser = original
        problemes += ecarts("fenêtre ouverte une fois", len(questions), 1)
        gardee = doc.getObject(nom_assemblage) is not None
        attendu = (depart[0], depart[1], depart[2] + 30.0) if supprimer else depart
        return [
            *problemes,
            *ecarts("assemblage gardé", gardee, not supprimer),
            *proches("angles de la pièce", angles_de(traverse), attendu),
            *proches("champs relus", champs(form), attendu),
        ]


def verifier_fin_de_saisie_annulee() -> list[str]:
    """C2 : la rotation défait le tenon ; « Annuler » remet l'angle d'avant la saisie (pièce,
    champs) et garde l'assemblage."""
    return _fin_de_saisie_avec_assemblage("VerifAnglesAnnule", supprimer=False)


def verifier_fin_de_saisie_supprimee() -> list[str]:
    """C2 : « Supprimer l'assemblage » garde l'angle saisi et retire l'assemblage."""
    return _fin_de_saisie_avec_assemblage("VerifAnglesSupprime", supprimer=True)


# --- C3 : relecture des champs ----------------------------------------------------------------


def verifier_champs_relus() -> list[str]:
    """C3 : un quart de tour, puis un changement du ``Placement`` signalé par la session (comme un
    glissement ou un anneau) font relire les champs ; la relecture n'écrit rien (signaux
    bloqués : pas de boucle)."""

    def verification(doc: Any) -> list[str]:
        piece = nouvelle_piece(doc)
        session = preparer(doc)
        form = ouvrir_par_double_clic(piece)
        cliquer(form, "rotateXButton")
        problemes = [
            *proches("quart de tour : angles", angles_de(piece), (90.0, 0.0, 0.0)),
            *proches("quart de tour : champs", champs(form), (90.0, 0.0, 0.0)),
        ]
        piece.Placement = App.Placement(piece.Placement.Base, App.Rotation(20.0, 0.0, 30.0))
        with ecritures(piece) as proprietes:
            session.panel.refresh()
        return [
            *problemes,
            *proches("relecture : champs", champs(form), (30.0, 0.0, 20.0)),
            *ecarts("relecture : aucune écriture", proprietes, []),
            *proches("relecture : angles intacts", angles_de(piece), (30.0, 0.0, 20.0)),
        ]

    return avec_document("VerifAnglesRelus", verification)


# --- C4 : position pilotée ---------------------------------------------------------------------


def _grises(form: Any, raison: str) -> list[str]:
    problemes: list[str] = []
    for nom in (*CHAMPS, "rotateXButton", "rotateYButton", "rotateZButton"):
        problemes += ecarts(f"{nom} grisé", getattr(form, nom).isEnabled(), False)
    for nom in CHAMPS:
        problemes += ecarts(f"{nom} infobulle", getattr(form, nom).toolTip(), raison)
    return problemes


def verifier_position_pilotee_par_une_formule() -> list[str]:
    """C4 : une formule sur le ``Placement`` grise champs et boutons ; l'infobulle des champs dit
    « Position pilotée par une formule »."""

    def verification(doc: Any) -> list[str]:
        piece = nouvelle_piece(doc)
        piece.setExpression("Placement.Base.x", "100 mm")
        doc.recompute()
        form = ouvrir_par_double_clic(piece)
        return _grises(form, PILOTE_PAR_UNE_FORMULE)

    return avec_document("VerifAnglesFormule", verification)


def verifier_position_pilotee_par_l_ensemble() -> list[str]:
    """C4 : un membre d'ensemble dont l'ensemble pilote le ``Placement`` : champs et boutons
    grisés, « Position pilotée par l'ensemble »."""
    with bureau_regroupe("VerifAnglesEnsemble") as bureau:
        preparer(bureau.doc)
        wood_part.start_editing(bureau.parts["V"])
        form = formulaire()
        if form is None:
            return ["panneau non ouvert"]
        problemes = _grises(form, PILOTE_PAR_L_ENSEMBLE)
        annuler()
        return problemes


# --- C5 : création -----------------------------------------------------------------------------


def verifier_creation_accrochage() -> list[str]:
    """C5 : en création, un quart de tour garde l'accrochage (la pièce reste reposée) ; une
    saisie d'angle l'arrête : l'angle saisi reste, la pièce n'est plus ramenée à sa pose."""

    def verification(doc: Any) -> list[str]:
        preparer(doc)
        piece = creer_par_la_commande(doc)
        form = formulaire()
        cliquer(form, "rotateXButton")
        problemes = proches("bouton : angles", angles_de(piece), (90.0, 0.0, 0.0))
        problemes += proches("bouton : champs", champs(form), (90.0, 0.0, 0.0))
        saisir_angle(form, "angleZEdit", 15.0)
        fin_de_saisie(form, "angleZEdit")
        return [
            *problemes,
            *proches("saisie : angle gardé", angles_de(piece)[2:], (15.0,)),
            *proches("saisie : champs", champs(form)[2:], (15.0,)),
        ]

    return avec_document("VerifAnglesCreation", verification)


VERIFICATIONS_PANNEAU_ROTATION: tuple[Callable[[], list[str]], ...] = (
    verifier_champs_d_angle,
    verifier_saisie_en_direct,
    verifier_fin_de_saisie_annulee,
    verifier_fin_de_saisie_supprimee,
    verifier_champs_relus,
    verifier_position_pilotee_par_une_formule,
    verifier_position_pilotee_par_l_ensemble,
    verifier_creation_accrochage,
)
