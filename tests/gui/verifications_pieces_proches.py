# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : pièces proches qui ne se touchent pas au moment d'un assemblage
(ADR 0039). La fenêtre de choix ne se clique pas hors écran : ``near_gap.chooser`` est remplacé.
Module importé par ``verifier_atelier.py``."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.gui import near_gap
from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_panneau import annuler, ecarts, nouveau_document, valider

TOURILLONS = "Menuiserie_Dowels"
ECART = 8.0
EPAISSEUR = 22.0


@contextmanager
def deux_planches(nom: str) -> Iterator[tuple[Any, Any, Any]]:
    """Document avec deux planches superposées, la seconde à ``ECART`` mm de la première."""
    doc = nouveau_document(nom)
    try:
        bas = api.make_wood_part(400, 60, EPAISSEUR, "chene", mark="A", doc=doc)
        haut = api.make_wood_part(400, 60, EPAISSEUR, "chene", mark="B", doc=doc)
        haut.Placement = App.Placement(App.Vector(0, 0, EPAISSEUR + ECART), App.Rotation())
        doc.recompute()
        yield doc, bas, haut
    finally:
        if Gui.Control.activeDialog():
            annuler()
        Gui.Selection.clearSelection()
        App.closeDocument(doc.Name)


def lancer(doc: Any, bas: Any, haut: Any, reponse: str | None) -> tuple[list[Any], list[Any]]:
    """Lance les tourillons sur les deux planches ; la fenêtre répond ``reponse``. Renvoie les
    questions posées et les assemblages créés (panneau validé)."""
    questions: list[Any] = []

    def choisir(ecart: float, options: Mapping[str, str]) -> str | None:
        questions.append((ecart, dict(options)))
        return reponse

    original, near_gap.chooser = near_gap.chooser, choisir
    avant = set(doc.Objects)
    try:
        selectionner(bas, haut)
        Gui.Command.get(TOURILLONS).run()
        if Gui.Control.activeDialog():
            valider()
    finally:
        near_gap.chooser = original
    return questions, [o for o in doc.Objects if o not in avant and hasattr(o, "HostPart")]


def verifier_deplacer_puis_assembler() -> list[str]:
    """« Déplacer » : la seconde planche vient au contact, l'assemblage est créé, une seule
    entrée d'annulation qui remet tout."""
    with deux_planches("VerifPiecesProchesDeplacer") as (doc, bas, haut):
        doc.UndoMode = 1
        entrees = list(doc.UndoNames)
        questions, joints = lancer(doc, bas, haut, "move")
        problemes = [
            *ecarts("question posée", len(questions), 1),
            *ecarts("écart annoncé", questions[0][0] if questions else None, ECART),
            *ecarts("deux options", sorted(questions[0][1]) if questions else [], ["grow", "move"]),
            *ecarts("assemblage créé", len(joints), 1),
            *ecarts("seconde planche au contact", round(haut.Placement.Base.z, 3), EPAISSEUR),
            *ecarts("épaisseur gardée", round(haut.Thickness.Value, 3), EPAISSEUR),
        ]
        doc.undo()
        problemes += ecarts("un seul undo", list(doc.UndoNames), entrees)
        problemes += ecarts("planche revenue", round(haut.Placement.Base.z, 3), EPAISSEUR + ECART)
        return problemes


def verifier_agrandir_puis_assembler() -> list[str]:
    """« Agrandir » : la seconde planche s'épaissit jusqu'au contact, sans bouger sa face haute."""
    with deux_planches("VerifPiecesProchesAgrandir") as (doc, bas, haut):
        _, joints = lancer(doc, bas, haut, "grow")
        return [
            *ecarts("assemblage créé", len(joints), 1),
            *ecarts("épaisseur", round(haut.Thickness.Value, 3), EPAISSEUR + ECART),
            *ecarts("face basse au contact", round(haut.Placement.Base.z, 3), EPAISSEUR),
        ]


def verifier_annuler_ne_change_rien() -> list[str]:
    """« Annuler » : ni assemblage, ni déplacement, ni entrée d'annulation."""
    with deux_planches("VerifPiecesProchesAnnuler") as (doc, bas, haut):
        doc.UndoMode = 1
        entrees = list(doc.UndoNames)
        questions, joints = lancer(doc, bas, haut, None)
        return [
            *ecarts("question posée", len(questions), 1),
            *ecarts("aucun assemblage", len(joints), 0),
            *ecarts("planche immobile", round(haut.Placement.Base.z, 3), EPAISSEUR + ECART),
            *ecarts("entrées d'annulation", list(doc.UndoNames), entrees),
        ]


def verifier_pas_de_question_au_contact() -> list[str]:
    """Pièces déjà en contact : aucune fenêtre."""
    with deux_planches("VerifPiecesProchesContact") as (doc, bas, haut):
        haut.Placement = App.Placement(App.Vector(0, 0, EPAISSEUR), App.Rotation())
        doc.recompute()
        questions, joints = lancer(doc, bas, haut, "move")
        return [
            *ecarts("aucune question", len(questions), 0),
            *ecarts("assemblage créé", len(joints), 1),
        ]


VERIFICATIONS_PIECES_PROCHES: tuple[Callable[[], list[str]], ...] = (
    verifier_deplacer_puis_assembler,
    verifier_agrandir_puis_assembler,
    verifier_annuler_ne_change_rien,
    verifier_pas_de_question_au_contact,
)
