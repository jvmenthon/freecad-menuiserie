# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : pièces transparentes pendant le panneau d'un assemblage.

Demande de jv (``docs/specs/J3-assemblages.md``, critère E8). Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification renvoie la liste
de ses problèmes. « OK » et « Annuler » passent par le dialogue actif de FreeCAD. La
transparence est une propriété du ViewObject : elle ne doit laisser aucune entrée d'annulation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.verifications_assemblages import CADRE, CREATION, cadre, usinee_de
from tests.gui.verifications_panneau import annuler, ecarts, valider
from tests.gui.verifications_panneau_assemblage import (
    MODIFICATION,
    creer_sans_valider,
    double_cliquer,
    panneau,
    tenon_valide,
    widget,
)

TRANSPARENCE = 60
# Transparences d'origine distinctes, pour vérifier une restauration exacte.
ORIGINES = {"M1": 30, "T1": 0}


def transparence(obj: Any) -> int:
    return int(obj.ViewObject.Transparency)


def transparences(objets: list[Any]) -> list[int]:
    return [transparence(obj) for obj in objets]


def poser_origines(pieces: dict[str, Any]) -> None:
    """Transparence d'origine propre à chaque pièce usinée de l'assemblage."""
    for repere, valeur in ORIGINES.items():
        usinee_de(pieces[repere]).ViewObject.Transparency = valeur


def entrees_en_plus(doc: Any) -> list[str]:
    """Entrées d'annulation autres que la transaction du panneau, encore ouverte (FreeCAD la
    liste ou non selon la version) : la transparence ne doit en créer aucune."""
    ouverte = App.getActiveTransaction()
    return [nom for nom in doc.UndoNames if ouverte is None or nom != ouverte[0]]


def usinees(pieces: dict[str, Any]) -> list[Any]:
    return [usinee_de(pieces[repere]) for repere in ORIGINES]


def verifier_transparence_a_la_creation_validee() -> list[str]:
    """Panneau de création ouvert : pièces usinées transparentes, autres pièces intactes ;
    « OK » rétablit les transparences, une seule entrée d'annulation (aucune pour la vue)."""
    with cadre("VerifTransparenceCreationOk") as (doc, pieces):
        doc.clearUndos()
        creer_sans_valider(doc, pieces)
        affichees = usinees(pieces)
        problemes = [
            *ecarts("panneau ouvert", panneau() is not None, True),
            *ecarts("transparentes", transparences(affichees), [TRANSPARENCE] * 2),
            *ecarts("autres pièces", transparences([pieces["M2"], pieces["T2"]]), [0, 0]),
            *ecarts("entrées en plus avant « OK »", entrees_en_plus(doc), []),
        ]
        valider()
        return [
            *problemes,
            *ecarts("rétablies", transparences(affichees), [0, 0]),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATION]),
        ]


def verifier_transparence_a_la_creation_annulee() -> list[str]:
    """« Annuler » à la création : rien ne reste, les brutes gardent leur transparence."""
    with cadre("VerifTransparenceCreationAnnulee") as (doc, pieces):
        doc.clearUndos()
        creer_sans_valider(doc, pieces)
        problemes = ecarts("transparentes", transparences(usinees(pieces)), [TRANSPARENCE] * 2)
        annuler()
        return [
            *problemes,
            *ecarts("objets", [o.Label for o in doc.Objects], list(CADRE)),
            *ecarts("brutes", transparences([pieces[r] for r in CADRE]), [0] * 4),
            *ecarts("brutes visibles", [pieces[r].Visibility for r in CADRE], [True] * 4),
            *ecarts("entrées d'annulation", doc.UndoNames, []),
        ]


def verifier_transparence_a_la_modification() -> list[str]:
    """Double-clic : transparentes ; « Annuler » puis « OK » rétablissent exactement les
    transparences d'origine (30 % et 0 %), sans entrée d'annulation en plus."""
    with cadre("VerifTransparenceModification") as (doc, pieces):
        tenon_valide(doc, pieces)
        poser_origines(pieces)
        affichees = usinees(pieces)
        problemes: list[str] = []
        for sortie, fermer, entrees in (
            ("Annuler", annuler, []),
            ("OK", valider, [MODIFICATION]),
        ):
            doc.clearUndos()
            joint = next(o for o in doc.Objects if hasattr(o, "HostPart"))
            if not double_cliquer(joint) or panneau() is None:
                return [*problemes, f"{sortie} : double-clic, panneau non ouvert"]
            problemes += [
                *ecarts(f"{sortie} : ouvert", transparences(affichees), [TRANSPARENCE] * 2),
                *ecarts(f"{sortie} : entrées en plus", entrees_en_plus(doc), []),
            ]
            fermer()
            problemes += [
                *ecarts(f"{sortie} : rétablies", transparences(affichees), [30, 0]),
                *ecarts(f"{sortie} : entrées", doc.UndoNames, entrees),
                *ecarts(f"{sortie} : panneau fermé", bool(Gui.Control.activeDialog()), False),
            ]
        return problemes


def verifier_transparence_apres_inversion() -> list[str]:
    """« Inverser » recalcule l'aperçu : les mêmes objets restent transparents, puis rétablis."""
    with cadre("VerifTransparenceInversion") as (doc, pieces):
        creer_sans_valider(doc, pieces)
        affichees = usinees(pieces)
        bouton = widget(panneau(), "invertButton")
        bouton.click()
        bouton.click()
        problemes = ecarts("après inversion", transparences(affichees), [TRANSPARENCE] * 2)
        annuler()
        return problemes


def verifier_transparence_retablie_si_l_assemblage_est_supprime() -> list[str]:
    """Assemblage supprimé pendant son panneau : panneau fermé, pièces rétablies (la
    transparence n'est jamais écrite sur un objet supprimé : aucune exception)."""
    with cadre("VerifTransparenceSuppression") as (doc, pieces):
        tenon_valide(doc, pieces)
        poser_origines(pieces)
        affichees = usinees(pieces)
        joint = next(o for o in doc.Objects if hasattr(o, "HostPart"))
        double_cliquer(joint)
        doc.removeObject(joint.Name)
        Gui.updateGui()
        return [
            *ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False),
            *ecarts("rétablies", transparences(affichees), [30, 0]),
        ]


def verifier_transparence_retablie_par_edition_annuler() -> list[str]:
    """Édition > Annuler pendant la création : panneau fermé, brutes inchangées."""
    with cadre("VerifTransparenceStdUndo") as (doc, pieces):
        doc.clearUndos()
        creer_sans_valider(doc, pieces)
        Gui.Command.get("Std_Undo").run()
        Gui.updateGui()
        return [
            *ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False),
            *ecarts("brutes", transparences([pieces[r] for r in CADRE]), [0] * 4),
        ]


VERIFICATIONS_TRANSPARENCE_ASSEMBLAGE: tuple[Callable[[], list[str]], ...] = (
    verifier_transparence_a_la_creation_validee,
    verifier_transparence_a_la_creation_annulee,
    verifier_transparence_a_la_modification,
    verifier_transparence_apres_inversion,
    verifier_transparence_retablie_si_l_assemblage_est_supprime,
    verifier_transparence_retablie_par_edition_annuler,
)
