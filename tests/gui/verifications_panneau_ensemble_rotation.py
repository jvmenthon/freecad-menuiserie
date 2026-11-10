# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des champs d'angle du panneau de l'ensemble et de la case « Cotes
fixes » d'un sous-ensemble (EN-d, ADR 0038, critères D1 et D2, question Q7).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Les champs sont
manipulés comme par l'utilisateur, par leurs propriétés et signaux Qt ; un geste dans la vue 3D
est simulé par les méthodes de la session (jamais de vrai clic ni de ``QCursor.setPos``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
from PySide import QtCore, QtGui

from freecad.menuiserie.features.furniture_drag import rotate_furniture_to
from tests.gui.verifications_ensemble import pieces_du_bureau
from tests.gui.verifications_panneau import annuler, ecarts, saisir, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_panneau_ensemble import MODIFIER, bureau_regroupe, ouvrir
from tests.gui.verifications_souris import preparer, proche, selection_dessinee
from tests.gui.verifications_souris_ensemble import (
    bureau_et_caisson,
    centre,
    cotes,
    lacet,
    std_de,
)
from tests.gui.verifications_souris_rotation import saisir_anneau, tourner_de, vue_isometrique

ANGLES = ("angleXEdit", "angleYEdit", "angleZEdit")


def fin_de_saisie(form: Any, nom: str) -> None:
    """Fin de saisie du champ ``nom`` (focus perdu, Entrée) : émet ``editingFinished``."""
    QtCore.QMetaObject.invokeMethod(widget(form, nom), "editingFinished")
    QtGui.QApplication.processEvents()


def angles(form: Any) -> list[float]:
    return [round(float(widget(form, nom).property("rawValue")), 3) for nom in ANGLES]


# --- D1 : trois champs d'angle ---------------------------------------------------------------


def verifier_panneau_ensemble_champs_d_angle() -> list[str]:
    """D1 : trois champs de -360 à 360, qui tournent l'ensemble autour du centre de sa boîte, forme
    canonique recalculée en fin de saisie, « Annuler » rétablit, « OK » : une seule entrée."""
    with bureau_regroupe("VerifPanneauEnsembleAngles") as bureau:
        ensemble, doc = bureau.furniture, bureau.doc
        avant = centre(ensemble)
        form = ouvrir(ensemble)
        if form is None:
            return ["panneau non ouvert"]
        bornes = [
            [float(widget(form, nom).property(p)) for p in ("minimum", "maximum")] for nom in ANGLES
        ]
        problemes = [
            *ecarts("bornes", bornes, [[-360.0, 360.0]] * 3),
            *ecarts("champs actifs", [widget(form, n).isEnabled() for n in ANGLES], [True] * 3),
            *ecarts("angles de départ", angles(form), [0.0, 0.0, 0.0]),
        ]
        saisir(widget(form, "angleZEdit"), 30.0)
        problemes += [
            *proche("l'ensemble tourne de 30°", lacet(ensemble), 30.0, 1e-6),
            *ecarts("centre immobile", centre(ensemble), avant),
            *ecarts("cotes inchangées", cotes(ensemble), (1200.0, 600.0, 750.0)),
        ]
        saisir(widget(form, "angleZEdit"), 270.0)
        problemes += ecarts("270° saisi", angles(form), [0.0, 0.0, 270.0])
        fin_de_saisie(form, "angleZEdit")
        problemes += [
            *ecarts("forme canonique en fin de saisie", angles(form), [0.0, 0.0, -90.0]),
            *proche("même orientation", lacet(ensemble), -90.0, 1e-6),
        ]
        annuler()
        problemes += proche("« Annuler » rétablit l'orientation", lacet(ensemble), 0.0, 1e-6)
        form = ouvrir(ensemble)
        saisir(widget(form, "angleXEdit"), 45.0)
        saisir(widget(form, "angleYEdit"), -20.0)
        fin_de_saisie(form, "angleYEdit")
        gardes = angles(form)
        valider()
        return [
            *problemes,
            *ecarts("deux axes tournés", [round(a, 1) for a in gardes], [45.0, -20.0, 0.0]),
            *ecarts("« OK » : une seule entrée", doc.UndoNames, [MODIFIER]),
            *ecarts("centre immobile après « OK »", centre(ensemble), avant),
        ]


def _anneau_relu(bureau: Any) -> list[str]:
    """Un anneau tire l'ensemble de 45° : les champs d'angle et la largeur relisent la valeur."""
    ensemble = bureau.furniture
    session = preparer(bureau.doc)
    vue_isometrique()
    selection_dessinee(ensemble)
    form = ouvrir(ensemble)
    if form is None:
        return ["panneau non ouvert"]
    _, depart = saisir_anneau(session, 2)
    arrivee = tourner_de(session, 2, 45.0, depart)
    relus = angles(form)
    session.release(arrivee)
    problemes = [
        *proche("anneau : champ Z relu", relus[2], 45.0, 0.01),
        *ecarts("anneau : champs X et Y", relus[:2], [0.0, 0.0]),
        *proche("anneau : champ Z relu au relâchement", angles(form)[2], 45.0, 0.01),
    ]
    annuler()
    return problemes


def verifier_panneau_ensemble_angle_relu_apres_un_geste() -> list[str]:
    """D2 : un geste dans la vue 3D (anneau) fait relire les champs d'angle du panneau ouvert."""
    with bureau_regroupe("VerifPanneauEnsembleRelu") as bureau:
        return _anneau_relu(bureau)


# --- D1 : champs grisés ----------------------------------------------------------------------


def _grises(form: Any) -> tuple[list[bool], str]:
    return (
        [widget(form, n).isEnabled() for n in ANGLES],
        " ".join(widget(form, n).toolTip() for n in ANGLES),
    )


def verifier_panneau_ensemble_champs_d_angle_grises() -> list[str]:
    """D1 : champs grisés, avec la raison en infobulle, pour un sous-ensemble lié par son parent et
    pour un ensemble sans Std Part propre ; ``rotate_furniture_to`` refuse alors sans rien
    écrire."""
    with pieces_du_bureau("VerifPanneauEnsembleGrises") as bureau:
        bureau_ens, caisson = bureau_et_caisson(bureau)
        form = ouvrir(caisson)
        etats, infobulles = _grises(form)
        avant = App.Placement(std_de(caisson).Placement)
        problemes = [
            *ecarts("sous-ensemble : champs grisés", etats, [False] * 3),
            *ecarts("sous-ensemble : raison en infobulle", "parent" in infobulles, True),
            *ecarts(
                "sous-ensemble : rotate_furniture_to refuse",
                rotate_furniture_to(caisson, (0, 0, 10)),
                False,
            ),
            *ecarts("sous-ensemble : rien d'écrit", std_de(caisson).Placement == avant, True),
        ]
        annuler()
        form = ouvrir(bureau_ens)
        etats, _ = _grises(form)
        problemes += ecarts("ensemble du sous-ensemble : champs actifs", etats, [True] * 3)
        annuler()
        etranger = bureau.doc.addObject("Part::Box", "Etranger")
        std_de(bureau_ens).addObject(etranger)
        form = ouvrir(bureau_ens)
        etats, infobulles = _grises(form)
        annuler()
        return [
            *problemes,
            *ecarts("sans Std Part propre : champs grisés", etats, [False] * 3),
            *ecarts("sans Std Part propre : raison", "Std Part" in infobulles, True),
        ]


# --- Q7 : « Cotes fixes » d'un sous-ensemble -------------------------------------------------


def verifier_panneau_ensemble_cotes_fixes_du_sous_ensemble() -> list[str]:
    """Q7 : la case « Cotes fixes » apparaît dans le panneau d'un sous-ensemble membre (pas dans
    celui du bureau) et s'écrit dans ``Locked`` : le parent refuse alors de changer de cote
    (le sous-ensemble garde ses cotes), tandis que décochée il suit."""
    with pieces_du_bureau("VerifPanneauEnsembleCotesFixes") as bureau:
        bureau_ens, caisson = bureau_et_caisson(bureau)
        form = ouvrir(bureau_ens)
        problemes = ecarts(
            "ensemble seul : pas de case", widget(form, "furnitureLockedCheck").isHidden(), True
        )
        saisir(widget(form, "Width"), 1400.0)
        problemes += ecarts("décoché : le sous-ensemble suit", round(caisson.Width.Value), 1378)
        annuler()
        form = ouvrir(caisson)
        case = widget(form, "furnitureLockedCheck")
        problemes += [
            *ecarts("sous-ensemble : case visible", case.isHidden(), False),
            *ecarts("sous-ensemble : décochée", case.isChecked(), False),
        ]
        case.setChecked(True)
        problemes += ecarts("case écrite dans Locked", bool(caisson.Locked), True)
        valider()
        largeur = round(caisson.Width.Value, 3)
        form = ouvrir(bureau_ens)
        saisir(widget(form, "Width"), 1400.0)
        refus = widget(form, "refusalLabel").text()
        problemes += [
            *ecarts("verrouillé : le parent n'est pas élargi", bureau_ens.Width.Value, 1200.0),
            *ecarts("verrouillé : le refus nomme le caisson", "« Caisson »" in refus, True),
            *ecarts("verrouillé : cotes gardées", round(caisson.Width.Value, 3), largeur),
        ]
        annuler()
        form = ouvrir(caisson)
        problemes += ecarts(
            "case relue cochée", widget(form, "furnitureLockedCheck").isChecked(), True
        )
        annuler()
        return problemes


VERIFICATIONS_PANNEAU_ENSEMBLE_ROTATION: tuple[Callable[[], list[str]], ...] = (
    verifier_panneau_ensemble_champs_d_angle,
    verifier_panneau_ensemble_angle_relu_apres_un_geste,
    verifier_panneau_ensemble_champs_d_angle_grises,
    verifier_panneau_ensemble_cotes_fixes_du_sous_ensemble,
)
