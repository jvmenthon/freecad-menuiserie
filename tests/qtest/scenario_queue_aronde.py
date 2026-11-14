# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest : deux pièces de 20 cm de large, la seconde tournée de 90°, assemblées par une
queue d'aronde à 10° avec 4 griffes de 30 mm.

Lancé dans le vrai FreeCAD, par son mode test (unittest) :

    xvfb-run -a freecad -t tests.qtest.scenario_queue_aronde

Gestes joués sur les vrais widgets (clavier et souris de QTest) : commande « Pièce en bois » et
son panneau (largeur, longueur, angle autour de Y, bouton OK), commande « Queue d'aronde » et son
panneau (cases « Auto » décochées, nombre de queues, largeur des griffes, angle, bouton OK).
Non simulés : la pose de la seconde pièce à la souris dans la vue 3D (sa position est écrite par
le script, dans une transaction) et les clics sur les pièces (``Gui.Selection``).

4 griffes = 3 queues : une griffe à chaque bord et une entre deux queues.
"""

from __future__ import annotations

import math
import unittest
from typing import Any, ClassVar

import FreeCAD as App

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    activer_faulthandler,
    bouton_ok,
    capturer,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    preparer,
    selectionner,
    taper,
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
VOLUME_QUEUES = (
    QUEUES * (GRANDE_BASE - EPAISSEUR * math.tan(math.radians(ANGLE))) * EPAISSEUR * EPAISSEUR
)
TOLERANCE_MM = 1e-6
TOLERANCE_MM3 = 1.0


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


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


def jouer(doc: Any) -> tuple[Any, Any, Any]:
    """Le scénario : renvoie la pièce à griffes, la pièce à queues et l'assemblage."""
    hote = creer_une_piece(doc)
    invitee = creer_une_piece(doc, angle_y=90.0)
    # Pièce 2 debout sur le bout de la pièce 1, sa face extérieure à fleur de ce bout.
    poser(doc, invitee, App.Vector(LONGUEUR - EPAISSEUR, 0, EPAISSEUR + LONGUEUR))
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


class QueueDAronde(unittest.TestCase):
    """Le scénario complet, puis les vérifications sur le document obtenu."""

    doc: ClassVar[Any]
    hote: ClassVar[Any]
    invitee: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioQueueDAronde")
        cls.addClassCleanup(fermer, cls.doc)
        cls.hote, cls.invitee, cls.assemblage = jouer(cls.doc)
        selectionner()
        capturer("queue-aronde")

    def test_dimensions_des_pieces(self) -> None:
        for piece in (self.hote, self.invitee):
            with self.subTest(piece=piece.Label):
                self.assertAlmostEqual(piece.Length.Value, LONGUEUR, delta=TOLERANCE_MM)
                self.assertAlmostEqual(piece.Width.Value, 200.0, delta=TOLERANCE_MM)  # 20 cm
                self.assertAlmostEqual(piece.Thickness.Value, EPAISSEUR, delta=TOLERANCE_MM)

    def test_placements(self) -> None:
        self.assertTrue(self.hote.Placement.isSame(App.Placement(), TOLERANCE_MM))
        attendu = App.Placement(
            App.Vector(LONGUEUR - EPAISSEUR, 0, EPAISSEUR + LONGUEUR),
            App.Rotation(App.Vector(0, 1, 0), 90),
        )
        self.assertTrue(
            self.invitee.Placement.isSame(attendu, TOLERANCE_MM), self.invitee.Placement
        )

    def test_parametres_de_l_assemblage(self) -> None:
        joint = self.assemblage
        self.assertEqual(joint.TypeId, "Part::FeaturePython")
        self.assertEqual(joint.Proxy.TYPE, TYPE_QUEUE_D_ARONDE)
        self.assertEqual((joint.HostPart, joint.GuestPart), (self.hote, self.invitee))
        # Valeurs de la demande écrites en clair : 4 griffes (donc 3 queues) de 30 mm, à 10°.
        self.assertEqual(joint.TailCount, 3)
        self.assertAlmostEqual(joint.PinWidth.Value, 30.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(joint.Angle.Value, 10.0, delta=TOLERANCE_MM)

    def test_assemblage_valide(self) -> None:
        self.assertFalse(self.doc.RecomputesFrozen)
        for obj in self.doc.Objects:
            with self.subTest(objet=obj.Label):
                self.assertNotIn("Invalid", obj.State)
                self.assertNotIn("Touched", obj.State)

    def test_pieces_usinees(self) -> None:
        """Queues ajoutées à la pièce 2, logements enlevés dans la pièce 1 : solides valides,
        volumes attendus, aucune matière commune."""
        hote, invitee = (usinee_de(piece) for piece in (self.hote, self.invitee))
        for usinee in (hote, invitee):
            with self.subTest(piece=usinee.Label):
                self.assertTrue(usinee.Shape.isValid())
                self.assertEqual(len(usinee.Shape.Solids), 1)
        self.assertAlmostEqual(hote.Shape.Volume, VOLUME_BRUT - VOLUME_QUEUES, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(
            invitee.Shape.Volume, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3
        )
        self.assertAlmostEqual(hote.Shape.common(invitee.Shape).Volume, 0.0, delta=TOLERANCE_MM3)

    def test_annulation(self) -> None:
        """Une entrée d'annulation par geste de l'utilisateur (libellés sources de l'atelier,
        sauf « Déplacer une pièce », écrit par ce scénario)."""
        self.assertEqual(
            self.doc.UndoNames,
            [
                "Créer un assemblage à queue d'aronde",
                DEPLACEMENT,
                "Créer une pièce de bois",
                "Créer une pièce de bois",
            ],
        )


class AnnulerPuisRetablir(unittest.TestCase):
    """Ctrl+Z puis Ctrl+Y sur l'assemblage : il disparaît avec ses pièces usinées, puis revient
    à l'identique. Joué après ``QueueDAronde`` (ordre alphabétique des classes), dans son propre
    document."""

    def test_annuler_puis_retablir(self) -> None:
        doc = preparer("ScenarioAnnulerRetablir")
        self.addCleanup(fermer, doc)
        hote, invitee, assemblage = jouer(doc)
        nom = assemblage.Name
        volumes = [usinee_de(piece).Shape.Volume for piece in (hote, invitee)]
        lancer("Std_Undo")
        self.assertIsNone(doc.getObject(nom))
        self.assertEqual(len(doc.Objects), 2)
        self.assertAlmostEqual(hote.Shape.Volume, VOLUME_BRUT, delta=TOLERANCE_MM3)
        lancer("Std_Redo")
        doc.recompute()
        self.assertIsNotNone(doc.getObject(nom))
        for obj in doc.Objects:
            with self.subTest(objet=obj.Label):
                self.assertNotIn("Invalid", obj.State)
        for piece, volume in zip((hote, invitee), volumes, strict=True):
            self.assertAlmostEqual(usinee_de(piece).Shape.Volume, volume, delta=TOLERANCE_MM3)
