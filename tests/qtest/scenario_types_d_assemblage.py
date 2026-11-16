# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S9 : chaque type d'assemblage, de la commande au panneau de modification.

Pour chaque type, sur un couple de pièces qui lui convient : la commande, le panneau validé avec
toutes les valeurs « Auto », puis le panneau rouvert par double-clic, chaque case « Auto »
décochée et sa valeur retapée, le bouton « Inverser » cliqué deux fois, « OK », et deux Ctrl+Z.
Attrape la régression d'un type quand le panneau générique des assemblages change.
"""

from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import Any

from PySide import QtCore, QtGui

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    activer_faulthandler,
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
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import PANNEAU_ASSEMBLAGE, controler_le_document, double_cliquer
from tests.qtest.pieces import angle_debout, assemblages, erreurs_python, montant_et_traverse

Disposition = Callable[[Any], tuple[Any, Any]]
# Type -> (commande, disposition des deux pièces).
TYPES: dict[str, tuple[str, Disposition]] = {
    "tenon-mortaise": ("Menuiserie_MortiseTenon", montant_et_traverse),
    "rainure et languette": ("Menuiserie_TongueGroove", montant_et_traverse),
    "feuillure": ("Menuiserie_Rabbet", montant_et_traverse),
    "tourillons": ("Menuiserie_Dowels", montant_et_traverse),
    "mi-bois": ("Menuiserie_HalfLap", montant_et_traverse),
    "onglet": ("Menuiserie_Miter", montant_et_traverse),
    "faux tenon": ("Menuiserie_LooseTenon", montant_et_traverse),
    "lamelles": ("Menuiserie_Biscuit", montant_et_traverse),
    "queue d'aronde": ("Menuiserie_Dovetail", angle_debout),
}
RETOUCHE = 0.9  # la valeur automatique est retapée un peu plus petite


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class TypesDAssemblage(unittest.TestCase):
    """Un document neuf par type (``subTest``)."""

    def jouer(self, commande: str, disposition: Disposition) -> None:
        doc = preparer("ScenarioTypesDAssemblage")
        try:
            hote, invitee = disposition(doc)
            doc.clearUndos()
            vider_la_vue_rapport()
            assemblage = self.creer_en_automatique(doc, commande, hote, invitee)
            self.retoucher(assemblage)
            self.inverser_deux_fois(assemblage)
            cliquer(bouton_ok())
            self.assertFalse(panneau_ouvert())
            controler_le_document(self, doc)
            self.assertEqual(len(doc.UndoNames), 2, doc.UndoNames)
            self.assertEqual(erreurs_python(vue_rapport()), [])
            self.annuler_tout(doc, hote, invitee)
        finally:
            fermer(doc)

    def creer_en_automatique(self, doc: Any, commande: str, hote: Any, invitee: Any) -> Any:
        """Commande sur les deux pièces, « OK » sans rien toucher : assemblage valide, les deux
        pièces usinées, une entrée d'annulation."""
        selectionner(invitee, hote)
        lancer(commande)
        self.assertFalse(self.refus_affiche(assemblages(doc)[0]))
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (assemblage,) = assemblages(doc)
        controler_le_document(self, doc)
        for brute in (hote, invitee):
            usinee = usinee_de(brute)
            self.assertEqual(len(usinee.Shape.Solids), 1, f"{brute.Label} en plusieurs solides")
            # Entaillée, ou allongée de ce qui entre dans l'autre (tenon, queues, recouvrement).
            self.assertNotAlmostEqual(
                usinee.Shape.Volume, brute.Shape.Volume, delta=1.0, msg=f"{brute.Label} intacte"
            )
        self.assertEqual(len(doc.UndoNames), 1, doc.UndoNames)
        return assemblage

    def refus_affiche(self, assemblage: Any) -> bool:
        """Vrai si le panneau refuse ; message, bouton OK et état de l'assemblage d'accord."""
        erreur = enfant(formulaire(PANNEAU_ASSEMBLAGE), "errorLabel")
        refuse = not erreur.isHidden()
        self.assertEqual(refuse, bool(erreur.text().strip()), "message vide ou resté affiché")
        self.assertEqual(bouton_ok().isEnabled(), not refuse, "bouton OK incohérent")
        self.assertEqual("Invalid" in assemblage.State, refuse, "état incohérent")
        return refuse

    def retoucher(self, assemblage: Any) -> None:
        """Double-clic, puis chaque case « Auto » décochée et la valeur automatique affichée
        retapée à 90 % : écrite dans la propriété, assemblage toujours cohérent."""
        double_cliquer(assemblage)
        form = formulaire(PANNEAU_ASSEMBLAGE)
        cases = [
            case
            for case in form.findChildren(QtGui.QCheckBox)
            if case.objectName().endswith("Auto") and case.isEnabled() and case.isVisible()
        ]
        for case in cases:
            nom = case.objectName().removesuffix("Auto")
            with self.subTest(parametre=nom):
                champ = enfant(form, nom)
                self.assertTrue(case.isChecked(), "valeur déjà saisie à la création")
                self.assertFalse(champ.isEnabled(), "champ modifiable malgré « Auto »")
                cliquer(case)
                self.assertTrue(champ.isEnabled(), "champ resté grisé")
                if isinstance(champ, QtGui.QSpinBox):
                    voulu = float(max(1, champ.value() - 1))
                    taper(champ, f"{voulu:g}")
                    ecrit = float(getattr(assemblage, nom))
                else:
                    voulu = round(float(champ.property("rawValue")) * RETOUCHE, 1)
                    taper(champ, QtCore.QLocale().toString(voulu, "g", 6))
                    ecrit = float(getattr(assemblage, nom).Value)
                self.assertAlmostEqual(ecrit, voulu, delta=0.01)
                self.assertFalse(self.refus_affiche(assemblage), "retouche de 10 % refusée")

    def inverser_deux_fois(self, assemblage: Any) -> None:
        """« Inverser » échange les rôles, un second clic les rend ; à chaque fois le panneau
        reste cohérent (accepté, ou refus expliqué et OK grisé)."""
        bouton = enfant(formulaire(PANNEAU_ASSEMBLAGE), "invertButton")
        if not bouton.isEnabled():
            self.assertTrue(bouton.toolTip().strip(), "bouton grisé sans explication")
            return
        roles = (assemblage.HostPart, assemblage.GuestPart)
        cliquer(bouton)
        self.assertEqual((assemblage.GuestPart, assemblage.HostPart), roles)
        self.refus_affiche(assemblage)
        cliquer(bouton)
        self.assertEqual((assemblage.HostPart, assemblage.GuestPart), roles)
        self.assertFalse(self.refus_affiche(assemblage), "refus après aller-retour")

    def annuler_tout(self, doc: Any, hote: Any, invitee: Any) -> None:
        """Deux Ctrl+Z : il ne reste que les deux brutes, entières et visibles."""
        lancer("Std_Undo")
        lancer("Std_Undo")
        self.assertEqual(doc.Objects, [hote, invitee])
        for brute in (hote, invitee):
            self.assertTrue(brute.ViewObject.Visibility, f"{brute.Label} restée masquée")
        controler_le_document(self, doc)

    def test_chaque_type(self) -> None:
        for nom, (commande, disposition) in TYPES.items():
            with self.subTest(type=nom):
                self.jouer(commande, disposition)
