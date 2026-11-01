# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la « Finition des chants » (issue #5, critères C1 à C6).

Commande dans la barre d'outils et le menu, panneau (famille, cotes, arêtes, raccourcis) avec
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
    """C1 : libellé, infobulle, icône, emplacements ; active seulement avec une pièce choisie."""
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
            [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")],
        ),
    ]

    def actif(doc: Any) -> list[str]:
        Gui.Selection.clearSelection()
        sans = commande.isActive()
        blank = piece(doc)
        Gui.Selection.addSelection(blank)
        return [
            *ecarts("inactive sans sélection", sans, False),
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
    choisir(widget(form, "family"), "Chamfer")
    saisir(widget(form, "size_a"), 5.0)
    saisir(widget(form, "size_b"), 4.0)
    widget(form, "Z+Y-").setChecked(True)
    machined = usinee(blank)
    problemes += ecarts(
        "aperçu", round(machined.Shape.Volume) if machined else None, round(VOLUME - 10.0 * 800.0)
    )
    widget(form, "shortcut_Z+").click()
    coches = [code for code in ("Z+Y-", "Z+Y+", "Z+X-", "Z+X+") if widget(form, code).isChecked()]
    problemes += ecarts("raccourci du dessus", len(coches), 4)
    widget(form, "shortcut_none").click()
    problemes += ecarts("aucune arête cochée", usinee(blank) is None or bool(usinee(blank)), True)
    widget(form, "Z+Y-").setChecked(True)
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
    widget(form, "broken_edge").click()
    widget(form, "Z+Y-").setChecked(True)
    problemes = ecarts("aperçu", usinee(blank) is not None, True)
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
    widget(form, "Z+Y-").setChecked(True)
    saisir(widget(form, "size_a"), 5.0)
    saisir(widget(form, "size_b"), 30.0)
    erreur = widget(form, "errorLabel")
    problemes = [
        *ecarts("refus affiché", erreur.isHidden(), False),
        *ecarts("arête citée", "dessus-avant" in erreur.text(), True),
    ]
    valider()  # sans effet : le panneau reste ouvert
    problemes += ecarts("panneau resté ouvert", formulaire() is not None, True)
    saisir(widget(form, "size_b"), 4.0)
    problemes += ecarts("refus effacé", erreur.isHidden(), True)
    annuler()
    return problemes


def verifier_cote_refusee() -> list[str]:
    """A5 dans le panneau : cote trop grande affichée, « OK » sans effet, refus effacé."""
    return avec_document("VerifChantsRefus", _refus)


def _modifier_et_supprimer(doc: Any) -> list[str]:
    from freecad.menuiserie import api

    blank = piece(doc)
    profile, _ = api.add_edge_profile(blank, ["Z+Y-"], "Chamfer", 5.0, 5.0)
    doc.recompute()
    vobj = profile.ViewObject
    ouvert = vobj.Proxy.doubleClicked(vobj)
    form = formulaire()
    if not ouvert or form is None:
        return ["double-clic sur le profil : panneau non ouvert"]
    problemes = [
        *ecarts("arête reprise", widget(form, "Z+Y-").isChecked(), True),
        *ecarts("cote reprise", widget(form, "size_a").property("rawValue"), 5.0),
    ]
    widget(form, "Z-Y-").setChecked(True)
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


VERIFICATIONS_CHANTS: tuple[Callable[[], list[str]], ...] = (
    verifier_commande,
    verifier_creation,
    verifier_annulation,
    verifier_cote_refusee,
    verifier_modification_et_suppression,
)
