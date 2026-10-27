# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : assemblage défait par un glissement, au relâchement (ADR 0024).

Une flèche tirée hors de portée de l'assemblage à tourillons de la joue gauche et du voile : au
relâchement, la fenêtre de choix s'ouvre (``gui/joint_choice``). Hors écran, la fenêtre modale est
pilotée par une minuterie qui clique ses boutons, envoie Échap ou la ferme (avec une garde qui la
rejette si rien ne l'a fermée) ; la fonction de choix injectée (``joint_choice.chooser``) est
vérifiée à part. Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.gui import joint_choice
from tests.gui.verifications_ensemble import pieces_du_bureau
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_souris import (
    TRANSACTION,
    place,
    preparer,
    saisir,
    selection_dessinee,
    sur_la_fleche,
    tirer,
)

ANNULER = "Annuler le déplacement"
SUPPRIMER = "Supprimer l'assemblage"
SUPPRIMER_PLURIEL = "Supprimer les assemblages"
GARDE_MS = 5000  # la fenêtre est rejetée si l'action n'a rien fermé après ce délai


def _bouton(boite: Any, texte: str) -> Any:
    return next(b for b in boite.buttons() if b.text() == texte)


def _echap(boite: Any) -> None:
    touche = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
    QtGui.QApplication.sendEvent(boite, touche)


ACTIONS: dict[str, Callable[[Any], None]] = {
    "bouton Supprimer": lambda boite: _bouton(boite, SUPPRIMER).click(),
    "bouton Annuler": lambda boite: _bouton(boite, ANNULER).click(),
    "Échap": _echap,
    "fermeture de la fenêtre": lambda boite: boite.close(),
}
SUPPRIME = {"bouton Supprimer"}


def piloter(action: Callable[[Any], None]) -> list[dict[str, Any]]:
    """Planifie ``action(fenêtre)`` dès que la fenêtre modale est ouverte (le ``exec`` de la
    fenêtre tourne dans la boucle d'évènements, qui sert les minuteries). Renvoie la liste où
    sera notée la fenêtre vue : titre, texte, textes des boutons."""
    vues: list[dict[str, Any]] = []

    def agir(essais: int = 0) -> None:
        boite = QtGui.QApplication.activeModalWidget()
        if boite is None:
            if essais < 200:
                QtCore.QTimer.singleShot(10, lambda: agir(essais + 1))
            return
        vues.append(
            {
                "titre": boite.windowTitle(),
                "texte": boite.text(),
                "boutons": sorted(b.text() for b in boite.buttons()),
            }
        )
        action(boite)

    def garde() -> None:
        boite = QtGui.QApplication.activeModalWidget()
        if boite is not None:
            boite.reject()

    QtCore.QTimer.singleShot(0, agir)
    QtCore.QTimer.singleShot(GARDE_MS, garde)
    return vues


class Choix:
    """Fonction de choix injectée : garde les libellés reçus, répond ``reponse``."""

    def __init__(self, reponse: bool) -> None:
        self.reponse = reponse
        self.recus: list[list[str]] = []

    def __call__(self, libelles: Any) -> bool:
        self.recus.append(list(libelles))
        return self.reponse


def _relacher(nom: str, mode: str) -> list[str]:
    """Glisse le voile de 100 mm le long de sa flèche X (hors de portée des tourillons de la joue
    gauche) et relâche, la fenêtre étant pilotée selon ``mode`` (clé de ``ACTIONS``, ou
    ``injecté : oui`` / ``injecté : non``)."""
    with pieces_du_bureau(nom) as bureau:
        doc, voile = bureau.doc, bureau.parts["V"]
        session = preparer(doc)
        joint = api.make_dowels(bureau.parts["JG"], voile)
        doc.recompute()
        identifiant, libelle = joint.Name, joint.Label
        doc.clearUndos()
        avant = place(voile)
        selection_dessinee(bureau.shown("V"))
        problemes = ecarts(
            "flèche X saisie", saisir(session, sur_la_fleche(session, 0, 40.0)), True
        )
        point = tirer(session, 100.0)
        problemes += ecarts("tirage : voile déplacé", place(voile) != avant, True)
        problemes += ecarts(
            "tirage : assemblage gardé", doc.getObject(identifiant) is not None, True
        )
        injecte = mode.startswith("injecté")
        choix = Choix(mode.endswith("oui"))
        original = joint_choice.chooser
        vues = [] if injecte else piloter(ACTIONS[mode])
        if injecte:
            joint_choice.chooser = choix
        try:
            problemes += ecarts("relâchement consommé", session.release(point), True)
        finally:
            joint_choice.chooser = original
        supprime = mode in SUPPRIME or mode == "injecté : oui"
        problemes += _constats(bureau, identifiant, avant, supprime=supprime, mode=mode)
        problemes += _fenetre(vues, choix, libelle, injecte=injecte)
        return problemes


def _constats(bureau: Any, identifiant: str, avant: Any, *, supprime: bool, mode: str) -> list[str]:
    doc, voile = bureau.doc, bureau.parts["V"]
    problemes = ecarts(
        f"{mode} : assemblage supprimé", doc.getObject(identifiant) is None, supprime
    )
    problemes += ecarts(f"{mode} : session libre", session_libre(), True)
    invalides = [o.Name for o in doc.Objects if "Invalid" in o.State]
    problemes += ecarts(f"{mode} : aucun objet en erreur", invalides, [])
    if supprime:
        problemes += [
            *ecarts(f"{mode} : déplacement gardé", place(voile) != avant, True),
            *ecarts(f"{mode} : pièce usinée supprimée", machined_part_of(voile) is None, True),
            *ecarts(f"{mode} : une seule transaction", doc.UndoNames, [TRANSACTION]),
        ]
        doc.undo()
        problemes += [
            *ecarts(f"{mode} : Ctrl+Z, voile revenu", place(voile), avant),
            *ecarts(
                f"{mode} : Ctrl+Z, assemblage revenu", doc.getObject(identifiant) is None, False
            ),
            *ecarts(f"{mode} : Ctrl+Z, pièce usinée", machined_part_of(voile) is None, False),
        ]
    else:
        problemes += [
            *ecarts(f"{mode} : pièce revenue", place(voile), avant),
            *ecarts(f"{mode} : pièce usinée gardée", machined_part_of(voile) is not None, True),
            *ecarts(f"{mode} : aucune transaction", TRANSACTION in doc.UndoNames, False),
        ]
    return problemes


def session_libre() -> bool:
    """Vrai si le glissement est fini (la session ne tient plus ni pièce tirée ni fenêtre)."""
    from freecad.menuiserie.gui.drag import events

    session = events.current_session()
    return (
        session is not None
        and not session.dragging
        and QtGui.QApplication.activeModalWidget() is None
    )


def _fenetre(vues: list[dict[str, Any]], choix: Choix, libelle: str, *, injecte: bool) -> list[str]:
    if injecte:
        return ecarts("fonction injectée : libellés reçus", choix.recus, [[f"« {libelle} »"]])
    if len(vues) != 1:
        return [f"fenêtre vue {len(vues)} fois au lieu d'une"]
    [vue] = vues
    return [
        *ecarts("fenêtre : boutons", vue["boutons"], sorted([ANNULER, SUPPRIMER])),
        *ecarts("fenêtre : nom de l'assemblage cité", f"« {libelle} »" in vue["texte"], True),
        *ecarts("fenêtre : titre", "assemblage défait" in vue["titre"], True),
    ]


def verifier_relachement_choix_injecte() -> list[str]:
    """Fonction de choix injectée : « non » annule, « oui » supprime (rien à cliquer)."""
    return [
        *_relacher("VerifAronde1", "injecté : non"),
        *_relacher("VerifAronde2", "injecté : oui"),
    ]


def verifier_relachement_fenetre() -> list[str]:
    """Vraie fenêtre : « Supprimer » supprime ; « Annuler le déplacement », Échap et la
    fermeture annulent."""
    problemes: list[str] = []
    for i, mode in enumerate(ACTIONS):
        problemes += _relacher(f"VerifAronde{i + 3}", mode)
    return problemes


def verifier_fenetre_au_pluriel() -> list[str]:
    """Plusieurs assemblages : tous les noms sont listés, bouton « Supprimer les assemblages »,
    Échap = annuler."""
    libelles = ["« Aronde du fond »", "« Tourillons du voile »"]
    vues = piloter(_echap)
    reponse = joint_choice.ask(libelles)
    [vue] = vues or [{"titre": "", "texte": "", "boutons": []}]
    return [
        *ecarts("Échap : annule", reponse, False),
        *ecarts("boutons", vue["boutons"], sorted([ANNULER, SUPPRIMER_PLURIEL])),
        *ecarts("titre", "assemblages défaits" in vue["titre"], True),
        *ecarts("noms listés", all(libelle in vue["texte"] for libelle in libelles), True),
        *ecarts("nombre cité", "2 assemblages" in vue["texte"], True),
    ]


VERIFICATIONS_ARONDE_RELACHEMENT: tuple[Callable[[], list[str]], ...] = (
    verifier_relachement_choix_injecte,
    verifier_relachement_fenetre,
    verifier_fenetre_au_pluriel,
)
