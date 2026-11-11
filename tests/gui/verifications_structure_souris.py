# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure » : déplacer et tourner à la souris depuis une
ligne choisie (ADR 0046, section « Sélection et tâche en cours »), par la session de glissement
comme ``verifications_souris``. Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors
écran)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tests.gui.verifications_panneau import avec_document, ecarts, piece_validee
from tests.gui.verifications_souris import (
    place,
    preparer,
    proche,
    px_en_mm,
    saisir,
    sur_la_fleche,
)
from tests.gui.verifications_souris import tirer as tirer_la_fleche
from tests.gui.verifications_souris_rotation import TRANSACTION as TRANSACTION_ROTATION
from tests.gui.verifications_souris_rotation import (
    lacet,
    saisir_anneau,
    tourner_de,
    vue_isometrique,
)
from tests.gui.verifications_structure import panneau_structure
from tests.gui.verifications_structure_selection import SELECTION, choisir_lignes, etat

# --- Déplacer et tourner depuis une ligne -------------------------------------------------


def _deplacer_et_tourner(doc: Any) -> list[str]:
    """Une ligne choisie donne les mêmes flèches et anneaux qu'une sélection faite en 3D ; le
    glissement (session interne, sans vrais évènements de souris) déplace puis tourne la pièce,
    une transaction chacun, sans toucher à la transparence de sélection."""
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    _dock, arbre, _synchro = panneau_structure()
    vue_isometrique()
    choisir_lignes(arbre, piece.Name)
    problemes = [
        *ecarts("ligne choisie : flèches actives", session.active, True),
        *ecarts("ligne choisie : trois flèches", len(session.layout.arrows), 3),
        *ecarts("ligne choisie : trois anneaux", len(session.layout.rings), 3),
        *ecarts("pièce transparente et teintée", etat(piece), SELECTION),
    ]
    avant, pas = place(piece), px_en_mm(session)
    survol = sur_la_fleche(session, 0, 40.0)
    session.move(survol)
    problemes += ecarts("flèche saisie", saisir(session, survol), True)
    voulu = tirer_la_fleche(session, 150.0, deplacer=False)
    session.move(voulu)
    session.release(voulu)
    problemes += proche("déplacée de 150 mm (x)", place(piece)[0], avant[0] + 150.0, 3 * pas)
    problemes += ecarts("déplacement : une transaction", doc.UndoNames, ["Déplacer la pièce"])
    problemes += ecarts("déplacement : transparence gardée", etat(piece), SELECTION)
    pris, depart = saisir_anneau(session, 2)
    arrivee = tourner_de(session, 2, 34.0, depart)
    session.release(arrivee)
    problemes += [
        *ecarts("anneau saisi", pris, True),
        *proche("tournée de 30° (aimant)", lacet(piece), 30.0, 0.01),
        *ecarts("rotation : une transaction de plus", doc.UndoNames[:1], [TRANSACTION_ROTATION]),
        *ecarts("rotation : transparence gardée", etat(piece), SELECTION),
    ]
    choisir_lignes(arbre)
    return problemes + ecarts("flèches retirées à la désélection", session.active, False)


def verifier_structure_deplacer_et_tourner_depuis_une_ligne() -> list[str]:
    return avec_document("VerifStructureSouris", _deplacer_et_tourner)


VERIFICATIONS_STRUCTURE_SOURIS: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_deplacer_et_tourner_depuis_une_ligne,
)
