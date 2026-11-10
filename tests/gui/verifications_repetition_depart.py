# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : face de la pièce répétée choisie comme point de départ, essai
automatique de « Déduire l'épaisseur de la pièce » (retours de jv, 2026-11-10).

Module importé par ``verifier_atelier.py`` : clics simulés par la sélection de FreeCAD.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App

from freecad.menuiserie import api
from tests.gui.verifications_ensemble import lancer
from tests.gui.verifications_panneau import avec_document, ecarts, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_repetition import REPETER, panneau, source
from tests.gui.verifications_repetition_butee import cliquer_dans_la_vue


def piece(doc: Any, mark: str, size: tuple[float, float, float], where: tuple[float, ...]) -> Any:
    part = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
    part.Placement = App.Placement(App.Vector(*where), App.Rotation())
    doc.recompute()
    return part


def face(part: Any, axis: str, value: float) -> str:
    """Face plane de ``part`` perpendiculaire à ``axis``, à la coordonnée ``value``."""
    for index, element in enumerate(part.Shape.Faces, start=1):
        box = element.BoundBox
        if getattr(box, f"{axis}Min") == getattr(box, f"{axis}Max") == value:
            return f"Face{index}"
    raise AssertionError((axis, value))


def _depart(doc: Any) -> list[str]:
    barreau = source(doc)  # 300 x 40 x 22, de X = 0 à 300, de Y = 0 à 40
    mur = piece(doc, "MurY", (300, 20, 100), (0, 500, 0))
    lancer(REPETER, barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    widget(form, "stopX").click()
    cliquer_dans_la_vue(doc, barreau, face(barreau, "Y", 40.0))  # face de la pièce répétée
    actifs = [widget(form, f"axis{a}").isChecked() for a in "XYZ"]
    problemes = [
        *ecarts("départ : axe Y seul actif", actifs, [False, True, False]),
        *ecarts(
            "départ : pas de butée", widget(form, "stopNameY").text().startswith("MurY"), False
        ),
        *ecarts("départ : butée encore à choisir", widget(form, "stopY").isDown(), True),
        *ecarts("départ : pas de refus", widget(form, "errorLabel").text(), ""),
    ]
    cliquer_dans_la_vue(doc, mur, face(mur, "Y", 500.0))
    rep = doc.getObject("Repeat")
    problemes += [
        *ecarts("butée sur Y", widget(form, "stopNameY").text().startswith("MurY"), True),
        *ecarts("longueur jusqu'au mur", round(rep.Span2.Value or rep.Span.Value, 3), 500.0),
    ]
    widget(form, "endGap").setChecked(True)  # 2 éléments : 2 intervalles de 250
    problemes += [
        *ecarts(
            "intervalle : déduction grisée", widget(form, "deductThickness").isEnabled(), False
        ),
        *ecarts("intervalle : pas de 250", round(rep.Step.Value, 3), 250.0),
    ]
    valider()
    return problemes + ecarts("intervalle enregistré", doc.getObject("Repeat").EndGap, True)


def verifier_face_de_la_piece_repetee_comme_depart() -> list[str]:
    """Une face de la pièce répétée cliquée comme butée donne l'axe ; la butée reste à choisir."""
    return avec_document("VerifButeeDepart", _depart)


def case(form: Any) -> bool:
    return bool(widget(form, "deductThickness").isChecked())


def choisir_sur_x(doc: Any, form: Any, part: Any, x: float) -> None:
    """Butée de l'axe X choisie : retrait de l'ancienne, case cochée, bouton puis clic."""
    widget(form, "stopClearX").click()
    widget(form, "deductThickness").setChecked(True)
    widget(form, "stopX").click()
    cliquer_dans_la_vue(doc, part, face(part, "X", x))


def _essai_epaisseur(doc: Any) -> list[str]:
    barreau = source(doc)  # 300 mm sur X
    proche = piece(doc, "Proche", (20, 40, 22), (250, 100, 0))  # face X = 250 : dans la pièce
    loin = piece(doc, "Loin", (20, 40, 22), (450, 100, 0))
    lancer(REPETER, barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    choisir_sur_x(doc, form, proche, 250.0)
    problemes = [
        *ecarts("trop proche : case décochée", case(form), False),
        *ecarts("trop proche : plus de refus", widget(form, "errorLabel").text(), ""),
    ]
    choisir_sur_x(doc, form, loin, 450.0)  # 2 éléments : pas de 150 (chevauchement) ou de 450
    rep = doc.getObject("Repeat")
    problemes += [
        *ecarts("chevauchement corrigé : case décochée", case(form), False),
        *ecarts("chevauchement corrigé : pas", round(rep.Step.Value, 3), 450.0),
    ]
    widget(form, "countX").setValue(3)  # pas de 75 ou de 225 : chevauchement des deux façons
    choisir_sur_x(doc, form, loin, 450.0)
    problemes += [
        *ecarts("chevauchement des deux façons : case revenue", case(form), True),
        *ecarts("avertissement gardé", bool(widget(form, "warningLabel").text()), True),
    ]
    valider()
    return problemes


def verifier_essai_de_la_deduction_d_epaisseur() -> list[str]:
    """Butée trop proche : la case passe décochée ; chevauchement dans les deux états : elle
    revient et l'avertissement reste."""
    return avec_document("VerifButeeEpaisseur", _essai_epaisseur)


VERIFICATIONS_REPETITION_DEPART: tuple[Callable[[], list[str]], ...] = (
    verifier_face_de_la_piece_repetee_comme_depart,
    verifier_essai_de_la_deduction_d_epaisseur,
)
