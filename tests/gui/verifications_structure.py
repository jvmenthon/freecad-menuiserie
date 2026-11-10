# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure » (ADR 0046, lots 2 et 3) : rafraîchissement,
sélection dans les deux sens, double-clic, détachement des observateurs ; menu contextuel
(entrées, grisées expliquées), renommer, ranger / sortir / refuser un dépôt, créer un
sous-ensemble, supprimer, ouvrir. Le glissement à la souris ne se simule pas hors écran : le dépôt
est exercé par le rappel ``on_drop`` de l'arbre (``dropEvent``) et le survol par ``judge``
(``dragMoveEvent``). Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) ; chaque vérification renvoie la liste de
ses problèmes. Les minuteries à 0 ms sont exécutées par ``processEvents``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, cast

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.structure_menu import Action
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.gui.structure_actions import StructureActions
from freecad.menuiserie.gui.structure_panel import DOCK_NAME, TREE_NAME, show_panel
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import KEY_ROLE, item_for, selected_keys
from tests.gui.verifications_assemblages import choix_de_suppression
from tests.gui.verifications_debit import avec_bureau
from tests.gui.verifications_ensemble import boite_de_refus
from tests.gui.verifications_panneau import ecarts
from tests.integration.bureau import Bureau


def _traiter() -> None:
    for _ in range(3):
        QtGui.QApplication.processEvents()


def _panneau() -> tuple[Any, Any, StructureSync]:
    show_panel()
    _traiter()
    fenetre = Gui.getMainWindow()
    dock = fenetre.findChild(QtGui.QDockWidget, DOCK_NAME)
    return dock, dock.findChild(QtGui.QTreeWidget, TREE_NAME), dock.findChild(StructureSync)


def _noms_selectionnes() -> list[str]:
    return [objet.Name for objet in Gui.Selection.getSelection()]


def _avec_panneau(
    verification: Callable[[Bureau, Any, Any, StructureSync], list[str]],
) -> list[str]:
    def corps(bureau: Bureau) -> list[str]:
        dock, arbre, synchro = _panneau()
        try:
            return verification(bureau, dock, arbre, synchro)
        finally:
            Gui.Control.closeDialog()
            dock.hide()
            _traiter()

    return avec_bureau("structure", corps)


def _verifier_lignes_et_selection(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece = bureau.shown("P").Name
    ligne = item_for(arbre, piece)
    problemes = [] if ligne is not None else [f"aucune ligne pour {piece}"]
    if ligne is None:
        return problemes
    # panneau -> FreeCAD
    ligne.setSelected(True)
    _traiter()
    problemes += ecarts("clic sur une ligne", _noms_selectionnes(), [piece])
    # FreeCAD -> panneau, par la brute (une seule ligne pour la brute et la pièce usinée)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(bureau.doc.Name, bureau.parts["JG"].Name)
    _traiter()
    problemes += ecarts("sélection côté FreeCAD", selected_keys(arbre), [bureau.shown("JG").Name])
    # pas de rétroaction : la sélection de FreeCAD n'a pas été remplacée
    problemes += ecarts("pas d'écho", _noms_selectionnes(), [bureau.parts["JG"].Name])
    Gui.Selection.clearSelection()
    _traiter()
    return problemes + ecarts("sélection vidée", selected_keys(arbre), [])


def _verifier_rafraichissement(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece = bureau.shown("P")
    bureau.parts["P"].Label = "Dessus de test"
    bureau.doc.recompute()
    _traiter()
    ligne = item_for(arbre, piece.Name)
    texte = ligne.text(0) if ligne is not None else None
    return ecarts("libellé suivi", texte, "Dessus de test")


def _verifier_double_clic(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    ligne = item_for(arbre, bureau.shown("P").Name)
    if ligne is None:
        return ["ligne du plateau absente"]
    arbre.itemDoubleClicked.emit(ligne, 0)
    _traiter()
    return ecarts("panneau de tâche ouvert", bool(Gui.Control.activeDialog()), True)


def _verifier_detachement(
    bureau: Bureau, dock: Any, arbre: Any, synchro: StructureSync
) -> list[str]:
    problemes = ecarts("observateurs posés", synchro.attached, True)
    dock.hide()
    _traiter()
    problemes += ecarts("observateurs retirés à la fermeture", synchro.attached, False)
    bureau.parts["P"].Label = "Après fermeture"
    _traiter()
    ligne = item_for(arbre, bureau.shown("P").Name)
    texte = ligne.text(0) if ligne is not None else None
    problemes += [] if texte != "Après fermeture" else ["panneau fermé mais encore mis à jour"]
    show_panel()
    _traiter()
    return problemes + ecarts("observateurs reposés", synchro.attached, True)


def verifier_structure_selection() -> list[str]:
    return _avec_panneau(_verifier_lignes_et_selection)


def verifier_structure_rafraichissement() -> list[str]:
    return _avec_panneau(_verifier_rafraichissement)


def verifier_structure_double_clic() -> list[str]:
    return _avec_panneau(_verifier_double_clic)


def verifier_structure_detachement() -> list[str]:
    return _avec_panneau(_verifier_detachement)


# --- Lot 3 : menu contextuel et glisser-déposer ---------------------------------------------

ENTREES_PIECE = [
    "Ouvrir",
    "Renommer…",
    "Ajouter à l'ensemble",
    "Sortir de l'ensemble",
    "Créer un sous-ensemble depuis la sélection",
    "Supprimer",
]


def _actions(dock: Any) -> StructureActions:
    return cast(StructureActions, dock.findChild(StructureActions))


def _menu_de(arbre: Any, cle: str) -> list[tuple[str, bool, str]]:
    """Entrées (texte, active, infobulle) du vrai menu contextuel de la ligne ``cle``, capturées
    pendant qu'il est ouvert puis refermé par une minuterie."""
    ligne = item_for(arbre, cle)
    if ligne is None:
        return []
    ancetre = ligne.parent()
    while ancetre is not None:
        ancetre.setExpanded(True)
        ancetre = ancetre.parent()
    saisies: list[tuple[str, bool, str]] = []

    def capturer() -> None:
        menu = QtGui.QApplication.activePopupWidget()
        if menu is not None:
            saisies.extend(
                (a.text(), a.isEnabled(), a.toolTip())
                for a in menu.actions()
                if not a.isSeparator()
            )
            menu.close()

    QtCore.QTimer.singleShot(150, capturer)
    arbre.customContextMenuRequested.emit(arbre.visualItemRect(ligne).center())
    return saisies


@contextmanager
def _saisie(reponse: str) -> Iterator[None]:
    """Fenêtre « Renommer » remplacée (hors écran, une boîte modale ne se clique pas)."""
    original = QtGui.QInputDialog.getText
    QtGui.QInputDialog.getText = staticmethod(lambda *_args, **_kwargs: (reponse, True))
    try:
        yield
    finally:
        QtGui.QInputDialog.getText = staticmethod(original)


def _armoire(bureau: Bureau) -> tuple[Any, Any, Any]:
    """Une pièce libre, et une armoire qui contient une étagère ; historique vidé."""
    libre = api.make_wood_part(600, 300, 18, "chene", mark="Libre", doc=bureau.doc)
    etagere = api.make_wood_part(500, 300, 18, "chene", mark="Etagere", doc=bureau.doc)
    armoire, _ = api.make_furniture([etagere], label="Armoire")
    bureau.doc.recompute()
    bureau.doc.UndoMode = 1
    bureau.doc.clearUndos()
    _traiter()
    return libre, etagere, armoire


def _ensemble_de(piece: Any) -> str | None:
    ensemble = furniture_of(piece)
    return None if ensemble is None else str(ensemble.Name)


def _annuler(doc: Any) -> None:
    """Ctrl+Z puis recalcul, comme les vérifications de l'ensemble (liens rétablis par l'annulation
    relus après le recalcul)."""
    doc.undo()
    doc.recompute()
    _traiter()


def _ligne_dans(arbre: Any, cle: str) -> str | None:
    """Clé de la ligne parente de la ligne ``cle`` (``None`` : à la racine)."""
    ligne = item_for(arbre, cle)
    parent = None if ligne is None else ligne.parent()
    return None if parent is None else str(parent.data(0, KEY_ROLE))


def _verifier_menu(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    plateau = bureau.shown("P").Name
    entrees = _menu_de(arbre, plateau)
    problemes = ecarts("entrées d'une pièce", [t for t, _on, _tip in entrees], ENTREES_PIECE)
    problemes += ecarts("pièce : tout est actif", [on for _t, on, _tip in entrees], [True] * 6)
    problemes += ecarts("ligne clic droit sélectionnée", selected_keys(arbre), [plateau])
    joue = _menu_de(arbre, bureau.shown("JG").Name)
    sortir = [(on, tip) for t, on, tip in joue if t == "Sortir de l'ensemble"]
    problemes += ecarts("joue : sortir grisé", [on for on, _tip in sortir], [False])
    problemes += ecarts("joue : raison", all("assemblée à" in tip for _on, tip in sortir), True)
    assemblage = _menu_de(arbre, bureau.joints[0].Name)
    actifs = [t for t, on, _tip in assemblage if on]
    problemes += ecarts("assemblage : actifs", actifs, ["Ouvrir", "Supprimer"])
    return problemes + ecarts(
        "assemblage : grisées expliquées", all(tip for _t, on, tip in assemblage if not on), True
    )


def _verifier_renommer(bureau: Bureau, dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    doc, actions, cle = bureau.doc, _actions(dock), bureau.shown("P").Name
    doc.UndoMode = 1
    doc.clearUndos()
    noms = [o.Name for o in doc.Objects]
    with _saisie("Dessus"):
        actions.run_action(Action.RENAME, [cle])
    _traiter()
    ligne = item_for(arbre, cle)
    problemes = [
        *ecarts("libellé de la brute", bureau.parts["P"].Label, "Dessus"),
        *ecarts("ligne rafraîchie", None if ligne is None else ligne.text(0), "Dessus"),
        *ecarts("une entrée d'annulation", len(doc.UndoNames), 1),
        *ecarts("aucun objet ajouté", [o.Name for o in doc.Objects], noms),
    ]
    _annuler(doc)
    problemes += ecarts("Ctrl+Z", bureau.parts["P"].Label, "Plateau")
    doc.clearUndos()
    with _saisie("   "):
        actions.run_action(Action.RENAME, [cle])
    with _saisie("Bu>reau"):
        actions.run_action(Action.RENAME, [bureau.furniture.Name])
    return [
        *problemes,
        *ecarts("nom vide : inchangé", bureau.parts["P"].Label, "Plateau"),
        *ecarts("nom inutilisable : inchangé", bureau.furniture.Label, "Bureau"),
        *ecarts("refus : aucune entrée", doc.UndoNames, []),
        *ecarts("refus expliqué", "inutilisable" in (boite_de_refus().text()), True),
    ]


def _verifier_ranger(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    doc = bureau.doc
    libre, etagere, armoire = _armoire(bureau)
    noms = [o.Name for o in doc.Objects]
    arbre.on_drop([libre.Name], armoire.Name)
    _traiter()
    problemes = [
        *ecarts("libre -> armoire", _ensemble_de(libre), armoire.Name),
        *ecarts("ligne sous l'armoire", _ligne_dans(arbre, libre.Name), armoire.Name),
        *ecarts("une entrée d'annulation", len(doc.UndoNames), 1),
        *ecarts("aucun objet ajouté", [o.Name for o in doc.Objects], noms),
    ]
    _annuler(doc)
    problemes += ecarts("Ctrl+Z : libre", _ensemble_de(libre), None)
    doc.clearUndos()
    arbre.on_drop([etagere.Name], bureau.furniture.Name)
    _traiter()
    problemes += ecarts("armoire -> bureau", _ensemble_de(etagere), bureau.furniture.Name)
    problemes += ecarts("changement : une entrée", len(doc.UndoNames), 1)
    _annuler(doc)
    problemes += ecarts("Ctrl+Z : étagère", _ensemble_de(etagere), armoire.Name)
    doc.clearUndos()
    arbre.on_drop([etagere.Name], None)
    _traiter()
    problemes += ecarts("sortie de l'armoire", _ensemble_de(etagere), None)
    problemes += ecarts("sortie : racine", _ligne_dans(arbre, etagere.Name), None)
    _annuler(doc)
    return problemes + ecarts("Ctrl+Z : sortie", _ensemble_de(etagere), armoire.Name)


def _verifier_refus(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    doc = bureau.doc
    _libre, _etagere, armoire = _armoire(bureau)
    joue, ensemble = bureau.shown("JG").Name, bureau.furniture.Name
    survol = arbre.judge([joue], armoire.Name)
    arbre.on_drop([joue], armoire.Name)
    _traiter()
    problemes = [
        *ecarts("survol : raison", "assemblée à" in survol, True),
        *ecarts("rien ne change", _ensemble_de(bureau.parts["JG"]), ensemble),
        *ecarts("aucune entrée", doc.UndoNames, []),
        *ecarts("refus affiché", "assemblée à" in boite_de_refus().text(), True),
    ]
    arbre.on_drop([ensemble], ensemble)
    _traiter()
    problemes += ecarts("cycle expliqué", "ne peut pas entrer" in boite_de_refus().text(), True)
    problemes += ecarts("cycle : aucune entrée", doc.UndoNames, [])
    problemes += ecarts("autre document", "ne se range pas" in arbre.judge(["Absent"], None), True)
    # déposer une pièce là où elle est déjà : refus expliqué (jamais une raison vide, qui voudrait
    # dire « permis »)
    return problemes + ecarts(
        "déjà en place : refus expliqué",
        arbre.judge([joue], ensemble),
        "« Joue gauche » est déjà dans « Bureau ».",
    )


def _verifier_sous_ensemble(
    bureau: Bureau, dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    doc, actions = bureau.doc, _actions(dock)
    _armoire(bureau)
    cles = [bureau.shown("P").Name, bureau.shown("V").Name]
    avant = [o.Name for o in doc.Objects if is_furniture(o)]
    actions.run_action(Action.CREATE, cles)
    _traiter()
    nouveau = [o for o in doc.Objects if is_furniture(o) and o.Name not in avant]
    if len(nouveau) != 1:
        return [f"un sous-ensemble attendu, {len(nouveau)} créé(s)"]
    problemes = [
        *ecarts("sous-ensemble dans le bureau", _ensemble_de(nouveau[0]), bureau.furniture.Name),
        *ecarts("pièce dans le sous-ensemble", _ensemble_de(bureau.parts["P"]), nouveau[0].Name),
        *ecarts("ligne sous le sous-ensemble", _ligne_dans(arbre, cles[0]), nouveau[0].Name),
        *ecarts("une entrée d'annulation", len(doc.UndoNames), 1),
        *ecarts("nouvel ensemble sélectionné", _noms_selectionnes(), [nouveau[0].Name]),
    ]
    _annuler(doc)
    return problemes + ecarts(
        "Ctrl+Z",
        [_ensemble_de(bureau.parts["P"]), len([o for o in doc.Objects if is_furniture(o)])],
        [bureau.furniture.Name, len(avant)],
    )


def _verifier_suppression(
    bureau: Bureau, dock: Any, _arbre: Any, _synchro: StructureSync
) -> list[str]:
    doc, actions = bureau.doc, _actions(dock)
    doc.UndoMode = 1
    doc.clearUndos()
    joue = bureau.shown("JG")
    noms = [joue.Name, bureau.parts["JG"].Name, bureau.joints[0].Name]
    with choix_de_suppression(False) as questions:
        actions.run_action(Action.DELETE, [joue.Name])
    problemes = [
        *ecarts("annulée : la fenêtre de l'arbre natif", len(questions), 1),
        *ecarts("annulée : objets", [doc.getObject(n) is not None for n in noms], [True] * 3),
        *ecarts("annulée : aucune entrée", doc.UndoNames, []),
    ]
    with choix_de_suppression(True):
        actions.run_action(Action.DELETE, [joue.Name])
    problemes += [
        *ecarts("supprimée : objets", [doc.getObject(n) is None for n in noms], [True] * 3),
        *ecarts("supprimée : une entrée", len(doc.UndoNames), 1),
    ]
    doc.undo()
    doc.recompute()
    return problemes + ecarts(
        "Ctrl+Z : tout revient", [doc.getObject(n) is not None for n in noms], [True] * 3
    )


def _verifier_ouvrir(bureau: Bureau, dock: Any, _arbre: Any, _synchro: StructureSync) -> list[str]:
    actions, cle = _actions(dock), bureau.shown("P").Name
    problemes = ecarts("ouvrir", actions.run_action(Action.OPEN, [cle]), True)
    _traiter()
    problemes += ecarts("panneau de tâche ouvert", bool(Gui.Control.activeDialog()), True)
    # panneau de tâche ouvert : ouvrir et supprimer sont grisés (règle des commandes de l'atelier)
    ferme = [actions.run_action(Action.OPEN, [cle]), actions.run_action(Action.DELETE, [cle])]
    return problemes + ecarts("pendant un panneau : grisés", ferme, [False, False])


def verifier_structure_menu() -> list[str]:
    return _avec_panneau(_verifier_menu)


def verifier_structure_renommer() -> list[str]:
    return _avec_panneau(_verifier_renommer)


def verifier_structure_ranger() -> list[str]:
    return _avec_panneau(_verifier_ranger)


def verifier_structure_refus() -> list[str]:
    return _avec_panneau(_verifier_refus)


def verifier_structure_sous_ensemble() -> list[str]:
    return _avec_panneau(_verifier_sous_ensemble)


def verifier_structure_suppression() -> list[str]:
    return _avec_panneau(_verifier_suppression)


def verifier_structure_ouvrir() -> list[str]:
    return _avec_panneau(_verifier_ouvrir)


VERIFICATIONS_STRUCTURE: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_selection,
    verifier_structure_rafraichissement,
    verifier_structure_double_clic,
    verifier_structure_detachement,
    verifier_structure_menu,
    verifier_structure_renommer,
    verifier_structure_ranger,
    verifier_structure_refus,
    verifier_structure_sous_ensemble,
    verifier_structure_suppression,
    verifier_structure_ouvrir,
)
