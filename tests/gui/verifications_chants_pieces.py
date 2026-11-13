# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la « Finition des chants » sur plusieurs pièces (issue #5).

Une carte par pièce (nom, couleur), une pièce cliquée pendant la tâche s'ajoute, chaque pièce
reçoit son profil en une seule entrée d'annulation, la croix d'une carte retire son profil,
bascule patron déplié / boîte en perspective mémorisée, mise en valeur dans la vue 3D posée
pendant la tâche et retirée après. Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.verifications_chants import (
    COMMANDE,
    carte,
    cocher,
    face_du_dessus,
    form_codes,
    formulaire,
    usinee,
)
from tests.gui.verifications_panneau import annuler, avec_document, ecarts, valider
from tests.gui.verifications_panneau_assemblage import widget

DESSUS = sorted(["Z+Y-", "Z+Y+", "Z+X-", "Z+X+"])


def _deux_pieces(doc: Any) -> tuple[Any, Any]:
    from freecad.menuiserie import api

    first = api.make_wood_part(800.0, 200.0, 22.0, "chene", doc=doc)
    second = api.make_wood_part(600.0, 300.0, 19.0, "chene", doc=doc)
    second.Placement.Base = App.Vector(0.0, 500.0, 0.0)
    doc.recompute()
    return first, second


def _ouvrir(*selection: tuple[Any, str]) -> Any:
    Gui.Selection.clearSelection()
    for obj, sub in selection:
        if sub:
            Gui.Selection.addSelection(obj, sub)
        else:
            Gui.Selection.addSelection(obj)
    Gui.Command.get(COMMANDE).run()
    return formulaire()


def _plusieurs(doc: Any) -> list[str]:
    from PySide import QtGui

    from freecad.menuiserie import api

    first, second = _deux_pieces(doc)
    form = _ouvrir((first, face_du_dessus(first)))
    if form is None:
        return ["panneau de finition non ouvert"]
    problemes = ecarts("une carte", widget(form, f"piece_{first.Name}") is not None, True)
    Gui.Selection.addSelection(second, face_du_dessus(second))  # clic pendant la tâche
    QtGui.QApplication.processEvents()
    try:
        ajoutee = carte(form, second)
    except LookupError:
        return [*problemes, "pièce cliquée pendant la tâche non ajoutée"]
    problemes += [
        *ecarts("arêtes de la seconde pièce", sorted(form_codes(form, second)), DESSUS),
        *ecarts("couleurs distinctes", carte(form, first).color != ajoutee.color, True),
        *ecarts(
            "aperçu des deux pièces",
            (usinee(first) is None, usinee(second) is None),
            (False, False),
        ),
    ]
    cocher(form, second, "Z+Y+", on=False)
    valider()
    return [
        *problemes,
        *ecarts("une entrée d'annulation", doc.UndoNames, ["Finition des chants"]),
        *ecarts("profil de la première", [p.Edges for p in api.edge_profiles_of(first)], [DESSUS]),
        *ecarts(
            "profil de la seconde",
            [sorted(p.Edges) for p in api.edge_profiles_of(second)],
            [sorted(set(DESSUS) - {"Z+Y+"})],
        ),
    ]


def verifier_plusieurs_pieces() -> list[str]:
    """Deux pièces, l'une sélectionnée, l'autre cliquée pendant la tâche : deux profils."""
    return avec_document("VerifChantsPieces", _plusieurs)


def _retirer(doc: Any) -> list[str]:
    from freecad.menuiserie import api

    first, second = _deux_pieces(doc)
    form = _ouvrir((first, face_du_dessus(first)), (second, face_du_dessus(second)))
    if form is None:
        return ["panneau de finition non ouvert"]
    problemes = ecarts("deux pièces usinées", usinee(second) is not None, True)
    widget(carte(form, second), "remove_piece").click()
    problemes += [
        *ecarts("profil de la pièce retirée", usinee(second), None),
        *ecarts("titre de la liste", widget(form, "piece_list").title(), "Pièces concernées (1)"),
    ]
    valider()
    return [
        *problemes,
        *ecarts("profil gardé", len(api.edge_profiles_of(first)), 1),
        *ecarts("rien sur la pièce retirée", api.edge_profiles_of(second), []),
    ]


def verifier_retirer_une_piece() -> list[str]:
    """La croix d'une carte retire la pièce et son profil de l'aperçu."""
    return avec_document("VerifChantsRetirer", _retirer)


def _bascule(doc: Any) -> list[str]:
    from freecad.menuiserie.features.library import PARAM_PATH
    from freecad.menuiserie.gui.task_panels.edge_targets import VIEW_KEY

    params = App.ParamGet(PARAM_PATH)
    avant = params.GetString(VIEW_KEY, "")
    first, second = _deux_pieces(doc)
    form = _ouvrir((first, ""), (second, ""))
    if form is None:
        return ["panneau de finition non ouvert"]
    try:
        widget(form, "view_box").click()
        dessins = [widget(carte(form, part), "diagram").view for part in (first, second)]
        problemes = [
            *ecarts("boîte en perspective", dessins, ["box", "box"]),
            *ecarts("choix mémorisé", params.GetString(VIEW_KEY, ""), "box"),
        ]
        widget(form, "view_net").click()
        problemes += ecarts("patron déplié", widget(carte(form, first), "diagram").view, "net")
        annuler()
        return problemes
    finally:
        if avant:
            params.SetString(VIEW_KEY, avant)
        else:
            params.RemString(VIEW_KEY)


def verifier_bascule_du_dessin() -> list[str]:
    """Bascule patron déplié / boîte en perspective pour toutes les cartes, mémorisée."""
    return avec_document("VerifChantsDessin", _bascule)


def _mise_en_valeur_posee(doc: Any) -> bool:
    from pivy import coin

    from freecad.menuiserie.gui.edge_highlight import NODE_NAME

    view = Gui.getDocument(doc.Name).ActiveView
    search = coin.SoSearchAction()
    search.setName(NODE_NAME)
    search.apply(view.getSceneGraph())
    return search.getPath() is not None


def _mise_en_valeur(doc: Any) -> list[str]:
    first, _second = _deux_pieces(doc)
    couleurs = (tuple(first.ViewObject.ShapeColor), first.ViewObject.Transparency)
    form = _ouvrir((first, face_du_dessus(first)))
    if form is None:
        return ["panneau de finition non ouvert"]
    problemes = ecarts("mise en valeur posée", _mise_en_valeur_posee(doc), True)
    annuler()
    return [
        *problemes,
        *ecarts("mise en valeur retirée", _mise_en_valeur_posee(doc), False),
        *ecarts(
            "couleurs de la pièce intactes",
            (tuple(first.ViewObject.ShapeColor), first.ViewObject.Transparency),
            couleurs,
        ),
        *ecarts("aucune entrée", doc.UndoNames, []),
    ]


def verifier_mise_en_valeur_3d() -> list[str]:
    """Arêtes choisies mises en valeur dans la vue 3D pendant la tâche, rien après."""
    return avec_document("VerifChantsValeur", _mise_en_valeur)


def _couleurs_apres_retrait(doc: Any) -> list[str]:
    """Une pièce ajoutée après le retrait d'une carte ne reprend pas la couleur d'une carte
    restante (deux pièces de même couleur se confondent dans le dessin et la vue 3D)."""
    from freecad.menuiserie import api

    first, second = _deux_pieces(doc)
    third = api.make_wood_part(400.0, 100.0, 18.0, "chene", doc=doc)
    fourth = api.make_wood_part(300.0, 100.0, 18.0, "chene", doc=doc)
    third.Placement.Base = App.Vector(0.0, 1000.0, 0.0)
    fourth.Placement.Base = App.Vector(0.0, 1300.0, 0.0)
    doc.recompute()
    form = _ouvrir(
        (first, face_du_dessus(first)),
        (second, face_du_dessus(second)),
        (third, face_du_dessus(third)),
    )
    if form is None:
        return ["panneau de finition non ouvert"]
    widget(carte(form, first), "remove_piece").click()
    Gui.Selection.addSelection(fourth, face_du_dessus(fourth))
    from PySide import QtGui

    QtGui.QApplication.processEvents()
    couleurs = [carte(form, piece).color for piece in (second, third, fourth)]
    problemes = ecarts("couleurs distinctes après retrait", len(set(couleurs)), 3)
    annuler()
    return problemes


def verifier_couleurs_apres_retrait() -> list[str]:
    """Les couleurs des cartes restent distinctes après retrait puis ajout d'une pièce."""
    return avec_document("VerifChantsCouleurs", _couleurs_apres_retrait)


def _piece_refusee(doc: Any) -> list[str]:
    from PySide import QtGui

    from freecad.menuiserie import api

    first, _second = _deux_pieces(doc)
    cylindre = doc.addObject("Part::Cylinder", "Cylindre")
    doc.recompute()
    forme = api.make_shaped_part(cylindre)
    doc.recompute()
    form = _ouvrir((first, face_du_dessus(first)))
    if form is None:
        return ["panneau de finition non ouvert"]
    Gui.Selection.addSelection(forme)
    QtGui.QApplication.processEvents()
    erreur = widget(form, "errorLabel")
    problemes = [
        *ecarts("refus affiché", "simple boîte" in erreur.text(), True),
        *ecarts("pas de carte pour la pièce refusée", _a_une_carte(form, forme), False),
    ]
    annuler()
    return problemes


def _a_une_carte(form: Any, part: Any) -> bool:
    try:
        carte(form, part)
    except LookupError:
        return False
    return True


def verifier_piece_refusee_pendant_la_tache() -> list[str]:
    """Une pièce qui n'est pas une boîte, cliquée pendant la tâche : refus affiché, pas de carte."""
    return avec_document("VerifChantsRefusee", _piece_refusee)


def _piece_supprimee(doc: Any) -> list[str]:
    first, second = _deux_pieces(doc)
    form = _ouvrir((first, face_du_dessus(first)), (second, ""))  # seconde sans arête
    if form is None:
        return ["panneau de finition non ouvert"]
    nom = second.Name
    doc.removeObject(nom)
    cocher(form, first, "Z-Y-")  # saisie suivante : la carte de la pièce supprimée disparaît
    problemes = [
        *ecarts("carte retirée", _a_une_carte_nommee(form, nom), False),
        *ecarts("panneau ouvert", formulaire() is not None, True),
    ]
    valider()
    return [*problemes, *ecarts("panneau fermé", formulaire() is None, True)]


def _a_une_carte_nommee(form: Any, nom: str) -> bool:
    try:
        widget(form, f"piece_{nom}")
    except LookupError:
        return False
    return True


def verifier_piece_supprimee_pendant_la_tache() -> list[str]:
    """Une pièce de la liste supprimée pendant la tâche : sa carte part, le panneau continue."""
    return avec_document("VerifChantsSupprimee", _piece_supprimee)


def _remplacer_plusieurs(doc: Any) -> list[str]:
    from freecad.menuiserie import api
    from freecad.menuiserie.gui.task_panels.edge_finish import EdgeFinishTaskPanel

    first, second = _deux_pieces(doc)
    for part in (first, second):
        api.add_edge_profile(part, ["Z+Y-"], "Chamfer", 3.0)
    doc.recompute()
    form = _ouvrir((first, ""), (second, ""))
    if form is None:
        return ["panneau de finition non ouvert"]
    for part in (first, second):
        cocher(form, part, "Z+Y-")
        cocher(form, part, "Z-Y-")
    confirmer = EdgeFinishTaskPanel._confirmed
    EdgeFinishTaskPanel._confirmed = lambda _self, _conflicts: True  # type: ignore[method-assign,assignment]
    try:
        valider()
    finally:
        EdgeFinishTaskPanel._confirmed = confirmer  # type: ignore[method-assign]
    return [
        *ecarts("panneau fermé", formulaire() is None, True),
        *(
            probleme
            for part in (first, second)
            for probleme in ecarts(
                f"profils de {part.Label}",
                sorted((p.Family, tuple(p.Edges)) for p in api.edge_profiles_of(part)),
                [("Round", ("Z+Y-", "Z-Y-"))],
            )
        ),
    ]


def verifier_remplacement_sur_plusieurs_pieces() -> list[str]:
    """Arêtes déjà profilées sur deux pièces, remplacement confirmé : un profil par pièce."""
    return avec_document("VerifChantsRemplacer", _remplacer_plusieurs)


def _modifier_et_ajouter(doc: Any) -> list[str]:
    from PySide import QtGui

    from freecad.menuiserie import api

    first, second = _deux_pieces(doc)
    profile, _ = api.add_edge_profile(first, ["Z+Y-"], "Chamfer", 3.0)
    doc.recompute()
    vobj = profile.ViewObject
    if not vobj.Proxy.doubleClicked(vobj) or formulaire() is None:
        return ["double-clic sur le profil : panneau non ouvert"]
    form = formulaire()
    Gui.Selection.addSelection(second, face_du_dessus(second))
    QtGui.QApplication.processEvents()
    problemes = ecarts("seconde pièce ajoutée", _a_une_carte(form, second), True)
    valider()
    return [
        *problemes,
        *ecarts("profil modifié intact", list(profile.Edges), ["Z+Y-"]),
        *ecarts(
            "profil de la seconde",
            [(p.Family, sorted(p.Edges)) for p in api.edge_profiles_of(second)],
            [("Chamfer", DESSUS)],
        ),
    ]


def verifier_modification_avec_une_autre_piece() -> list[str]:
    """Double-clic sur un profil puis clic sur une autre pièce : elle reçoit les mêmes réglages."""
    return avec_document("VerifChantsModifAjout", _modifier_et_ajouter)


VERIFICATIONS_CHANTS_PIECES: tuple[Callable[[], list[str]], ...] = (
    verifier_plusieurs_pieces,
    verifier_retirer_une_piece,
    verifier_bascule_du_dessin,
    verifier_mise_en_valeur_3d,
    verifier_couleurs_apres_retrait,
    verifier_piece_refusee_pendant_la_tache,
    verifier_piece_supprimee_pendant_la_tache,
    verifier_remplacement_sur_plusieurs_pieces,
    verifier_modification_avec_une_autre_piece,
)
