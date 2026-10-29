# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : glisser à la souris une pièce en bois (recette de jv, FreeCAD 1.1.4).

Une pièce en bois issue d'une forme Part (``Part::Box``) ou d'un corps PartDesign porte les
flèches de la session du glissement dès que son panneau est ouvert (il s'ouvre à la conversion) et
peut être déplacée par une flèche, dans la transaction du panneau. Module importé par
``verifier_atelier.py`` ; hors écran, la session est appelée directement (voir
``verifications_souris.py``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PySide import QtGui

from tests.gui.verifications_panneau import avec_document, ecarts, valider
from tests.gui.verifications_piece_en_bois import convertir, pied
from tests.gui.verifications_souris import (
    cadrer,
    place,
    preparer,
    px_en_mm,
    saisir,
    selection_dessinee,
    sur_la_fleche,
    tirer,
)

DISTANCE = 100.0  # mm tirés le long de la flèche X


def boite(doc: Any) -> Any:
    """Forme Part : parallélépipède de 800 x 100 x 22."""
    forme = doc.addObject("Part::Box", "Boite")
    forme.Length, forme.Width, forme.Height = 800.0, 100.0, 22.0
    doc.recompute()
    return forme


def _distance(avant: tuple[float, float, float], apres: tuple[float, float, float]) -> float:
    return math.dist(avant, apres)


def _glisser_depuis(doc: Any, fabrique: Callable[[Any], Any]) -> list[str]:
    session = preparer(doc)
    source = fabrique(doc)
    cadrer()
    pieces = convertir(doc, source)
    QtGui.QApplication.processEvents()
    if len(pieces) != 1 or session is None:
        return [f"conversion : {len(pieces)} pièce(s), session {session!r}"]
    piece = pieces[0]
    problemes = ecarts("panneau ouvert : flèches sur la pièce", session.active, True)
    if not session.active:
        return problemes
    problemes += [
        *ecarts("panneau : trois flèches", len(session.layout.arrows), 3),
        *ecarts("pièce en bois : aucune poignée", len(session.layout.handles), 0),
    ]
    avant, pas = place(piece), px_en_mm(session)
    problemes += ecarts("flèche saisie", saisir(session, sur_la_fleche(session, 0, 40.0)), True)
    voulu = tirer(session, DISTANCE)
    ecart = _distance(avant, place(piece))
    if abs(ecart - DISTANCE) > 3 * pas:
        problemes.append(
            f"pièce déplacée de {ecart:.3f} mm au lieu de {DISTANCE} (± {3 * pas:.3f})"
        )
    problemes += ecarts("relâchement consommé", session.release(voulu), True)
    valider()
    selection_dessinee(piece)
    problemes += ecarts("panneau fermé : flèches sur la pièce", session.active, True)
    return problemes


def verifier_souris_piece_en_bois_forme_part() -> list[str]:
    """Pièce en bois d'un ``Part::Box`` : flèches et glissement, panneau ouvert à la conversion."""
    return avec_document("VerifSourisPartBox", lambda doc: _glisser_depuis(doc, boite))


def verifier_souris_piece_en_bois_corps() -> list[str]:
    """Même geste sur la pièce en bois d'un corps PartDesign."""
    return avec_document("VerifSourisCorps", lambda doc: _glisser_depuis(doc, pied))


VERIFICATIONS_SOURIS_PIECE_EN_BOIS: tuple[Callable[[], list[str]], ...] = (
    verifier_souris_piece_en_bois_forme_part,
    verifier_souris_piece_en_bois_corps,
)
