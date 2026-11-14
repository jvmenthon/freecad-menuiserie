# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la « Finition des chants » (issue #5, critères C1 à C6).

Commande dans la barre d'outils et le menu, panneau (famille, cotes, cartes des pièces avec le
dessin cliquable de leurs arêtes, raccourcis) avec
aperçu en direct, « OK » = une entrée d'annulation, « Annuler » ne laisse rien, cote refusée
affichée sans rien changer, modification et suppression d'un profil au double-clic. Module
importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui

from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    choisir,
    ecarts,
    emplacements,
    formulaire_nomme,
    saisir,
    valider,
)
from tests.gui.verifications_panneau_assemblage import widget

COMMANDE = "Menuiserie_EdgeFinish"
FORM = "EdgeFinishTaskPanel"
VOLUME = 800.0 * 200.0 * 22.0


def formulaire() -> Any:
    """Formulaire du panneau ouvert (``None`` s'il n'y en a pas)."""
    return formulaire_nomme(FORM)


def carte(form: Any, blank: Any) -> Any:
    """Carte de la pièce ``blank`` dans le panneau ``form``."""
    return widget(form, f"piece_{blank.Name}")


def form_codes(form: Any, blank: Any) -> list[str]:
    """Arêtes choisies de la pièce ``blank`` dans le panneau ``form``."""
    codes: list[str] = carte(form, blank).codes()
    return codes


def cocher(form: Any, blank: Any, code: str, on: bool = True) -> None:
    """Clic sur l'arête ``code`` du dessin de la carte de ``blank`` si son état n'est pas
    ``on``."""
    from freecad.menuiserie.core.edges import Hit

    if (code in form_codes(form, blank)) != on:
        widget(carte(form, blank), "diagram").click(Hit("edge", code))


def piece(doc: Any) -> Any:
    from freecad.menuiserie import api

    blank = api.make_wood_part(800.0, 200.0, 22.0, "chene", doc=doc)
    doc.recompute()
    return blank


def lancer(blank: Any) -> Any:
    """Sélectionne ``blank``, lance la commande et renvoie le formulaire du panneau."""
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(blank)
    Gui.Command.get(COMMANDE).run()
    return formulaire()


def usinee(blank: Any) -> Any:
    from freecad.menuiserie import api

    return api.machined_part_of(blank)


def verifier_commande() -> list[str]:
    """C1 : libellé, infobulle, icône, emplacements ; active même sans sélection."""
    from freecad.menuiserie import icon_path

    commande = Gui.Command.get(COMMANDE)
    if commande is None:
        return [f"commande {COMMANDE} absente"]
    infos = commande.getInfo()
    problemes = [
        *ecarts("libellé", infos["menuText"], "Finition des chants"),
        *ecarts("infobulle renseignée", bool(infos["toolTip"].strip()), True),
        *ecarts("icône", infos["pixmap"], icon_path("Menuiserie_FinitionChants.svg")),
        *ecarts(
            "emplacements",
            sorted(emplacements(COMMANDE)),
            [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie : Pièces")],
        ),
    ]

    def actif(doc: Any) -> list[str]:
        Gui.Selection.clearSelection()
        sans = commande.isActive()
        blank = piece(doc)
        Gui.Selection.addSelection(blank)
        return [
            *ecarts("active sans sélection", sans, True),
            *ecarts("active avec une pièce", commande.isActive(), True),
        ]

    return problemes + avec_document("VerifChantsCommande", actif)


def _creer(doc: Any) -> list[str]:
    blank = piece(doc)
    form = lancer(blank)
    if form is None:
        return ["panneau de finition non ouvert"]
    problemes = [
        *ecarts("titre", form.windowTitle(), "Finition des chants"),
        *ecarts("aucun profil sans arête", usinee(blank), None),
        *ecarts("erreur masquée", widget(form, "errorLabel").isHidden(), True),
    ]
    problemes += [
        *ecarts("profil par défaut", widget(form, "family").currentData(), "Round"),
        *ecarts("cote par défaut", widget(form, "size_a").property("rawValue"), 1.0),
        *ecarts("cote B masquée", widget(form, "size_b").isHidden(), True),
    ]
    choisir(widget(form, "family"), "Chamfer")
    saisir(widget(form, "size_a"), 5.0)
    cocher(form, blank, "Z+Y-")
    machined = usinee(blank)
    problemes += ecarts(
        "aperçu", round(machined.Shape.Volume) if machined else None, round(VOLUME - 12.5 * 800.0)
    )
    choisir(widget(form, "family"), "Beak")
    problemes += ecarts("cote B demandée", widget(form, "size_b").isHidden(), False)
    choisir(widget(form, "family"), "Chamfer")
    cocher(form, blank, "Z+X-")
    cocher(form, blank, "Z+X-", on=False)
    problemes += ecarts("second clic sur l'arête", "Z+X-" in form_codes(form, blank), False)
    widget(form, "shortcut_all").click()
    problemes += ecarts("raccourci « toutes »", len(form_codes(form, blank)), 12)
    widget(form, "shortcut_none").click()
    problemes += ecarts("aucune arête : pas de pièce usinée", usinee(blank), None)
    cocher(form, blank, "Z+Y-")
    valider()
    machined = usinee(blank)
    return [
        *problemes,
        *ecarts("panneau fermé", formulaire() is None, True),
        *ecarts("entrée d'annulation", doc.UndoNames, ["Finition des chants"]),
        *ecarts("profil", [p.Edges for p in machined.Finishes], [["Z+Y-"]]),
        *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
    ]


def verifier_creation() -> list[str]:
    """C2, C4 : saisies visibles aussitôt, raccourcis, « OK » = une entrée d'annulation."""
    return avec_document("VerifChantsCreation", _creer)


def _annuler(doc: Any) -> list[str]:
    blank = piece(doc)
    form = lancer(blank)
    if form is None:
        return ["panneau de finition non ouvert"]
    cocher(form, blank, "Z+Y-")  # profil par défaut : arête cassée (quart de rond 1 mm)
    machined = usinee(blank)
    problemes = ecarts(
        "arête cassée",
        [(p.Family, p.SizeA.Value) for p in machined.Finishes] if machined else None,
        [("Round", 1.0)],
    )
    annuler()
    return [
        *problemes,
        *ecarts("pièce usinée retirée", usinee(blank), None),
        *ecarts("aucune entrée", doc.UndoNames, []),
        *ecarts("panneau fermé", formulaire() is None, True),
    ]


def verifier_annulation() -> list[str]:
    """C4 : « Annuler » remet l'état d'avant, arête cassée 1 mm comprise."""
    return avec_document("VerifChantsAnnule", _annuler)


def _refus(doc: Any) -> list[str]:
    blank = piece(doc)
    form = lancer(blank)
    if form is None:
        return ["panneau de finition non ouvert"]
    choisir(widget(form, "family"), "Chamfer")
    cocher(form, blank, "Z+Y-")
    saisir(widget(form, "size_a"), 30.0)
    erreur = widget(form, "errorLabel")
    problemes = [
        *ecarts("refus affiché", erreur.isHidden(), False),
        *ecarts("arête citée", "dessus-avant" in erreur.text(), True),
    ]
    valider()  # sans effet : le panneau reste ouvert
    problemes += ecarts("panneau resté ouvert", formulaire() is not None, True)
    saisir(widget(form, "size_a"), 4.0)
    problemes += ecarts("refus effacé", erreur.isHidden(), True)
    annuler()
    return problemes


def verifier_cote_refusee() -> list[str]:
    """A5 dans le panneau : cote trop grande affichée, « OK » sans effet, refus effacé."""
    return avec_document("VerifChantsRefus", _refus)


def face_du_dessus(blank: Any) -> str:
    """Nom du sous-élément « FaceN » de la face du dessus de ``blank``."""
    index = next(
        i + 1
        for i, face in enumerate(blank.Shape.Faces)
        if face.normalAt(0, 0).z > 0.99 and face.CenterOfMass.z > 1
    )
    return f"Face{index}"


def _preselection(doc: Any) -> list[str]:
    blank = piece(doc)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(blank, face_du_dessus(blank))
    Gui.Command.get(COMMANDE).run()
    form = formulaire()
    if form is None:
        return ["panneau de finition non ouvert"]
    from freecad.menuiserie.core.edges import Hit

    dessus = sorted(["Z+Y-", "Z+Y+", "Z+X-", "Z+X+"])
    problemes = [
        *ecarts("arêtes du dessus choisies", sorted(form_codes(form, blank)), dessus),
        *ecarts("nom de la pièce", widget(carte(form, blank), "name").text(), blank.Label),
        *ecarts("aperçu des 4 arêtes", usinee(blank) is not None, True),
    ]
    dessin = widget(carte(form, blank), "diagram")
    cocher(form, blank, "Z+Y+", on=False)  # arête arrière du dessus
    problemes += ecarts(
        "arête retirée", sorted(form_codes(form, blank)), sorted(set(dessus) - {"Z+Y+"})
    )
    dessin.click(Hit("face", "Z+"))  # une arête manque : les quatre sont choisies
    problemes += ecarts("clic dans la face", sorted(form_codes(form, blank)), dessus)
    dessin.click(Hit("face", "Z+"))  # toutes choisies : les quatre sont retirées
    problemes += ecarts("second clic dans la face", form_codes(form, blank), [])
    annuler()
    return problemes


def verifier_preselection() -> list[str]:
    """Une face sélectionnée avant la commande : ses 4 arêtes cochées, sélecteur visuel."""
    return avec_document("VerifChantsPresel", _preselection)


def _sans_selection(doc: Any) -> list[str]:
    from PySide import QtGui

    blank = piece(doc)
    Gui.Selection.clearSelection()
    Gui.Command.get(COMMANDE).run()
    form = formulaire()
    if form is None:
        return ["panneau de finition non ouvert sans sélection"]
    problemes = [*ecarts("consigne affichée", widget(form, "hint").isHidden(), False)]
    Gui.Selection.addSelection(blank, face_du_dessus(blank))
    QtGui.QApplication.processEvents()  # l'observateur transmet hors du rappel
    problemes += [
        *ecarts("consigne masquée", widget(form, "hint").isHidden(), True),
        *ecarts("arêtes du dessus choisies", len(form_codes(form, blank)), 4),
    ]
    annuler()
    return problemes


def verifier_sans_selection() -> list[str]:
    """Commande sans sélection : on désigne la pièce et la face dans la vue 3D."""
    return avec_document("VerifChantsSansSelection", _sans_selection)


def _dans_un_ensemble(doc: Any) -> list[str]:
    from freecad.menuiserie.gui.pick_edge import pick_at

    blank = piece(doc)
    ensemble = doc.addObject("App::Part", "Ensemble")
    ensemble.addObject(blank)
    doc.recompute()
    face = face_du_dessus(blank)
    pick = pick_at(doc, ensemble.Name, f"{blank.Name}.{face}")
    direct = pick_at(doc, blank.Name, face)
    return [
        *ecarts("pièce trouvée dans l'ensemble", pick is not None and pick.part == blank, True),
        *ecarts(
            "4 arêtes",
            sorted(pick.codes) if pick else None,
            sorted(["Z+Y-", "Z+Y+", "Z+X-", "Z+X+"]),
        ),
        *ecarts(
            "sans ensemble",
            sorted(direct.codes) if direct else None,
            sorted(["Z+Y-", "Z+Y+", "Z+X-", "Z+X+"]),
        ),
        *ecarts("chemin inconnu", pick_at(doc, ensemble.Name, f"Inconnu.{face}"), None),
    ]


def verifier_selection_dans_un_ensemble() -> list[str]:
    """Un clic sur une face d'une pièce rangée dans un ensemble désigne la pièce et ses arêtes."""
    return avec_document("VerifChantsEnsemble", _dans_un_ensemble)


def _modifier_et_supprimer(doc: Any) -> list[str]:
    from PySide import QtGui

    from freecad.menuiserie import api

    blank = piece(doc)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    doc.recompute()
    vobj = profile.ViewObject
    ouvert = vobj.Proxy.doubleClicked(vobj)
    form = formulaire()
    if not ouvert or form is None:
        return ["double-clic sur le profil : panneau non ouvert"]
    croix = [
        w
        for w in carte(form, blank).findChildren(QtGui.QWidget)
        if w.objectName() == "remove_piece"
    ]
    problemes = [
        *ecarts("arête reprise", form_codes(form, blank), ["Z+Y-"]),
        *ecarts("cote reprise", widget(form, "size_a").property("rawValue"), 5.0),
        *ecarts("pièce du profil sans croix", croix, []),
    ]
    cocher(form, blank, "Z-Y-")
    valider()
    problemes += ecarts("arêtes modifiées", profile.Edges, ["Z+Y-", "Z-Y-"])
    ouvert = vobj.Proxy.doubleClicked(vobj)
    form = formulaire()
    if not ouvert or form is None:
        return [*problemes, "second double-clic : panneau non ouvert"]
    widget(form, "delete_profile").click()
    return [
        *problemes,
        *ecarts("panneau fermé", formulaire() is None, True),
        *ecarts("pièce usinée retirée", api.machined_part_of(blank), None),
    ]


def verifier_modification_et_suppression() -> list[str]:
    """C5 : double-clic sur un profil, modification, suppression."""
    return avec_document("VerifChantsModifier", _modifier_et_supprimer)


def _conflit(doc: Any) -> list[str]:
    from freecad.menuiserie import api

    blank = piece(doc)
    first, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    doc.recompute()
    form = lancer(blank)
    if form is None:
        return ["panneau de finition non ouvert"]
    cocher(form, blank, "Z+Y-")  # déjà profilée par un autre profil
    cocher(form, blank, "Z-Y-")
    problemes = ecarts("aperçu : premier profil intact", first.Edges, ["Z+Y-"])
    cocher(form, blank, "Z+Y-", on=False)
    valider()
    return [
        *problemes,
        *ecarts("premier profil intact après OK", first.Edges, ["Z+Y-"]),
        *ecarts(
            "profils",
            sorted(tuple(p.Edges) for p in api.edge_profiles_of(blank)),
            [("Z+Y-",), ("Z-Y-",)],
        ),
    ]


def verifier_arete_deja_profilee() -> list[str]:
    """Une arête cochée puis décochée n'enlève rien à l'autre profil (revue M1)."""
    return avec_document("VerifChantsConflit", _conflit)


VERIFICATIONS_CHANTS: tuple[Callable[[], list[str]], ...] = (
    verifier_commande,
    verifier_creation,
    verifier_annulation,
    verifier_cote_refusee,
    verifier_modification_et_suppression,
    verifier_arete_deja_profilee,
    verifier_preselection,
    verifier_sans_selection,
    verifier_selection_dans_un_ensemble,
)
