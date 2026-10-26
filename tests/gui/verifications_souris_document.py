# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du glissement : document fermé (SM-c, issue #65 ;
``DragSession.forget`` et observateur de documents).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Comme pour
``verifications_souris.py``, la session est appelée directement, sans évènement Qt.
"""

from __future__ import annotations

from collections.abc import Callable

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.session import DragSession
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_panneau_ensemble import bureau_regroupe
from tests.gui.verifications_souris import noeuds_incrustes, preparer, selection_dessinee
from tests.integration.bureau import Bureau


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


VERIFICATIONS_SOURIS_DOCUMENT: tuple[Callable[[], list[str]], ...] = (
    verifier_souris_document_ferme,
)
