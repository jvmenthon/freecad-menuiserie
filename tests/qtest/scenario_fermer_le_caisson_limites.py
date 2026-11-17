# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S24 : « Fermer le caisson », saisies limites et transitoires (ADR 0064, FC7/FC8).

Dans le panneau, on tape au clavier la hauteur et les épaisseurs : zéro, négatif, juste sous le
minimum, énorme, texte, vide. Après chaque saisie : le panneau reste ouvert, le message, le bouton
« OK » et le document disent la même chose (un refus ne laisse aucune pièce d'aperçu). Un
assemblage impossible est grisé avec sa raison ; tous les éléments décochés restent acceptés ;
une ancre trop épaisse pour sa largeur ouvre le panneau ; « Annuler » rend un document identique.
"""

from __future__ import annotations

import time
import unittest
from typing import Any, ClassVar

from freecad.menuiserie import api
from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_annuler,
    bouton_ok,
    choisir,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    refus_signale,
    selectionner,
    taper,
)
from tests.qtest.pieces import du_type

COMMANDE = "Menuiserie_CloseCarcass"
PANNEAU = "ClosingTaskPanel"
TYPE_PIECE = "Menuiserie::WoodPart"
TYPE_ENSEMBLE = "Menuiserie::Furniture"
HOSTILES = ("0", "-5", "0.01", "36", "36.99", "99999", "1e9", "abc", "", "720")
DELAI_MAX_S = 5.0
PLAFOND_MM = 20_000.0  # plafond des champs de cote (MAX_DIMENSION_MM)
ELEMENTS = ("left", "right", "back", "front", "opposite")


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def empreinte(doc: Any) -> list[tuple[str, str]]:
    return sorted((objet.Name, objet.TypeId) for objet in doc.Objects)


class SaisiesLimites(Etapes):
    """Panneau ouvert sur une ancre 600 x 400 x 18, saisies enchaînées."""

    doc: ClassVar[Any]
    form: ClassVar[Any]
    avant: ClassVar[list[tuple[str, str]]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioFermerLimites")
        cls.addClassCleanup(fermer, cls.doc)
        ancre = api.make_wood_part(600.0, 400.0, 18.0, doc=cls.doc)
        cls.avant = empreinte(cls.doc)
        selectionner(ancre)
        lancer(COMMANDE)
        cls.form = formulaire(PANNEAU)

    def controler_coherence(self) -> bool:
        """Vrai si la saisie est refusée ; message, bouton OK et aperçu disent la même chose."""
        erreur = enfant(self.form, "errorLabel")
        refuse = not erreur.isHidden()
        self.assertTrue(panneau_ouvert(), "panneau fermé par la saisie")
        self.assertEqual(refuse, bool(erreur.text().strip()), "message vide ou resté affiché")
        self.assertEqual(bouton_ok().isEnabled(), not refuse, "bouton OK incohérent")
        ensembles = du_type(self.doc, TYPE_ENSEMBLE)
        self.assertEqual(len(ensembles), 0 if refuse else 1, "aperçu incohérent avec le refus")
        if refuse:
            self.assertEqual(len(du_type(self.doc, TYPE_PIECE)), 1, "pièces d'aperçu restées")
        return refuse

    def saisir(self, nom: str, texte: str) -> None:
        debut = time.monotonic()
        taper(enfant(self.form, nom), texte)
        self.assertLess(time.monotonic() - debut, DELAI_MAX_S, "interface figée")

    def test_1_hauteur_hostile(self) -> None:
        for texte in HOSTILES:
            with self.subTest(saisie=texte):
                self.saisir("height", texte)
                refuse = self.controler_coherence()
                if texte in ("0", "-5", "36"):
                    self.assertTrue(refuse, f"« {texte} » aurait dû être refusé")
                champ = enfant(self.form, "height")
                # Au-delà du plafond du champ, Qt ignore les chiffres en trop (selon la version
                # de FreeCAD, la saisie est alors acceptée tronquée) : jamais plus que le plafond.
                self.assertLessEqual(float(champ.property("rawValue")), PLAFOND_MM)
        self.assertFalse(self.controler_coherence())  # dernière saisie : 720, valable

    def test_2_hauteur_minimale_37(self) -> None:
        """37 mm = ancre + dessus + 1 mm : les tourillons n'y tiennent pas (refus expliqué), sans
        assemblage le caisson est accepté."""
        liste = enfant(self.form, "joinery")
        rang = {str(liste.itemData(i)): i for i in range(liste.count())}
        self.saisir("height", "37")
        self.assertTrue(self.controler_coherence())
        choisir(liste, rang["None"])
        self.assertFalse(self.controler_coherence())
        self.saisir("height", "720")
        choisir(liste, rang["Dowels"])  # de nouveau possible : plus grisé
        self.assertFalse(self.controler_coherence())

    def test_2b_valeurs_transitoires_depuis_une_valeur_valide(self) -> None:
        """Taper « 0.01 » après « 18 » (cote qui passe par 0,1 mm) : message, pas d'exception.
        Les valeurs valides sont retapées avec leur unité : FreeCAD 1.1 réaffiche 0,01 mm en
        « 10 µm », et « 18 » seul y vaudrait 18 µm (comportement du champ, pas du panneau)."""
        for nom, valable in (
            ("thickness", "18 mm"),
            ("oppositeThickness", "18 mm"),
            ("backThickness", "8 mm"),
        ):
            for transitoire in ("0.01", "0.05", "0.099"):
                with self.subTest(champ=nom, saisie=transitoire):
                    self.saisir(nom, valable)
                    self.assertFalse(self.controler_coherence())
                    self.saisir(nom, transitoire)
                    self.assertTrue(self.controler_coherence())
            self.saisir(nom, valable)
            self.assertFalse(self.controler_coherence())

    def test_3_epaisseurs_hostiles(self) -> None:
        for nom in ("thickness", "oppositeThickness", "backThickness"):
            for texte in ("0", "-5", "0.01", "99999", "abc", ""):
                with self.subTest(champ=nom, saisie=texte):
                    self.saisir(nom, texte)
                    self.controler_coherence()
            self.saisir(nom, "18 mm" if nom != "backThickness" else "8 mm")
            self.assertFalse(self.controler_coherence(), nom)

    def test_4_assemblage_impossible_grise_avec_sa_raison(self) -> None:
        liste = enfant(self.form, "joinery")
        modele = liste.model()
        rang = {str(liste.itemData(i)): i for i in range(liste.count())}
        self.assertTrue(modele.item(rang["Dowels"]).isEnabled())
        self.saisir("thickness", "8")  # tourillons impossibles sous 12 mm
        self.assertFalse(modele.item(rang["Dowels"]).isEnabled(), "tourillons non grisés")
        self.assertTrue(liste.itemData(rang["Dowels"], 3), "raison absente (infobulle)")
        self.assertTrue(modele.item(rang["None"]).isEnabled())
        self.assertTrue(self.controler_coherence(), "tourillons choisis sous 12 mm acceptés")
        choisir(liste, rang["None"])
        self.assertFalse(self.controler_coherence())
        self.saisir("thickness", "18")
        self.assertTrue(modele.item(rang["Dowels"]).isEnabled(), "tourillons restés grisés")
        choisir(liste, rang["Dowels"])
        self.assertFalse(self.controler_coherence())

    def test_5_tous_les_elements_decoches(self) -> None:
        for cle in ELEMENTS:
            case = enfant(self.form, f"element_{cle}")
            if case.isChecked():
                cliquer(case)
            self.controler_coherence()
        pieces = du_type(self.doc, TYPE_PIECE)
        self.assertEqual(len(pieces), 1, "des pièces restent sans élément coché")
        for cle in ELEMENTS:
            if cle != "front":
                cliquer(enfant(self.form, f"element_{cle}"))
        self.assertFalse(self.controler_coherence())

    def test_6_annuler_rend_un_document_identique(self) -> None:
        cliquer(bouton_annuler())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(empreinte(self.doc), self.avant)
        self.assertEqual(self.doc.UndoNames, [])


class AncreEtroite(Etapes):
    """Ancre 300 x 50 x 25 : l'épaisseur par défaut atteint la moitié de la petite cote."""

    doc: ClassVar[Any]
    ancre: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioFermerAncreEtroite")
        cls.addClassCleanup(fermer, cls.doc)
        cls.ancre = api.make_wood_part(300.0, 50.0, 25.0, doc=cls.doc)

    def test_refus_expliqué_sans_panneau_ni_trace(self) -> None:
        """L'épaisseur par défaut (celle de l'ancre) atteint la moitié de la profondeur : la
        commande dit pourquoi au lieu de lever une exception, et ne laisse rien."""
        avant = empreinte(self.doc)
        selectionner(self.ancre)
        lancer(COMMANDE)
        self.assertFalse(panneau_ouvert())
        message = refus_signale()
        self.assertIn("épaisseur des côtés", message)
        self.assertEqual(empreinte(self.doc), avant)
        self.assertEqual(self.doc.UndoNames, [])
        self.assertFalse(self.doc.HasPendingTransaction)


if __name__ == "__main__":
    unittest.main()
