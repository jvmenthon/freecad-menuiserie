# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure » avec de vraies répétitions (ADR 0046, lot 4 ;
ADR 0043 et 0044) : ligne « <nom> xN » dépliable en ses copies, pièces et ensembles répétés,
icônes, sélection, transparence de toutes les copies, double-clic « Modifier la répétition »,
menu, dissociation, pas de glisser-déposer sur une copie.

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) ; chaque vérification
renvoie la liste de ses problèmes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.structure_icons import ICON_BY_KIND
from freecad.menuiserie.core.structure_menu import Action
from freecad.menuiserie.core.structure_tree import NodeKind
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import KIND_ROLE, item_for
from tests.gui.verifications_panneau import annuler, ecarts
from tests.gui.verifications_structure import avec_panneau, noms_selectionnes, traiter
from tests.gui.verifications_structure_lot3 import actions_de, menu_de
from tests.gui.verifications_structure_lot4 import genres_de, lignes_de
from tests.gui.verifications_structure_selection import SELECTION, choisir_lignes, etat
from tests.integration.bureau import Bureau

TIMES = chr(0x00D7)  # signe de multiplication des lignes de répétition
PANNEAU = "RepeatTaskPanel"


def _planche_repetee(bureau: Bureau, synchro: StructureSync) -> tuple[Any, Any]:
    """Planche libre répétée deux fois (pas de 700 mm sur X) ; l'arbre est relu."""
    planche = api.make_wood_part(600, 300, 19, "chene", mark="Planche", doc=bureau.doc)
    bureau.doc.recompute()
    repetition = api.make_repeat(
        [planche], api.RepeatParams(count=2, step=700.0, axis=api.RepeatAxis.X)
    )
    bureau.doc.recompute()
    synchro.refresh_now(force=True)
    traiter()
    return planche, repetition


def _parent(arbre: Any, cle: str) -> str | None:
    """Texte de la ligne parente de la ligne ``cle`` (``None`` : racine ou ligne absente)."""
    ligne = item_for(arbre, cle)
    parent = None if ligne is None else ligne.parent()
    return None if parent is None else str(parent.text(0))


def _copies(repetition: Any) -> list[Any]:
    return [obj for obj in repetition.InList if api.repeat_of(obj) == repetition]


def _lignes_et_icones(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
    planche, repetition = _planche_repetee(bureau, synchro)
    copies = _copies(repetition)
    lignes = genres_de(arbre, NodeKind.REPEAT)
    problemes = ecarts(
        "une ligne de répétition",
        [(t, c) for _g, t, c in lignes],
        [(f"{repetition.Label} {TIMES}2", repetition.Name)],
    )
    ligne = item_for(arbre, repetition.Name)
    if ligne is None:
        return [*problemes, "ligne de la répétition absente"]
    problemes += ecarts("repliée", ligne.isExpanded(), False)
    problemes += ecarts(
        "chaque copie sous la ligne de répétition",
        [_parent(arbre, c.Name) for c in copies],
        [ligne.text(0)] * 2,
    )
    cles = [cle for _g, _t, cle in lignes_de(arbre) if cle]
    problemes += ecarts("aucune ligne en double", len(cles), len(set(cles)))
    problemes += ecarts(
        "planche d'origine : ligne ordinaire à la racine", _parent(arbre, planche.Name), None
    )
    for genre in (NodeKind.REPEAT, NodeKind.COPY):
        attendu = QtGui.QIcon(icon_path(ICON_BY_KIND[genre])).isNull()
        for _g, _t, cle in genres_de(arbre, genre):
            rang = item_for(arbre, cle)
            icone = None if rang is None else rang.icon(0).isNull()
            problemes += ecarts(f"icône {genre.value}", icone, attendu)
    problemes += ecarts(
        "répétition non glissable", bool(ligne.flags() & QtCore.Qt.ItemIsDragEnabled), False
    )
    return problemes


def verifier_structure_repetition_lignes() -> list[str]:
    return avec_panneau(_lignes_et_icones)


def _transparence(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
    """Une répétition met en évidence toutes ses copies ; une copie, elle seule."""
    planche, repetition = _planche_repetee(bureau, synchro)
    premiere, seconde = _copies(repetition)
    choisir_lignes(arbre, repetition.Name)
    problemes = ecarts(
        "répétition : ses deux copies", [etat(premiere), etat(seconde)], [SELECTION] * 2
    )
    problemes += ecarts("répétition : l'original intact", etat(planche)[0], 0)
    choisir_lignes(arbre, premiere.Name)
    problemes += ecarts("copie : elle seule", etat(premiere), SELECTION)
    problemes += ecarts("copie : l'autre intacte", etat(seconde)[0], 0)
    problemes += ecarts("sélection synchronisée", noms_selectionnes(), [premiere.Name])
    choisir_lignes(arbre)
    return problemes + ecarts(
        "désélection : origine", [etat(premiere)[0], etat(seconde)[0]], [0, 0]
    )


def verifier_structure_repetition_transparence() -> list[str]:
    return avec_panneau(_transparence)


def _double_clic(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
    """Double-clic sur la répétition ou sur une copie : « Modifier la répétition »."""
    _planche, repetition = _planche_repetee(bureau, synchro)
    problemes: list[str] = []
    for cle in (repetition.Name, _copies(repetition)[0].Name):
        ligne = item_for(arbre, cle)
        if ligne is None:
            problemes.append(f"ligne {cle} absente")
            continue
        arbre.itemDoubleClicked.emit(ligne, 0)
        traiter()
        panneau = Gui.Control.activeTaskDialog() if Gui.Control.activeDialog() else None
        problemes += ecarts(f"double-clic {cle}", type(panneau).__name__, PANNEAU)
        if panneau is not None:
            annuler()
        traiter()
    return problemes


def verifier_structure_repetition_double_clic() -> list[str]:
    return avec_panneau(_double_clic)


def _menu_et_dissociation(
    bureau: Bureau, dock: Any, arbre: Any, synchro: StructureSync
) -> list[str]:
    """Menu d'une copie (Modifier la répétition, Dissocier la copie), pas de dépôt sur une copie,
    copie non glissable, puis dissociation : la ligne devient une pièce ordinaire."""
    _planche, repetition = _planche_repetee(bureau, synchro)
    premiere, seconde = _copies(repetition)
    ligne = item_for(arbre, premiere.Name)
    if ligne is None:
        return ["ligne de la copie absente"]
    entrees = menu_de(arbre, premiere.Name)
    textes = [texte for texte, _actif, _tip in entrees]
    problemes = ecarts("menu : modifier la répétition", "Modifier la répétition" in textes, True)
    problemes += ecarts("menu : dissocier la copie", "Dissocier la copie" in textes, True)
    problemes += ecarts(
        "copie non glissable", bool(ligne.flags() & QtCore.Qt.ItemIsDragEnabled), False
    )
    point = arbre.visualItemRect(ligne).center()
    problemes += ecarts("dépôt refusé sur une copie", bool(arbre.blocked_reason(point)), True)
    avant = len(bureau.doc.Objects)
    actions = actions_de(dock)
    problemes += ecarts(
        "dissocier : fait", actions.run_action(Action.DISSOCIATE, [premiere.Name]), True
    )
    traiter()
    synchro.refresh_now(force=True)
    traiter()
    problemes += ecarts("copie dissociée : plus de répétition", api.repeat_of(premiere), None)
    problemes += ecarts("autre copie : toujours liée", api.repeat_of(seconde), repetition)
    problemes += ecarts("aucun objet créé ni perdu", len(bureau.doc.Objects), avant)
    ligne = item_for(arbre, repetition.Name)
    problemes += ecarts(
        "ligne mise à jour",
        None if ligne is None else ligne.text(0),
        f"{repetition.Label} {TIMES}1",
    )
    nouvelle = item_for(arbre, premiere.Name)
    problemes += ecarts(
        "dissociée : pièce ordinaire à la racine",
        None if nouvelle is None else (nouvelle.parent(), nouvelle.data(0, KIND_ROLE)),
        (None, NodeKind.PIECE.value),
    )
    return problemes


def verifier_structure_repetition_menu() -> list[str]:
    return avec_panneau(_menu_et_dissociation)


def _ensemble_repete(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
    """Le bureau répété : la copie est une ligne d'ensemble complet sous la répétition (ses
    pièces dedans, jamais son Std Part) ; la sélectionner met en évidence ses pièces."""
    repetition = api.make_repeat(
        [bureau.furniture], api.RepeatParams(count=1, step=1500.0, axis=api.RepeatAxis.Y)
    )
    bureau.doc.recompute()
    synchro.refresh_now(force=True)
    traiter()
    (copie,) = [o for o in repetition.InList if api.repeat_of(o) == repetition and is_furniture(o)]
    lignes = lignes_de(arbre)
    cles = [cle for _g, _t, cle in lignes if cle]
    parts = [c for c in cles if bureau.doc.getObject(c).TypeId == "App::Part"]
    ligne = item_for(arbre, copie.Name)
    problemes = ecarts("aucun Std Part montré", parts, [])
    problemes += ecarts("aucune ligne en double", len(cles), len(set(cles)))
    problemes += ecarts(
        "la copie est une ligne COPY sous la répétition",
        None if ligne is None else (ligne.data(0, KIND_ROLE), ligne.parent().text(0)),
        (NodeKind.COPY.value, f"{repetition.Label} {TIMES}1"),
    )
    problemes += ecarts(
        "la copie contient des pièces", ligne is not None and ligne.childCount() > 0, True
    )
    choisir_lignes(arbre, copie.Name)
    pieces = [o for o in bureau.doc.Objects if api.furniture_of(o) == copie and not is_furniture(o)]
    attendus = [(api.machined_part_of(p) or p) for p in pieces]
    problemes += ecarts(
        "copie d'ensemble : ses pièces en évidence",
        [etat(p) for p in attendus],
        [SELECTION] * len(attendus),
    )
    choisir_lignes(arbre)
    arbre.itemDoubleClicked.emit(ligne, 0)
    traiter()
    panneau = Gui.Control.activeTaskDialog() if Gui.Control.activeDialog() else None
    problemes += ecarts("double-clic sur la copie d'ensemble", type(panneau).__name__, PANNEAU)
    if panneau is not None:
        annuler()
    traiter()
    return problemes + ecarts("document sain", App.ActiveDocument is not None, True)


def verifier_structure_repetition_ensemble() -> list[str]:
    return avec_panneau(_ensemble_repete)


VERIFICATIONS_STRUCTURE_REPETITION: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_repetition_lignes,
    verifier_structure_repetition_transparence,
    verifier_structure_repetition_double_clic,
    verifier_structure_repetition_menu,
    verifier_structure_repetition_ensemble,
)
