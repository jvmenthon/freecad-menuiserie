# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de l'ensemble (J4c) : commandes, arbre, suppression,
observateurs (critères P1, P2, P6 de ``docs/specs/J4-ensembles.md``).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque
vérification renvoie la liste de ses problèmes. Le bureau de référence (§ 3) est construit par
l'api (``tests/integration/bureau.py``) ; les commandes sont lancées sur la sélection.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api, icon_path
from tests.commandes_ensembles import COMMANDES_ENSEMBLE
from tests.gui.verifications_assemblages import observateurs_comptes, selectionner
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    emplacements,
    formulaire_nomme,
    nouveau_document,
)
from tests.integration.bureau import LAYOUT, Bureau, build_parts

ENSEMBLE = "Menuiserie_Furniture"
AJOUTER = "Menuiserie_FurnitureAdd"
RETIRER = "Menuiserie_FurnitureRemove"
RELIER = "Menuiserie_FurnitureRebind"
VP_ENSEMBLE = "freecad.menuiserie.gui.view_providers.furniture.ViewProviderFurniture"
PROPRIETES_DE_MEMBRE = ("Furniture", "PositionMode", "FixedBack", "FurnitureBindings")
FORM = "FurnitureTaskPanel"


@contextmanager
def pieces_du_bureau(nom: str, *, assemble: bool = False) -> Iterator[Bureau]:
    """Document des quatre pièces du bureau (tourillons si ``assemble``), toujours refermé
    (panneau compris)."""
    doc = nouveau_document(nom)
    nom_du_document = doc.Name
    try:
        bureau = build_parts(doc)
        if assemble:
            for joue in ("JG", "JD"):
                bureau.joints.append(api.make_dowels(bureau.parts[joue], bureau.parts["V"]))
        yield bureau
    finally:
        if Gui.Control.activeDialog():
            annuler()
        Gui.Selection.clearSelection()
        if nom_du_document in App.listDocuments():  # sinon déjà fermé (réouverture)
            App.closeDocument(nom_du_document)


def regrouper(bureau: Bureau, label: str = "Bureau") -> Any:
    """Ensemble des quatre pièces (visibles), par l'api ; historique d'annulation vidé."""
    bureau.furniture, bureau.notices = api.make_furniture(
        [bureau.shown(mark) for mark in LAYOUT], label=label
    )
    bureau.doc.clearUndos()
    return bureau.furniture


def lancer(commande: str, *objets: Any) -> None:
    selectionner(*objets)
    Gui.Command.get(commande).run()


def classe_du_proxy(vobj: Any) -> str:
    return f"{type(vobj.Proxy).__module__}.{type(vobj.Proxy).__qualname__}"


def membre(obj: Any) -> bool:
    return any(nom in obj.PropertiesList for nom in PROPRIETES_DE_MEMBRE)


EMPLACEMENTS = [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")]


# --- P1 : commandes ---------------------------------------------------------------------


def verifier_commandes_d_ensemble_presentes() -> list[str]:
    """P1 : libellés, icônes générées, barre d'outils et menu Menuiserie."""
    problemes = []
    for nom, (libelle, _transaction) in COMMANDES_ENSEMBLE.items():
        commande = Gui.Command.get(nom)
        if commande is None:
            problemes.append(f"{nom} non enregistrée")
            continue
        infos = commande.getInfo()
        constats = {
            "libellé": (infos["menuText"], libelle),
            "infobulle": (bool(infos["toolTip"].strip()), True),
            "icône": (infos["pixmap"], icon_path(f"{nom}.svg")),
            "icône affichée": (commande.getAction()[0].icon().isNull(), False),
            "emplacements": (sorted(emplacements(nom)), EMPLACEMENTS),
        }
        for quoi, (obtenu, attendu) in constats.items():
            problemes += ecarts(f"{nom} {quoi}", obtenu, attendu)
    return problemes


def actives() -> tuple[bool, ...]:
    return tuple(bool(Gui.Command.get(nom).isActive()) for nom in COMMANDES_ENSEMBLE)


def verifier_activation_des_commandes_d_ensemble() -> list[str]:
    """P1 : « Ensemble » si des pièces sont sélectionnées, « Ajouter » avec un ensemble,
    « Retirer » pour des membres, « Relier » pour un ensemble ; rien avec un panneau ouvert."""
    with pieces_du_bureau("VerifActivationEnsemble") as bureau:
        p, jg = bureau.parts["P"], bureau.parts["JG"]
        Gui.Selection.clearSelection()
        problemes = ecarts("aucune sélection", actives(), (False, False, False, False))
        selectionner(p, jg)
        problemes += ecarts("deux pièces", actives(), (True, False, False, False))
        ensemble, _ = api.make_furniture([p, jg], label="Bureau")
        selectionner(ensemble)
        problemes += ecarts("un ensemble", actives(), (True, False, False, True))
        selectionner(jg)
        problemes += ecarts("un membre", actives(), (True, False, True, False))
        selectionner(ensemble, bureau.parts["V"])
        problemes += ecarts("ensemble et pièce", actives(), (True, True, False, False))
        ensemble.ViewObject.Proxy.doubleClicked(ensemble.ViewObject)
        selectionner(ensemble, bureau.parts["V"])
        problemes += ecarts("panneau ouvert", actives(), (False, False, False, False))
    return problemes


def verifier_commandes_d_ensemble_annulables() -> list[str]:
    """P1 : une entrée d'annulation par commande ; un refus n'en laisse aucune."""
    with pieces_du_bureau("VerifCommandesEnsemble", assemble=True) as bureau:
        doc = bureau.doc
        doc.clearUndos()
        lancer(ENSEMBLE, *(bureau.shown(mark) for mark in LAYOUT))
        ensembles = [o for o in doc.Objects if o.TypeId == "App::FeaturePython"]
        if len(ensembles) != 1:
            return [f"{len(ensembles)} ensembles créés"]
        ensemble = ensembles[0]
        nom_de_l_ensemble = ensemble.Name
        joue = bureau.parts["JG"]
        problemes = [
            *ecarts("libellé", ensemble.Label, "Ensemble"),
            *ecarts("ViewProvider", classe_du_proxy(ensemble.ViewObject), VP_ENSEMBLE),
            *ecarts("liaison", bureau.expressions("JG")["Width"], "<<Ensemble>>.Depth - 40 mm"),
            *ecarts("panneau ouvert", bool(Gui.Control.activeDialog()), False),
        ]
        lancer(RETIRER, bureau.shown("JG"))
        problemes += ecarts("retirée", membre(joue), False)
        lancer(AJOUTER, ensemble, bureau.shown("JG"))
        problemes += ecarts("ajoutée", api.furniture_of(joue), ensemble)
        lancer(RELIER, ensemble)
        noms = [nom for _libelle, nom in COMMANDES_ENSEMBLE.values()]
        attendu = [noms[3], noms[1], noms[2], noms[0]]
        problemes += ecarts("entrées d'annulation", doc.UndoNames, attendu)
        lancer(AJOUTER, ensemble, bureau.shown("JG"))
        message = Gui.getMainWindow().statusBar().currentMessage()
        problemes += [
            *ecarts("refus sans entrée", doc.UndoNames, attendu),
            *ecarts("refus affiché", "déjà membre" in message, True),
        ]
        for _ in attendu:
            doc.undo()
        problemes += [
            *ecarts("tout annulé : ensemble", doc.getObject(nom_de_l_ensemble), None),
            *ecarts(
                "tout annulé : membres", [membre(p) for p in bureau.parts.values()], [False] * 4
            ),
            *ecarts("tout annulé : expressions", bureau.expressions("JG"), {}),
        ]
    return problemes


# --- P2 : arbre, double-clic, suppression ---------------------------------------------------


def verifier_arbre_de_l_ensemble() -> list[str]:
    """P2 : membres visibles (pièces usinées), sous-ensemble et assemblages internes sous
    l'ensemble ; icône ; double-clic → panneau."""
    with pieces_du_bureau("VerifArbreEnsemble", assemble=True) as bureau:
        caisson, _ = api.make_furniture(
            [bureau.shown(mark) for mark in ("JG", "JD", "V")], label="Caisson"
        )
        ensemble, _ = api.make_furniture([bureau.shown("P"), caisson], label="Bureau")
        vobj = ensemble.ViewObject
        enfants = sorted(o.Label for o in vobj.Proxy.claimChildren())
        du_caisson = sorted(o.Label for o in caisson.ViewObject.Proxy.claimChildren())
        tourillons = sorted(j.Label for j in bureau.joints)
        attendus = sorted([bureau.shown(m).Label for m in ("JG", "JD", "V")] + tourillons)
        problemes = [
            *ecarts("enfants du bureau", enfants, sorted(["Caisson", "Plateau"])),
            *ecarts("enfants du caisson", du_caisson, attendus),
            *ecarts("icône", vobj.Proxy.getIcon(), icon_path("Menuiserie_Furniture.svg")),
            *ecarts("icône de l'arbre chargée", vobj.Icon.isNull(), False),
            *ecarts("double-clic", bool(vobj.Proxy.doubleClicked(vobj)), True),
            *ecarts("panneau", panneau_ouvert(), True),
        ]
        annuler()
        return problemes


def panneau_ouvert() -> bool:
    return formulaire_nomme(FORM) is not None


def verifier_suppression_de_l_ensemble() -> list[str]:
    """P2 : supprimer l'ensemble dans l'interface retire d'abord liaisons et propriétés de
    membre (``onDelete``), dans la même transaction ; « Annuler » rétablit tout."""
    with pieces_du_bureau("VerifSuppressionEnsemble", assemble=True) as bureau:
        doc = bureau.doc
        ensemble = regrouper(bureau)
        avant = bureau.expressions("JD")
        doc.openTransaction("Supprimer")
        vobj = ensemble.ViewObject
        accepte = bool(vobj.Proxy.onDelete(vobj, []))
        doc.removeObject(ensemble.Name)
        doc.commitTransaction()
        doc.recompute()
        problemes = [
            *ecarts("suppression acceptée", accepte, True),
            *ecarts("membres", [membre(p) for p in bureau.parts.values()], [False] * 4),
            *ecarts("expressions", [bureau.expressions(m) for m in LAYOUT], [{}] * 4),
            *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
            *ecarts("une entrée", doc.UndoNames, ["Supprimer"]),
        ]
        doc.undo()
        doc.recompute()
        retabli = doc.getObjectsByLabel("Bureau")
        problemes += [
            *ecarts("ensemble rétabli", len(retabli), 1),
            *ecarts("liaisons rétablies", bureau.expressions("JD"), avant),
            *ecarts(
                "ViewProvider rétabli",
                classe_du_proxy(retabli[0].ViewObject) if retabli else None,
                VP_ENSEMBLE,
            ),
        ]
        return problemes


def verifier_ensemble_du_caisson() -> list[str]:
    """P2 : l'ensemble créé par le gabarit « Caisson » reçoit aussi le ViewProvider de
    l'ensemble (pièces rangées dessous dans l'arbre)."""
    doc = nouveau_document("VerifCaissonEnsemble")
    try:
        caisson, _ = api.make_carcass(doc)
        vobj = caisson.ViewObject
        enfants = vobj.Proxy.claimChildren() if vobj.Proxy is not None else []
        return [
            *ecarts("ViewProvider", classe_du_proxy(vobj), VP_ENSEMBLE),
            *ecarts("pièces rangées", bool(enfants), True),
        ]
    finally:
        App.closeDocument(doc.Name)


# --- P6 : observateurs ----------------------------------------------------------------------


def verifier_aucun_observateur_apres_l_ensemble() -> list[str]:
    """P6 : aucun observateur laissé par les commandes ni par le panneau."""
    with pieces_du_bureau("VerifObservateursEnsemble") as bureau, observateurs_comptes() as solde:
        lancer(ENSEMBLE, *bureau.parts.values())
        problemes = ecarts("après la commande", solde[0], 0)
        ensemble: Any = api.furniture_of(bureau.parts["P"])
        ensemble.ViewObject.Proxy.doubleClicked(ensemble.ViewObject)
        annuler()
        return problemes + ecarts("après le panneau", solde[0], 0)


VERIFICATIONS_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_commandes_d_ensemble_presentes,
    verifier_activation_des_commandes_d_ensemble,
    verifier_commandes_d_ensemble_annulables,
    verifier_arbre_de_l_ensemble,
    verifier_ensemble_du_caisson,
    verifier_suppression_de_l_ensemble,
    verifier_aucun_observateur_apres_l_ensemble,
)
