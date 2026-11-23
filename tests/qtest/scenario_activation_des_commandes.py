# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S20 : quels boutons sont actifs selon la sélection.

Pour 0, 1, 2 puis 3 pièces sélectionnées, et avec un panneau ouvert, l'état de chaque bouton de
l'atelier (son action Qt, après le rafraîchissement périodique de FreeCAD) est comparé à ce que
la commande exige. Une commande qui attend une sélection le dit dans son infobulle, par la ligne
« Prérequis : … » (issue #221). Les commandes qui demandent des faces, un ensemble ou un membre
sont jouées avec leur vraie sélection. Attrape un bouton actif à tort (puis une erreur au clic)
ou grisé à tort.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCADGui as Gui

from tests.qtest.aides import (
    activer_faulthandler,
    attendre,
    bouton_annuler,
    cliquer,
    fermer,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    selectionner_des_faces,
)
from tests.qtest.pieces import cadre, du_type, face_vers, piece

ASSEMBLAGES = frozenset(
    f"Menuiserie_{nom}"
    for nom in (
        "MortiseTenon",
        "TongueGroove",
        "Rabbet",
        "Dowels",
        "HalfLap",
        "Dovetail",
        "Miter",
        "LooseTenon",
        "Biscuit",
        "DrawerSlide",
    )
)
UNE_PIECE = frozenset({"Menuiserie_Foot", "Menuiserie_ShelfPins", "Menuiserie_CloseCarcass"})
DES_PIECES = frozenset({"Menuiserie_Furniture", "Menuiserie_Repeat"})
SANS_SELECTION = frozenset(
    {
        "Menuiserie_WoodPart",
        "Menuiserie_Carcass",
        "Menuiserie_CutList",
        "Menuiserie_CutListPreview",
        "Menuiserie_CutListExport",
        "Menuiserie_CutListPdf",
        "Menuiserie_NumberMarks",
        "Menuiserie_EdgeFinish",  # on désigne les pièces dans la vue 3D
        "Menuiserie_Drawing",  # plans : tout le document sans sélection
        "Menuiserie_PartDrawings",
        "Menuiserie_ExplodedDrawing",
    }
)
# Demandent autre chose que des pièces entières (faces, ensemble, copie, corps) : jamais
# actives dans ce scénario.
AUTRE_SELECTION = frozenset(
    {
        "Menuiserie_AlignFaces",
        "Menuiserie_SetDistance",
        "Menuiserie_FurnitureAdd",
        "Menuiserie_FurnitureRemove",
        "Menuiserie_FurnitureRebind",
        "Menuiserie_RepeatEdit",
        "Menuiserie_RepeatDissociate",
        "Menuiserie_ShapedPart",
        "Menuiserie_DrawingPdf",  # une page de plan
    }
)
AVEC_PREREQUIS = ASSEMBLAGES | UNE_PIECE | DES_PIECES | AUTRE_SELECTION
TOUTES = AVEC_PREREQUIS | SANS_SELECTION
# Nombre de pièces sélectionnées -> commandes actives.
ATTENDU = {
    0: SANS_SELECTION,
    1: SANS_SELECTION | UNE_PIECE | DES_PIECES,
    2: SANS_SELECTION | ASSEMBLAGES | DES_PIECES,
    3: SANS_SELECTION | DES_PIECES,
}
PREREQUIS = "Prérequis"
DROITE, GAUCHE = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def action(commande: str) -> Any:
    return Gui.Command.get(commande).getAction()[0]


def actives(attendues: frozenset[str]) -> set[str]:
    """Commandes dont le bouton est actif, une fois l'état attendu atteint ou le délai passé
    (FreeCAD rafraîchit ses boutons sur une minuterie)."""

    def etat() -> set[str]:
        return {commande for commande in TOUTES if action(commande).isEnabled()}

    attendre(lambda: etat() == attendues)
    return etat()


def actives_parmi(commandes: frozenset[str]) -> frozenset[str]:
    return frozenset(commande for commande in commandes if action(commande).isEnabled())


class ActivationDesCommandes(unittest.TestCase):
    """Un cadre de quatre pièces, sans aucun assemblage."""

    doc: ClassVar[Any]
    pieces: ClassVar[list[Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioActivation")
        cls.addClassCleanup(fermer, cls.doc)
        cls.pieces = list(cadre(cls.doc).values())

    def test_toutes_les_commandes_de_l_atelier_sont_connues(self) -> None:
        """Une commande ajoutée à l'atelier doit entrer dans ce scénario."""
        atelier = {nom for nom in Gui.Command.listAll() if nom.startswith("Menuiserie_")}
        self.assertLessEqual(TOUTES, atelier)
        self.assertEqual(atelier - TOUTES - {"Menuiserie_Structure"}, set())

    def test_selon_le_nombre_de_pieces(self) -> None:
        for nombre, attendues in ATTENDU.items():
            with self.subTest(pieces=nombre):
                selectionner(*self.pieces[:nombre])
                vues = actives(attendues)
                self.assertEqual(vues - attendues, set(), "actives à tort")
                self.assertEqual(attendues - vues, set(), "grisées à tort")

    def annuler_le_panneau(self) -> None:
        if panneau_ouvert():
            cliquer(bouton_annuler())

    def test_tout_est_grise_quand_un_panneau_est_ouvert(self) -> None:
        selectionner()
        lancer("Menuiserie_WoodPart")
        self.addCleanup(self.annuler_le_panneau)
        selectionner(*self.pieces[:2])
        self.assertEqual(actives(frozenset()), set(), "actives malgré le panneau ouvert")
        cliquer(bouton_annuler())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(actives(ATTENDU[2]), set(ATTENDU[2]))

    def test_prerequis_dans_l_infobulle(self) -> None:
        for commande in sorted(TOUTES):
            with self.subTest(commande=commande):
                infobulle = str(Gui.Command.get(commande).getInfo()["toolTip"])
                derniere_ligne = infobulle.strip().splitlines()[-1]
                if commande in AVEC_PREREQUIS:
                    self.assertIn(PREREQUIS, derniere_ligne, infobulle)
                else:
                    self.assertNotIn(PREREQUIS, infobulle)


class SelectionsParticulieres(unittest.TestCase):
    """Les commandes qui demandent autre chose que des pièces entières, chacune avec sa vraie
    sélection : deux pièces A et B rangées dans un ensemble, une pièce C libre. Les copies
    (S12) et le corps à convertir (S17) sont joués par leurs scénarios."""

    doc: ClassVar[Any]
    membres: ClassVar[tuple[Any, Any]]
    libre: ClassVar[Any]
    ensemble: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioActivationParticuliere")
        cls.addClassCleanup(fermer, cls.doc)
        cls.membres = (
            piece(cls.doc, (500.0, 200.0, 22.0), repere="A"),
            piece(cls.doc, (300.0, 100.0, 22.0), (800.0, 0.0, 0.0), repere="B"),
        )
        cls.libre = piece(cls.doc, (300.0, 100.0, 22.0), (0.0, 600.0, 0.0), repere="C")
        cls.doc.recompute()
        selectionner(*cls.membres)
        lancer("Menuiserie_Furniture")
        (cls.ensemble,) = du_type(cls.doc, "Menuiserie::Furniture")
        selectionner()

    def verifier(self, attendues: set[str]) -> None:
        """Parmi les commandes à sélection particulière, seules ``attendues`` sont actives."""
        voulues = frozenset(attendues)
        attendre(lambda: actives_parmi(AUTRE_SELECTION) == voulues)
        self.assertEqual(actives_parmi(AUTRE_SELECTION), voulues)

    def test_deux_faces(self) -> None:
        a, b = self.membres
        selectionner_des_faces((a, face_vers(a, DROITE)), (b, face_vers(b, GAUCHE)))
        # Une face choisie vaut sa pièce : les deux membres peuvent aussi être retirés.
        self.verifier(
            {"Menuiserie_AlignFaces", "Menuiserie_SetDistance", "Menuiserie_FurnitureRemove"}
        )

    def test_une_seule_face(self) -> None:
        a, _b = self.membres
        selectionner_des_faces((a, face_vers(a, DROITE)))
        self.verifier({"Menuiserie_FurnitureRemove"})

    def test_l_ensemble(self) -> None:
        selectionner(self.ensemble)
        self.verifier({"Menuiserie_FurnitureRebind"})

    def test_un_membre(self) -> None:
        selectionner(self.membres[0])
        self.verifier({"Menuiserie_FurnitureRemove"})

    def test_une_piece_libre_et_l_ensemble(self) -> None:
        selectionner(self.libre, self.ensemble)
        self.verifier({"Menuiserie_FurnitureAdd"})

    def test_une_piece_libre(self) -> None:
        selectionner(self.libre)
        self.verifier(set())
