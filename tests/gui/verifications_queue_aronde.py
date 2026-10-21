# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la queue d'aronde (critère D6 de ``docs/specs/J4-ensembles.md``).

Commande « Queue d'aronde » sur deux planches en angle, panneau générique de J3e : nombre de
queues, griffes et pente effectifs affichés, pente saisie dans un champ décimal, une entrée
d'annulation à la validation. Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App

from freecad.menuiserie import api
from tests.gui.verifications_assemblages import assembler, cadre, usinee_de
from tests.gui.verifications_panneau import ecarts, valider
from tests.gui.verifications_panneau_assemblage import panneau, texte, valeur, widget

QUEUE_D_ARONDE = "Menuiserie_Dovetail"
BRUTE = 400 * 150 * 18
QUEUES_PENTE_8 = 3 * (42 - 18 / 8) * 18 * 18  # trois queues de 42 mm, pente 1:8


def planches(doc: Any) -> tuple[Any, Any]:
    """Deux planches 400 x 150 x 18 en chêne : H à plat, I debout sur son bout, sa face
    extérieure à fleur du bout de H."""
    poses = {
        "H": App.Placement(),
        "I": App.Placement(App.Vector(18, 0, 18), App.Rotation(App.Vector(0, 1, 0), -90)),
    }
    pieces = []
    for repere, pose in poses.items():
        piece = api.make_wood_part(400.0, 150.0, 18.0, "chene", mark=repere, doc=doc)
        piece.Label = repere
        piece.Placement = pose
        pieces.append(piece)
    doc.recompute()
    return pieces[0], pieces[1]


def verifier_formulaire_de_la_queue_d_aronde() -> list[str]:
    """D6 : rôles devinés (I sélectionnée d'abord porte les queues), valeurs effectives,
    pente saisie, une entrée d'annulation, volumes des pièces usinées."""
    with cadre("VerifPanneauQueueAronde") as (doc, _pieces):
        hote, invitee = planches(doc)
        doc.clearUndos()
        joint = assembler(doc, invitee, hote, commande=QUEUE_D_ARONDE, ok=False)
        form = panneau()
        if joint is None or form is None:
            return ["queue d'aronde non créée ou panneau non ouvert"]
        nombre, pente = widget(form, "TailCount"), widget(form, "Slope")
        problemes = [
            *ecarts("titre", form.windowTitle(), "Nouvel assemblage : Queue d'aronde"),
            *ecarts("hôte", texte(form, "hostLabel"), "Pièce hôte : « H »"),
            *ecarts("nombre auto", widget(form, "TailCountAuto").isChecked(), True),
            *ecarts("nombre effectif", nombre.value(), 3),
            *ecarts("nombre inactif", nombre.isEnabled(), False),
            *ecarts("griffes effectives", valeur(widget(form, "PinWidth")), 6.0),
            *ecarts("pente effective", pente.value(), 6.0),
            *ecarts("pente inactive", pente.isEnabled(), False),
        ]
        widget(form, "SlopeAuto").setChecked(False)
        problemes += [
            *ecarts("pente figée", joint.Slope, 6.0),
            *ecarts("pente active", pente.isEnabled(), True),
        ]
        pente.setValue(1.5)  # refusée par core : le champ la borne à 2
        problemes += [
            *ecarts("bornes de la pente", (pente.minimum(), pente.maximum()), (2.0, 20.0)),
            *ecarts("pente sous 2 bornée", (pente.value(), joint.Slope), (2.0, 2.0)),
            *ecarts("erreur masquée", widget(form, "errorLabel").isHidden(), True),
        ]
        pente.setValue(8.0)
        problemes += ecarts("pente saisie", joint.Slope, 8.0)
        valider()
        problemes += [
            *ecarts("entrées", doc.UndoNames, ["Créer un assemblage à queue d'aronde"]),
            *ecarts(
                "volumes",
                [round(usinee_de(p).Shape.Volume) for p in (hote, invitee)],
                [round(BRUTE - QUEUES_PENTE_8), round(BRUTE + QUEUES_PENTE_8)],
            ),
        ]
        return problemes


VERIFICATIONS_QUEUE_ARONDE: tuple[Callable[[], list[str]], ...] = (
    verifier_formulaire_de_la_queue_d_aronde,
)
