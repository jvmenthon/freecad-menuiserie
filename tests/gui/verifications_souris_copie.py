# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la copie par glissement : Ctrl + flèche (lot R-d de
``docs/specs/repetition.md``, critères R17 et R18).

R17 : le lâcher crée une répétition d'une copie liée, au bon endroit, en une transaction, et ouvre
le panneau « Modifier la répétition » ; R18 : Échap, un simple clic ou un refus ne laissent rien.
Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : comme
``verifications_souris``, il appelle la session ou le filtre directement, jamais ``sendEvent``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie import api
from freecad.menuiserie.core.repeat import RepeatParams
from freecad.menuiserie.features import repeat
from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.copying import check_copyable
from tests.gui.verifications_double_clic import vue_3d_active
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    ecarts,
    formulaire_nomme,
    piece_validee,
)
from tests.gui.verifications_repetition import FORM
from tests.gui.verifications_souris import (
    place,
    preparer,
    proche,
    px_en_mm,
    selection_dessinee,
    souris,
    sur_la_fleche,
    tirer,
)

COPIE = "Répéter"


def saisir_avec_ctrl(session: Any, axe: int = 0) -> bool:
    """Ctrl + clic gauche enfoncé sur la flèche ``axe`` de la pièce."""
    return bool(session.press(sur_la_fleche(session, axe, 40.0), False, True))


def copies(doc: Any) -> list[Any]:
    return [o for o in doc.Objects if repeat.is_copy(o)]


def repetition(copie: Any) -> Any:
    found: Any = api.repeat_of(copie)
    return found


def panneau_ouvert() -> bool:
    return formulaire_nomme(FORM) is not None


def _copie_par_glissement(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    avant = place(piece)
    selection_dessinee(piece)
    pas = px_en_mm(session)
    problemes = [*ecarts("Ctrl + flèche saisie", saisir_avec_ctrl(session), True)]
    voulu = tirer(session, 150.0)
    fantome = session.state.ghost
    problemes += [
        *ecarts("copie : la pièce reste en place", place(piece), avant),
        *ecarts("fantôme décalé", fantome is not None and abs(fantome.x - 150.0) < 3 * pas, True),
        *ecarts("aucune copie avant le lâcher", copies(doc), []),
        *ecarts("aucune transaction avant le lâcher", doc.UndoNames, []),
    ]
    problemes += ecarts("relâchement consommé", session.release(voulu), True)
    if not copies(doc):
        return [*problemes, "aucune copie créée au lâcher"]
    copie = copies(doc)[0]
    rep = repetition(copie)
    problemes += [
        *ecarts("une seule copie", len(copies(doc)), 1),
        *ecarts("l'original n'a pas bougé", place(piece), avant),
        *proche("copie à 150 mm (x)", copie.Placement.Base.x, avant[0] + 150.0, 3 * pas),
        *ecarts("copie sur l'axe (y, z)", place(copie)[1:], avant[1:]),
        *proche("pas de la répétition", rep.Step.Value, 150.0, 3 * pas),
        *ecarts("nombre de copies", rep.Count, 1),
        *ecarts("axe X, sens positif", (rep.Axis, rep.Reverse), ("X", False)),
        *ecarts("une seule transaction", doc.UndoNames, [COPIE]),
        *ecarts("panneau « Modifier la répétition » ouvert", panneau_ouvert(), True),
        *ecarts("plus de flèches sous le panneau", session.active, False),
    ]
    annuler()
    problemes += ecarts("« Annuler » du panneau garde la copie", len(copies(doc)), 1)
    doc.undo()
    return [
        *problemes,
        *ecarts("Ctrl+Z : copie et répétition défaites", len(copies(doc)), 0),
        *ecarts("Ctrl+Z : l'original reste", place(piece), avant),
    ]


def verifier_souris_copie() -> list[str]:
    """R17 : Ctrl + flèche tirée de 150 mm, lâcher : une copie liée à 150 mm, l'original en place,
    une transaction, panneau ouvert ; Ctrl+Z défait la copie."""
    return avec_document("VerifSourisCopie", _copie_par_glissement)


def _copie_en_arriere(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    avant = place(piece)
    selection_dessinee(piece)
    pas = px_en_mm(session)
    saisir_avec_ctrl(session, 1)
    voulu = tirer(session, -90.0, shift=True)  # Maj : sans aimantation, la copie reste Ctrl
    problemes = ecarts("Ctrl+Maj : toujours une copie", type(session.state).__name__, "Copying")
    session.release(voulu)
    if not copies(doc):
        return [*problemes, "aucune copie créée au lâcher"]
    rep = repetition(copies(doc)[0])
    return [
        *problemes,
        *proche("pas de 90 mm", rep.Step.Value, 90.0, 3 * pas),
        *ecarts("axe Y, sens inverse", (rep.Axis, rep.Reverse), ("Y", True)),
        *proche("copie à -90 mm (y)", copies(doc)[0].Placement.Base.y, avant[1] - 90.0, 3 * pas),
        *ecarts("l'original n'a pas bougé", place(piece), avant),
    ]


def verifier_souris_copie_en_arriere() -> list[str]:
    """Ctrl + Maj, flèche Y tirée vers le négatif : axe Y, ``Reverse``, original en place."""
    return avec_document("VerifSourisCopieArriere", _copie_en_arriere)


def _echap_et_clic(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    avant = place(piece)
    selection_dessinee(piece)
    problemes = [*ecarts("Ctrl + flèche saisie", saisir_avec_ctrl(session), True)]
    voulu = tirer(session, 100.0)
    problemes += [
        *ecarts("Échap consommé", session.escape(), True),
        *ecarts("glissement fini", session.dragging, False),
        *ecarts("fantôme enlevé", session.state.ghost, None),
        *ecarts("rien de créé", len(copies(doc)), 0),
        *ecarts("répétition absente", doc.getObject("Repeat"), None),
        *ecarts("historique inchangé", doc.UndoNames, []),
        *ecarts("pièce en place", place(piece), avant),
        *ecarts("relâchement consommé", session.release(voulu), True),
        *ecarts("puis rendu à FreeCAD", session.release(voulu), False),
        *ecarts("pas de panneau", panneau_ouvert(), False),
    ]
    saisir_avec_ctrl(session)
    session.release(session.state.cursor)  # clic sans glissement
    return [
        *problemes,
        *ecarts("clic sans glissement : rien de créé", len(copies(doc)), 0),
        *ecarts("clic sans glissement : historique", doc.UndoNames, []),
        *ecarts("clic sans glissement : pas de panneau", panneau_ouvert(), False),
    ]


def verifier_souris_copie_annulee() -> list[str]:
    """R18 : Échap et simple clic avec Ctrl ne créent rien (ni copie, ni transaction, ni
    panneau)."""
    return avec_document("VerifSourisCopieAnnulee", _echap_et_clic)


def _copie_d_une_copie(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    api.make_repeat([piece], RepeatParams(count=1, step=200.0))
    doc.recompute()
    doc.clearUndos()
    copie = copies(doc)[0]
    selection_dessinee(copie)
    try:
        check_copyable(copie)
        refus = ""
    except ValueError as erreur:
        refus = str(erreur)
    fleches = len(session.layout.arrows) if session.active else 0
    problemes = [
        *ecarts("copie liée : aucune flèche à saisir", fleches, 0),
        *ecarts("copie liée : refus expliqué", "copie liée" in refus, True),
        *ecarts("une seule copie", len(copies(doc)), 1),
        *ecarts("historique inchangé", doc.UndoNames, []),
    ]
    Gui.Selection.clearSelection()
    return problemes


def verifier_souris_copie_d_une_copie() -> list[str]:
    """Une copie liée n'a pas de flèche (placement piloté par la répétition) : Ctrl + glisser ne
    peut pas la saisir ; le garde-fou ``check_copyable`` la refuse avec un message."""
    return avec_document("VerifSourisCopieDeCopie", _copie_d_une_copie)


def _filtre(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    selection_dessinee(piece)
    viewport = vue_3d_active(doc)
    filtre = events._INSTALLATION.filter
    if viewport is None or filtre is None:
        return ["vue 3D ou filtre absents"]
    gauche, ctrl = QtCore.Qt.LeftButton, QtCore.Qt.ControlModifier
    ctrl_maj = ctrl | QtCore.Qt.ShiftModifier
    press, move, release = (
        QtCore.QEvent.MouseButtonPress,
        QtCore.QEvent.MouseMove,
        QtCore.QEvent.MouseButtonRelease,
    )
    sur = sur_la_fleche(session, 0, 40.0)
    problemes = ecarts(
        "Ctrl + clic ailleurs : rendu à FreeCAD (sélection multiple)",
        bool(filtre.eventFilter(viewport, souris(viewport, press, (5, 5), gauche, ctrl))),
        False,
    )
    problemes += ecarts("aucun glissement", session.dragging, False)
    pris = filtre.eventFilter(viewport, souris(viewport, press, sur, gauche, ctrl_maj))
    problemes += ecarts("Ctrl + Maj + clic sur la flèche pris", bool(pris), True)
    problemes += ecarts("copie en cours", type(session.state).__name__, "Copying")
    voulu = tirer(session, 80.0, deplacer=False)
    bouge = filtre.eventFilter(viewport, souris(viewport, move, voulu, gauche, ctrl_maj))
    lache = filtre.eventFilter(viewport, souris(viewport, release, voulu, gauche, ctrl_maj))
    return [
        *problemes,
        *ecarts("mouvement consommé", bool(bouge), True),
        *ecarts("relâchement consommé", bool(lache), True),
        *ecarts("une copie créée", len(copies(doc)), 1),
    ]


def verifier_souris_copie_filtre() -> list[str]:
    """Le filtre prend Ctrl + clic sur une flèche et laisse à FreeCAD Ctrl + clic ailleurs."""
    return avec_document("VerifSourisCopieFiltre", _filtre)


VERIFICATIONS_SOURIS_COPIE: tuple[Callable[[], list[str]], ...] = (
    verifier_souris_copie,
    verifier_souris_copie_en_arriere,
    verifier_souris_copie_annulee,
    verifier_souris_copie_d_une_copie,
    verifier_souris_copie_filtre,
)
