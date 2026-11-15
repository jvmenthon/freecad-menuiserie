# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S5 : saisies hostiles au clavier (règles « Entrées utilisateur » de CONTRIBUTING).

Dans le panneau d'une queue d'aronde puis d'une pièce en bois, on tape zéro, des valeurs
négatives, minuscules, énormes, du texte, rien, et des valeurs transitoires (« 3 » avant « 32 »).
Après chaque saisie : FreeCAD répond toujours (pas de gel), le panneau est encore ouvert, ce que
montre le champ est ce qui est écrit dans le document, et un refus est toujours expliqué (message
visible, bouton OK inactif, assemblage en erreur : les trois ensemble ou aucun).
"""

from __future__ import annotations

import time
import unittest
from typing import Any, ClassVar

from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_annuler,
    bouton_ok,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    taper,
)
from tests.qtest.angle_a_queues import (
    PANNEAU_ASSEMBLAGE,
    PANNEAU_PIECE,
    PIECE_EN_BOIS,
    QUEUE_D_ARONDE,
    TOLERANCE_MM,
    TYPE_QUEUE_D_ARONDE,
    controler_le_document,
    deux_pieces,
)

HOSTILES = ("0", "-5", "0.01", "3", "32", "99999", "1e9", "abc", "", "30 cm")
DELAI_MAX_S = 5.0  # une saisie ne doit jamais figer l'interface
COTE_MAX_MM = 9999.0
PRECISION_AFFICHEE = 0.01  # le champ arrondit à l'affichage ce qu'il a écrit
TROP_ETROITES = "Queues trop étroites"
GRIFFES_TROP_ETROITES = "Griffes trop étroites"


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class SaisiesHostilesDeLAssemblage(Etapes):
    """Panneau de création d'une queue d'aronde sur les deux pièces en angle."""

    doc: ClassVar[Any]
    form: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioSaisiesHostilesAssemblage")
        cls.addClassCleanup(fermer, cls.doc)
        hote, invitee = deux_pieces(cls.doc)
        selectionner(invitee, hote)
        lancer(QUEUE_D_ARONDE)
        cls.form = formulaire(PANNEAU_ASSEMBLAGE)
        (cls.assemblage,) = (
            obj for obj in cls.doc.Objects if getattr(obj.Proxy, "TYPE", "") == TYPE_QUEUE_D_ARONDE
        )

    def saisir(self, nom: str, texte: str) -> None:
        """Case « Auto » décochée si besoin, ``texte`` tapé dans le champ ``nom``, sans gel."""
        auto = enfant(self.form, f"{nom}Auto")
        if auto.isChecked():
            cliquer(auto)
        debut = time.monotonic()
        taper(enfant(self.form, nom), texte)
        self.assertLess(time.monotonic() - debut, DELAI_MAX_S, "interface figée")

    def refus_affiche(self) -> bool:
        """Vrai si la saisie est refusée ; vérifie que message, bouton OK et état de
        l'assemblage disent la même chose."""
        erreur = enfant(self.form, "errorLabel")
        refuse = not erreur.isHidden()
        self.assertTrue(panneau_ouvert(), "panneau fermé par la saisie")
        self.assertEqual(refuse, bool(erreur.text().strip()), "message vide ou resté affiché")
        self.assertEqual(bouton_ok().isEnabled(), not refuse, "bouton OK incohérent")
        self.assertEqual("Invalid" in self.assemblage.State, refuse, "état incohérent")
        return refuse

    def champ_et_propriete(self, nom: str) -> tuple[float, float]:
        champ = enfant(self.form, nom)
        if nom == "TailCount":
            return float(champ.value()), float(self.assemblage.TailCount)
        return float(champ.property("rawValue")), float(getattr(self.assemblage, nom).Value)

    def test_1_chaque_saisie_est_ecrite_ou_refusee(self) -> None:
        for nom in ("TailCount", "PinWidth", "Angle"):
            for texte in HOSTILES:
                with self.subTest(champ=nom, saisie=texte):
                    self.saisir(nom, texte)
                    self.refus_affiche()
                    if not enfant(self.form, f"{nom}Auto").isChecked():
                        affiche, ecrit = self.champ_et_propriete(nom)
                        self.assertAlmostEqual(affiche, ecrit, delta=PRECISION_AFFICHEE)
                        self.assertGreater(ecrit, 0.0)
            self.saisir(nom, "0")  # retour à l'automatique avant le champ suivant

    def test_2_griffe_de_moins_d_un_dixieme_refusee(self) -> None:
        """0,05 mm : refus expliqué dans le panneau ; 0,1 mm : accepté."""
        self.addCleanup(self.saisir, "PinWidth", "0")  # retour à l'automatique, même en échec
        self.saisir("PinWidth", "0.05 mm")
        self.assertTrue(self.refus_affiche())
        self.assertIn(GRIFFES_TROP_ETROITES, enfant(self.form, "errorLabel").text())
        self.saisir("PinWidth", "0.1 mm")
        self.assertFalse(self.refus_affiche())
        self.assertAlmostEqual(self.assemblage.PinWidth.Value, 0.1, delta=1e-6)

    def test_3_zero_remet_l_automatique(self) -> None:
        for nom, effectif in (("TailCount", 3.0), ("PinWidth", 7.0)):
            with self.subTest(champ=nom):
                self.saisir(nom, "5")
                self.saisir(nom, "0")
                self.assertTrue(enfant(self.form, f"{nom}Auto").isChecked())
                self.assertFalse(enfant(self.form, nom).isEnabled())
                affiche, ecrit = self.champ_et_propriete(nom)
                self.assertEqual((affiche, ecrit), (effectif, 0.0))
                self.assertFalse(self.refus_affiche())

    def test_4_combinaison_impossible_refusee_puis_corrigee(self) -> None:
        """12 queues entre des griffes de 30 mm ne tiennent pas dans 200 mm : refus expliqué,
        OK sans effet ; 3 queues : accepté et validé."""
        self.saisir("PinWidth", "30")
        self.saisir("TailCount", "12")
        self.assertTrue(self.refus_affiche())
        self.assertIn(TROP_ETROITES, enfant(self.form, "errorLabel").text())
        cliquer(bouton_ok())
        self.assertTrue(panneau_ouvert(), "panneau validé malgré le refus")
        self.saisir("TailCount", "3")
        self.assertFalse(self.refus_affiche())
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.assemblage.TailCount, 3)
        self.assertAlmostEqual(self.assemblage.PinWidth.Value, 30.0, delta=TOLERANCE_MM)
        controler_le_document(self, self.doc)


class SaisiesHostilesDeLaPiece(unittest.TestCase):
    """Panneau de création d'une pièce en bois."""

    def test_cotes_et_angles(self) -> None:
        doc = preparer("ScenarioSaisiesHostilesPiece")
        self.addCleanup(fermer, doc)
        selectionner()
        lancer(PIECE_EN_BOIS)
        form = formulaire(PANNEAU_PIECE)
        (piece,) = doc.Objects
        cotes = {"lengthEdit": "Length", "widthEdit": "Width", "thicknessEdit": "Thickness"}
        for champ, propriete in cotes.items():
            for texte in HOSTILES:
                with self.subTest(champ=champ, saisie=texte):
                    debut = time.monotonic()
                    taper(enfant(form, champ), texte)
                    self.assertLess(time.monotonic() - debut, DELAI_MAX_S, "interface figée")
                    self.assertTrue(panneau_ouvert(), "panneau fermé par la saisie")
                    ecrit = getattr(piece, propriete).Value
                    affiche = float(enfant(form, champ).property("rawValue"))
                    self.assertAlmostEqual(affiche, ecrit, delta=TOLERANCE_MM)
                    self.assertTrue(0.0 < ecrit <= COTE_MAX_MM, f"cote {ecrit} hors bornes")
                    self.assertTrue(piece.Shape.isValid())
                    self.assertNotIn("Invalid", piece.State)
        for texte in ("361", "-361", "99999", "abc", "", "45"):
            with self.subTest(champ="angleXEdit", saisie=texte):
                taper(enfant(form, "angleXEdit"), texte)
                affiche = float(enfant(form, "angleXEdit").property("rawValue"))
                self.assertTrue(-360.0 <= affiche <= 360.0, f"angle {affiche} hors bornes")
                roulis = piece.Placement.Rotation.getYawPitchRoll()[2]
                self.assertAlmostEqual(roulis, affiche, delta=1e-6)
        cliquer(bouton_annuler())
        self.assertEqual(doc.Objects, [])
        controler_le_document(self, doc)
