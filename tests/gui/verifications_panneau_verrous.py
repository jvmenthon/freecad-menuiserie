# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des pièces à cotes fixes (ADR 0019, critères G1 à G3 de
``docs/specs/ensembles-epaisseurs-fixes.md``) : case « Cotes fixes » du panneau de l'ensemble,
refus d'une rangée bloquée avec ses cases et son bouton « Déverrouiller et appliquer », dans le
panneau de l'ensemble (cote) et dans celui de la pièce de bois (épaisseur).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Les widgets sont
manipulés comme par l'utilisateur ; aucun formulaire n'est gardé au-delà de son panneau
(enveloppes PySide réutilisées par FreeCAD 1.0).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui

from freecad.menuiserie import api
from tests.gui.aides_panneau import double_cliquer
from tests.gui.verifications_panneau import EDIT, ecarts, formulaire, saisir, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_panneau_ensemble import (
    MODIFIER,
    bouton_ok,
    bureau_regroupe,
    choisir_membre,
    lignes,
    ouvrir,
)
from tests.integration.bureau import EXPRESSIONS, LAYOUT, Bureau

BLOQUEE_LARGEUR = "Impossible de changer la largeur de l'ensemble à"
BLOQUEE_EPAISSEUR = "Impossible de changer l'épaisseur de « Joue gauche » à 25 mm"


def verrouiller_le_voile(bureau: Bureau) -> None:
    """Voile à cotes fixes, historique d'annulation vidé."""
    api.set_member_options(bureau.parts["V"], locked=True)
    bureau.doc.clearUndos()


def liaisons_de_cote(bureau: Bureau, repere: str) -> list[str]:
    """Propriétés de cote (``Length``, ``Width``) de la pièce ``repere`` qui ont une liaison."""
    return sorted(set(bureau.expressions(repere)) & {"Length", "Width"})


def refus_masque(form: Any) -> bool:
    """Vrai si ni le refus ni les cases ne sont affichés."""
    return bool(widget(form, "refusalLabel").isHidden() and widget(form, "unlockPieces").isHidden())


def etat_du_refus(form: Any, voile: Any) -> dict[str, object]:
    """Refus, case du voile et bouton, tels qu'affichés."""
    case = widget(form, f"unlock_{voile.Name}")
    return {
        "refus visible": not widget(form, "refusalLabel").isHidden(),
        "zone visible": not widget(form, "unlockPieces").isHidden(),
        "case visible": not case.isHidden(),
        "case cochée": case.isChecked(),
        "case libellé": case.text(),
        "bouton visible": not widget(form, "unlockButton").isHidden(),
        "OK actif": bool(bouton_ok().isEnabled()),
    }


REFUS_AFFICHE = {
    "refus visible": True,
    "zone visible": True,
    "case visible": True,
    "case cochée": True,
    "case libellé": "Voile",
    "bouton visible": True,
    "OK actif": False,
}


# --- G1 : case « Cotes fixes » --------------------------------------------------------------


def verifier_case_cotes_fixes() -> list[str]:
    """G1 : la case du membre choisi verrouille le voile, relie tout l'ensemble (la joue droite
    cite désormais le voile), l'aperçu suit aussitôt ; décochée, les liaisons reviennent ;
    « OK » = une entrée."""
    with bureau_regroupe("VerifCaseCotesFixes") as bureau:
        voile = bureau.parts["V"]
        form = ouvrir(bureau.furniture)
        choisir_membre(form, voile)
        case = widget(form, "lockedCheck")
        problemes = [
            *ecarts("libellé", case.text(), "Cotes fixes"),
            *ecarts("décochée", case.isChecked(), False),
            *ecarts("active", case.isEnabled(), True),
        ]
        case.setChecked(True)
        joue_droite = bureau.expressions("JD").get("Placement.Base.x")
        problemes += [
            *ecarts("verrou écrit", voile.Locked, True),
            *ecarts(
                "cotes du voile sans liaison",
                sorted(set(bureau.expressions("V")) & {"Length", "Width"}),
                [],
            ),
            *ecarts(
                "joue droite reliée",
                joue_droite,
                "<<Bureau>>.Origin.x + <<Joue gauche>>.Thickness + <<Joue droite>>.Thickness"
                " + 1156 mm",
            ),
            *ecarts("aperçu", [p.Name for p in bureau.parts.values() if "Touched" in p.State], []),
            *ecarts(
                "colonne Suit",
                any(ligne[0] == "Voile" and "cotes fixes" in ligne[2] for ligne in lignes(form)),
                True,
            ),
        ]
        case.setChecked(False)
        problemes += ecarts(
            "liaisons rétablies", {m: bureau.expressions(m) for m in LAYOUT}, EXPRESSIONS
        )
        case.setChecked(True)
        valider()
        return [
            *problemes,
            *ecarts("entrées", bureau.doc.UndoNames, [MODIFIER]),
            *ecarts("verrou gardé", voile.Locked, True),
        ]


# --- G2 : cote refusée, déverrouillage dans le panneau de l'ensemble ------------------------


def verifier_refus_de_la_largeur_et_deverrouillage() -> list[str]:
    """G2 : largeur 1300 refusée par la rangée bloquée (refus, case cochée, bouton, « OK »
    inactif, rien d'écrit) ; une autre cote refusée met le refus à jour ; revenir à la cote de
    l'ensemble efface tout ; « Déverrouiller et appliquer » déverrouille, relie, applique, en
    une seule entrée."""
    with bureau_regroupe("VerifDeverrouillageLargeur") as bureau:
        voile = bureau.parts["V"]
        verrouiller_le_voile(bureau)
        form = ouvrir(bureau.furniture)
        saisir(widget(form, "Width"), 1300.0)
        refus = widget(form, "refusalLabel")
        problemes = [
            *ecarts("refus", BLOQUEE_LARGEUR in refus.text() and "1300" in refus.text(), True),
            *ecarts("affichage", etat_du_refus(form, voile), REFUS_AFFICHE),
            *ecarts("rien d'écrit", (bureau.furniture.Width.Value, voile.Locked), (1200.0, True)),
            *ecarts("OK refusé", bool(valider_refuse()), False),
        ]
        case = widget(form, f"unlock_{voile.Name}")
        case.setChecked(False)
        problemes += ecarts(
            "rien de coché : bouton inactif", widget(form, "unlockButton").isEnabled(), False
        )
        case.setChecked(True)
        saisir(widget(form, "Width"), 1250.0)
        problemes += [
            *ecarts("refus mis à jour", "1250" in refus.text(), True),
            *ecarts("case gardée", etat_du_refus(form, voile), REFUS_AFFICHE),
        ]
        saisir(widget(form, "Width"), 1200.0)
        problemes += [
            *ecarts("refus et cases effacés", refus_masque(form), True),
            *ecarts("OK actif", bool(bouton_ok().isEnabled()), True),
        ]
        saisir(widget(form, "Width"), 1300.0)
        widget(form, "unlockButton").click()
        problemes += [
            *ecarts("voile déverrouillé", voile.Locked, False),
            *ecarts("largeur", bureau.furniture.Width.Value, 1300.0),
            *ecarts("voile étiré", bureau.sizes("V")[0], 1256.0),
            *ecarts("joue droite suit", bureau.bounds("JD")[0], (1278.0, 1300.0)),
            *ecarts(
                "refus disparu",
                (refus.isHidden(), widget(form, "unlockPieces").isHidden()),
                (True, True),
            ),
            *ecarts("OK actif après", bool(bouton_ok().isEnabled()), True),
        ]
        valider()
        bureau.doc.undo()
        bureau.doc.recompute()
        return [
            *problemes,
            *ecarts("une entrée", bureau.doc.UndoNames, []),
            *ecarts(
                "annulé : verrou et largeur",
                (voile.Locked, bureau.furniture.Width.Value),
                (True, 1200.0),
            ),
        ]


def valider_refuse() -> bool:
    """Résultat de « OK » demandé pendant un refus (le panneau doit rester ouvert)."""
    return bool(Gui.Control.activeTaskDialog().accept())


# --- G3 : épaisseur refusée, déverrouillage dans le panneau de la pièce --------------------


def verifier_refus_de_l_epaisseur_et_deverrouillage() -> list[str]:
    """G3 : épaisseur 25 de la joue gauche refusée par la rangée bloquée (même refus, même case,
    même bouton) ; « Déverrouiller et appliquer » écrit l'épaisseur, déverrouille le voile et
    décale celui-ci ; « OK » = une entrée."""
    with bureau_regroupe("VerifDeverrouillageEpaisseur") as bureau:
        joue, voile = bureau.parts["JG"], bureau.parts["V"]
        verrouiller_le_voile(bureau)
        double_cliquer(bureau.shown("JG"))
        form = formulaire()
        saisir(form.thicknessEdit, 25.0)
        refus = widget(form, "refusalLabel")
        problemes = [
            *ecarts("refus", BLOQUEE_EPAISSEUR in refus.text(), True),
            *ecarts("affichage", etat_du_refus(form, voile), REFUS_AFFICHE),
            *ecarts("rien d'écrit", (joue.Thickness.Value, voile.Locked), (22.0, True)),
        ]
        saisir(form.thicknessEdit, 22.0)
        problemes += ecarts("refus effacé", refus.isHidden(), True)
        saisir(form.thicknessEdit, 25.0)
        widget(form, "unlockButton").click()
        problemes += [
            *ecarts("épaisseur écrite", joue.Thickness.Value, 25.0),
            *ecarts("voile déverrouillé", voile.Locked, False),
            *ecarts("voile décalé", bureau.bounds("V")[0], (25.0, 1178.0)),
            *ecarts(
                "refus disparu",
                (refus.isHidden(), widget(form, "unlockPieces").isHidden()),
                (True, True),
            ),
            *ecarts("OK actif", bool(bouton_ok().isEnabled()), True),
        ]
        valider()
        return [
            *problemes,
            *ecarts("entrées", bureau.doc.UndoNames, [EDIT]),
            *ecarts("ensemble inchangé", bureau.furniture.Width.Value, 1200.0),
        ]


def verifier_epaisseur_acceptee_d_un_membre() -> list[str]:
    """G3 : sans pièce verrouillée, l'épaisseur d'une joue est contrôlée puis écrite, sans refus
    ni case ; le voile suit."""
    with bureau_regroupe("VerifEpaisseurMembre") as bureau:
        joue = bureau.parts["JG"]
        double_cliquer(bureau.shown("JG"))
        form = formulaire()
        saisir(form.thicknessEdit, 25.0)
        problemes = [
            *ecarts("épaisseur écrite", joue.Thickness.Value, 25.0),
            *ecarts("pas de refus", widget(form, "refusalLabel").isHidden(), True),
            *ecarts("voile décalé", bureau.bounds("V")[0], (25.0, 1178.0)),
            *ecarts("OK actif", bool(bouton_ok().isEnabled()), True),
        ]
        valider()
        return problemes


VERIFICATIONS_PANNEAU_VERROUS: tuple[Callable[[], list[str]], ...] = (
    verifier_case_cotes_fixes,
    verifier_refus_de_la_largeur_et_deverrouillage,
    verifier_refus_de_l_epaisseur_et_deverrouillage,
    verifier_epaisseur_acceptee_d_un_membre,
)
