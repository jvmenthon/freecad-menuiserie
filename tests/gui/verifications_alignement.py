# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de « Aligner deux faces » (ADR 0054) : grisage sur un axe et
boutons « Centrer sur X, Y, Z ».

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


def verifier_centrer_sur_les_axes() -> list[str]:
    """Trois boutons à cocher avec icône ; X puis Y cochés : le centre de la cale vient sous
    celui du plateau, face contre face ; « OK » garde la position."""

    def verification(doc: Any) -> list[str]:
        cale, form = ouvrir(doc)
        if form is None:
            return ["panneau absent"]
        boutons = [form.findChild(QtGui.QToolButton, f"center{a}Button") for a in "XYZ"]
        if None in boutons:
            return ["boutons Centrer sur X, Y, Z absents"]
        problemes = ecarts("à cocher", [b.isCheckable() for b in boutons], [True] * 3)
        problemes += ecarts("icônes", [b.icon().isNull() for b in boutons], [False] * 3)
        problemes += ecarts("sans centrage", base(cale), (300.0, 40.0, 678.0))
        boutons[0].setChecked(True)
        problemes += ecarts("centrée sur X", base(cale), (350.0, 40.0, 678.0))
        boutons[1].setChecked(True)
        boutons[2].setChecked(True)  # Z : les faces sont déjà dans le même plan
        problemes += ecarts("centrée sur X, Y, Z", base(cale), (350.0, 50.0, 678.0))
        valider()
        problemes += ecarts("après OK", base(cale), (350.0, 50.0, 678.0))
        return problemes

    return avec_document("AlignementCentrage", verification)


VERIFICATIONS_ALIGNEMENT: tuple[Callable[[], list[str]], ...] = (
    verifier_grisage_sur_un_axe,
    verifier_centrer_sur_les_axes,
)
