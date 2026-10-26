# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface complémentaires de la pièce en bois (fin de jalon : D1, D2, D5, E6).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification
renvoie la liste de ses problèmes. Activation de la commande selon la sélection, conversion de
plusieurs sources en une transaction, panneau d'une esquisse (épaisseur du profil) et cible de
« Modifier le dessin », assemblage avec une pièce en bois par la commande de l'atelier.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
import Part

from freecad.menuiserie import api
from freecad.menuiserie.gui.task_panels.shaped_part import drawing_target
from tests.gui.verifications_assemblages import assembler, selectionner
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    ecarts,
    formulaire_nomme,
    valider,
)
from tests.gui.verifications_panneau_assemblage import panneau as panneau_d_assemblage
from tests.gui.verifications_piece_en_bois import COMMANDE, FORM, convertir, enfant, pied


def esquisse_fermee(doc: Any) -> Any:
    """Esquisse rectangulaire fermée 200 x 80, hors corps."""
    esquisse = doc.addObject("Sketcher::SketchObject", "Profil")
    coins = [
        App.Vector(0, 0, 0),
        App.Vector(200, 0, 0),
        App.Vector(200, 80, 0),
        App.Vector(0, 80, 0),
    ]
    for i, debut in enumerate(coins):
        esquisse.addGeometry(Part.LineSegment(debut, coins[(i + 1) % 4]), False)
    doc.recompute()
    return esquisse


def _activation(doc: Any) -> list[str]:
    corps = pied(doc)
    planche = api.make_wood_part(800, 200, 22, "chene", mark="M1", doc=doc)
    commande = Gui.Command.get(COMMANDE)
    problemes = []
    for nom, objets, attendu in (
        ("sélection vide", (), False),
        ("pièce de bois", (planche,), False),
        ("corps PartDesign", (corps,), True),
    ):
        selectionner(*objets)
        problemes += ecarts(f"active : {nom}", commande.isActive(), attendu)
    convertir(doc, corps)
    valider()
    selectionner(corps)
    return [*problemes, *ecarts("active : source déjà convertie", commande.isActive(), False)]


def verifier_activation_selon_la_selection() -> list[str]:
    """D1 : active seulement s'il y a une source acceptable (ni vide, ni pièce de bois, ni
    source déjà convertie)."""
    return avec_document("VerifPieceEnBoisActivation", _activation)


def _plusieurs_sources(doc: Any) -> list[str]:
    premier, second = pied(doc), pied(doc)
    doc.clearUndos()
    pieces = convertir(doc, premier, second)
    problemes = [
        *ecarts("deux pièces", len(pieces), 2),
        *ecarts("pas de panneau", formulaire_nomme(FORM) is None, True),
        *ecarts("une seule entrée d'annulation", doc.UndoCount, 1),
    ]
    doc.undo()
    return [
        *problemes,
        *ecarts(
            "annulation : aucune pièce",
            [o for o in doc.Objects if o.TypeId == "Part::FeaturePython"],
            [],
        ),
        *ecarts(
            "annulation : sources réaffichées",
            (premier.Visibility, second.Visibility),
            (True, True),
        ),
    ]


def verifier_conversion_de_plusieurs_sources() -> list[str]:
    """D1 : une pièce par source sélectionnée, une seule transaction, pas de panneau."""
    return avec_document("VerifPieceEnBoisPlusieurs", _plusieurs_sources)


def _mode_profil(doc: Any) -> list[str]:
    esquisse = esquisse_fermee(doc)
    piece = convertir(doc, esquisse)[0]
    form = formulaire_nomme(FORM)
    if form is None:
        return ["panneau non ouvert"]
    problemes = [
        *ecarts("épaisseur du profil visible", enfant(form, "profileGroup").isHidden(), False),
        *ecarts("bouton Modifier le dessin", enfant(form, "editDrawingButton") is not None, True),
        *ecarts("cible : l'esquisse", drawing_target(piece), esquisse),
    ]
    del form
    annuler()
    corps = pied(doc)
    piece = convertir(doc, corps)[0]
    form = formulaire_nomme(FORM)
    if form is None:
        return [*problemes, "panneau d'un corps non ouvert"]
    problemes += [
        *ecarts(
            "corps : épaisseur du profil cachée", enfant(form, "profileGroup").isHidden(), True
        ),
        *ecarts("cible : dernière fonction du corps", drawing_target(piece), corps.Tip),
    ]
    del form
    return problemes


def verifier_mode_profil_et_cible_du_dessin() -> list[str]:
    """D2, D5 : l'épaisseur du profil n'apparaît que pour une esquisse ; « Modifier le dessin »
    vise l'esquisse ou le Tip du corps."""
    return avec_document("VerifPieceEnBoisProfil", _mode_profil)


def _assemblage(doc: Any) -> list[str]:
    source = doc.addObject("Part::Box", "SourcePied")
    source.Length, source.Width, source.Height = 720.0, 95.0, 45.0
    doc.recompute()
    hote = api.make_shaped_part(source, mark="P1")
    traverse = api.make_wood_part(200, 40, 20, "chene", mark="T1", doc=doc)
    traverse.Placement = hote.Placement.multiply(
        App.Placement(App.Vector(300, 0, 10), App.Rotation(App.Vector(0, 0, 1), -90))
    )
    doc.recompute()
    assemblage = assembler(doc, hote, traverse, ok=False)
    problemes = [
        *ecarts("assemblage créé", assemblage is not None, True),
        *ecarts("panneau d'assemblage ouvert", panneau_d_assemblage() is not None, True),
    ]
    if assemblage is None:
        return problemes
    valider()
    usinee = api.machined_part_of(hote)
    problemes += ecarts("pièce usinée de la pièce en bois", usinee is not None, True)
    if usinee is None:
        return problemes
    selectionner(usinee, traverse)  # la pièce usinée d'une pièce en bois se sélectionne aussi
    problemes += ecarts(
        "commande active sur la pièce usinée", Gui.Command.get("Menuiserie_Dowels").isActive(), True
    )
    Gui.Selection.clearSelection()
    vobj = usinee.ViewObject
    ouvert = bool(vobj.Proxy.doubleClicked(vobj))
    problemes += ecarts(
        "double-clic sur la pièce usinée : panneau de la pièce en bois",
        ouvert and formulaire_nomme(FORM) is not None,
        True,
    )
    return problemes


def verifier_assemblage_avec_une_piece_en_bois() -> list[str]:
    """E6 : la commande d'assemblage accepte une pièce en bois, son panneau s'ouvre, le
    double-clic sur sa pièce usinée ouvre le panneau de la pièce en bois."""
    return avec_document("VerifPieceEnBoisAssemblage", _assemblage)


VERIFICATIONS_PIECE_EN_BOIS_LIMITES: tuple[Callable[[], list[str]], ...] = (
    verifier_activation_selon_la_selection,
    verifier_conversion_de_plusieurs_sources,
    verifier_mode_profil_et_cible_du_dessin,
    verifier_assemblage_avec_une_piece_en_bois,
)
