# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du double-clic sur la liste de débit vivante (issue #76) : il ouvre
l'aperçu sur la portée de la liste, sans modifier le document, et ne fait rien tant qu'un panneau
de tâche est ouvert. Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui

from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_debit import (
    LISTE,
    avec_bureau,
    etat_du_document,
    fermer_les_apercus,
    widgets_apercu,
)
from tests.gui.verifications_panneau import annuler, ecarts
from tests.gui.verifications_panneau_ensemble import ouvrir
from tests.integration.bureau import Bureau


def liste_vivante(bureau: Bureau) -> Any:
    """Objet ``CutList`` créé par la commande « Liste de débit » (``None`` s'il manque)."""
    Gui.Command.get(LISTE).run()
    return bureau.doc.getObject("CutList")


def double_clic(obj: Any) -> bool:
    vobj = obj.ViewObject
    return bool(vobj.Proxy.doubleClicked(vobj))


def _apercu_au_double_clic(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    selectionner(bureau.shown("V"))
    liste = liste_vivante(bureau)
    if liste is None:
        return ["liste vivante absente"]
    Gui.Selection.clearSelection()  # la portée vient de la liste, pas de la sélection
    doc.clearUndos()
    avant = etat_du_document(doc)
    accepte = double_clic(liste)
    trouves = widgets_apercu()
    texte = trouves["navigateur"].toPlainText() if "navigateur" in trouves else ""
    problemes = [
        *ecarts("double-clic accepté", accepte, True),
        *ecarts("aperçu ouvert", "fenetre" in trouves, True),
        *ecarts("portée de la liste : voile", "Voile" in texte, True),
        *ecarts("portée de la liste : plateau absent", "Plateau" in texte, False),
        *ecarts("document inchangé", etat_du_document(doc), avant),
    ]
    del trouves
    fermer_les_apercus()
    return problemes


def verifier_apercu_au_double_clic() -> list[str]:
    """Double-clic sur la liste vivante : aperçu limité à sa portée (ici le voile choisi à la
    création), document et sélection inchangés."""
    return avec_bureau("VerifDoubleClicListe", _apercu_au_double_clic)


def _double_clic_pendant_un_panneau(bureau: Bureau) -> list[str]:
    liste = liste_vivante(bureau)
    if liste is None:
        return ["liste vivante absente"]
    if ouvrir(bureau.furniture) is None:
        return ["panneau de l'ensemble non ouvert"]
    accepte = double_clic(liste)
    problemes = [
        *ecarts("double-clic refusé", accepte, False),
        *ecarts("aucun aperçu", "fenetre" in widgets_apercu(), False),
    ]
    annuler()
    fermer_les_apercus()
    return problemes


def verifier_double_clic_pendant_un_panneau() -> list[str]:
    """Un panneau de tâche est ouvert : le double-clic sur la liste ne fait rien (le recalcul de
    l'aperçu validerait la transaction du panneau)."""
    return avec_bureau("VerifDoubleClicListePanneau", _double_clic_pendant_un_panneau)


VERIFICATIONS_DOUBLE_CLIC: tuple[Callable[[], list[str]], ...] = (
    verifier_apercu_au_double_clic,
    verifier_double_clic_pendant_un_panneau,
)
