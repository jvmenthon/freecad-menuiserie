# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de l'aperçu et des boutons X, Y, Z (J6c, critères V1 à V7).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification
renvoie la liste de ses problèmes. Les boutons sont cliqués comme par l'utilisateur.
"""

from __future__ import annotations

from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.verifications_panneau import (
    CREATE,
    annuler,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    ouvrir_par_double_clic,
    piece_validee,
    valider,
)

BOUTONS = ("rotateXButton", "rotateYButton", "rotateZButton")
APERCU = 60


def cliquer(form: Any, bouton: str) -> None:
    getattr(form, bouton).click()


def memes_placements(a: Any, b: Any) -> bool:
    return bool(a.Base.isEqual(b.Base, 1e-6) and a.Rotation.isSame(b.Rotation, 1e-9))


def verifier_apercu_transparent() -> list[str]:
    """V1 + V3 : 60 % tant que le panneau est ouvert, transparence d'origine après « OK »."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        origine = 0
        problemes = ecarts("transparence de l'aperçu", obj.ViewObject.Transparency, APERCU)
        valider()
        return [
            *problemes,
            *ecarts("transparence après OK", obj.ViewObject.Transparency, origine),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
        ]

    return avec_document("VerifApercu", verification)


def verifier_apercu_annule() -> list[str]:
    """V3 : « Annuler » après des rotations ne laisse ni objet ni entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        creer_par_la_commande(doc)
        cliquer(formulaire(), "rotateXButton")
        annuler()
        return [
            *ecarts("pièces", len(doc.Objects), 0),
            *ecarts("entrées d'annulation", doc.UndoCount, 0),
            *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
        ]

    return avec_document("VerifApercuAnnule", verification)


def verifier_boutons_xyz() -> list[str]:
    """V4 + V5 : trois boutons avec icône et infobulle ; quatre clics ramènent la pièce au
    départ ; le fil ne change pas ; repère, dimensions, matériau puis rotation dans cet ordre."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        form = formulaire()
        problemes: list[str] = []
        depart, fil = obj.Placement.copy(), obj.GrainDirection
        for nom in BOUTONS:
            bouton = getattr(form, nom)
            problemes += [
                *ecarts(f"{nom} présent", bouton is not None, True),
                *ecarts(f"{nom} icône", bouton.icon().isNull(), False),
                *ecarts(f"{nom} infobulle", bool(bouton.toolTip()), True),
            ]
            cliquer(form, nom)
            problemes += ecarts(f"{nom} tourne", memes_placements(obj.Placement, depart), False)
            for _ in range(3):
                cliquer(form, nom)
            problemes += ecarts(f"{nom} x4", memes_placements(obj.Placement, depart), True)
        # Rang dans la disposition du formulaire (la géométrie n'est pas calculée hors écran).
        haut = {
            n: form.layout().indexOf(getattr(form, n))
            for n in ("identificationGroup", "dimensionsGroup", "materialGroup", "rotationGroup")
        }
        problemes += [
            *ecarts("fil", obj.GrainDirection, fil),
            *ecarts(
                "Identification avant Dimensions",
                haut["identificationGroup"] < haut["dimensionsGroup"],
                True,
            ),
            *ecarts(
                "Dimensions avant Matériau", haut["dimensionsGroup"] < haut["materialGroup"], True
            ),
            *ecarts("Matériau avant Rotation", haut["materialGroup"] < haut["rotationGroup"], True),
            *ecarts("Rotation titrée", form.rotationGroup.title(), "Rotation"),
        ]
        valider()
        return problemes

    return avec_document("VerifBoutonsXYZ", verification)


def verifier_rotation_en_modification() -> list[str]:
    """V3 + V4 : la pièce tourne sur place (centre fixe) ; « Annuler » rétablit le placement."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        centre, depart = obj.Shape.BoundBox.Center, obj.Placement.copy()
        form = ouvrir_par_double_clic(obj)
        cliquer(form, "rotateZButton")
        problemes = [
            *ecarts("tourne", memes_placements(obj.Placement, depart), False),
            *ecarts("centre fixe", obj.Shape.BoundBox.Center.isEqual(centre, 1e-6), True),
            *ecarts("transparence inchangée", obj.ViewObject.Transparency, 0),
        ]
        annuler()
        return [
            *problemes,
            *ecarts("placement rétabli", memes_placements(obj.Placement, depart), True),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
        ]

    return avec_document("VerifRotationModification", verification)


def verifier_boutons_inactifs_si_pilotes() -> list[str]:
    """V6 : placement piloté par une expression, boutons inactifs avec une infobulle."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("Placement.Base.x", "10 mm")
        doc.recompute()
        form = ouvrir_par_double_clic(obj)
        problemes: list[str] = []
        for nom in BOUTONS:
            bouton = getattr(form, nom)
            problemes += [
                *ecarts(f"{nom} inactif", bouton.isEnabled(), False),
                *ecarts(f"{nom} explication", "Std Transform" in bouton.toolTip(), True),
            ]
        annuler()
        return problemes

    return avec_document("VerifBoutonsPilotes", verification)


def verifier_aucune_trace_apres_fermeture() -> list[str]:
    """V7 : aucun observateur de sélection ni préférence créés par le panneau."""

    def verification(doc: Any) -> list[str]:
        racine = App.ParamGet("User parameter:BaseApp/Preferences/Mod")
        avant = sorted(racine.GetGroups())
        creer_par_la_commande(doc)
        valider()
        return [
            *ecarts("préférences", sorted(racine.GetGroups()), avant),
            *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
        ]

    return avec_document("VerifApercuTraces", verification)


VERIFICATIONS_APERCU = (
    verifier_apercu_transparent,
    verifier_apercu_annule,
    verifier_boutons_xyz,
    verifier_rotation_en_modification,
    verifier_boutons_inactifs_si_pilotes,
    verifier_aucune_trace_apres_fermeture,
)
