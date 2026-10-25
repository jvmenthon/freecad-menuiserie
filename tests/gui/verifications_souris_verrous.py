# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du glissement : rangée bloquée au relâchement et document fermé
(SM-c, issue #65 ; ``DragSession(unlock=...)`` et ``DragSession.forget``).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Comme pour
``verifications_souris.py``, la session est appelée directement (``press``, ``move``,
``release``), sans évènement Qt.

Aucun glissement réel ne bloque une rangée aujourd'hui (``bind_members`` ne contrôle pas les
rangées) : le refus est donc simulé, comme dans ``test_souris_guides.py``, par un
``bind_members`` qui lève ``BlockedRowError`` tant que la joue gauche est verrouillée. La boîte
modale « Déverrouiller et appliquer » est remplacée par une fonction (paramètre ``unlock``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
from typing import Any

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.furniture import BlockedRowError
from freecad.menuiserie.features import part_drag
from freecad.menuiserie.features.furniture_bindings import LockedPiecesError
from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.session import DragSession
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_panneau_ensemble import bureau_regroupe
from tests.gui.verifications_souris import (
    TRANSACTION,
    cadrer,
    noeuds_incrustes,
    preparer,
    px_en_mm,
    saisir,
    selection_dessinee,
    sur_la_fleche,
    tirer,
)
from tests.integration.bureau import Bureau

AXE = 2  # épaisseur du voile = -Y du monde : visible de dessus (l'axe Y du voile est de bout)
DEPLACEMENT = 40.0  # mm demandés au voile le long de cet axe


@contextmanager
def rangee_bloquee(bureau: Bureau, toujours: bool = False) -> Iterator[None]:
    """``bind_members`` du glissement refuse tant que la joue gauche est verrouillée (ou
    toujours, ``toujours``), comme le ferait une rangée sans cellule libre."""
    joue, voile = bureau.parts["JG"], bureau.parts["V"]
    original = getattr(part_drag, "bind_members")  # noqa: B009

    def bloque(*args: Any, **kwargs: Any) -> Any:
        if toujours or joue.Locked:
            raise BlockedRowError("Impossible", {}, locked=(joue.Name,), members=(voile.Name,))
        return original(*args, **kwargs)

    setattr(part_drag, "bind_members", bloque)  # noqa: B010
    try:
        yield
    finally:
        setattr(part_drag, "bind_members", original)  # noqa: B010


def etendue_du_voile(bureau: Bureau) -> tuple[tuple[float, float], ...]:
    return bureau.bounds("V")


def glisser_le_voile(bureau: Bureau, deverrouiller: Callable[[Any], Sequence[Any] | None]) -> Any:
    """Session propre (avec ``deverrouiller`` pour la boîte), le voile sélectionné et tiré de
    ``DEPLACEMENT`` mm sans aimant (Maj) puis relâché. Renvoie la session (à fermer)."""
    preparer(bureau.doc)
    cadrer()
    selection_dessinee(bureau.shown("V"))
    session = DragSession(unlock=deverrouiller)
    session.refresh()
    if not session.active or session.layout is None:
        raise RuntimeError("la session de vérification n'a pas de flèches")
    fleche = next(a for a in session.layout.arrows if a.axis == AXE)
    a, b = fleche.start, fleche.end
    longueur = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
    if not saisir(session, sur_la_fleche(session, AXE, 0.8 * longueur)):
        raise RuntimeError("flèche du voile non saisie")
    arret = tirer(session, DEPLACEMENT, shift=True)
    session.release(arret)
    return session


class Boite:
    """Remplace la boîte « Déverrouiller et appliquer » : garde les refus reçus, répond
    ``reponse``."""

    def __init__(self, reponse: Callable[[], Sequence[Any] | None]) -> None:
        self.reponse = reponse
        self.erreurs: list[ValueError] = []

    def __call__(self, erreur: ValueError) -> Sequence[Any] | None:
        self.erreurs.append(erreur)
        return self.reponse()


def _repondre(reponse: Sequence[Any] | None) -> Sequence[Any] | None:
    return reponse


def preparer_bureau(bureau: Bureau) -> None:
    """Joue gauche à cotes fixes ; historique vidé."""
    api.set_member_options(bureau.parts["JG"], locked=True)
    bureau.doc.clearUndos()


def _apres_refus(bureau: Bureau, avant: Any, boite: Boite, session: Any) -> list[str]:
    """Constats communs aux glissements finalement annulés."""
    return [
        *ecarts("boîte proposée une fois", len(boite.erreurs), 1),
        *ecarts("voile revenu", etendue_du_voile(bureau), avant),
        *ecarts("joue toujours verrouillée", bureau.parts["JG"].Locked, True),
        *ecarts("aucune entrée d'historique", list(bureau.doc.UndoNames), []),
        *ecarts("glissement fini", session.dragging, False),
    ]


# --- Déverrouiller et appliquer ----------------------------------------------------------


def verifier_souris_deverrouiller_et_appliquer() -> list[str]:
    """Rangée bloquée au relâchement, boîte acceptée : la joue est déverrouillée, le glissement
    refait depuis le début (position de la souris gardée), une seule entrée « Déplacer la
    pièce » qui annule aussi le déverrouillage."""
    with bureau_regroupe("VerifSourisDeverrouille") as bureau:
        preparer_bureau(bureau)
        joue = bureau.parts["JG"]
        avant = etendue_du_voile(bureau)
        boite = Boite(lambda: [bureau.shown("JG")])
        with rangee_bloquee(bureau):
            session = glisser_le_voile(bureau, boite)
        try:
            pas = px_en_mm(session)
            apres = etendue_du_voile(bureau)
            decalage = abs(apres[1][0] - avant[1][0])  # Y du monde
            problemes = [
                *ecarts("boîte proposée une fois", len(boite.erreurs), 1),
                *ecarts(
                    "refus de la rangée", isinstance(boite.erreurs[0], LockedPiecesError), True
                ),
                *ecarts(
                    "pièces proposées",
                    [p.Name for p in getattr(boite.erreurs[0], "members", ())],
                    [joue.Name],
                ),
                *ecarts("joue déverrouillée", joue.Locked, False),
                *ecarts("glissement fini", session.dragging, False),
                *ecarts(
                    "voile déplacé comme demandé", abs(decalage - DEPLACEMENT) <= 3 * pas, True
                ),
                *ecarts("une seule entrée", list(bureau.doc.UndoNames), [TRANSACTION]),
                *ecarts(
                    "document à jour",
                    [o.Name for o in bureau.doc.Objects if "Invalid" in o.State],
                    [],
                ),
            ]
            bureau.doc.undo()
            bureau.doc.recompute()
            return [
                *problemes,
                *ecarts("annuler : voile revenu", etendue_du_voile(bureau), avant),
                *ecarts("annuler : joue reverrouillée", joue.Locked, True),
            ]
        finally:
            session.shutdown()


def verifier_souris_deverrouiller_refuse() -> list[str]:
    """Boîte fermée sans pièce (``None`` ou liste vide) : le glissement est annulé, la pièce
    revient et rien n'entre dans l'historique."""
    problemes: list[str] = []
    for nom, reponse in (("fermée", None), ("sans pièce", [])):
        with bureau_regroupe("VerifSourisRefus") as bureau:
            preparer_bureau(bureau)
            avant = etendue_du_voile(bureau)
            boite = Boite(partial(_repondre, reponse))
            with rangee_bloquee(bureau):
                session = glisser_le_voile(bureau, boite)
            try:
                problemes += [f"{nom} : {p}" for p in _apres_refus(bureau, avant, boite, session)]
            finally:
                session.shutdown()
    return problemes


def verifier_souris_deverrouiller_encore_bloque() -> list[str]:
    """Rangée encore bloquée après le déverrouillage : le glissement est annulé, la joue reste
    verrouillée (la transaction est abandonnée) et rien n'entre dans l'historique."""
    with bureau_regroupe("VerifSourisEncoreBloque") as bureau:
        preparer_bureau(bureau)
        avant = etendue_du_voile(bureau)
        boite = Boite(lambda: [bureau.shown("JG")])
        with rangee_bloquee(bureau, toujours=True):
            session = glisser_le_voile(bureau, boite)
        try:
            return _apres_refus(bureau, avant, boite, session)
        finally:
            session.shutdown()


# --- Document fermé -----------------------------------------------------------------------


def verifier_souris_document_ferme() -> list[str]:
    """Un document fermé emporte les flèches : la session de l'atelier les oublie (observateur
    de documents), sans toucher à celles d'un autre document ; ``forget`` d'un autre document
    ne change rien."""
    with bureau_regroupe("VerifSourisFermeA") as bureau:
        preparer(bureau.doc)
        session = events.current_session()
        if session is None:
            return ["session absente : atelier actif sans filtre de glissement"]
        selection_dessinee(bureau.shown("V"))
        problemes = [
            *ecarts("flèches affichées", session.active, True),
            *ecarts("nœud posé", noeuds_incrustes(), 1),
        ]
        session.forget("UnAutreDocument")
        problemes += [
            *ecarts("autre document : flèches gardées", session.active, True),
            *ecarts("autre document : nœud gardé", noeuds_incrustes(), 1),
        ]
        session.forget(bureau.doc.Name)
        problemes += [
            *ecarts("forget : flèches oubliées", session.active, False),
            *ecarts("forget : vue libérée", session.port is None, True),
            *ecarts("forget : nœud retiré", noeuds_incrustes(), 0),
        ]
        session.forget(bureau.doc.Name)  # sans flèches : sans effet
        selection_dessinee(bureau.shown("V"))
        problemes += ecarts("flèches revenues", session.active, True)
        return [*problemes, *_fermeture_du_document(session, bureau)]


def _fermeture_du_document(session: DragSession, bureau: Bureau) -> list[str]:
    """Fermeture réelle du document qui porte les flèches : l'observateur appelle ``forget``
    aussitôt (avant que la sélection, notifiée plus tard, ne rafraîchisse la session)."""
    nom = bureau.doc.Name
    oublis: list[str] = []
    original = session.forget

    def espion(document: str) -> None:
        oublis.append(document)
        original(document)

    autre = App.newDocument("VerifSourisFermeB")
    setattr(session, "forget", espion)  # noqa: B010
    try:
        App.setActiveDocument(autre.Name)
        App.closeDocument(nom)
        problemes = [
            *ecarts("document fermé : forget appelé", oublis, [nom]),
            *ecarts("document fermé : flèches oubliées", session.active, False),
            *ecarts("document fermé : plus de pièce", session.part is None, True),
            *ecarts("document fermé : plus de vue", session.port is None, True),
        ]
        QtGui.QApplication.processEvents()
        session.refresh()  # la session reste utilisable
        return [*problemes, *ecarts("session utilisable", session.active, False)]
    finally:
        delattr(session, "forget")
        App.closeDocument(autre.Name)


VERIFICATIONS_SOURIS_VERROUS: tuple[Callable[[], list[str]], ...] = (
    verifier_souris_deverrouiller_et_appliquer,
    verifier_souris_deverrouiller_refuse,
    verifier_souris_deverrouiller_encore_bloque,
    verifier_souris_document_ferme,
)
