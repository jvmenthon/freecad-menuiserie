# SPDX-License-Identifier: LGPL-2.1-or-later
"""Angle à queue d'aronde, construit par les gestes de l'utilisateur : base commune des scénarios.

Deux pièces de 500 x 200 x 22 créées par la commande « Pièce en bois » et son panneau, la seconde
tournée de 90° autour de Y et posée debout sur le bout de la première, puis une queue d'aronde à
10° avec 4 griffes de 30 mm (3 queues : une griffe à chaque bord et une entre deux queues).

Non simulés : la pose de la seconde pièce à la souris dans la vue 3D (sa position est écrite par
le script, dans une transaction) et les clics sur les pièces (``Gui.Selection``).
"""

from __future__ import annotations

import math
import unittest
from typing import Any

import FreeCAD as App

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    bouton_ok,
    cliquer,
    enfant,
    formulaire,
    lancer,
    selectionner,
    taper,
    traiter_les_evenements,
)

PIECE_EN_BOIS = "Menuiserie_WoodPart"
QUEUE_D_ARONDE = "Menuiserie_Dovetail"
PANNEAU_PIECE = "WoodPartTaskPanel"
PANNEAU_ASSEMBLAGE = "JointTaskPanel"
TYPE_QUEUE_D_ARONDE = "Menuiserie::Dovetail"
DEPLACEMENT = "Déplacer une pièce"
LONGUEUR, LARGEUR, EPAISSEUR = 500.0, 200.0, 22.0
GRIFFES, LARGEUR_GRIFFE, ANGLE = 4, 30.0, 10.0
QUEUES = GRIFFES - 1
VOLUME_BRUT = LONGUEUR * LARGEUR * EPAISSEUR
# Queue : trapèze dont la grande base (entre deux griffes, là où elles sont le plus étroites)
# rétrécit de e·tan(angle) de chaque côté vers l'épaulement, sur l'épaisseur de la pièce à griffes.
GRANDE_BASE = (LARGEUR - GRIFFES * LARGEUR_GRIFFE) / QUEUES


def volume_des_queues(angle: float, epaisseur_hote: float = EPAISSEUR) -> float:
    """Volume des 3 queues (mm³) pour des flancs à ``angle`` degrés : elles traversent la pièce
    à griffes (``epaisseur_hote``) et ont l'épaisseur de la pièce à queues."""
    base_moyenne = GRANDE_BASE - epaisseur_hote * math.tan(math.radians(angle))
    return QUEUES * base_moyenne * epaisseur_hote * EPAISSEUR


VOLUME_QUEUES = volume_des_queues(ANGLE)
TOLERANCE_MM = 1e-6
TOLERANCE_MM3 = 1.0


def creer_une_piece(doc: Any, angle_y: float | None = None) -> Any:
    """Commande « Pièce en bois » : cotes tapées dans le panneau, angle autour de Y éventuel,
    puis clic sur OK ; renvoie la pièce créée."""
    avant = set(doc.Objects)
    selectionner()
    lancer(PIECE_EN_BOIS)
    form = formulaire(PANNEAU_PIECE)
    taper(enfant(form, "lengthEdit"), f"{LONGUEUR:g} mm")
    taper(enfant(form, "widthEdit"), "20 cm")
    if angle_y is not None:
        taper(enfant(form, "angleYEdit"), f"{angle_y:g}")
    cliquer(bouton_ok())
    (piece,) = (obj for obj in doc.Objects if obj not in avant)
    return piece


def poser(doc: Any, piece: Any, base: App.Vector) -> None:
    """Remplace le glissement à la souris : position écrite, annulable comme un geste."""
    doc.openTransaction(DEPLACEMENT)
    piece.Placement = App.Placement(base, piece.Placement.Rotation)
    doc.commitTransaction()
    doc.recompute()


def regler(form: Any, nom: str, texte: str) -> None:
    """Décoche la case « Auto » du paramètre ``nom`` puis tape sa valeur."""
    cliquer(enfant(form, f"{nom}Auto"))
    taper(enfant(form, nom), texte)


def deux_pieces(doc: Any) -> tuple[Any, Any]:
    """Les deux pièces en angle, pas encore assemblées : la pièce 1 à plat, la pièce 2 debout
    sur son bout, sa face extérieure à fleur de ce bout."""
    hote = creer_une_piece(doc)
    invitee = creer_une_piece(doc, angle_y=90.0)
    poser(doc, invitee, App.Vector(LONGUEUR - EPAISSEUR, 0, EPAISSEUR + LONGUEUR))
    return hote, invitee


def jouer(doc: Any) -> tuple[Any, Any, Any]:
    """Le scénario : renvoie la pièce à griffes, la pièce à queues et l'assemblage."""
    hote, invitee = deux_pieces(doc)
    avant = set(doc.Objects)
    selectionner(invitee, hote)  # la première sélectionnée porte les queues
    lancer(QUEUE_D_ARONDE)
    form = formulaire(PANNEAU_ASSEMBLAGE)
    regler(form, "TailCount", str(QUEUES))
    regler(form, "PinWidth", f"{LARGEUR_GRIFFE:g} mm")
    regler(form, "Angle", f"{ANGLE:g}")
    cliquer(bouton_ok())
    (assemblage,) = (
        obj
        for obj in doc.Objects
        if obj not in avant and getattr(obj.Proxy, "TYPE", "") == TYPE_QUEUE_D_ARONDE
    )
    return hote, invitee, assemblage


def double_cliquer(obj: Any) -> None:
    """Double-clic sur ``obj`` dans l'arbre : ouvre son panneau de modification."""
    vobj = obj.ViewObject
    if not vobj.Proxy.doubleClicked(vobj):
        raise AssertionError(f"le double-clic sur {obj.Label} n'ouvre rien")
    traiter_les_evenements()


def volumes_usines(hote: Any, invitee: Any) -> list[float]:
    """Volumes des pièces usinées de la pièce à griffes et de la pièce à queues."""
    return [usinee_de(piece).Shape.Volume for piece in (hote, invitee)]


def controler_le_document(test: unittest.TestCase, doc: Any) -> None:
    """Contrôles communs de fin de scénario : aucun objet en erreur ni à recalculer, formes
    valides, aucune transaction restée ouverte, aucun panneau ouvert."""
    import FreeCADGui as Gui

    for obj in doc.Objects:
        with test.subTest(objet=obj.Label):
            test.assertNotIn("Invalid", obj.State)
            test.assertNotIn("Touched", obj.State)
            if hasattr(obj, "Shape") and not obj.Shape.isNull():
                test.assertTrue(obj.Shape.isValid())
    test.assertFalse(doc.RecomputesFrozen)
    test.assertFalse(doc.HasPendingTransaction)
    test.assertFalse(Gui.Control.activeDialog())
