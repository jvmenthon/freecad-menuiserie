# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la relecture de fin de jalon « Ensemble à la souris » (ADR 0038) :
Std Part sélectionné dans l'arbre, suppression de l'ensemble et du Std Part à la main.

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) ; aucun clic Qt réel.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from freecad.menuiserie import api
from freecad.menuiserie.features.furniture_container import std_part_of
from freecad.menuiserie.gui.drag.furniture_target import FurnitureTarget
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_panneau_ensemble import bureau_regroupe
from tests.gui.verifications_souris import preparer, selection_dessinee
from tests.gui.verifications_souris_rotation import vue_isometrique


def verifier_std_part_selectionne_cible_son_ensemble() -> list[str]:
    """Mineur 8 : sélectionner « X (Std Part) » dans l'arbre donne les flèches de l'ensemble."""
    with bureau_regroupe("VerifRevueStdPartCible") as bureau:
        session = preparer(bureau.doc)
        vue_isometrique()
        selection_dessinee(std_part_of(bureau.furniture))
        cible = session.target
        return [
            *ecarts("cible : un ensemble", isinstance(cible, FurnitureTarget), True),
            *ecarts(
                "cible : l'ensemble du Std Part", getattr(cible, "obj", None), bureau.furniture
            ),
        ]


def _geometrie(doc: Any) -> dict[str, tuple[float, ...]]:
    trouve = {}
    for obj in doc.Objects:
        if obj.TypeId == "Part::FeaturePython" and not obj.Shape.isNull():
            forme = obj.Shape.copy()
            forme.Placement = obj.getGlobalPlacement()
            b = forme.BoundBox
            trouve[obj.Name] = tuple(round(v, 3) for v in (b.XMin, b.YMin, b.XMax, b.YMax))
    return trouve


def verifier_suppression_du_std_part_a_la_main() -> list[str]:
    """Majeur 3 : l'observateur de l'atelier (actif) garde les pièces en place quand le Std Part
    est supprimé, même tourné."""
    with bureau_regroupe("VerifRevueStdPartSupprime") as bureau:
        preparer(bureau.doc)
        api.rotate_furniture(bureau.furniture, (0.0, 0.0, 30.0))
        bureau.doc.recompute()
        avant = _geometrie(bureau.doc)
        part = std_part_of(bureau.furniture)
        bureau.doc.removeObject("" if part is None else part.Name)
        bureau.doc.recompute()
        return ecarts("pièces en place après la suppression", _geometrie(bureau.doc), avant)


def verifier_suppression_de_l_ensemble_et_de_son_std_part() -> list[str]:
    """Majeur 4 : supprimer l'ensemble (``onDelete``) supprime son Std Part vide."""
    with bureau_regroupe("VerifRevueEnsembleSupprime") as bureau:
        preparer(bureau.doc)
        part = std_part_of(bureau.furniture)
        nom_std = "" if part is None else part.Name
        avant = _geometrie(bureau.doc)
        ensemble = bureau.furniture
        autorise = ensemble.ViewObject.Proxy.onDelete(ensemble.ViewObject, [])
        bureau.doc.removeObject(ensemble.Name)
        bureau.doc.recompute()
        apres = {k: v for k, v in _geometrie(bureau.doc).items() if k in avant}
        return [
            *ecarts("suppression autorisée", autorise, True),
            *ecarts("Std Part supprimé", bureau.doc.getObject(nom_std), None),
            *ecarts("pièces en place", apres, avant),
        ]


VERIFICATIONS_ENSEMBLE_REVUE: tuple[Callable[[], list[str]], ...] = (
    verifier_std_part_selectionne_cible_son_ensemble,
    verifier_suppression_du_std_part_a_la_main,
    verifier_suppression_de_l_ensemble_et_de_son_std_part,
)
