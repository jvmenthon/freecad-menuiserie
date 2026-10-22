# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de l'onglet (critère A5 de ``docs/specs/J4-ensembles.md``).

Commande « Onglet » sur deux traverses d'angle de largeurs différentes, panneau générique de
J3e : aucun champ, angles de coupe affichés, « Inverser » qui les échange, une entrée
d'annulation à la validation. Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie import api
from tests.gui.verifications_assemblages import assembler, cadre, usinee_de
from tests.gui.verifications_panneau import ecarts, valider
from tests.gui.verifications_panneau_assemblage import panneau, texte, widget

ONGLET = "Menuiserie_Miter"
DEMI_COIN = 60 * 40 * 20 / 2  # moitié de la boîte commune 40 x 60 x 20
ANGLES = (
    "Angles de coupe : {}° pour la pièce hôte, {}° pour la pièce invitée (depuis une coupe "
    "d'équerre)."
)


def traverses(doc: Any) -> tuple[Any, Any]:
    """Traverses 500 x 60 x 20 (H, selon X) et 500 x 40 x 20 (I, selon Y) en chêne, dessinées
    hors tout, qui se chevauchent de 40 x 60 au coin."""
    poses = {
        "H": (60.0, App.Placement()),
        "I": (40.0, App.Placement(App.Vector(40, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))),
    }
    pieces = []
    for repere, (largeur, pose) in poses.items():
        piece = api.make_wood_part(500.0, largeur, 20.0, "chene", mark=repere, doc=doc)
        piece.Label = repere
        piece.Placement = pose
        pieces.append(piece)
    doc.recompute()
    return pieces[0], pieces[1]


def champs_de_saisie(form: Any) -> list[str]:
    """Noms des champs de saisie du panneau (il ne doit y en avoir aucun)."""
    types = (QtGui.QAbstractSpinBox, QtGui.QCheckBox, QtGui.QLineEdit)
    return [w.objectName() for w in form.findChildren(QtGui.QWidget) if isinstance(w, types)]


def verifier_formulaire_de_l_onglet() -> list[str]:
    """A5 : rôles dans l'ordre de sélection, aucun champ, angles affichés puis échangés par
    « Inverser », une entrée d'annulation, volumes des pièces usinées."""
    with cadre("VerifPanneauOnglet") as (doc, _pieces):
        hote, invitee = traverses(doc)
        doc.clearUndos()
        joint = assembler(doc, hote, invitee, commande=ONGLET, ok=False)
        form = panneau()
        if joint is None or form is None:
            return ["onglet non créé ou panneau non ouvert"]
        resume = widget(form, "summaryLabel")
        problemes = [
            *ecarts("titre", form.windowTitle(), "Nouvel assemblage : Onglet"),
            *ecarts("hôte", texte(form, "hostLabel"), "Pièce hôte : « H »"),
            *ecarts("champs", champs_de_saisie(form), []),
            *ecarts(
                "angles",
                (resume.isHidden(), resume.text()),
                (False, ANGLES.format("33,69", "56,31")),
            ),
            *ecarts("erreur masquée", widget(form, "errorLabel").isHidden(), True),
            # Demande de jv : pas de bouton « Inverser » pour un onglet (rôles symétriques).
            *ecarts("bouton Inverser", form.findChild(QtGui.QPushButton, "invertButton"), None),
        ]
        valider()
        problemes += [
            *ecarts("entrées", doc.UndoNames, ["Créer un assemblage d'onglet"]),
            *ecarts(
                "volumes",
                [round(usinee_de(p).Shape.Volume) for p in (hote, invitee)],
                [round(500 * 60 * 20 - DEMI_COIN), round(500 * 40 * 20 - DEMI_COIN)],
            ),
            *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
        ]
        return problemes


VERIFICATIONS_ONGLET: tuple[Callable[[], list[str]], ...] = (verifier_formulaire_de_l_onglet,)
