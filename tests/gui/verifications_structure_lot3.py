# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure », lot 3 (ADR 0046) : menu contextuel,
renommer, ranger, refuser un dépôt, sous-ensemble, supprimer, ouvrir.

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) ; chaque vérification
renvoie la liste de ses problèmes."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, cast

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.structure_decision import Decision, Move
from freecad.menuiserie.core.structure_menu import Action
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.gui.structure_actions import StructureActions, move_rows
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import (
    KEY_ROLE,
    item_for,
    selected_keys,
)
from tests.gui.verifications_assemblages import choix_de_suppression
from tests.gui.verifications_ensemble import boite_de_refus
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_structure import avec_panneau, noms_selectionnes, traiter
from tests.integration.bureau import Bureau

# --- Lot 3 : menu contextuel et glisser-déposer ---------------------------------------------

ENTREES_PIECE = [
    "Ouvrir",
    "Renommer…",
    "Ajouter à l'ensemble",
    "Sortir de l'ensemble",
    "Créer un sous-ensemble depuis la sélection",
    "Supprimer",
]


def actions_de(dock: Any) -> StructureActions:
    return cast(StructureActions, dock.findChild(StructureActions))


def menu_de(arbre: Any, cle: str) -> list[tuple[str, bool, str]]:
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
    traiter()
    return libre, etagere, armoire


def _ensemble_de(piece: Any) -> str | None:
    ensemble = furniture_of(piece)
    return None if ensemble is None else str(ensemble.Name)


def _etat(piece: Any) -> str:
    """État réel des propriétés de membre de ``piece`` (diagnostic d'une annulation)."""
    noms = [
        n for n in ("Furniture", "PositionMode", "FurnitureBindings") if n in piece.PropertiesList
    ]
    lien = getattr(piece, "Furniture", None) if "Furniture" in noms else None
    return f"{piece.Name} : propriétés {noms}, Furniture = {getattr(lien, 'Name', lien)!r}"


def _annuler(doc: Any, *pieces: Any) -> str:
    """Ctrl+Z puis recalcul, comme les vérifications de l'ensemble. Renvoie (et écrit dans la vue
    rapport) l'état réel des ``pieces`` après l'annulation, pour diagnostiquer un échec sans
    deviner : propriété présente ou non, valeur du lien."""
    doc.undo()
    doc.recompute()
    traiter()
    etat = " ; ".join(_etat(piece) for piece in pieces)
    App.Console.PrintMessage(f"Menuiserie : diagnostic Ctrl+Z, {etat}\n")
    return etat


def _ligne_dans(arbre: Any, cle: str) -> str | None:
    """Clé de la ligne parente de la ligne ``cle`` (``None`` : à la racine)."""
    ligne = item_for(arbre, cle)
    parent = None if ligne is None else ligne.parent()
    return None if parent is None else str(parent.data(0, KEY_ROLE))


def _verifier_menu(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    plateau = bureau.shown("P").Name
    entrees = menu_de(arbre, plateau)
    problemes = ecarts("entrées d'une pièce", [t for t, _on, _tip in entrees], ENTREES_PIECE)
    problemes += ecarts("pièce : tout est actif", [on for _t, on, _tip in entrees], [True] * 6)
    problemes += ecarts("ligne clic droit sélectionnée", selected_keys(arbre), [plateau])
    joue = menu_de(arbre, bureau.shown("JG").Name)
    sortir = [(on, tip) for t, on, tip in joue if t == "Sortir de l'ensemble"]
    problemes += ecarts("joue : sortir grisé", [on for on, _tip in sortir], [False])
    problemes += ecarts("joue : raison", all("assemblée à" in tip for _on, tip in sortir), True)
    assemblage = menu_de(arbre, bureau.joints[0].Name)
    actifs = [t for t, on, _tip in assemblage if on]
    problemes += ecarts("assemblage : actifs", actifs, ["Ouvrir", "Supprimer"])
    return problemes + ecarts(
        "assemblage : grisées expliquées", all(tip for _t, on, tip in assemblage if not on), True
    )


def _verifier_renommer(bureau: Bureau, dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    doc, actions, cle = bureau.doc, actions_de(dock), bureau.shown("P").Name
    doc.UndoMode = 1
    doc.clearUndos()
    noms = [o.Name for o in doc.Objects]
    with _saisie("Dessus"):
        actions.run_action(Action.RENAME, [cle])
    traiter()
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
    refus_inutilisable = boite_de_refus().text()  # avant le refus suivant, qui la remplace
    with _saisie("Pla\nteau"):
        actions.run_action(Action.RENAME, [cle])
    return [
        *problemes,
        *ecarts("caractère de contrôle : inchangé", bureau.parts["P"].Label, "Plateau"),
        *ecarts("refus en texte brut", boite_de_refus().textFormat(), QtCore.Qt.PlainText),
        *ecarts("nom vide : inchangé", bureau.parts["P"].Label, "Plateau"),
        *ecarts("nom inutilisable : inchangé", bureau.furniture.Label, "Bureau"),
        *ecarts("refus : aucune entrée", doc.UndoNames, []),
        *ecarts("refus expliqué", "inutilisable" in refus_inutilisable, True),
    ]


def _verifier_ranger(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    doc = bureau.doc
    libre, etagere, armoire = _armoire(bureau)
    noms = [o.Name for o in doc.Objects]
    arbre.on_drop([libre.Name], armoire.Name)
    traiter()
    problemes = [
        *ecarts("libre -> armoire", _ensemble_de(libre), armoire.Name),
        *ecarts("ligne sous l'armoire", _ligne_dans(arbre, libre.Name), armoire.Name),
        *ecarts("une entrée d'annulation", len(doc.UndoNames), 1),
        *ecarts("aucun objet ajouté", [o.Name for o in doc.Objects], noms),
    ]
    etat = _annuler(doc, libre)
    problemes += ecarts(f"Ctrl+Z : libre ({etat})", _ensemble_de(libre), None)
    doc.clearUndos()
    arbre.on_drop([etagere.Name], bureau.furniture.Name)
    traiter()
    problemes += ecarts("armoire -> bureau", _ensemble_de(etagere), bureau.furniture.Name)
    problemes += ecarts("changement : une entrée", len(doc.UndoNames), 1)
    etat = _annuler(doc, etagere)
    problemes += ecarts(f"Ctrl+Z : étagère ({etat})", _ensemble_de(etagere), armoire.Name)
    doc.clearUndos()
    arbre.on_drop([etagere.Name], None)
    traiter()
    problemes += ecarts("sortie de l'armoire", _ensemble_de(etagere), None)
    problemes += ecarts("sortie : racine", _ligne_dans(arbre, etagere.Name), None)
    etat = _annuler(doc, etagere)
    return problemes + ecarts(f"Ctrl+Z : sortie ({etat})", _ensemble_de(etagere), armoire.Name)


def _verifier_refus(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    doc = bureau.doc
    _libre, _etagere, armoire = _armoire(bureau)
    joue, ensemble = bureau.shown("JG").Name, bureau.furniture.Name
    survol = arbre.judge([joue], armoire.Name)
    arbre.on_drop([joue], armoire.Name)
    traiter()
    problemes = [
        *ecarts("survol : raison", "assemblée à" in survol, True),
        *ecarts("rien ne change", _ensemble_de(bureau.parts["JG"]), ensemble),
        *ecarts("aucune entrée", doc.UndoNames, []),
        *ecarts("refus affiché", "assemblée à" in boite_de_refus().text(), True),
    ]
    arbre.on_drop([ensemble], ensemble)
    traiter()
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
    doc, actions = bureau.doc, actions_de(dock)
    _armoire(bureau)
    cles = [bureau.shown("P").Name]  # le voile est assemblé aux joues : il resterait seul (refus)
    avant = [o.Name for o in doc.Objects if is_furniture(o)]
    actions.run_action(Action.CREATE, cles)
    traiter()
    nouveau = [o for o in doc.Objects if is_furniture(o) and o.Name not in avant]
    if len(nouveau) != 1:
        return [f"un sous-ensemble attendu, {len(nouveau)} créé(s)"]
    problemes = [
        *ecarts("sous-ensemble dans le bureau", _ensemble_de(nouveau[0]), bureau.furniture.Name),
        *ecarts("pièce dans le sous-ensemble", _ensemble_de(bureau.parts["P"]), nouveau[0].Name),
        *ecarts("ligne sous le sous-ensemble", _ligne_dans(arbre, cles[0]), nouveau[0].Name),
        *ecarts("une entrée d'annulation", len(doc.UndoNames), 1),
        *ecarts("nouvel ensemble sélectionné", noms_selectionnes(), [nouveau[0].Name]),
    ]
    etat = _annuler(doc, bureau.parts["P"])
    restants = len([o for o in doc.Objects if is_furniture(o)])
    return problemes + ecarts(
        f"Ctrl+Z ({etat})",
        [_ensemble_de(bureau.parts["P"]), restants],
        [bureau.furniture.Name, len(avant)],
    )


def _verifier_suppression(
    bureau: Bureau, dock: Any, _arbre: Any, _synchro: StructureSync
) -> list[str]:
    doc, actions = bureau.doc, actions_de(dock)
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
    actions, cle = actions_de(dock), bureau.shown("P").Name
    problemes = ecarts("ouvrir", actions.run_action(Action.OPEN, [cle]), True)
    traiter()
    problemes += ecarts("panneau de tâche ouvert", bool(Gui.Control.activeDialog()), True)
    # panneau de tâche ouvert : ouvrir et supprimer sont grisés (règle des commandes de l'atelier)
    ferme = [actions.run_action(Action.OPEN, [cle]), actions.run_action(Action.DELETE, [cle])]
    return problemes + ecarts("pendant un panneau : grisés", ferme, [False, False])


def _verifier_accueil_supprime(
    bureau: Bureau, _dock: Any, _arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Ensemble d'accueil supprimé entre la décision et l'écriture : rien ne bouge, la pièce n'est
    jamais « sortie » à la place."""
    libre, _etagere, armoire = _armoire(bureau)
    decision = Decision(True, keys=(libre.Name,), moves=(Move(armoire.Name, (libre.Name,)),))
    bureau.doc.removeObject(armoire.Name)
    avant = _ensemble_de(libre)
    return [
        *ecarts("accueil supprimé : rien n'est rangé", move_rows(bureau.doc, decision), None),
        *ecarts("accueil supprimé : pièce en place", _ensemble_de(libre), avant),
        *ecarts("accueil supprimé : aucune entrée d'annulation", bureau.doc.UndoNames, []),
    ]


def verifier_structure_accueil_supprime() -> list[str]:
    return avec_panneau(_verifier_accueil_supprime)


def verifier_structure_menu() -> list[str]:
    return avec_panneau(_verifier_menu)


def verifier_structure_renommer() -> list[str]:
    return avec_panneau(_verifier_renommer)


def verifier_structure_ranger() -> list[str]:
    return avec_panneau(_verifier_ranger)


def verifier_structure_refus() -> list[str]:
    return avec_panneau(_verifier_refus)


def verifier_structure_sous_ensemble() -> list[str]:
    return avec_panneau(_verifier_sous_ensemble)


def verifier_structure_suppression() -> list[str]:
    return avec_panneau(_verifier_suppression)


def verifier_structure_ouvrir() -> list[str]:
    return avec_panneau(_verifier_ouvrir)


VERIFICATIONS_STRUCTURE_LOT3: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_accueil_supprime,
    verifier_structure_menu,
    verifier_structure_renommer,
    verifier_structure_ranger,
    verifier_structure_refus,
    verifier_structure_sous_ensemble,
    verifier_structure_suppression,
    verifier_structure_ouvrir,
)
