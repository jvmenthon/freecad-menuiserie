# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure », lot 4 (ADR 0046) : liste de débit, autres
objets, absence de répétition, icônes, ouverture par défaut.

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
from freecad.menuiserie.features.cutlist_object import find_cut_list
from freecad.menuiserie.gui.cutlist_preview import DIALOG_NAME
from freecad.menuiserie.gui.structure_panel import (
    DOCK_NAME,
    open_by_default,
    show_panel,
)
from freecad.menuiserie.gui.structure_preferences import closed_by_user, remember_closed
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import (
    KEY_ROLE,
    KIND_ROLE,
    item_for,
)
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_structure import avec_panneau, noms_selectionnes, traiter
from tests.gui.verifications_structure_lot3 import actions_de, menu_de
from tests.integration.bureau import Bureau

# --- Lot 4 : liste de débit, autres objets, répétition ------------------------------------


def _lignes(arbre: Any) -> list[tuple[str, str, str]]:
    """(genre, texte, clé) de chaque ligne de l'arbre, en profondeur d'abord."""
    lignes: list[tuple[str, str, str]] = []
    iterateur = QtGui.QTreeWidgetItemIterator(arbre)
    while iterateur.value():
        ligne = iterateur.value()
        lignes.append(
            (
                str(ligne.data(0, KIND_ROLE) or ""),
                ligne.text(0),
                str(ligne.data(0, KEY_ROLE) or ""),
            )
        )
        iterateur += 1
    return lignes


def _genres(arbre: Any, genre: NodeKind) -> list[tuple[str, str, str]]:
    return [ligne for ligne in _lignes(arbre) if ligne[0] == genre.value]


def _verifier_bureau_sans_ligne_parasite(
    _bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Un bureau ordinaire (Std Part, Origine, sources) ne produit ni « Autres objets », ni
    répétition, ni liste de débit : si l'heuristique de ``structure_foreign`` se trompe, la liste
    des lignes parasites est écrite ici."""
    parasites = [
        ligne
        for ligne in _lignes(arbre)
        if ligne[0]
        in (NodeKind.OTHERS.value, NodeKind.OTHER.value, NodeKind.REPEAT.value, NodeKind.COPY.value)
    ]
    return ecarts("lignes parasites", parasites, [])


def _verifier_liste_de_debit(
    bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync
) -> list[str]:
    feuille = api.make_cut_list(bureau.doc)
    bureau.doc.recompute()
    synchro.refresh_now(force=True)
    traiter()
    liste = find_cut_list(bureau.doc)
    if liste is None:
        return ["objet liste de débit absent"]
    lignes = _genres(arbre, NodeKind.CUTLIST)
    problemes = ecarts("une seule ligne de liste", [cle for _g, _t, cle in lignes], [liste.Name])
    problemes += ecarts("tableur non montré", item_for(arbre, feuille.Name), None)
    ligne = item_for(arbre, liste.Name)
    if ligne is None:
        return [*problemes, "ligne de la liste absente"]
    problemes += ecarts("liste à la racine", ligne.parent(), None)
    ligne.setSelected(True)
    traiter()
    problemes += ecarts("clic : liste sélectionnée", noms_selectionnes(), [liste.Name])
    arbre.itemDoubleClicked.emit(ligne, 0)
    traiter()
    # Le double-clic de la liste ouvre l'aperçu (fenêtre non modale), pas un panneau de tâche.
    apercus = [
        d for d in Gui.getMainWindow().findChildren(QtGui.QDialog, DIALOG_NAME) if d.isVisible()
    ]
    actif = QtGui.QApplication.activeWindow()
    diagnostic = (
        f"fenêtres ouvertes {[(d.objectName(), d.windowTitle()) for d in apercus]}, "
        f"panneau de tâche {bool(Gui.Control.activeDialog())}, "
        f"fenêtre active {None if actif is None else actif.windowTitle()!r}"
    )
    App.Console.PrintMessage(f"Menuiserie : diagnostic double-clic liste, {diagnostic}\n")
    problemes += ecarts("double-clic : aperçu de la liste ouvert", len(apercus), 1)
    for apercu in apercus:
        apercu.close()
    traiter()
    return problemes


def _verifier_autres_objets(
    bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync
) -> list[str]:
    boite = bureau.doc.addObject("Part::Box", "BoiteEtrangere")
    boite.Label = "Boite d'un autre atelier"
    bureau.doc.recompute()
    avant = (boite.Label, tuple(boite.Placement.Base), len(bureau.doc.Objects))
    synchro.refresh_now(force=True)
    traiter()
    noeuds = _genres(arbre, NodeKind.OTHERS)
    problemes = ecarts(
        "un nœud « Autres objets »", [t for _g, t, _c in noeuds], ["Autres objets (1)"]
    )
    ligne = item_for(arbre, boite.Name)
    if ligne is None:
        return [*problemes, "ligne de l'objet étranger absente"]
    parent = ligne.parent()
    problemes += ecarts("replié", None if parent is None else parent.isExpanded(), False)
    problemes += ecarts("glissable", bool(ligne.flags() & QtCore.Qt.ItemIsDragEnabled), False)
    # double-clic : rien ne s'ouvre ; menu : tout est grisé, raison expliquée
    arbre.itemDoubleClicked.emit(ligne, 0)
    traiter()
    problemes += ecarts("double-clic : aucun panneau", bool(Gui.Control.activeDialog()), False)
    entrees = menu_de(arbre, boite.Name)
    problemes += ecarts("menu : tout grisé", [on for _t, on, _tip in entrees], [False] * 6)
    problemes += ecarts("menu : raison", all(tip for _t, _on, tip in entrees), True)
    actions = actions_de(_dock)
    refus = [actions.run_action(a, [boite.Name]) for a in (Action.OPEN, Action.DELETE)]
    problemes += ecarts("ouvrir et supprimer refusés", refus, [False, False])
    # la sélection (lecture) fonctionne dans les deux sens
    ligne.setSelected(True)
    traiter()
    problemes += ecarts("sélection de l'objet", noms_selectionnes(), [boite.Name])
    # dépôt refusé sur la ligne : raison (infobulle) et aucune écriture
    point = arbre.visualItemRect(ligne).center()
    problemes += ecarts("dépôt refusé sur un autre objet", bool(arbre.blocked_reason(point)), True)
    apres = (boite.Label, tuple(boite.Placement.Base), len(bureau.doc.Objects))
    return problemes + ecarts("objet étranger intact", apres, avant)


def _verifier_aucune_repetition(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Sans type Répétition dans la branche, le point d'extension est vide : aucune ligne « xN »
    et toutes les pièces du bureau restent à plat, comme aux lots précédents."""
    problemes = ecarts("aucune répétition", _genres(arbre, NodeKind.REPEAT), [])
    problemes += ecarts("aucune copie", _genres(arbre, NodeKind.COPY), [])
    return problemes + ecarts(
        "pièce du bureau toujours montrée",
        item_for(arbre, bureau.shown("P").Name) is not None,
        True,
    )


def verifier_structure_bureau_ordinaire() -> list[str]:
    return avec_panneau(_verifier_bureau_sans_ligne_parasite)


def verifier_structure_liste_de_debit() -> list[str]:
    return avec_panneau(_verifier_liste_de_debit)


def verifier_structure_autres_objets() -> list[str]:
    return avec_panneau(_verifier_autres_objets)


def verifier_structure_sans_repetition() -> list[str]:
    return avec_panneau(_verifier_aucune_repetition)


def _verifier_icones(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    """Chaque ligne a l'icône de son genre (aucune si Qt ne lit pas le SVG : sans erreur)."""
    problemes: list[str] = []
    for genre, nom in ICON_BY_KIND.items():
        attendu = QtGui.QIcon(icon_path(nom)).isNull()
        for _g, _texte, cle in _genres(arbre, genre):
            ligne = item_for(arbre, cle)
            if ligne is not None:
                problemes += ecarts(f"icône {genre.value}", ligne.icon(0).isNull(), attendu)
    vus = {genre for genre in NodeKind if _genres(arbre, genre)}
    problemes += ecarts("genres vus", NodeKind.FURNITURE in vus and NodeKind.PIECE in vus, True)
    # Les tourillons du bureau sont de la quincaillerie, avec l'icône de leur commande.
    problemes += ecarts("quincaillerie vue", NodeKind.HARDWARE_ITEM in vus, True)
    attendu = QtGui.QIcon(icon_path("Menuiserie_Dowels.svg")).isNull()
    for _g, _texte, cle in _genres(arbre, NodeKind.HARDWARE_ITEM):
        ligne = item_for(arbre, cle)
        if ligne is not None:
            problemes += ecarts("icône tourillons", ligne.icon(0).isNull(), attendu)
    return problemes


def verifier_structure_icones() -> list[str]:
    return avec_panneau(_verifier_icones)


def _docks() -> list[Any]:
    return list(Gui.getMainWindow().findChildren(QtGui.QDockWidget, DOCK_NAME))


def _retirer_docks() -> None:
    for dock in _docks():
        dock.setParent(None)
        dock.deleteLater()
    traiter()


def verifier_structure_ouverture_par_defaut() -> list[str]:
    """Ouverture seule à l'activation, sans doublon, sauf si l'utilisateur l'a fermé (réglage
    des préférences)."""
    avant = closed_by_user()
    try:
        _retirer_docks()
        remember_closed(True)
        open_by_default()
        traiter()
        problemes = ecarts("fermé par l'utilisateur : pas d'ouverture", len(_docks()), 0)
        remember_closed(False)
        open_by_default()
        open_by_default()
        traiter()
        problemes += ecarts("ouvert une seule fois", len(_docks()), 1)
        problemes += ecarts("ouverture seule : réglage gardé", closed_by_user(), False)
        _docks()[0].close()
        traiter()
        problemes += ecarts("fermeture mémorisée", closed_by_user(), True)
        open_by_default()
        problemes += ecarts("fermé : pas de doublon", len(_docks()), 1)
        show_panel()
        traiter()
        problemes += ecarts("commande : réglage levé", closed_by_user(), False)
        return problemes
    finally:
        _retirer_docks()
        remember_closed(avant)


VERIFICATIONS_STRUCTURE_LOT4: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_bureau_ordinaire,
    verifier_structure_liste_de_debit,
    verifier_structure_autres_objets,
    verifier_structure_sans_repetition,
    verifier_structure_icones,
    verifier_structure_ouverture_par_defaut,
)
