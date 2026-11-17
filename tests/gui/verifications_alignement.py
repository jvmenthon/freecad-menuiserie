# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de « Aligner deux faces » (ADR 0054, 0066) : grisage sur un axe et
grille « Parallèle et aligner sur ».

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque
vérification renvoie la liste de ses problèmes. Les faces sont sélectionnées par script, aucun
clic de souris.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtGui

from tests.gui.verifications_distance import avec_document, piece, selectionner
from tests.gui.verifications_panneau import ecarts, formulaire_nomme, valider

COMMANDE = "Menuiserie_AlignFaces"
FORM = "AlignTaskPanel"


def ouvrir(doc: Any) -> tuple[Any, Any]:
    """Plateau (dessous à 700) et cale (dessus à 122, plus petite et décalée) : faces
    sélectionnées, commande lancée ; renvoie la cale (déplacée) et le formulaire."""
    plateau = piece(doc, (800, 200, 22), (0, 0, 700), "Plateau")
    cale = piece(doc, (100, 100, 22), (300, 40, 100), "Cale")
    selectionner((plateau, "Face", (400, 100, 700)), (cale, "Face", (350, 90, 122)))
    doc.clearUndos()
    Gui.Command.get(COMMANDE).run()
    return cale, formulaire_nomme(FORM)


def base(obj: Any) -> tuple[float, float, float]:
    point = obj.Placement.Base
    return (round(point.x, 3), round(point.y, 3), round(point.z, 3))


def verifier_grisage_sur_un_axe() -> list[str]:
    """Sur un axe, la position et les deux décalages dans le plan sont grisés ; « Libre » les
    rend."""

    def verification(doc: Any) -> list[str]:
        _cale, form = ouvrir(doc)
        if form is None:
            return ["panneau absent"]
        axe = form.findChild(QtGui.QComboBox, "axisCombo")
        actifs = [
            form.findChild(QtGui.QComboBox, "modeCombo"),
            *(form.findChild(QtGui.QWidget, f"offset{a}") for a in "XY"),
        ]
        axe.setCurrentIndex(axe.findData("Z"))
        problemes = ecarts("grisés sur Z", [w.isEnabled() for w in actifs], [False] * 3)
        problemes += ecarts(
            "3e décalage actif", form.findChild(QtGui.QWidget, "offsetZ").isEnabled(), True
        )
        axe.setCurrentIndex(axe.findData(""))
        problemes += ecarts("rendus en Libre", [w.isEnabled() for w in actifs], [True] * 3)
        return problemes

    return avec_document("AlignementGrisage", verification)


def _boutons(form: Any, prefixe: str) -> list[Any]:
    return [form.findChild(QtGui.QToolButton, f"{prefixe}{a}Button") for a in "XYZ"]


def verifier_grille_parallele_et_aligner() -> list[str]:
    """Grille « // , début, centre, fin » : boutons à cocher avec icône, ligne Z (normale des
    faces) grisée ; X fin, puis X centre (exclusifs), Y centre : la cale se place sous le
    plateau face contre face ; « OK » garde la position. « // » est grisé sur un axe."""

    def verification(doc: Any) -> list[str]:
        cale, form = ouvrir(doc)
        if form is None:
            return ["panneau absent"]
        grille = {nom: _boutons(form, nom) for nom in ("parallel", "start", "center", "end")}
        tous = [b for ligne in grille.values() for b in ligne]
        if None in tous:
            return ["grille Parallèle et aligner sur incomplète"]
        problemes = ecarts("à cocher", all(b.isCheckable() for b in tous), True)
        problemes += ecarts("icônes", any(b.icon().isNull() for b in tous), False)
        problemes += ecarts(
            "ligne Z grisée", [ligne[2].isEnabled() for ligne in grille.values()], [False] * 4
        )
        problemes += ecarts("ligne X active", grille["center"][0].isEnabled(), True)
        problemes += ecarts("sans disposition", base(cale), (300.0, 40.0, 678.0))
        grille["end"][0].setChecked(True)
        problemes += ecarts("fin sur X", base(cale), (700.0, 40.0, 678.0))
        grille["center"][0].setChecked(True)
        problemes += ecarts("fin décochée", grille["end"][0].isChecked(), False)
        problemes += ecarts("centre sur X", base(cale), (350.0, 40.0, 678.0))
        grille["center"][1].setChecked(True)
        problemes += ecarts("centre sur X et Y", base(cale), (350.0, 50.0, 678.0))
        grille["parallel"][0].setChecked(True)
        grille["parallel"][1].setChecked(True)
        problemes += ecarts("un seul //", grille["parallel"][0].isChecked(), False)
        grille["parallel"][1].setChecked(False)
        axe = form.findChild(QtGui.QComboBox, "axisCombo")
        axe.setCurrentIndex(axe.findData("Z"))
        problemes += ecarts("// grisé sur Z", grille["parallel"][0].isEnabled(), False)
        axe.setCurrentIndex(axe.findData(""))
        problemes += ecarts("// rendu en Libre", grille["parallel"][0].isEnabled(), True)
        valider()
        problemes += ecarts("après OK", base(cale), (350.0, 50.0, 678.0))
        return problemes

    return avec_document("AlignementGrille", verification)


VERIFICATIONS_ALIGNEMENT: tuple[Callable[[], list[str]], ...] = (
    verifier_grisage_sur_un_axe,
    verifier_grille_parallele_et_aligner,
)
