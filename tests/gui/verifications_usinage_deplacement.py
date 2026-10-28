# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : pièces usinées visibles après un glissement à la souris.

Bogue de jv : après un tenon-mortaise, la pièce qui porte le tenon (l'invitée) tirée par sa flèche,
l'assemblage reste dans l'arbre mais n'est plus dans la vue 3D. Le glissement passe par la
session (pression, mouvement, relâchement) ; la pièce usinée doit rester visible avec sa forme
recalculée, la brute cachée, aucune transparence laissée. Module importé par
``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from freecad.menuiserie.gui import joint_choice
from tests.gui.verifications_assemblages import cadre, usinee_de
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_panneau_assemblage import tenon_valide
from tests.gui.verifications_souris import (
    place,
    preparer,
    saisir,
    selection_dessinee,
    sur_la_fleche,
    tirer,
)

# (pièce tirée, axe de la flèche, distance tirée en mm le long de la flèche) : la traverse T1
# (invitée) glisse le long de la rive de M1 (hôte), qui glisse le long de son propre axe X.
GLISSEMENTS = {"invitée": ("T1", 1, -20.0), "hôte": ("M1", 0, -100.0)}
# jv : la traverse passe de l'autre côté du montant, son bout opposé touche M1.
AUTRE_COTE = ("T1", 0, -340.0)


def _forme(piece: Any) -> tuple[float, bool]:
    return round(float(piece.Shape.Volume), 3), bool(piece.Shape.isValid())


def _affichage(pieces: dict[str, Any]) -> list[str]:
    """Visibilité et transparence de chaque couple brute / usinée de l'assemblage."""
    problemes: list[str] = []
    for repere in ("M1", "T1"):
        brute, usinee = pieces[repere], usinee_de(pieces[repere])
        problemes += ecarts(f"{repere} : usinée visible", usinee.ViewObject.Visibility, True)
        problemes += ecarts(f"{repere} : brute cachée", brute.ViewObject.Visibility, False)
        problemes += ecarts(f"{repere} : usinée opaque", int(usinee.ViewObject.Transparency), 0)
        problemes += ecarts(f"{repere} : usinée suit la brute", usinee.Placement, brute.Placement)
    return problemes


def _glissement(nom: str, cas: str) -> list[str]:
    repere, axe, mm = GLISSEMENTS[cas]
    with cadre(nom) as (doc, pieces):
        session = preparer(doc)
        tenon_valide(doc, pieces)
        volumes = {r: _forme(usinee_de(pieces[r])) for r in ("M1", "T1")}
        problemes = _affichage(pieces)
        piece = pieces[repere]
        avant = place(piece)
        selection_dessinee(usinee_de(piece))
        problemes += ecarts(
            "flèche saisie", saisir(session, sur_la_fleche(session, axe, 40.0)), True
        )
        point = tirer(session, mm)
        problemes += ecarts("pièce déplacée", place(piece) != avant, True)
        problemes += ecarts("relâchement consommé", session.release(point), True)
        problemes += _affichage(pieces)
        problemes += ecarts(
            "formes recalculées", {r: _forme(usinee_de(pieces[r])) for r in volumes}, volumes
        )
        problemes += ecarts(
            "ni modifié ni invalide",
            [o.Name for o in doc.Objects if "Touched" in o.State or "Invalid" in o.State],
            [],
        )
        return problemes


def verifier_usinage_apres_glissement_de_l_invitee() -> list[str]:
    """La traverse (tenon) tirée par sa flèche reste visible et usinée."""
    return _glissement("VerifUsinageInvitee", "invitée")


def verifier_usinage_apres_glissement_de_l_hote() -> list[str]:
    """Le montant (mortaise) tiré par sa flèche reste visible et usiné."""
    return _glissement("VerifUsinageHote", "hôte")


def verifier_usinage_traverse_de_l_autre_cote() -> list[str]:
    """Scénario de jv : la traverse tirée de l'autre côté du montant (son bout opposé touche M1).
    Soit le tenon et la mortaise sont recalculés et visibles, soit la fenêtre de choix s'ouvre
    (annulation : la traverse revient) ; jamais d'usinage silencieusement absent."""
    repere, axe, mm = AUTRE_COTE
    with cadre("VerifUsinageAutreCote") as (doc, pieces):
        session = preparer(doc)
        tenon_valide(doc, pieces)
        brutes = {r: float(pieces[r].Shape.Volume) for r in ("M1", "T1")}
        piece = pieces[repere]
        avant = place(piece)
        selection_dessinee(usinee_de(piece))
        problemes = ecarts(
            "flèche saisie", saisir(session, sur_la_fleche(session, axe, 40.0)), True
        )
        point = tirer(session, mm)
        questions: list[Any] = []

        def choisir(libelles: Any) -> bool:
            questions.append(list(libelles))
            return False

        original, joint_choice.chooser = joint_choice.chooser, choisir
        try:
            problemes += ecarts("relâchement consommé", session.release(point), True)
        finally:
            joint_choice.chooser = original
        if questions:
            return [*problemes, *ecarts("annulé : la traverse revient", place(piece), avant)]
        volumes = {r: float(usinee_de(pieces[r]).Shape.Volume) for r in brutes}
        return [
            *problemes,
            *_affichage(pieces),
            *ecarts("tenon présent", volumes["T1"] > brutes["T1"], True),
            *ecarts("mortaise creusée", volumes["M1"] < brutes["M1"], True),
        ]


VERIFICATIONS_USINAGE_DEPLACEMENT: tuple[Callable[[], list[str]], ...] = (
    verifier_usinage_apres_glissement_de_l_invitee,
    verifier_usinage_apres_glissement_de_l_hote,
    verifier_usinage_traverse_de_l_autre_cote,
)
